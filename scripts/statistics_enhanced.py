"""Enhanced statistics extraction with structured provenance.

This module upgrades the legacy statistics parsing in three key ways:

* Anchors statistics to document structure (section titles, paragraph offsets).
* Surfaces provenance such as page numbers, figure/table identifiers and
  bounding boxes when available.
* Expands the catalogue of statistical metrics to include guideline-centric
  values such as sensitivity, specificity, PPV/NPV, complication rates, sample
  sizes and p-values, in addition to classic confidence intervals.

The extractor is intentionally conservative: it only emits values when a clear
statistical cue is present and skips common hard negatives (DOIs, grant IDs,
etc.). A legacy fall-back is still invoked when the richer parser produces no
results so existing downstream consumers continue to receive at least the
baseline statistics payload.

The output schema for each statistic is a dictionary containing:

    {
        "id": str,  # stable identifier within the document
        "type": str,  # e.g. "sensitivity", "negative_predictive_value"
        "value": float | None,  # normalised numeric value when parseable
        "display": str,  # original matched text for presentation
        "unit": str | None,  # "percent", "ratio", "count", ...
        "context": str,  # surrounding sentence or cell contents
        "section_title": str | None,
        "section_index": int | None,
        "paragraph_index": int | None,
        "page": int | None,
        "char_start": int | None,
        "char_end": int | None,
        "source": str,  # "text" | "table" | "figure" | "footnote"
        "table_id": str | None,
        "table_row": str | None,
        "table_column": str | None,
        "figure_id": str | None,
        "bbox": Dict[str, float] | None,
        "ci": Dict[str, float] | None,  # optional confidence interval
        "p_value": float | None,  # attached when found in same context
    }

All numeric values representing percentages are normalised to 0-1 (e.g. 86%
becomes 0.86) while retaining the original display string for readability.

This file is purposely self-contained so it can be unit-tested in isolation
without requiring the full extraction pipeline to execute.
"""

from __future__ import annotations

import itertools
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

from loguru import logger

from scripts.statistics_gated import extract_statistics as legacy_extract_statistics

Sentence = Dict[str, Any]
Stat = Dict[str, Any]


# ---------------------------------------------------------------------------
# Regex catalogue
# ---------------------------------------------------------------------------

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(])")
_WHITESPACE_RE = re.compile(r"\s+")

_P_VALUE_RE = re.compile(r"\b[Pp]\s*([=<>≤≥])\s*(0?\.?\d+(?:e-?\d+)?)\b")

_CI_RE = re.compile(
    r"(?:(?P<level>\d{2})\s*%\s*)?CI"  # optional level, e.g. 95 CI
    r"\s*[:=]?\s*"
    r"[\[(]?\s*"
    r"(?P<low>-?\d+(?:\.\d+)?)"  # lower bound
    r"\s*(?:[-–—]|to|,|/)\s*"
    r"(?P<high>-?\d+(?:\.\d+)?)"  # upper bound
    r"\s*[%]?(?:\s*(?:CI))?\s*[\])]?",
    re.IGNORECASE,
)

_METRIC_KEYWORD_RE = re.compile(
    r"\b("
    r"sensitivity|sensitivities|specificity|specificities|accuracy|"
    r"npv|npvs|negative predictive value|negative predictive values|"
    r"ppv|ppvs|positive predictive value|positive predictive values|"
    r"complication rate|complication rates|mortality rate|mortality rates|"
    r"false positive rate|false negative rate|prevalence|incidence|"
    r"unnecessary thoracotomies|yield|coverage"
    r")\b",
    re.IGNORECASE,
)

_PERCENT_VALUE_RE = re.compile(r"(?P<num>-?\d{1,3}(?:\.\d+)?)\s*%")
_DECIMAL_VALUE_RE = re.compile(r"(?P<num>-?0?\.\d{1,3})")
_INT_VALUE_RE = re.compile(r"\b(?P<num>\d{1,5})\b")
_FIRST_FLOAT_RE = re.compile(r"-?\d+(?:\.\d+)?")

