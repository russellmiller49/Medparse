"""Recommendation extraction from structured sections."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

_NUMBER_RE = re.compile(r"^[\s●•]*(\d{1,2})[.)]?\s+(.*)")
_MULTI_NUMBER_RE = re.compile(r"(?:^|(?<=\s))(\d{1,2})[.)]?\s+")
_GRADE_RE = re.compile(r"\(?\s*Recommendation grade\s+([A-Z])\)?", re.IGNORECASE)
_BACKGROUND_KEYWORDS = ("background", "review")
_SECTION_SKIP_KEYWORDS = ("institution", "reference", "bibliography", "appendix", "correction")


def extract_recommendations(sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return structured recommendations with grades and supporting sections."""
    if not sections:
        return []

    rec_data: Dict[int, Dict[str, Any]] = {}

    background_refs = [
        {"index": idx, "title": (sec.get("title") or "").strip()}
        for idx, sec in enumerate(sections)
        if (sec.get("title") or "").strip()
        and any(k in (sec.get("title") or "").strip().lower() for k in _BACKGROUND_KEYWORDS)
    ]
    background_refs = background_refs[:2]

    for idx, section in enumerate(sections):
        title = (section.get("title") or "").strip()
        if title and any(keyword in title.lower() for keyword in _SECTION_SKIP_KEYWORDS):
            continue
        paragraphs = section.get("paragraphs", []) or []
        prev_num: int | None = None

        for item in paragraphs:
            if isinstance(item, dict):
                text = item.get("text") or ""
            else:
                text = str(item or "")
            text = text.strip()
            if not text:
                continue

            text = re.sub(r"\s+", " ", text)
            if "green background" in text.lower():
                continue

            chunks = _split_recommendation_chunks(text)
            if not chunks:
                if prev_num is not None:
                    _append_to_existing(prev_num, text, rec_data, idx, title)
                continue

            for chunk in chunks:
                num = chunk.get("num")
                body = chunk.get("body", "").strip()
                if not body:
                    continue

                if num is None:
                    if prev_num is None:
                        continue
                    _append_to_existing(prev_num, body, rec_data, idx, title)
                    continue

                if not 1 <= num <= 11:
                    prev_num = None
                    continue

                cleaned_text, grade = _strip_grade(body)
                cleaned_text = cleaned_text.strip()
                if not cleaned_text:
                    prev_num = num
                    continue

                record = rec_data.setdefault(
                    num,
                    {
                        "segments": [],
                        "grade": None,
                        "section_entries": [],
                        "supplementary": [],
                    },
                )

                record["section_entries"].append((idx, title))

                if grade and not record["grade"]:
                    record["grade"] = grade

                if chunk.get("is_new", False):
                    if not record["segments"]:
                        record["segments"].append(cleaned_text)
                        record["primary_index"] = idx
                    else:
                        if cleaned_text not in record["supplementary"]:
                            record["supplementary"].append(cleaned_text)
                else:
                    if record["segments"]:
                        record["segments"][-1] = _append_segment(record["segments"][-1], cleaned_text)
                    else:
                        record["segments"].append(cleaned_text)

                prev_num = num
        # reset between sections
        prev_num = None

    recommendations: List[Dict[str, Any]] = []
    for num in sorted(rec_data):
        record = rec_data[num]
        if not record.get("segments") and record.get("supplementary"):
            record["segments"] = [record["supplementary"][0]]
        text_value = _combine_segments(record.get("segments", []))
        if not text_value:
            continue
        section_refs = _dedupe_sections(record.get("section_entries", []))
        supporting = [ref for ref in section_refs if any(k in (ref["title"] or "").lower() for k in _BACKGROUND_KEYWORDS)]
        recommendation = {
            "id": f"R{num}",
            "number": num,
            "text": text_value,
            "grade": record.get("grade"),
            "sections": section_refs,
        }
        if supporting:
            recommendation["supporting_sections"] = supporting
        elif background_refs:
            recommendation["supporting_sections"] = background_refs
        if record.get("supplementary"):
            recommendation["supplementary_text"] = record["supplementary"]
        recommendations.append(recommendation)

    return recommendations


def _strip_grade(text: str) -> Tuple[str, str | None]:
    grade: str | None = None

    def _repl(match: re.Match[str]) -> str:
        nonlocal grade
        if not grade:
            grade = match.group(1).upper()
        return ""

    cleaned = _GRADE_RE.sub(_repl, text)
    cleaned = re.sub(r"\s*(?:\(|\))\s*", lambda m: "" if m.group(0) in "()" else m.group(0), cleaned)
    return cleaned.strip(), grade


def _append_segment(existing: str, addition: str) -> str:
    if not existing:
        return addition.strip()
    if existing.endswith("-"):
        return (existing[:-1] + addition.lstrip()).strip()
    if addition.startswith((".", ",", ";", ":", "'", "\"")):
        return (existing + addition).strip()
    return (existing + " " + addition).strip()


def _combine_segments(segments: List[str]) -> str:
    if not segments:
        return ""
    combined = segments[0].strip()
    for seg in segments[1:]:
        combined = _append_segment(combined, seg.strip())
    combined = re.sub(r"\s+", " ", combined).strip()
    combined = combined.rstrip(";,. ")
    return combined


def _dedupe_sections(entries: List[Tuple[int, str]]) -> List[Dict[str, Any]]:
    seen: set[Tuple[int, str]] = set()
    deduped: List[Dict[str, Any]] = []
    for idx, title in entries:
        key = (idx, title)
        if key in seen:
            continue
        seen.add(key)
        deduped.append({"index": idx, "title": title})
    return deduped


def _split_recommendation_chunks(text: str) -> List[Dict[str, Any]]:
    matches = list(_MULTI_NUMBER_RE.finditer(text))
    if not matches:
        return []

    chunks: List[Dict[str, Any]] = []
    cursor = 0
    for i, match in enumerate(matches):
        if match.start() > cursor:
            leading = text[cursor:match.start()].strip()
            if leading:
                chunks.append({"num": None, "body": leading, "is_new": False})
        num = int(match.group(1))
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        chunks.append({"num": num, "body": body, "is_new": True})
        cursor = end

    if cursor < len(text):
        trailing = text[cursor:].strip()
        if trailing:
            chunks.append({"num": None, "body": trailing, "is_new": False})

    return chunks


def _append_to_existing(num: int, text: str, rec_data: Dict[int, Dict[str, Any]], idx: int, title: str) -> None:
    record = rec_data.get(num)
    if not record:
        return
    record["section_entries"].append((idx, title))
    cleaned_text, _ = _strip_grade(text)
    cleaned_text = cleaned_text.strip()
    if not cleaned_text:
        return
    if record["segments"]:
        record["segments"][-1] = _append_segment(record["segments"][-1], cleaned_text)
    else:
        record["segments"].append(cleaned_text)


__all__ = ["extract_recommendations"]
