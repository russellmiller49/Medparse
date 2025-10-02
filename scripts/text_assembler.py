"""Utilities for assembling clean document text from GROBID TEI or Docling outputs."""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

from wordfreq import zipf_frequency

from lxml import etree

TEI_NS = {"tei": "http://www.tei-c.org/ns/1.0"}

BULLET_CHARS = {"\u2022", "\u25cf", "\u25aa", "\uf0b7"}

FOOTER_PATTERNS = (
    re.compile(r"^this document was downloaded for personal use only", re.I),
    re.compile(r"^the user may print one copy", re.I),
    re.compile(r"^copyright", re.I),
    re.compile(r"^please cite", re.I),
    re.compile(r"^for personal use only", re.I),
    re.compile(r"^this article is protected by copyright", re.I),
    re.compile(r"^georg thieme verlag", re.I),
)


def _clean_text(text: str) -> str:
    if not text:
        return ""
    # Normalize soft hyphen and other hidden glyphs
    text = text.replace("\u00ad", "")
    for bullet in BULLET_CHARS:
        text = text.replace(bullet, " ")
    # Collapse intra-word hyphenation produced by page breaks
    text = re.sub(r"(?<=\w)-\s+(?=\w)", "", text)
    text = re.sub(r"\s+", " ", text)
    text = text.strip()
    if text:
        text = _fix_inline_hyphenation(text)
    if len(text) <= 2 and not any(ch.isalpha() for ch in text):
        return ""
    return text


def _is_footer(text: str) -> bool:
    if not text:
        return True
    for pattern in FOOTER_PATTERNS:
        if pattern.search(text):
            return True
    return False


def _normalize_for_compare(text: str) -> str:
    if not text:
        return ""
    text = text.lower().strip()
    text = text.replace("- ", "")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _is_redundant_norm(candidate: str, existing: set[str]) -> bool:
    if not candidate:
        return True
    for item in existing:
        if not item:
            continue
        if candidate == item:
            return True
        len_candidate = len(candidate)
        len_item = len(item)
        if len_candidate >= 40 and candidate in item:
            return True
        if len_item >= 40 and item in candidate:
            return True
        if len_candidate >= 80 and len_item >= 80:
            shorter, longer = (candidate, item) if len_candidate <= len_item else (item, candidate)
            ratio = SequenceMatcher(None, shorter, longer).ratio()
            if ratio >= 0.92:
                return True
    return False


def extract_sections_from_tei(tei_xml: str, *, max_sections: int = 200) -> List[Dict[str, Any]]:
    """Return structured sections from a GROBID TEI document."""
    if not tei_xml:
        return []

    try:
        root = etree.fromstring(tei_xml.encode("utf-8"))
    except Exception:
        return []

    body = root.xpath("//tei:text/tei:body", namespaces=TEI_NS)
    if not body:
        return []

    sections: List[Dict[str, Any]] = []
    seen_spans: set[tuple[str, str]] = set()

    divs = body[0].xpath(".//tei:div[not(tei:div)]", namespaces=TEI_NS)
    if not divs:
        divs = body[0].xpath(".//tei:div", namespaces=TEI_NS)

    for div in divs:
        if len(sections) >= max_sections:
            break
        title = _clean_text(" ".join(div.xpath("./tei:head//text()", namespaces=TEI_NS)))

        paragraphs: List[Dict[str, Any]] = []
        for para in div.xpath(".//tei:p", namespaces=TEI_NS):
            text = _clean_text("".join(para.xpath(".//text()", namespaces=TEI_NS)))
            if not text:
                continue
            if _is_footer(text):
                continue
            key = (title.lower(), text.lower())
            if key in seen_spans:
                continue
            seen_spans.add(key)
            paragraphs.append({"text": text})

        for item in div.xpath(".//tei:list/tei:item", namespaces=TEI_NS):
            text = _clean_text("".join(item.xpath(".//text()", namespaces=TEI_NS)))
            if not text or _is_footer(text):
                continue
            key = (title.lower(), text.lower())
            if key in seen_spans:
                continue
            seen_spans.add(key)
            paragraphs.append({"text": text})

        if not paragraphs and not title:
            continue

        sections.append({"title": title, "paragraphs": paragraphs})

    return sections


