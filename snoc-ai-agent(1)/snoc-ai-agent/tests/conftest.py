import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from app.database import init_db


@pytest.fixture(autouse=True)
def _init_db(tmp_path, monkeypatch):
    """Isole chaque test avec sa propre base SQLite et un backend NLU déterministe."""
    import app.database as db
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test_audit.db")
    init_db()

    import app.llm.llm_client as llm_client
    monkeypatch.setattr(llm_client, "LLM_BACKEND", "mock")
    yield
