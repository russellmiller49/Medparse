"""Utilities for constructing full text and page maps."""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Tuple


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


def _index_docling(body: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for elem in body or []:
        label = elem.get("label")
        if label not in {"text", "list_item", "section_header", "caption"}:
            continue
        text = elem.get("text") or ""
        norm = _normalize(text)
        if not norm:
            continue
        page_no = elem.get("page_no")
        if page_no is None:
            page = None
        else:
            try:
                page = int(page_no) + 1
            except (TypeError, ValueError):
                page = None
        records.append(
            {
                "text": text,
                "norm": norm,
                "page": page,
            }
        )
    return records


def build_full_text_with_spans(
    sections: Iterable[Dict[str, Any]],
    *,
    docling_body: Optional[Iterable[Dict[str, Any]]] = None,
    limit: Optional[int] = None,
) -> Tuple[str, List[Dict[str, Any]]]:
    """Return full_text and span metadata with page numbers when available."""

    body_records = _index_docling(docling_body or [])
    pointer = 0

    def resolve_page(text: str) -> Optional[int]:
        nonlocal pointer
        norm = _normalize(text)
        if not norm or not body_records:
            return None
        for idx in range(pointer, len(body_records)):
            record = body_records[idx]
            if record.get("used"):
                continue
            record_norm = record["norm"]
            if norm == record_norm or norm in record_norm or record_norm in norm:
                record["used"] = True
                pointer = idx + 1
                return record.get("page")
        for idx, record in enumerate(body_records):
            if record.get("used"):
                continue
            record_norm = record["norm"]
            if norm == record_norm or norm in record_norm or record_norm in norm:
                record["used"] = True
                pointer = max(pointer, idx + 1)
                return record.get("page")
        return None

    records: List[Dict[str, Any]] = []
    for sec_idx, section in enumerate(sections or []):
        title = section.get("title")
        if title:
            records.append(
                {
                    "kind": "title",
                    "text": title,
                    "section_title": title,
                    "section_index": sec_idx,
                    "paragraph_index": None,
                }
            )
        for para_idx, para in enumerate(section.get("paragraphs", []) or []):
            text = para.get("text") or ""
            if not text.strip():
                continue
            records.append(
                {
                    "kind": "paragraph",
                    "text": text,
                    "section_title": title,
                    "section_index": sec_idx,
                    "paragraph_index": para_idx,
                }
            )

    full_chunks: List[str] = []
    spans: List[Dict[str, Any]] = []
    cursor = 0

    for record in records:
        text = record["text"]
        if text is None:
            continue
        if full_chunks:
            if limit is not None and cursor >= limit:
                break
            full_chunks.append("\n")
            cursor += 1
        if limit is not None and cursor >= limit:
            break
        remaining = None if limit is None else max(limit - cursor, 0)
        content = text if remaining is None else text[:remaining]
        start = cursor
        cursor += len(content)
        full_chunks.append(content)
        spans.append(
            {
                "kind": record["kind"],
                "section_title": record.get("section_title"),
                "section_index": record.get("section_index"),
                "paragraph_index": record.get("paragraph_index"),
                "page": resolve_page(text),
                "start": start,
                "end": cursor,
                "text": content,
            }
        )
        if remaining is not None and len(content) < len(text):
            break

    return "".join(full_chunks), spans


__all__ = ["build_full_text_with_spans"]
