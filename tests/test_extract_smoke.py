import io

from fastapi.testclient import TestClient

from api.main import app
from api import service


def test_extract_returns_stub_when_pipeline_disabled(monkeypatch) -> None:
    monkeypatch.setattr(service.settings, "ENABLE_PIPELINE", False, raising=False)
    client = TestClient(app)
    pdf_bytes = b"%PDF-1.4\n%"
    files = {"pdf": ("test.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    data = {"doc_id": "TESTDOC"}
    response = client.post("/extract", files=files, data=data)
    assert response.status_code == 200
    payload = response.json()
    assert payload["doc_id"] == "TESTDOC"
    assert payload["metadata"] == {}


def test_link_requires_text(monkeypatch) -> None:
    monkeypatch.setattr(service.settings, "ENABLE_PIPELINE", False, raising=False)
    client = TestClient(app)
    response = client.post("/link", json={"text": ""})
    assert response.status_code == 400


def test_link_without_api_key_returns_empty_when_uml_key_missing(monkeypatch) -> None:
    monkeypatch.setattr(service.settings, "ENABLE_PIPELINE", False, raising=False)
    monkeypatch.setattr(service.settings, "UMLS_API_KEY", "", raising=False)
    monkeypatch.setattr(service.settings, "QUICKUMLS_PATH", None, raising=False)
    client = TestClient(app)
    response = client.post("/link", json={"text": "massive hemoptysis"})
    assert response.status_code == 200
    assert response.json()["umls_links"] == []


def test_link_falls_back_to_quickumls(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(service.settings, "ENABLE_PIPELINE", False, raising=False)
    monkeypatch.setattr(service.settings, "UMLS_API_KEY", "", raising=False)
    monkeypatch.setattr(service.settings, "QUICKUMLS_PATH", str(tmp_path), raising=False)

    fake_result = [{"cui": "C123", "text": "massive hemoptysis", "score": 0.91, "source": "QuickUMLS"}]

    monkeypatch.setattr("scripts.linker_router.link_quickumls", lambda text, path: fake_result)

    client = TestClient(app)
    response = client.post("/link", json={"text": "massive hemoptysis"})
    assert response.status_code == 200
    payload = response.json()["umls_links"]
    assert len(payload) == 1
    assert payload[0]["cui"] == "C123"
    assert payload[0]["source"] == "QuickUMLS"