_SAMPLE_SIZE_RE = re.compile(
    r"\b(?:n\s*[=:]\s*|sample size(?:s)?(?:\s*of)?\s*|"
    r"patients?\s*(?:n=)?|subjects?\s*(?:n=)?|participants?\s*(?:n=)?)"
    r"(?P<num>\d{1,5})\b",
    re.IGNORECASE,
)

_EFFECT_SIZE_RE = re.compile(
    r"\b(?P<label>OR|RR|HR|hazard ratio|odds ratio|risk ratio)"
    r"\s*[:=]?\s*"
    r"(?P<num>-?\d+(?:\.\d+)?)",
    re.IGNORECASE,
)


_NOISY_PERCENT_LEVELS = {"95", "97", "99"}


_METRIC_TYPE_MAP = {
    "sensitivity": "sensitivity",
    "sensitivities": "sensitivity",
    "specificity": "specificity",
    "specificities": "specificity",
    "accuracy": "accuracy",
    "npv": "negative_predictive_value",
    "npvs": "negative_predictive_value",
    "negative predictive value": "negative_predictive_value",
    "negative predictive values": "negative_predictive_value",
    "ppv": "positive_predictive_value",
    "ppvs": "positive_predictive_value",
    "positive predictive value": "positive_predictive_value",
    "positive predictive values": "positive_predictive_value",
    "complication rate": "complication_rate",
    "complication rates": "complication_rate",
    "mortality rate": "mortality_rate",
    "mortality rates": "mortality_rate",
    "false positive rate": "false_positive_rate",
    "false negative rate": "false_negative_rate",
    "prevalence": "prevalence",
    "incidence": "incidence",
    "unnecessary thoracotomies": "unnecessary_thoracotomies",
    "yield": "yield",
    "coverage": "coverage",
}


# ---------------------------------------------------------------------------
# Helper dataclasses
# ---------------------------------------------------------------------------


@dataclass
class TextNode:
    text: str
    section_title: Optional[str]
    section_index: Optional[int]
    paragraph_index: Optional[int]
    offset: int


@dataclass
class PageRecord:
    number: Optional[int]
    text: str
    normalised: str


# ---------------------------------------------------------------------------
# Core public API
# ---------------------------------------------------------------------------


def extract_statistics(
    doc: Dict[str, Any],
    full_text: str,
    docling_json: Optional[Dict[str, Any]] = None,
) -> List[Stat]:
    """Return enriched statistics for a merged extraction payload.

    Args:
        doc: Final merged document dictionary (post Docling/GROBID merge).
        full_text: Concatenated textual representation produced by
            :func:`scripts.postprocess.concat_text`.
        docling_json: Raw Docling output used for provenance lookups.
    """

    if not doc:
        return []

    sections = doc.get("structure", {}).get("sections", [])
    nodes, rebuilt_text = _collect_text_nodes(sections)

    if full_text and rebuilt_text and full_text != rebuilt_text:
        logger.debug(
            "Rebuilt full text length (%d) does not match provided full text (%d)",
            len(rebuilt_text),
            len(full_text),
        )
        # Prefer the pipeline-generated text for offset calculations to avoid
        # propagating drift introduced by normalisation.
        full_text_reference = rebuilt_text
    else:
        full_text_reference = full_text or rebuilt_text

    page_index = _build_page_index(docling_json)
    table_assets = _build_table_asset_index(doc.get("assets", {}).get("tables"))
    figure_assets = _build_figure_asset_index(doc.get("assets", {}).get("figures"))

    stats: List[Stat] = []
    dedupe_keys: set[Tuple[Any, ...]] = set()
    next_id = itertools.count(1)

    # Textual statistics ----------------------------------------------------
    for node in nodes:
        sentences = _split_sentences(node.text)
        for sent in sentences:
            sentence_stats = _extract_from_sentence(sent["text"], full_text_reference, node, sent)
            for stat in sentence_stats:
                stat.setdefault("section_title", node.section_title)
                stat.setdefault("section_index", node.section_index)
                stat.setdefault("paragraph_index", node.paragraph_index)
                stat.setdefault("source", "text")
                stat.setdefault("page", _find_page(page_index, stat.get("context")))
                _maybe_add_stat(stat, stats, dedupe_keys, next_id)

    # Table statistics ------------------------------------------------------
    table_entries = doc.get("tables") or []
    if not table_entries:
        table_entries = _tables_from_assets(doc.get("assets", {}).get("tables"))
    for table in table_entries:
        for stat in _extract_from_table(table, table_assets.get(table.get("id"))):
            _maybe_add_stat(stat, stats, dedupe_keys, next_id)

    # Figure statistics (captions + footnotes) ------------------------------
    for figure in doc.get("figures", []):
        figure_id = figure.get("id") or figure.get("local_id") or _safe_id(figure)
        payload = figure_assets.get(figure_id, {})
        for stat in _extract_from_figure(figure, payload):
            _maybe_add_stat(stat, stats, dedupe_keys, next_id)

    if stats:
        return stats

    # Fallback to legacy extractor to avoid regressions.
    legacy_stats = legacy_extract_statistics(full_text_reference or "")
    wrapped: List[Stat] = []
    for idx, item in enumerate(legacy_stats, start=1):
        wrapped.append(
            {
                "id": f"legacy_stat_{idx}",
                "type": item.get("type"),
                "value": item.get("value"),
                "display": item.get("text") or item.get("sentence"),
                "unit": None,
                "context": item.get("sentence"),
                "source": "text",
            }
        )
    return wrapped


