"""Compatibility wrapper re-exporting statistics helpers."""
from __future__ import annotations

from scripts.legacy.statistics_gated import (  # type: ignore re-export shim
    EXCLUDE_PATTERNS,
    STAT_KEYWORDS,
    STAT_SECTIONS,
    extract_statistics,
    has_statistical_context,
    is_excluded_pattern,
)

__all__ = [
    "EXCLUDE_PATTERNS",
    "STAT_KEYWORDS",
    "STAT_SECTIONS",
    "extract_statistics",
    "has_statistical_context",
    "is_excluded_pattern",
]

if __name__ == "__main__":  # pragma: no cover - legacy CLI passthrough
    import runpy

    runpy.run_module("scripts.legacy.statistics_gated", run_name="__main__")
