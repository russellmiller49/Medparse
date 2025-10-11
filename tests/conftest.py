# tests/conftest.py
from __future__ import annotations

import os
from pathlib import Path
from importlib import reload

import pytest
from fastapi.testclient import TestClient

# We purposely import AFTER env is loaded in the fixtures that need it.
# For the TestClient fixture we import lazily inside the function.


def _load_env_file_into_os(env_path: Path) -> None:
    if env_path.exists():
        for raw in env_path.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()


# --- 1) Load .env.test for EVERY test (function-scoped, autouse, NO monkeypatch) ---
@pytest.fixture(autouse=True)
def set_test_env_per_test():
    """
    Function-scoped (so no scope mismatch) and modifies os.environ directly.
    Ensures tests run offline and pass auth with a harmless key.
    """
    # Load tests/.env.test if present
    env_path = Path(__file__).parent / ".env.test"
    _load_env_file_into_os(env_path)

    # Force critical switches for tests regardless of file contents
    os.environ["ENABLE_PIPELINE"] = "false"
    os.environ["TESTING"] = "true"
    os.environ["REQUIRE_API_KEY"] = "true"
    os.environ["API_KEY"] = "test"

    # No return; just ensures process env is ready before app/settings import.


# --- 2) Shared TestClient that always sends x-api-key header ---
@pytest.fixture(scope="session")
def client() -> TestClient:
    # Import here (after env is prepared by the first test call)
    from api import service
    from api.main import app

    # If your settings object is already constructed at import time,
    # reflect env flags onto it for consistency.
    # If you have a reload helper, call it; otherwise set attrs directly.
    # Prefer reload(service) once if settings are created at import.
    try:
        reload(service)  # makes service.settings re-read env if implemented that way
    except Exception:
        pass

    # Mirror key flags (safe even if already correct)
    setattr(service.settings, "ENABLE_PIPELINE", False)
    setattr(service.settings, "API_KEY", "test")

    return TestClient(app, headers={"x-api-key": "test"})


# --- 3) Optional helpers for finding fixtures on disk ---
@pytest.fixture(scope="session")
def pdf_dir() -> Path:
    return Path(__file__).parent / "data" / "pdfs"


@pytest.fixture(scope="session")
def golden_dir() -> Path:
    return Path(__file__).parent / "golden"
