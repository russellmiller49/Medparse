"""Guideline-specific extractor heuristics."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from medparse.structured.models import GuidelineExtract, GuidelineRecommendation, StationCoverageEntry
from .utils import PageLookup


IASLC_STATIONS = {
    "1", "2", "2R", "2L", "3", "4", "4R", "4L", "5", "6", "7",
    "8", "9", "10", "10R", "10L", "11", "11R", "11L", "12", "12R",
    "12L", "13", "13R", "13L", "14", "14R", "14L"
}


def _trim_after_callouts(text: str) -> str:
    match = re.search(r"(?:see\s+)?(?:fig|table)[\s.:;\-]", text, re.IGNORECASE)
    if match:
        return text[: match.start()].rstrip()
    return text


def _strip_trailing_citations(text: str) -> str:
    return re.sub(r"\s*\[[0-9,\s\-]+\]\s*$", "", text).strip()


def _clean_recommendation_text(text: str) -> str:
    cleaned = _trim_after_callouts(text)
    cleaned = _strip_trailing_citations(cleaned)
    lines = [ln for ln in cleaned.splitlines() if "orcid" not in ln.lower() and "www" not in ln.lower()]
    return " ".join(ln.strip() for ln in lines if ln.strip())


def _normalize_station(token: str) -> Optional[str]:
    candidate = token.strip().upper().rstrip(".,;:")
    if candidate in IASLC_STATIONS:
        return candidate
    if candidate.isdigit() and candidate in {"1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "14"}:
        return candidate
    return None


_RE_NUMBERED = re.compile(r"(?:^|\s)(?P<num>\d{1,2})\s+(?=[A-Z])")
_RE_GRADE = re.compile(r"(?:recommendation\s+grade|grade)\s*([A-D])", re.IGNORECASE)
_RE_EVIDENCE = re.compile(r"(?:level|quality)\s+of\s+evidence\s*([A-Z0-9]+)", re.IGNORECASE)
_RE_STATION = re.compile(r"(?:station|stations|location|locations)[^0-9]{0,10}(\d{1,2}[A-Z]?)", re.IGNORECASE)
_RE_FIGURE = re.compile(r"fig\.?\s*\d+[A-Za-z]?", re.IGNORECASE)


def _split_recommendations(text: str) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    text = text or ""
    matches = list(_RE_NUMBERED.finditer(text))
    if not matches:
        return items
    for idx, match in enumerate(matches):
        number = int(match.group("num"))
        start_body = match.end()
        end_body = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        snippet = text[start_body:end_body].strip()
        if not snippet:
            continue
        items.append(
            {
                "number": number,
                "text": snippet,
                "local_start": start_body,
                "local_end": end_body,
            }
        )
    return items


def _parse_coverage(
    doc_id: str,
    sections: List[Dict[str, Any]],
    page_map: Optional[List[Dict[str, Any]]],
) -> List[StationCoverageEntry]:
    lookup = PageLookup(page_map)
    coverage: Dict[str, StationCoverageEntry] = {}
    for section in sections:
        for para in section.get("paragraphs", []) or []:
            text = para.get("text") or ""
            lower = text.lower()
            if "station" not in lower and "locations" not in lower:
                continue
            stations = {_normalize_station(match.replace(" ", "")) for match in _RE_STATION.findall(text)}
            stations.discard(None)
            if not stations:
                continue
            page_info = lookup.resolve(text, mark_used=False) or {}
            clean_note = _clean_recommendation_text(text)
            for station in sorted(stations):
                entry = coverage.get(station)
                if not entry:
                    entry = StationCoverageEntry(
                        doc_id=doc_id,
                        station=station,
                        ebus="ebus" in lower,
                        eus="eus" in lower,
                        notes=clean_note or None,
                        page=page_info.get("page"),
                    )
                    coverage[station] = entry
                else:
                    if "ebus" in lower:
                        entry.ebus = True
                    if "eus" in lower or "eus-b" in lower:
                        entry.eus = True
                    if not entry.page and page_info.get("page"):
                        entry.page = page_info.get("page")
    return list(coverage.values())


def extract_guideline_data(
    doc_id: str,
    sections: List[Dict[str, Any]],
    full_text: str,
    page_map: Optional[List[Dict[str, Any]]],
) -> Optional[GuidelineExtract]:
    """Extract guideline recommendations and coverage map."""

    rec_sections = [
        sec for sec in sections if "recommend" in (sec.get("title") or "").lower()
    ]
    if not rec_sections:
        return None

    lookup = PageLookup(page_map)
    recommendations: List[GuidelineRecommendation] = []

    for section in rec_sections:
        section_title = section.get("title") or ""
        for para in section.get("paragraphs", []) or []:
            text = para.get("text") or ""
            if not text.strip():
                continue
            page_info = lookup.resolve(text) or {}
            paragraph_start = page_info.get("start")
            items = _split_recommendations(text)
            if not items:
                continue
            cursor = 0
            for item in items:
                raw_snippet = item["text"].strip()
                snippet = _clean_recommendation_text(raw_snippet)
                if not snippet:
                    continue
                grade_match = _RE_GRADE.search(snippet)
                grade = grade_match.group(1).upper() if grade_match else None
                evidence_match = _RE_EVIDENCE.search(snippet)
                evidence = evidence_match.group(1).upper() if evidence_match else None
                stations_raw = sorted({s.replace(" ", "") for s in _RE_STATION.findall(snippet)})
                stations = [st for st in (_normalize_station(token) for token in stations_raw) if st]
                figures = [fig.upper() for fig in _RE_FIGURE.findall(snippet)]

                local_start = text.find(snippet, cursor)
                if local_start == -1:
                    local_start = item["local_start"]
                local_end = local_start + len(snippet)
                cursor = local_end

                if paragraph_start is not None:
                    span = (
                        paragraph_start + max(local_start, 0),
                        paragraph_start + max(local_end, max(local_start, 0)),
                    )
                else:
                    span = None

                rec = GuidelineRecommendation(
                    id=f"{doc_id}::rec_{len(recommendations)+1}",
                    doc_id=doc_id,
                    number=item.get("number"),
                    text=snippet,
                    grade=grade,
                    evidence_level=evidence,
                    stations=stations,
                    figures=figures,
                    page=page_info.get("page"),
                    span=span,
                    section=section_title,
                )
                recommendations.append(rec)

    if not recommendations:
        return None

    coverage_map = _parse_coverage(doc_id, sections, page_map)
    return GuidelineExtract(
        doc_id=doc_id,
        recommendations=recommendations,
        coverage_map=coverage_map,
    )


__all__ = ["extract_guideline_data"]
