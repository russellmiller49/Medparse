# tests/conftest.py
import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

# import your FastAPI app and your settings singleton
from api.main import app
from api import service  # service.settings is your AppConfig (adjust import if needed)

@pytest.fixture(scope="session", autouse=True)
def load_test_env(monkeypatch):
    """
    Load tests/.env.test and apply key flags for offline, deterministic tests.
    """
    env_path = Path(__file__).parent / ".env.test"
    if env_path.exists():
        # minimal loader: read .env.test and set into process env
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            monkeypatch.setenv(k.strip(), v.strip())
    # Make sure critical switches are set even if .env.test is incomplete
    monkeypatch.setenv("ENABLE_PIPELINE", "false")
    monkeypatch.setenv("TESTING", "true")
    monkeypatch.setenv("REQUIRE_API_KEY", "true")
    monkeypatch.setenv("API_KEY", "test")

    # If your service.settings reads env only once at import time,
    # refresh it here if you have a constructor like model_construct_from_env
    if hasattr(service, "reload_settings"):
        service.reload_settings()
    else:
        # Fallback: hard-patch the few fields the tests rely on
        setattr(service.settings, "enable_pipeline", False)
        setattr(service.settings, "testing", True)
        setattr(service.settings, "require_api_key", True)
        setattr(service.settings, "api_key", "test")


@pytest.fixture(scope="session")
def client() -> TestClient:
    """
    Test client that ALWAYS sends the expected x-api-key header.
    """
    return TestClient(app, headers={"x-api-key": "test"})
