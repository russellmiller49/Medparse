from scripts.recommendation_extractor import extract_recommendations


def test_extract_recommendations_handles_multiple_numbers_in_paragraph():
    sections = [
        {
            "title": "Recommendations",
            "paragraphs": [
                {
                    "text": (
                        "8 In patients with suspected metastasis we suggest imaging (Recommendation grade C). "
                        "9 For optimal staging, operators should master both techniques (Recommendation grade D)."
                    )
                }
            ],
        }
    ]

    recs = extract_recommendations(sections)
    by_id = {rec["id"]: rec for rec in recs}

    assert by_id["R8"]["grade"] == "C"
    assert "suspected metastasis" in by_id["R8"]["text"]
    assert by_id["R9"]["grade"] == "D"
    assert "both techniques" in by_id["R9"]["text"]
