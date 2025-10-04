"""Tests for document-type structured extractors."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from medparse.extractors import run_structured_extractors
from medparse.layout.page_map import build_full_text_with_spans

SAMPLES = {
    "guideline_ebus_eus": Path("output/ebus_eus_guideline_enhanced.json"),
    "guideline_ats_yield": Path("output/Guideline ATS diagnostic yield.pdf.json"),
    "ifu_ion_system": Path("output/Ion_Endoluminal_System_IFU.json"),
    "chapter_airway_fistula": Path("output/Airway-Esophageal Fistulas_Chapter.json"),
    "article_cryobiopsy": Path("output/Robotic_Cyrobiopsy_2022.json"),
}

GOLDEN_DIR = Path(__file__).parent / "golden"


@pytest.mark.parametrize("name", SAMPLES.keys())
def test_structured_extractors_match_golden(name: str) -> None:
    sample_path = SAMPLES[name]
    golden_path = GOLDEN_DIR / f"{name}.json"

    with sample_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    sections = (payload.get("structure") or {}).get("sections") or []
    full_text, page_map = build_full_text_with_spans(sections)

    structured = run_structured_extractors(
        doc_id=sample_path.stem,
        payload=payload,
        full_text=full_text,
        page_map=page_map,
    )

    with golden_path.open("r", encoding="utf-8") as f:
        expected = json.load(f)["structured"]

    assert structured == expected

    # Targeted behavioural assertions
    if "guideline" in structured:
        guideline = structured["guideline"]
        assert guideline["recommendations"], "guideline extraction should produce recommendations"
        if name == "guideline_ebus_eus":
            assert len(guideline["recommendations"]) >= 10
            assert sum(1 for rec in guideline["recommendations"] if rec.get("grade")) >= 5
    if "article" in structured:
        outcome = structured["article"]["diagnostic_outcome"]
        if name == "guideline_ats_yield":
            assert outcome["yield_definition"] == "strict"
        if name == "article_cryobiopsy":
            cryo_yield = outcome["tool_yield"].get("cryobiopsy")
            assert cryo_yield is not None and abs(cryo_yield - 0.972) < 0.02
            assert outcome["exclusive_by_tool"].get("cryobiopsy") is not None
    if "ifu" in structured:
        ifu = structured["ifu"]
        assert ifu["warnings"], "IFU warnings should not be empty"
        assert ifu["intended_use"], "IFU intended_use should be captured"
    if "chapter" in structured and name == "chapter_airway_fistula":
        chapter = structured["chapter"]
        assert (
            chapter["management_principles"] or chapter["diagnostic_workup"]
        ), "Chapter extraction should capture management or diagnostic sections"


def test_page_map_alignment() -> None:
    sample_path = SAMPLES["guideline_ebus_eus"]
    with sample_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    sections = (payload.get("structure") or {}).get("sections") or []
    full_text, page_map = build_full_text_with_spans(sections)

    assert full_text
    assert page_map

    for entry in page_map[:20]:
        start = entry["start"]
        end = entry["end"]
        text = entry["text"]
        assert full_text[start:end] == text
