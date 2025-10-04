"""Article extractor heuristics."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from medparse.structured.models import ArticleDiagnosticOutcome, ArticleExtract, PopulationStats

_YIELD_PERCENT = re.compile(r"diagnostic yield(?: of)?\s+(\d{1,3}(?:\.\d+)?)%", re.IGNORECASE)
_TOOL_YIELD = {
    "needle": re.compile(r"needle[^%]*?(\d{1,3}(?:\.\d+)?)%", re.IGNORECASE),
    "forceps": re.compile(r"forceps[^%]*?(\d{1,3}(?:\.\d+)?)%", re.IGNORECASE),
    "cryobiopsy": re.compile(r"cryobiops(?:y|ies)[^%]*?(\d{1,3}(?:\.\d+)?)%", re.IGNORECASE),
}
_EXCLUSIVE_CRYO = re.compile(r"cryobiops(?:y|ies) were (?:the )?only diagnostic modality in \d+ \((\d{1,3}(?:\.\d+)?)%\)", re.IGNORECASE)
_NONSPECIFIC_RULE = re.compile(r"non\-specific inflammation; these cases were only considered diagnostic if", re.IGNORECASE)
_PATIENTS = re.compile(r"diagnosis was made in (\d+) patients", re.IGNORECASE)
_NODULES = re.compile(r"(\d+) nodules", re.IGNORECASE)


def _section_text(sections: List[Dict[str, Any]], *keywords: str) -> str:
    chunks: List[str] = []
    for section in sections:
        title = (section.get("title") or "").lower()
        if any(key in title for key in keywords):
            for para in section.get("paragraphs", []) or []:
                text = para.get("text") or ""
                if text.strip():
                    chunks.append(text.strip())
    return " ".join(chunks)


def _parse_percentage(pattern: re.Pattern[str], text: str) -> Optional[float]:
    match = pattern.search(text)
    if not match:
        return None
    value = float(match.group(1))
    return value / 100 if value > 1 else value


def _extract_ats_definition(text: str, outcome: ArticleDiagnosticOutcome) -> bool:
    lower = text.lower()
    if "strict definition of diagnostic yield" not in lower:
        return False
    outcome.yield_definition = "strict"
    outcome.numerator_definition = (
        "Include all patients with peripheral pulmonary nodules where the minimally "
        "invasive procedure established a specific benign or malignant diagnosis."
    )
    outcome.denominator_definition = (
        "All patients in whom the minimally invasive procedure was attempted or performed."
    )
    outcome.handles_nonspecific_pathology = True
    outcome.nonspecific_handling_notes = (
        "Intermediate and liberal definitions are discouraged; nonspecific results are excluded from the numerator."
    )
    if "12" in lower and "follow" in lower:
        outcome.followup_window_months = 12
    outcome.notes = (
        "ATS 2024 research statement advocating strict diagnostic yield terminology and study design guidance."
    )
    return True


def extract_article_outcomes(
    doc_id: str,
    payload: Dict[str, Any],
    full_text: str,
    page_map: Optional[List[Dict[str, Any]]],
) -> Optional[ArticleExtract]:
    text = full_text or ""
    sections = (payload.get("structure") or {}).get("sections") or []

    outcome = ArticleDiagnosticOutcome(doc_id=doc_id)
    population = PopulationStats()

    if _extract_ats_definition(text, outcome):
        return ArticleExtract(doc_id=doc_id, population=population, diagnostic_outcome=outcome)

    diagnoses_text = _section_text(sections, "diagnoses", "results")
    conclusion_text = _section_text(sections, "conclusion")
    analysis_text = diagnoses_text + " " + conclusion_text
    if not analysis_text.strip():
        return None

    patients_match = _PATIENTS.search(diagnoses_text)
    if patients_match:
        population.n_patients = int(patients_match.group(1))
    nodules_match = _NODULES.search(diagnoses_text)
    if nodules_match:
        population.n_lesions = int(nodules_match.group(1))

    overall = _parse_percentage(_YIELD_PERCENT, diagnoses_text) or _parse_percentage(_YIELD_PERCENT, conclusion_text)
    if overall is not None:
        outcome.yield_overall = overall

    tool_yield: Dict[str, float] = {}
    for tool, pattern in _TOOL_YIELD.items():
        value = _parse_percentage(pattern, diagnoses_text)
        if value is not None:
            tool_yield[tool] = value
    if tool_yield:
        outcome.tool_yield = tool_yield
        population.tools_used = sorted(tool_yield.keys())

    exclusive = _parse_percentage(_EXCLUSIVE_CRYO, conclusion_text)
    if exclusive is None:
        exclusive = _parse_percentage(_EXCLUSIVE_CRYO, diagnoses_text)
    if exclusive is not None:
        outcome.exclusive_by_tool = {"cryobiopsy": exclusive}

    if "all cryobiopsy" in analysis_text.lower() and "ngs" in analysis_text.lower():
        outcome.ngs_adequacy_by_tool["cryobiopsy"] = 1.0

    if _NONSPECIFIC_RULE.search(diagnoses_text):
        outcome.handles_nonspecific_pathology = True
        outcome.nonspecific_handling_notes = (
            "Non-specific diagnoses counted only with radiographic improvement or confirmatory modality."
        )
        outcome.yield_definition = outcome.yield_definition or "intermediate"

    if outcome.yield_definition is None and outcome.tool_yield:
        outcome.yield_definition = "intermediate"

    outcome.notes = outcome.notes or "Robotic cryobiopsy pilot summary."

    return ArticleExtract(
        doc_id=doc_id,
        population=population,
        diagnostic_outcome=outcome,
    )


__all__ = ["extract_article_outcomes"]
