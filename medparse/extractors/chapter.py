"""Textbook chapter extractor heuristics."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from medparse.structured.models import ChapterExtract, ChapterSection
from .utils import PageLookup

CATEGORY_KEYWORDS: Dict[str, tuple[str, ...]] = {
    "etiology": ("etiology", "pathogenesis", "causes"),
    "classification": ("classification", "types"),
    "signs_symptoms": ("signs", "symptoms", "clinical presentation"),
    "diagnostic_workup": ("diagnosis", "diagnostic", "workup", "evaluation"),
    "management_principles": ("management", "treatment", "therapy"),
    "complications": ("complications", "adverse"),
}


def extract_chapter_data(
    doc_id: str,
    sections: List[Dict[str, Any]],
    full_text: str,
    page_map: Optional[List[Dict[str, Any]]],
) -> Optional[ChapterExtract]:
    if not sections:
        return None

    lookup = PageLookup(page_map)
    buckets: Dict[str, List[ChapterSection]] = {key: [] for key in CATEGORY_KEYWORDS}

    matched = False
    for section in sections:
        title = section.get("title") or ""
        title_lower = title.lower()
        for category, keywords in CATEGORY_KEYWORDS.items():
            if not any(key in title_lower for key in keywords):
                continue
            matched = True
            for para in section.get("paragraphs", []) or []:
                text = para.get("text") or ""
                if not text.strip():
                    continue
                page_info = lookup.resolve(text, mark_used=False) or {}
                start = page_info.get("start")
                end = page_info.get("end")
                buckets[category].append(
                    ChapterSection(
                        title=title,
                        text=text.strip(),
                        page=page_info.get("page"),
                        span=(start, end) if start is not None and end is not None else None,
                    )
                )
            break

    if not matched:
        return None

    return ChapterExtract(doc_id=doc_id, **buckets)


__all__ = ["extract_chapter_data"]