# ---------------------------------------------------------------------------
# Text extraction helpers
# ---------------------------------------------------------------------------


def _collect_text_nodes(sections: Sequence[Dict[str, Any]]) -> Tuple[List[TextNode], str]:
    parts: List[str] = []
    nodes: List[TextNode] = []
    offset = 0

    for sec_idx, section in enumerate(sections):
        title = (section.get("title") or "").strip()
        if title:
            parts.append(title)
            nodes.append(
                TextNode(
                    text=title,
                    section_title=title,
                    section_index=sec_idx,
                    paragraph_index=None,
                    offset=offset,
                )
            )
            offset += len(title) + 1  # account for newline joiner

        for para_idx, para in enumerate(section.get("paragraphs", [])):
            text = ""
            if isinstance(para, str):
                text = para
            elif isinstance(para, dict):
                text = para.get("text", "")
            if not text:
                continue
            text = text.strip()
            if not text:
                continue
            parts.append(text)
            nodes.append(
                TextNode(
                    text=text,
                    section_title=title or section.get("title"),
                    section_index=sec_idx,
                    paragraph_index=para_idx,
                    offset=offset,
                )
            )
            offset += len(text) + 1

    rebuilt = "\n".join(parts)
    return nodes, rebuilt


def _split_sentences(text: str) -> List[Sentence]:
    sentences: List[Sentence] = []
    if not text:
        return sentences

    start = 0
    for match in _SENTENCE_SPLIT_RE.finditer(text):
        end = match.start()
        sentences.extend(_build_sentence(text, start, end))
        start = match.end()
    # final sentence
    sentences.extend(_build_sentence(text, start, len(text)))
    return sentences


def _build_sentence(text: str, start: int, end: int) -> List[Sentence]:
    chunk = text[start:end]
    if not chunk:
        return []
    leading = len(chunk) - len(chunk.lstrip())
    trailing = len(chunk.rstrip())
    sentence_text = chunk.strip()
    if not sentence_text:
        return []
    sentence = {
        "text": sentence_text,
        "start": start + leading,
        "end": start + trailing,
    }
    return [sentence]


