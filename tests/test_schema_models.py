"""Tests for the canonical schema dataclasses."""

from __future__ import annotations

import json

from medparse.schema import (
    Concept,
    CrossRef,
    DocumentArtifact,
    Figure,
    Quality,
    Reference,
    StatResult,
    Table,
)


def test_document_artifact_serializes_to_json() -> None:
    artifact = DocumentArtifact(
        meta={"title": "Test Document", "doc_id": "doc-001"},
        sections=[{"id": "sec-1", "title": "Introduction", "text": "Sample text."}],
        concepts=[
            Concept(
                cui="C1234567",
                tui="T047",
                pref_label="Non-small cell lung carcinoma",
                synonyms=["NSCLC"],
                offsets=[(0, 5)],
                source="quickumls",
                score=0.98,
            )
        ],
        statistics=[
            StatResult(
                type="sensitivity",
                value=0.96,
                ci_low=0.90,
                ci_high=0.99,
                p=0.01,
                n=120,
                group_labels=["EBUS", "EUS"],
                text_span="Sensitivity 96% (95% CI 90-99)",
                table_ref="Table 2",
            )
        ],
        figures=[
            Figure(
                id="Fig. 1",
                caption="Complementary nature of EBUS/EUS.",
                page=3,
                bbox=[0.1, 0.1, 0.9, 0.8],
                ocr_text="EBUS and EUS schematic",
            )
        ],
        tables=[
            Table(
                id="Table 2",
                caption="Diagnostic performance",
                page=4,
                structure_json=[["Modality", "Sensitivity"], ["Combined", "96%"]],
                csv_path="tables/doc-001_table-2.csv",
            )
        ],
        references=[
            Reference(
                raw="Annema J.A. et al. JAMA. 2010;304:1763-9.",
                doi="10.1001/jama.2010.1531",
                pmid="20978260",
                title="Mediastinal staging in lung cancer",
                journal="JAMA",
                year=2010,
            )
        ],
        crossrefs=[
            CrossRef(
                source_type="section",
                source_id="sec-1",
                target_type="figure",
                target_id="Fig. 1",
                anchor_text="(Fig. 1)",
                page=3,
            )
        ],
        quality=Quality(
            completeness_score=0.92,
            missing_fields=[],
            warnings=[],
        ),
        provenance={"pipeline_version": "0.1.0"},
    )

    json_payload = artifact.model_dump_json()
    payload = json.loads(json_payload)

    assert payload["meta"]["title"] == "Test Document"
    assert payload["concepts"][0]["cui"] == "C1234567"
    assert payload["statistics"][0]["ci_low"] == 0.90
    assert payload["figures"][0]["id"] == "Fig. 1"
    assert payload["tables"][0]["structure_json"][1][1] == "96%"
    assert payload["references"][0]["doi"] == "10.1001/jama.2010.1531"
    assert payload["crossrefs"][0]["anchor_text"] == "(Fig. 1)"
    assert payload["quality"]["completeness_score"] == 0.92
