"""Utility helpers for cleaning section text prior to extraction."""
from __future__ import annotations

import re
from typing import Dict, List, Any

_HEADER_PATTERNS = (
    re.compile(r"american thoracic society documents", re.IGNORECASE),
    re.compile(r"©", re.IGNORECASE),
    re.compile(r"orcid", re.IGNORECASE),
    re.compile(r"www\.", re.IGNORECASE),
    re.compile(r"doi:\s*", re.IGNORECASE),
    re.compile(r"https?://", re.IGNORECASE),
)

_CALLOUT_PATTERN = re.compile(r"\s*Fig\.?\s?\d+[a-zA-Z\-]*\.?$|"
                               r"\s*Table\s?\d+[a-zA-Z\-]*\.?$",
                              re.IGNORECASE | re.VERBOSE)

_SOFT_HYPHEN = "\u00ad"


def _drop_header_line(text: str) -> bool:
    lowered = text.strip().lower()
    if not lowered:
        return True
    for pattern in _HEADER_PATTERNS:
        if pattern.search(lowered):
            return True
    return False


def _normalize_line(text: str) -> str:
    text = text.replace(_SOFT_HYPHEN, "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def sanitize_sections(structure: Dict[str, Any]) -> None:
    """In-place cleanup of section paragraphs to remove headers and callouts."""
    sections: List[Dict[str, Any]] = structure.get("sections") or []
    for section in sections:
        paragraphs = section.get("paragraphs") or []
        cleaned: List[Dict[str, Any]] = []
        for para in paragraphs:
            text = para.get("text")
            if not isinstance(text, str):
                continue
            if _drop_header_line(text):
                continue
            norm = _normalize_line(text)
            if not norm or _CALLOUT_PATTERN.match(norm):
                continue
            para = dict(para)
            para["text"] = norm
            cleaned.append(para)
        section["paragraphs"] = cleaned
