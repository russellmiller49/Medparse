"""Document-type specific extractors for Medparse outputs."""
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from medparse.structured.models import (
    ArticleExtract,
    GuidelineExtract,
    IFUExtract,
    ChapterExtract,
)

from .article import extract_article_outcomes
from .guideline import extract_guideline_data
from .ifu import extract_ifu_data
from .chapter import extract_chapter_data


DOC_TYPE_ALIASES = {
    "guideline": {"guideline", "guidelines", "consensus", "statement"},
    "ifu": {"ifu", "manual", "instructions_for_use", "user_manual"},
    "article": {"article", "journal_article", "research", "study", "statement"},
    "chapter": {"chapter", "textbook", "book_chapter"},
}


def infer_doc_type(
    payload: Mapping[str, Any],
    *,
    doc_id: str,
    explicit: Optional[str] = None,
) -> Optional[str]:
    """Best-effort doc_type inference with fallbacks."""

    if explicit:
        return explicit.lower()
    meta = payload.get("metadata") or {}
    doc_type = meta.get("doc_type")
    if isinstance(doc_type, str) and doc_type.strip():
        return doc_type.lower()
    title = str(meta.get("title") or "").lower()
    if "instructions for use" in title or "user manual" in title or "ifu" in title:
        return "ifu"
    if "guideline" in title or "recommendation" in title:
        return "guideline"
    if "chapter" in title:
        return "chapter"
    journal = str(meta.get("journal") or "").lower()
    if journal:
        return "article"
    if "research statement" in title:
        return "article"
    if "manual" in title:
        return "ifu"
    if any(word in doc_id.lower() for word in ("ifu", "manual")):
        return "ifu"
    if any(word in doc_id.lower() for word in ("chapter", "textbook")):
        return "chapter"
    if any(keyword in doc_id.lower() for keyword in ("guideline", "recommendation")):
        return "guideline"
    return None


def run_structured_extractors(
    doc_id: str,
    payload: Mapping[str, Any],
    *,
    full_text: str,
    page_map: Optional[list[dict[str, Any]]] = None,
    doc_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute document-type extractors and return JSON-serialisable data."""

    results: Dict[str, Any] = {}
    sections = ((payload.get("structure") or {}).get("sections") or [])
    metadata = payload.get("metadata") or {}

    resolved_type = (doc_type or infer_doc_type(payload, doc_id=doc_id)) or "unknown"

    if resolved_type in {"guideline", "consensus"} or resolved_type == "unknown":
        guideline = extract_guideline_data(doc_id, sections, full_text, page_map)
        if guideline and guideline.recommendations:
            results["guideline"] = guideline.model_dump(mode="json")

    if resolved_type in {"ifu", "manual"} or resolved_type == "unknown":
        ifu = extract_ifu_data(doc_id, sections, full_text, page_map, metadata)
        if ifu and (ifu.warnings or ifu.intended_use or ifu.setup_steps):
            results["ifu"] = ifu.model_dump(mode="json")

    if resolved_type in {"article", "research", "study"} or resolved_type == "unknown":
        article = extract_article_outcomes(doc_id, payload, full_text, page_map)
        if article and (article.diagnostic_outcome.yield_overall or article.diagnostic_outcome.tool_yield):
            results["article"] = article.model_dump(mode="json")

    if resolved_type in {"chapter", "textbook"} or resolved_type == "unknown":
        chapter = extract_chapter_data(doc_id, sections, full_text, page_map)
        if chapter and (
            chapter.etiology
            or chapter.management_principles
            or chapter.diagnostic_workup
        ):
            results["chapter"] = chapter.model_dump(mode="json")

    return results


__all__ = ["infer_doc_type", "run_structured_extractors"]