def _extract_from_sentence(
    sentence: str,
    full_text: Optional[str],
    node: TextNode,
    span: Sentence,
) -> List[Stat]:
    stats: List[Stat] = []
    if not sentence:
        return stats

    base_char_start = node.offset + (span.get("start") or 0)

    # Confidence intervals --------------------------------------------------
    cis = []
    for match in _CI_RE.finditer(sentence):
        low = float(match.group("low"))
        high = float(match.group("high"))
        ci_stat: Stat = {
            "type": "confidence_interval",
            "value": None,
            "display": match.group(0),
            "unit": None,
            "context": sentence,
            "char_start": base_char_start + match.start(),
            "char_end": base_char_start + match.end(),
            "ci": {
                "low": low,
                "high": high,
                "level": int(match.group("level") or 95),
            },
        }
        stats.append(ci_stat)
        cis.append((match.start(), match.end(), low, high))

    # p-values --------------------------------------------------------------
    for match in _P_VALUE_RE.finditer(sentence):
        numeric = _safe_float(match.group(2))
        p_stat: Stat = {
            "type": "p_value",
            "value": numeric,
            "display": match.group(0),
            "unit": None,
            "context": sentence,
            "char_start": base_char_start + match.start(),
            "char_end": base_char_start + match.end(),
        }
        stats.append(p_stat)

    # Effect sizes ----------------------------------------------------------
    for match in _EFFECT_SIZE_RE.finditer(sentence):
        value = _safe_float(match.group("num"))
        if value is None:
            continue
        effect_type = match.group("label").lower()
        stats.append(
            {
                "type": "effect_size",
                "subtype": effect_type,
                "value": value,
                "display": match.group(0),
                "unit": None,
                "context": sentence,
                "char_start": base_char_start + match.start(),
                "char_end": base_char_start + match.end(),
            }
        )

    # Metric percentages ----------------------------------------------------
    for match in _METRIC_KEYWORD_RE.finditer(sentence):
        label_raw = match.group(1)
        metric_type = _METRIC_TYPE_MAP.get(label_raw.lower())
        if not metric_type:
            continue

        window = sentence[match.start() : match.end() + 140]
        percent_hits = [m for m in _PERCENT_VALUE_RE.finditer(window) if _allow_percent(m)]
        if percent_hits:
            for idx, hit in enumerate(percent_hits, start=1):
                value = _safe_float(hit.group("num"))
                if value is None:
                    continue
                stat = {
                    "type": metric_type,
                    "value": value / 100.0,
                    "display": hit.group(0).strip(),
                    "unit": "percent",
                    "context": sentence,
                    "char_start": base_char_start + match.start() + hit.start(),
                    "char_end": base_char_start + match.start() + hit.end(),
                }
                stat["ordinal"] = idx if len(percent_hits) > 1 else None
                # Attach nearby CI if present in window
                closest_ci = _nearest_ci(hit.start(), cis)
                if closest_ci:
                    stat["ci"] = {"low": closest_ci[2], "high": closest_ci[3]}
                stats.append(stat)
            continue

        # Some authors report decimals without percent signs after the term
        decimal_hits = list(_DECIMAL_VALUE_RE.finditer(window[:80]))
        if decimal_hits:
            hit = decimal_hits[0]
            value = _safe_float(hit.group("num"))
            if value is not None:
                stats.append(
                    {
                        "type": metric_type,
                        "value": value,
                        "display": hit.group("num"),
                        "unit": "ratio",
                        "context": sentence,
                        "char_start": base_char_start + match.start() + hit.start(),
                        "char_end": base_char_start + match.start() + hit.end(),
                    }
                )

    # Sample sizes ----------------------------------------------------------
    for match in _SAMPLE_SIZE_RE.finditer(sentence):
        value = _safe_int(match.group("num"))
        if value is None:
            continue
        stats.append(
            {
                "type": "sample_size",
                "value": value,
                "display": match.group(0),
                "unit": "count",
                "context": sentence,
                "char_start": base_char_start + match.start(),
                "char_end": base_char_start + match.end(),
            }
        )

    return stats


# ---------------------------------------------------------------------------
# Table extraction helpers
# ---------------------------------------------------------------------------


