"""Utility helpers for document-type extractors."""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional


def normalize_text(text: str) -> str:
    """Normalize whitespace and casing for fuzzy comparisons."""

    return re.sub(r"\s+", " ", text or "").strip().lower()


class PageLookup:
    """Best-effort resolver from paragraph text to page metadata."""

    def __init__(
        self,
        page_map: Optional[Iterable[Dict[str, Any]]],
        *,
        kind: str = "paragraph",
    ) -> None:
        self._records: List[Dict[str, Any]] = []
        if not page_map:
            return
        for entry in page_map:
            if entry.get("kind") != kind:
                continue
            text = entry.get("text") or ""
            self._records.append(
                {
                    "text": text,
                    "norm": normalize_text(text),
                    "page": entry.get("page"),
                    "start": entry.get("start"),
                    "end": entry.get("end"),
                    "section": entry.get("section_title"),
                }
            )
        self._index = 0

    def resolve(self, text: str, *, mark_used: bool = True) -> Optional[Dict[str, Any]]:
        """Return the metadata record for the supplied text if possible."""

        norm = normalize_text(text)
        if not norm or not self._records:
            return None
        for idx in range(self._index, len(self._records)):
            record = self._records[idx]
            if record.get("used"):
                continue
            if norm == record["norm"] or norm in record["norm"] or record["norm"] in norm:
                if mark_used:
                    record["used"] = True
                    self._index = idx + 1
                return record
        for idx, record in enumerate(self._records):
            if record.get("used"):
                continue
            if norm == record["norm"] or norm in record["norm"] or record["norm"] in norm:
                if mark_used:
                    record["used"] = True
                    self._index = max(self._index, idx + 1)
                return record
        return None


__all__ = ["normalize_text", "PageLookup"]