def extract_sections_from_docling(docling_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    document = docling_json.get("document", {})
    assembled = docling_json.get("assembled", {})
    body = assembled.get("body", [])

    if not body:
        # Fall back to basic page text if assembled body missing
        pages = document.get("pages", [])
        sections: List[Dict[str, Any]] = []
        for page in pages:
            text = _clean_text(page.get("text", ""))
            if not text or _is_footer(text):
                continue
            sections.append({"title": f"Page {page.get('number', '')}", "paragraphs": [{"text": text}]})
        return sections

    sections: List[Dict[str, Any]] = []
    current = {"title": "", "paragraphs": []}
    last_title_key: Optional[str] = None

    def _flush() -> None:
        nonlocal current
        if current.get("paragraphs"):
            sections.append(current)
        current = {"title": "", "paragraphs": []}

    for elem in body:
        label = elem.get("label")
        text = _clean_text(elem.get("text", ""))
        if not text:
            continue
        if _is_footer(text):
            continue
        if label == "section_header":
            title_key = _normalize_for_compare(text)
            if title_key and title_key == last_title_key and not current.get("paragraphs"):
                continue
            _flush()
            current["title"] = text
            last_title_key = title_key
        elif label in {"text", "list_item"}:
            current.setdefault("paragraphs", []).append({"text": text})

    _flush()
    sections = _dedupe_sections(sections)
    return sections


def assemble_sections(tei_xml: Optional[str], docling_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    tei_sections = extract_sections_from_tei(tei_xml) if tei_xml else []
    fallback_sections = extract_sections_from_docling(docling_json)

    if not tei_sections:
        return fallback_sections

    fallback_text = build_full_text(fallback_sections)
    tei_text = build_full_text(tei_sections)

    if not fallback_text:
        return tei_sections

    coverage = len(tei_text) / len(fallback_text) if fallback_text else 0.0
    if coverage >= 0.95:
        return tei_sections

    merged = _merge_with_fallback(tei_sections, fallback_sections)
    merged_text = build_full_text(merged)
    merged_ratio = len(merged_text) / len(fallback_text) if fallback_text else 0.0

    if merged_ratio < 0.9:
        return fallback_sections
    if merged_ratio > 1.1:
        return fallback_sections

    return merged


def _merge_with_fallback(
    primary: List[Dict[str, Any]],
    fallback: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = [
        {
            "title": sec.get("title"),
            "paragraphs": [{"text": para.get("text")}
                            for para in sec.get("paragraphs", []) if para.get("text")],
        }
        for sec in primary
    ]

    seen_text = {
        _normalize_for_compare(para.get("text"))
        for sec in merged
        for para in sec.get("paragraphs", [])
        if para.get("text")
    }
    seen_text.discard("")

    title_to_sections: Dict[str, List[Dict[str, Any]]] = {}
    for sec in merged:
        title = (sec.get("title") or "").strip().lower()
        if not title:
            continue
        title_to_sections.setdefault(title, []).append(sec)

    for fb_section in fallback:
        fb_title = (fb_section.get("title") or "").strip().lower()
        sections_for_title = title_to_sections.get(fb_title, [])
        target = sections_for_title[-1] if sections_for_title else None
        extend_target = True
        if sections_for_title:
            existing_len = 0
            for sec in sections_for_title:
                for para in sec.get("paragraphs", []):
                    existing_len += len(_clean_text(para.get("text", "")))
            fb_len = sum(len(_clean_text(p.get("text", ""))) for p in fb_section.get("paragraphs", []))
            if fb_len and existing_len / fb_len >= 0.6:
                extend_target = False
        if target is not None and target.get("paragraphs") and not extend_target:
            continue
        additions: List[Dict[str, Any]] = []
        for para in fb_section.get("paragraphs", []):
            text = para.get("text")
            if not text:
                continue
            cleaned = _clean_text(text)
            if not cleaned:
                continue
            key = _normalize_for_compare(cleaned)
            if not key or key in seen_text:
                continue
            if _is_redundant_norm(key, seen_text):
                continue
            seen_text.add(key)
            additions.append({"text": cleaned})
        if not additions:
            continue
        if target is None:
            new_section = {"title": fb_section.get("title"), "paragraphs": additions}
            merged.append(new_section)
            title_key = (new_section.get("title") or "").strip().lower()
            if title_key:
                title_to_sections.setdefault(title_key, []).append(new_section)
        else:
            target.setdefault("paragraphs", []).extend(additions)

    return merged


def _dedupe_sections(sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    deduped: List[Dict[str, Any]] = []
    seen_titles: Dict[str, Dict[str, Any]] = {}
    for sec in sections:
        title = sec.get("title") or ""
        norm_title = _normalize_for_compare(title)
        seen_para: set[str] = set()
        paragraphs: List[Dict[str, Any]] = []
        for para in sec.get("paragraphs", []):
            text = para.get("text")
            if not text:
                continue
            key = _normalize_for_compare(text)
            if not key or key in seen_para:
                continue
            seen_para.add(key)
            paragraphs.append({"text": text})
        if not paragraphs and not norm_title:
            continue
        if norm_title and norm_title in seen_titles:
            seen_titles[norm_title].setdefault("paragraphs", []).extend(paragraphs)
            continue
        record = {"title": title, "paragraphs": paragraphs}
        deduped.append(record)
        if norm_title:
            seen_titles[norm_title] = record
    return deduped


_HYPHEN_TOKEN_PATTERN = re.compile(r"^([A-Za-z][A-Za-z']*)(-)([A-Za-z'][A-Za-z]*)([^A-Za-z]*)$")
_SMALL_SUFFIX_SKIP = {"up", "in", "out", "off", "on", "per", "non", "pre", "post"}


def _fix_inline_hyphenation(text: str) -> str:
    tokens = text.split()
    if not tokens:
        return text

    def _merge(token: str) -> str:
        match = _HYPHEN_TOKEN_PATTERN.match(token)
        if not match:
            return token

        head, _, tail, suffix = match.groups()

        # Avoid merging identifiers or all-caps abbreviations
        if head.isupper() or tail.isupper():
            return token

        combined = head + tail

        combined_freq = zipf_frequency(combined.lower(), "en")

        head_freq = zipf_frequency(head.lower(), "en")
        tail_freq = zipf_frequency(tail.lower(), "en")
        hyphen_freq = zipf_frequency((head + '-' + tail).lower(), "en")

        merge_allowed = False

        if combined_freq > 0 and combined_freq >= max(head_freq + 0.3, tail_freq + 0.3, hyphen_freq + 0.3, 3.5):
            merge_allowed = True
        elif len(tail) <= 3 and tail.lower() not in _SMALL_SUFFIX_SKIP and len(head) >= 4:
            merge_allowed = True

        if not merge_allowed:
            return token

        # Preserve leading capitalization pattern (e.g., Netherlands)
        if head[0].isupper():
            merged = head[0] + (head[1:] + tail)
        else:
            merged = combined

        return merged + suffix

    merged_tokens = [_merge(tok) for tok in tokens]
    return " ".join(merged_tokens)


def build_full_text(sections: List[Dict[str, Any]], *, limit: int | None = None) -> str:
    parts: List[str] = []
    for section in sections:
        title = section.get("title")
        if title:
            parts.append(title)
        for para in section.get("paragraphs", []):
            text = para.get("text", "")
            if text:
                parts.append(text)
    full_text = "\n".join(parts)
    if limit is not None and len(full_text) > limit:
        return full_text[:limit]
    return full_text


def compute_page_text_ratio(docling_json: Dict[str, Any], full_text: str) -> Optional[float]:
    baseline_sections = extract_sections_from_docling(docling_json)
    baseline_text = build_full_text(baseline_sections)
    if not baseline_text:
        return None
    ratio = len(full_text) / len(baseline_text) if baseline_text else 0.0
    return round(min(max(ratio, 0.0), 1.0), 4)