def _extract_from_table(table: Dict[str, Any], asset_payload: Optional[Dict[str, Any]]) -> List[Stat]:
    stats: List[Stat] = []
    if not table:
        return stats

    rows = table.get("rows") or table.get("cells")
    if not rows:
        return stats

    headers = _derive_table_headers(rows)
    page = table.get("page") or (asset_payload or {}).get("page")
    bbox = (asset_payload or {}).get("bbox")
    table_id = table.get("id") or table.get("local_id") or _safe_id(table)

    for row_idx, row in enumerate(rows[1:], start=1):  # skip header row
        if not isinstance(row, list):
            continue
        row_label = ""
        if row:
            row_label = (row[0].get("text") if isinstance(row[0], dict) else str(row[0])).strip()
        if row_label == "" and all(
            isinstance(cell, dict) and (cell.get("header") == "column" or cell.get("placeholder"))
            for cell in row
        ):
            continue
        for col_idx, cell in enumerate(row):
            cell_text = ""
            if isinstance(cell, dict):
                if cell.get("placeholder"):
                    continue
                cell_text = (cell.get("text") or "").strip()
            else:
                cell_text = str(cell).strip()
            if not cell_text:
                continue
            header = headers[col_idx] if col_idx < len(headers) else ""
            metric_type = _classify_header(header)
            if metric_type:
                stats.extend(
                    _build_table_metric_stats(
                        cell_text,
                        metric_type,
                        table_id,
                        header,
                        row_label,
                        row_idx,
                        col_idx,
                        page,
                        bbox,
                    )
                )
            else:
                # P-values and CIs can appear in generic columns.
                for stat in _extract_inline_stats(cell_text, page, bbox, table_id, header, row_label, row_idx, col_idx):
                    stats.append(stat)

    return stats


def _derive_table_headers(rows: Sequence[Sequence[Dict[str, Any]]]) -> List[str]:
    if not rows:
        return []
    num_cols = max(len(row) for row in rows if isinstance(row, list))
    headers: List[List[str]] = [[] for _ in range(num_cols)]

    for row in rows[:2]:  # inspect first two rows for headers
        if not isinstance(row, list):
            continue
        for idx, cell in enumerate(row):
            if idx >= num_cols:
                continue
            text = ""
            if isinstance(cell, dict):
                if cell.get("placeholder"):
                    continue
                text = (cell.get("text") or "").strip()
            else:
                text = str(cell).strip()
            if text:
                headers[idx].append(text)

    return [" ".join(parts).strip() for parts in headers]


def _classify_header(header: str) -> Optional[str]:
    if not header:
        return None
    h = header.lower()
    h_clean = h.replace("-", "").replace(" ", "")
    if "sensitivity" in h:
        return "sensitivity"
    if "sensitivity" in h_clean:
        return "sensitivity"
    if "specificity" in h:
        return "specificity"
    if "specificity" in h_clean:
        return "specificity"
    if "npv" in h or "negative" in h and "predict" in h:
        return "negative_predictive_value"
    if "ppv" in h or "positive" in h and "predict" in h:
        return "positive_predictive_value"
    if "accuracy" in h:
        return "accuracy"
    if "prevalence" in h:
        return "prevalence"
    if "prevalence" in h_clean:
        return "prevalence"
    if "incidence" in h:
        return "incidence"
    if "complication" in h:
        return "complication_rate"
    if "mortality" in h:
        return "mortality_rate"
    if h.strip() in {"n", "n patients", "sample size"}:
        return "sample_size"
    if "patients" in h and "n" in h:
        return "sample_size"
    return None


def _build_table_metric_stats(
    cell_text: str,
    metric_type: str,
    table_id: str,
    header: str,
    row_label: str,
    row_idx: int,
    col_idx: int,
    page: Optional[int],
    bbox: Optional[Dict[str, Any]],
) -> List[Stat]:
    stats: List[Stat] = []
    percent_hits = [m for m in _PERCENT_VALUE_RE.finditer(cell_text) if _allow_percent(m)]
    header_lower = header.lower() if header else ""
    header_implies_percent = "%" in header_lower or "percent" in header_lower or metric_type in {
        "sensitivity",
        "specificity",
        "negative_predictive_value",
        "positive_predictive_value",
        "accuracy",
        "complication_rate",
        "mortality_rate",
        "false_positive_rate",
        "false_negative_rate",
        "prevalence",
        "incidence",
        "yield",
        "coverage",
    }
    if percent_hits:
        for hit in percent_hits:
            value = _safe_float(hit.group("num"))
            if value is None:
                continue
            stats.append(
                {
                    "type": metric_type,
                    "value": value / 100.0,
                    "display": hit.group(0).strip(),
                    "unit": "percent",
                    "context": cell_text,
                    "source": "table",
                    "table_id": table_id,
                    "table_row": row_label,
                    "table_column": header,
                    "table_row_index": row_idx,
                    "table_column_index": col_idx,
                    "page": page,
                    "bbox": bbox,
                }
            )
    else:
        value = _safe_float(cell_text)
        display_value = cell_text.strip()
        if value is None:
            first = _FIRST_FLOAT_RE.search(cell_text)
            if first:
                value = _safe_float(first.group(0))
                display_value = first.group(0)
        if value is not None:
            is_percent = header_implies_percent and value > 1
            unit = "percent" if is_percent else ("ratio" if 0 <= value <= 1 else "count")
            normalized_value = value / 100.0 if is_percent else value
            stats.append(
                {
                    "type": metric_type,
                    "value": normalized_value,
                    "display": display_value,
                    "unit": unit,
                    "context": cell_text,
                    "source": "table",
                    "table_id": table_id,
                    "table_row": row_label,
                    "table_column": header,
                    "table_row_index": row_idx,
                    "table_column_index": col_idx,
                    "page": page,
                    "bbox": bbox,
                }
            )
    return stats


