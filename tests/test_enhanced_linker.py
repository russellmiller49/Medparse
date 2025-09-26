import pytest

from scripts.linking import enhanced_linker


@pytest.fixture(autouse=True)
def reset_linker_cache(monkeypatch):
    # Ensure per-test isolation for cached lookups
    monkeypatch.setattr(enhanced_linker, "_SCISPACY_CACHE", {}, raising=False)
    yield


def test_enhanced_linker_prefers_umls(monkeypatch):
    text = "The procedure endobronchial ultrasound was performed."

    monkeypatch.setattr(
        enhanced_linker,
        "link_with_quickumls",
        lambda *_args, **_kwargs: [
            {
                "text": "endobronchial ultrasound",
                "term": "endobronchial ultrasound",
                "cui": "C0001234",
                "semtypes": ["T060"],
                "score": 0.92,
                "start": 17,
                "end": 40,
                "preferred": True,
                "synonyms": ["endobronchial ultrasound", "EBUS"],
            }
        ],
    )

    monkeypatch.setattr(
        enhanced_linker,
        "link_with_scispacy",
        lambda *_args, **_kwargs: [
            {
                "text": "endobronchial ultrasound",
                "start": 17,
                "end": 40,
                "cui": "C0009999",
                "tui": ["T060"],
                "preferred": "Endobronchial ultrasound",
                "synonyms": ["EBUS"],
                "score": 0.7,
            }
        ],
    )

    monkeypatch.setattr(
        enhanced_linker,
        "umls_lookup_exact",
        lambda term: {
            "cui": "C2983795",
            "name": "Endobronchial Ultrasonography",
            "tuis": ["T060"],
        }
        if term.lower() == "endobronchial ultrasound"
        else None,
    )

    monkeypatch.setattr(enhanced_linker, "umls_search_approximate", lambda *_: [])

    results = enhanced_linker.link_medical_concepts(text, top_k=5, quickumls_path="/mock")
    assert len(results) == 1
    result = results[0]
    assert result["cui"] == "C2983795"
    assert result["source"] == "UMLS"
    assert result["preferred_term"] == "Endobronchial Ultrasonography"
    assert result["confidence"] == 1.0
    assert result["semtypes"] == ["T060"]
    assert "EBUS" in result["synonyms"]


def test_enhanced_linker_falls_back_to_quickumls(monkeypatch):
    text = "Thoracotomy was completed without complications."

    monkeypatch.setattr(
        enhanced_linker,
        "link_with_quickumls",
        lambda *_args, **_kwargs: [
            {
                "text": "Thoracotomy",
                "term": "Thoracotomy",
                "cui": "C0040105",
                "semtypes": ["T060"],
                "score": 0.92,
                "start": 0,
                "end": 10,
                "preferred": True,
                "synonyms": ["Thoracotomy"],
            }
        ],
    )
    monkeypatch.setattr(enhanced_linker, "link_with_scispacy", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(enhanced_linker, "umls_lookup_exact", lambda *_: None)
    monkeypatch.setattr(enhanced_linker, "umls_search_approximate", lambda *_: [])

    results = enhanced_linker.link_medical_concepts(text, top_k=5, quickumls_path="/mock")
    assert len(results) == 1
    result = results[0]
    assert result["source"] == "QuickUMLS"
    assert result["confidence"] == 0.92
    assert result["cui"] == "C0040105"


def test_enhanced_linker_filters_disallowed_semtypes(monkeypatch):
    text = "The analysis covered various geographic regions."

    monkeypatch.setattr(
        enhanced_linker,
        "link_with_quickumls",
        lambda *_args, **_kwargs: [
            {
                "text": "geographic regions",
                "term": "geographic regions",
                "cui": "C0017426",
                "semtypes": ["T083"],  # Geographic Area (should be filtered)
                "score": 0.91,
                "start": 32,
                "end": 51,
                "preferred": True,
                "synonyms": ["geographic region"],
            }
        ],
    )
    monkeypatch.setattr(enhanced_linker, "link_with_scispacy", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(enhanced_linker, "umls_lookup_exact", lambda *_: None)
    monkeypatch.setattr(enhanced_linker, "umls_search_approximate", lambda *_: [])

    results = enhanced_linker.link_medical_concepts(text, top_k=5, quickumls_path="/mock")
    assert results == []
