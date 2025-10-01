from scripts.statistics_enhanced import extract_statistics


def _build_page_payload(text: str) -> dict:
    return {
        "document": {
            "pages": [
                {
                    "number": 1,
                    "text": text,
                }
            ]
        }
    }


def test_textual_statistics_capture_npvs_and_sensitivity():
    paragraph = (
        "Sensitivity and NPV for EUS-FNA of the left adrenal gland were at least 86% "
        "(95%CI 74 -93%) and 70%, respectively. Values (NPVs) of 86% and 93% (P=0.26), "
        "respectively. The sensitivity of the combination was 85%; this reduced the "
        "percentage of unnecessary thoracotomies from 18% to 7% (P = 0.02)."
    )
    doc = {
        "structure": {
            "sections": [
                {
                    "title": "Recommendations",
                    "paragraphs": [{"text": paragraph}],
                }
            ]
        }
    }
    full_text = "Recommendations\n" + paragraph
    stats = extract_statistics(doc, full_text, _build_page_payload(full_text))

    types_to_values = {
        (s["type"], s.get("display")): s for s in stats if s.get("type") in {"sensitivity", "negative_predictive_value"}
    }

    assert ("sensitivity", "86%") in types_to_values
    assert ("negative_predictive_value", "86%") in types_to_values
    assert ("negative_predictive_value", "93%") in types_to_values

    # Ensure p-values and CIs are present
    p_values = [s for s in stats if s.get("type") == "p_value"]
    assert any(abs(s.get("value") - 0.02) < 1e-6 for s in p_values)

    cis = [s for s in stats if s.get("type") == "confidence_interval"]
    assert any(s.get("ci", {}).get("low") == 74.0 and s.get("ci", {}).get("high") == 93.0 for s in cis)

    # Page provenance is captured
    assert any(s.get("page") == 1 for s in stats if s.get("type") == "sensitivity")


def test_table_statistics_parse_percentages():
    table = {
        "id": "table01",
        "page": 5,
        "rows": [
            [{"text": "Author"}, {"text": "Sensitivity (%)"}, {"text": "NPV (%)"}],
            [{"text": "Study A"}, {"text": "85"}, {"text": "93"}],
        ],
    }
    doc = {
        "structure": {"sections": []},
        "tables": [table],
        "assets": {
            "tables": [
                {
                    "content": {
                        "local_id": "table01",
                        "prov": [
                            {
                                "page_no": 5,
                                "bbox": {"l": 0, "t": 0, "r": 10, "b": 10},
                            }
                        ],
                    },
                    "footnotes": [],
                }
            ]
        },
    }

    stats = extract_statistics(doc, "", None)

    table_stats = [s for s in stats if s.get("source") == "table" and s.get("type") == "sensitivity"]
    assert table_stats, "Expected sensitivity stat from table"
    top = table_stats[0]
    assert abs(top.get("value") - 0.85) < 1e-6
    assert top.get("table_id") == "table01"
    assert top.get("page") == 5
    assert top.get("bbox") == {"l": 0, "t": 0, "r": 10, "b": 10}


def test_figure_footnote_statistics():
    figure = {
        "id": "fig01",
        "caption": "Fig. 1 Complication rate overview",
        "footnotes": ["The overall complication rate was 1.23% (95%CI 0.97-1.48%)."],
        "page": 2,
    }
    doc = {
        "structure": {"sections": []},
        "figures": [figure],
        "assets": {
            "figures": [
                {
                    "content": {
                        "local_id": "fig01",
                        "prov": [
                            {
                                "page_no": 2,
                                "bbox": {"l": 1, "t": 1, "r": 5, "b": 5},
                            }
                        ],
                    },
                    "footnotes": figure["footnotes"],
                }
            ]
        },
    }

    stats = extract_statistics(doc, "", None)
    comp_rates = [s for s in stats if s.get("type") == "complication_rate"]
    assert comp_rates, "Expected complication rate stat from figure footnote"
    assert abs(comp_rates[0].get("value") - 0.0123) < 1e-6
    assert comp_rates[0].get("page") == 2
    assert comp_rates[0].get("source") == "footnote"