def _extract_inline_stats(
    cell_text: str,
    page: Optional[int],
    bbox: Optional[Dict[str, Any]],
    table_id: str,
    header: str,
    row_label: str,
    row_idx: int,
    col_idx: int,
) -> List[Stat]:
    stats: List[Stat] = []
    for match in _P_VALUE_RE.finditer(cell_text):
        stats.append(
            {
                "type": "p_value",
                "value": _safe_float(match.group(2)),
                "display": match.group(0),
                "unit": None,
                "context": cell_text,
                "source": "table",
                "table_id": table_id,
                "table_row": row_label,
                "table_column": header,
                "table_row_index": row_idx,
                "table_column_index": col_idx,
                "page": page,
                "bbox": bbox,
            }
        )
    for match in _CI_RE.finditer(cell_text):
        stats.append(
            {
                "type": "confidence_interval",
                "value": None,
                "display": match.group(0),
                "unit": None,
                "context": cell_text,
                "source": "table",
                "table_id": table_id,
                "table_row": row_label,
                "table_column": header,
                "table_row_index": row_idx,
                "table_column_index": col_idx,
                "page": page,
                "bbox": bbox,
                "ci": {
                    "low": _safe_float(match.group("low")),
                    "high": _safe_float(match.group("high")),
                    "level": int(match.group("level") or 95),
                },
            }
        )
    return stats


# ---------------------------------------------------------------------------
# Figure extraction helpers
# ---------------------------------------------------------------------------


def _extract_from_figure(
    figure: Dict[str, Any],
    asset_payload: Optional[Dict[str, Any]],
) -> List[Stat]:
    stats: List[Stat] = []
    if not figure:
        return stats

    figure_id = figure.get("id") or figure.get("local_id") or _safe_id(figure)
    page = figure.get("page") or (asset_payload or {}).get("page")
    bbox = (asset_payload or {}).get("bbox")

    def _make_stat(text: str, source: str) -> Iterable[Stat]:
        if not text:
            return []
        sentences = _split_sentences(text)
        results: List[Stat] = []
        for sent in sentences:
            for stat in _extract_from_sentence(sent["text"], None, TextNode(text, None, None, None, 0), sent):
                stat.update(
                    {
                        "source": source,
                        "figure_id": figure_id,
                        "page": page,
                        "bbox": bbox,
                        "section_title": None,
                        "section_index": None,
                        "paragraph_index": None,
                    }
                )
                results.append(stat)
        return results

    caption = figure.get("caption") or figure.get("caption_text")
    stats.extend(_make_stat(caption, "figure"))
    for footnote in figure.get("footnotes", []) or []:
        stats.extend(_make_stat(footnote, "footnote"))

    return stats


# ---------------------------------------------------------------------------
# Provenance helpers
# ---------------------------------------------------------------------------


def _build_page_index(docling_json: Optional[Dict[str, Any]]) -> List[PageRecord]:
    pages: List[PageRecord] = []
    if not docling_json:
        return pages

    document = docling_json.get("document", {})
    for page in document.get("pages", []):
        if not isinstance(page, dict):
            continue
        text = page.get("text", "")
        normalised = _normalise_text(text)
        pages.append(PageRecord(number=page.get("number"), text=text, normalised=normalised))
    return pages


