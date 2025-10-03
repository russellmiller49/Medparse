import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from scripts.graph_export import build_graph_payload


def test_build_graph_payload_creates_nodes_and_edges():
    doc = {
        "metadata": {"title": "Test Doc", "doi": "10.1234/test"},
        "structure": {
            "sections": [
                {
                    "title": "Recommendations",
                    "category": "recommendations",
                    "paragraphs": [],
                }
            ]
        },
        "recommendations": [
            {
                "id": "R1",
                "number": 1,
                "grade": "A",
                "text": "We recommend endobronchial ultrasound.",
                "sections": [{"index": 0, "title": "Recommendations"}],
            }
        ],
        "statistics": [
            {
                "id": "stat_0001",
                "type": "p_value",
                "value": 0.05,
                "section_index": 0,
                "source": "text",
            }
        ],
        "figures": [
            {"local_id": "fig01", "caption": "Figure caption", "page": 1}
        ],
        "tables": [
            {"local_id": "table01", "caption": "Table caption", "page": 2}
        ],
        "references_enriched": [
            {"pmid": "12345", "title": "Reference", "journal": "Journal"}
        ],
        "umls_links": [
            {
                "text": "endobronchial ultrasound",
                "cui": "C123",
                "semtypes": ["T060"],
                "score": 0.9,
                "preferred_term": "Endobronchial ultrasound",
                "synonyms": ["EBUS"],
                "start": 10,
                "end": 34,
                "section_index": 0,
            }
        ],
    }

    payload = build_graph_payload(doc)
    node_types = {node["type"] for node in payload["nodes"]}
    assert {"Document", "Section", "Recommendation", "Concept", "Statistic", "Figure", "Table", "Reference"}.issubset(
        node_types
    )

    edge_types = {edge["type"] for edge in payload["edges"]}
    assert "HAS_RECOMMENDATION" in edge_types
    assert "MENTIONS_CONCEPT" in edge_types
    assert "SUPPORTED_BY" in edge_types
