"""Tests for environment-based configuration loading."""

from __future__ import annotations

from pathlib import Path

from medparse.config import AppConfig


def test_app_config_loads_from_env_file(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        """
UMLS_API_KEY=test-key
QUICKUMLS_PATH=/data/quickumls
SCISPACY_MODEL=en_core_sci_md
TUI_WHITELIST=T191,T047 , T060
ENABLE_OCR=true
GROBID_URL=http://localhost:8070
PUBMED_EMAIL=user@example.com
PUBMED_TOOL=medparse-tests
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=secret
""".strip()
    )

    config = AppConfig.model_construct_from_env(env_file=env_file)

    assert config.umls_api_key == "test-key"
    assert str(config.quickumls_path) == "/data/quickumls"
    assert config.scispacy_model == "en_core_sci_md"
    assert config.tui_whitelist == {"T191", "T047", "T060"}
    assert config.enable_ocr is True
    assert config.grobid_url == "http://localhost:8070"
    assert config.pubmed_email == "user@example.com"
    assert config.pubmed_tool == "medparse-tests"
    assert config.neo4j_uri == "bolt://localhost:7687"
    assert config.neo4j_user == "neo4j"
    assert config.neo4j_password == "secret"
