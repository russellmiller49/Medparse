"""IFU extractor heuristics."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from medparse.structured.models import IFUExtract, IFUStep, IFUWarning
from .utils import PageLookup

_SEVERITY = re.compile(r"^(?P<label>DANGER|WARNING|CAUTION|NOTE)[:\-\s]+(?P<body>.+)", re.IGNORECASE)
_STEP = re.compile(r"^(?P<label>(?:[0-9]+|[A-Z]))[\).:-]\s+(?P<body>.+)")
_SOFTWARE = re.compile(r"software version\s*([A-Z0-9\.\-]+)", re.IGNORECASE)
_MODEL = re.compile(r"model\s+([A-Z0-9\-]+)", re.IGNORECASE)
_PART = re.compile(r"\b\d{6}-\d{2}\b")


def _section_matches(title: str, *keywords: str) -> bool:
    lower = (title or "").lower()
    return any(key in lower for key in keywords)


def _collect_paragraphs(sections: List[Dict[str, Any]], *keywords: str) -> List[str]:
    collected: List[str] = []
    for section in sections:
        if _section_matches(section.get("title", ""), *keywords):
            for para in section.get("paragraphs", []) or []:
                text = para.get("text") or ""
                if text.strip():
                    collected.append(text.strip())
    return collected


def _extract_steps(
    doc_id: str,
    sections: List[Dict[str, Any]],
    page_map: Optional[List[Dict[str, Any]]],
    *,
    keywords: tuple[str, ...],
) -> List[IFUStep]:
    lookup = PageLookup(page_map)
    steps: List[IFUStep] = []
    for section in sections:
        if not _section_matches(section.get("title", ""), *keywords):
            continue
        for para in section.get("paragraphs", []) or []:
            text = para.get("text") or ""
            match = _STEP.match(text.strip())
            if not match:
                continue
            label = match.group("label")
            body = match.group("body").strip()
            page_info = lookup.resolve(text, mark_used=False) or {}
            steps.append(
                IFUStep(
                    number=label,
                    text=body,
                    page=page_info.get("page"),
                )
            )
    return steps


def extract_ifu_data(
    doc_id: str,
    sections: List[Dict[str, Any]],
    full_text: str,
    page_map: Optional[List[Dict[str, Any]]],
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[IFUExtract]:
    meta = metadata or {}
    cue_sections = [
        sec for sec in sections if _section_matches(sec.get("title", ""), "intended", "warnings", "cautions")
    ]
    if not cue_sections:
        return None

    lookup = PageLookup(page_map)

    warnings: List[IFUWarning] = []
    cautions: List[IFUWarning] = []
    notes: List[IFUWarning] = []

    for section in sections:
        title = section.get("title") or ""
        for para in section.get("paragraphs", []) or []:
            raw = para.get("text") or ""
            match = _SEVERITY.match(raw.strip())
            if not match:
                continue
            label = match.group("label").upper()
            body = match.group("body").strip()
            page_info = lookup.resolve(raw, mark_used=False) or {}
            payload = IFUWarning(
                id=f"{doc_id}::warning_{len(warnings)+len(cautions)+len(notes)+1}",
                doc_id=doc_id,
                severity=label,
                section=title,
                text=body,
                page=page_info.get("page"),
                span=None,
            )
            if label == "CAUTION":
                cautions.append(payload)
            elif label == "NOTE":
                notes.append(payload)
            else:
                warnings.append(payload)

    intended_use = _collect_paragraphs(sections, "intended use")
    indications = _collect_paragraphs(sections, "indications for use")
    contraindications = _collect_paragraphs(sections, "contraindications")

    software_versions = []
    for match in _SOFTWARE.findall(full_text or ""):
        if match not in software_versions:
            software_versions.append(match)

    model = None
    meta_title = meta.get("title") or meta.get("short_title") or ""
    meta_match = _MODEL.search(meta_title)
    if meta_match:
        model = meta_match.group(1)
    if model is None:
        first_block = full_text.split("\n", 1)[0] if full_text else ""
        for match in _MODEL.findall(first_block):
            model = match
            break

    part_numbers = sorted(set(_PART.findall(full_text or "")))

    setup_steps = _extract_steps(
        doc_id,
        sections,
        page_map,
        keywords=("prepare", "setup", "system test", "position"),
    )
    procedure_steps = _extract_steps(
        doc_id,
        sections,
        page_map,
        keywords=("procedure", "biopsy", "dock", "navigate"),
    )

    accessories = _collect_paragraphs(sections, "compatibility", "third-party")

    device_name = meta.get("title") or (sections[0].get("title") if sections else None)

    return IFUExtract(
        doc_id=doc_id,
        device_name=device_name,
        model=model,
        software_versions=software_versions,
        part_numbers=part_numbers,
        intended_use=intended_use,
        indications_for_use=indications,
        contraindications=contraindications,
        warnings=warnings,
        cautions=cautions,
        notes=notes,
        setup_steps=setup_steps,
        procedure_steps=procedure_steps,
        compatible_accessories=accessories,
    )


__all__ = ["extract_ifu_data"]
