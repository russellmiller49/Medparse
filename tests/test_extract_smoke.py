import io
from api import service

def test_extract_returns_stub_when_pipeline_disabled(client):
    setattr(service.settings, "ENABLE_PIPELINE", False)
    pdf_bytes = b"%PDF-1.4\n%"
    files = {"pdf": ("test.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    data = {"doc_id": "TESTDOC"}
    resp = client.post("/extract", files=files, data=data)
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["doc_id"] == "TESTDOC"
    assert payload["metadata"] == {}

def test_link_requires_text(client):
    setattr(service.settings, "ENABLE_PIPELINE", False)
    resp = client.post("/link", json={"text": ""})
    assert resp.status_code == 400

def test_link_without_api_key_returns_empty_when_uml_key_missing(client):
    setattr(service.settings, "ENABLE_PIPELINE", False)
    setattr(service.settings, "UMLS_API_KEY", "")
    setattr(service.settings, "QUICKUMLS_PATH", None)
    resp = client.post("/link", json={"text": "massive hemoptysis"})
    assert resp.status_code == 200
    assert resp.json()["umls_links"] == []

def test_link_falls_back_to_quickumls(tmp_path, client, monkeypatch):
    # force UMLS off and QuickUMLS path on
    setattr(service.settings, "ENABLE_PIPELINE", False)
    setattr(service.settings, "UMLS_API_KEY", "")
    setattr(service.settings, "QUICKUMLS_PATH", str(tmp_path))

    fake = [{
        "text": "massive hemoptysis",
        "term": "massive hemoptysis", 
        "cui": "C123",
        "tui": "T047",
        "semtypes": ["T047"],
        "score": 0.91,
        "start": 0,
        "end": 18,
        "preferred": True,
        "synonyms": ["massive hemoptysis"],
        "source": "QuickUMLS"
    }]

    # PATCH THE CALL SITE (module that actually uses the symbol)
    import scripts.linking.enhanced_linker as el
    monkeypatch.setattr(el, "link_with_quickumls", lambda text, quickumls_path: fake, raising=False)

    resp = client.post("/link", json={"text": "massive hemoptysis"})
    assert resp.status_code == 200
    links = resp.json()["umls_links"]
    assert len(links) == 1
    assert links[0]["cui"] == "C123"
    assert links[0]["source"] == "QuickUMLS"