def _find_page(pages: Sequence[PageRecord], snippet: Optional[str]) -> Optional[int]:
    if not snippet:
        return None
    normalised = _normalise_text(snippet)
    if not normalised:
        return None
    for page in pages:
        if normalised and normalised in page.normalised:
            return page.number
    return None


def _build_table_asset_index(assets: Optional[Sequence[Dict[str, Any]]]) -> Dict[str, Dict[str, Any]]:
    index: Dict[str, Dict[str, Any]] = {}
    if not assets:
        return index
    for asset in assets:
        content = asset.get("content", {}) if isinstance(asset, dict) else {}
        table_id = content.get("local_id") or asset.get("id")
        if not table_id:
            continue
        payload: Dict[str, Any] = {}
        prov = content.get("prov") or asset.get("prov")
        if isinstance(prov, list) and prov:
            payload["page"] = prov[0].get("page_no")
            payload["bbox"] = prov[0].get("bbox")
        elif isinstance(prov, dict):
            payload["page"] = prov.get("page")
            payload["bbox"] = prov.get("bbox")
        index[str(table_id)] = payload
    return index


def _tables_from_assets(assets: Optional[Sequence[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    tables: List[Dict[str, Any]] = []
    if not assets:
        return tables
    for asset in assets:
        content = asset.get("content")
        if isinstance(content, dict):
            table_entry = {
                "id": content.get("local_id"),
                "rows": content.get("cells") or content.get("rows"),
                "page": content.get("page"),
                "footnotes": asset.get("footnotes", []),
                "caption": content.get("caption"),
            }
            tables.append(table_entry)
    return tables


def _build_figure_asset_index(assets: Optional[Sequence[Dict[str, Any]]]) -> Dict[str, Dict[str, Any]]:
    index: Dict[str, Dict[str, Any]] = {}
    if not assets:
        return index
    for asset in assets:
        content = asset.get("content", {})
        figure_id = content.get("local_id") or asset.get("id")
        if not figure_id:
            continue
        prov = content.get("prov") or asset.get("prov")
        payload: Dict[str, Any] = {}
        if isinstance(prov, list) and prov:
            payload["page"] = prov[0].get("page_no")
            payload["bbox"] = prov[0].get("bbox")
        elif isinstance(prov, dict):
            payload["page"] = prov.get("page")
            payload["bbox"] = prov.get("bbox")
        index[str(figure_id)] = payload
    return index


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------


def _maybe_add_stat(
    stat: Stat,
    stats: List[Stat],
    dedupe_keys: set[Tuple[Any, ...]],
    counter: Iterator[int],
) -> None:
    key = (
        stat.get("type"),
        stat.get("display"),
        stat.get("context"),
        stat.get("table_id"),
        stat.get("figure_id"),
        stat.get("char_start"),
    )
    if key in dedupe_keys:
        return
    dedupe_keys.add(key)
    stat = dict(stat)  # ensure we store a copy
    stat.setdefault("id", f"stat_{next(counter):04d}")
    stats.append(stat)


def _allow_percent(match: re.Match[str]) -> bool:
    num = match.group("num")
    if not num:
        return False
    if num in _NOISY_PERCENT_LEVELS:
        # Skip 95/97/99% when they likely reference CI levels.
        return False
    try:
        value = float(num)
    except ValueError:
        return False
    if value < 0:
        return False
    if value > 120:  # percentages above 120% are unlikely to be valid stats
        return False
    return True


def _nearest_ci(position: int, cis: Sequence[Tuple[int, int, float, float]]):
    closest = None
    min_distance = None
    for start, end, low, high in cis:
        if start <= position <= end:
            return (start, end, low, high)
        distance = min(abs(position - start), abs(position - end))
        if min_distance is None or distance < min_distance:
            closest = (start, end, low, high)
            min_distance = distance
    return closest


def _safe_float(value: Optional[str]) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Optional[str]) -> Optional[int]:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalise_text(text: Optional[str]) -> str:
    if not text:
        return ""
    text = text.lower()
    return _WHITESPACE_RE.sub(" ", text).strip()


def _safe_id(payload: Dict[str, Any]) -> str:
    return payload.get("id") or payload.get("local_id") or hex(id(payload))


__all__ = ["extract_statistics"]
