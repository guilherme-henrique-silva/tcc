"""Fixtures compartilhadas dos testes (Requisito 13): storage isolado em banco temporário.

Garante que tanto os imports `backend.src...` (usados pelos testes) quanto os imports
internos `src...`/`app...` (usados pelo código) resolvam, adicionando `backend/` ao path.
"""

import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[1]  # .../TCC/backend
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

import pytest

from backend.src.adapters.storage import SQLiteStorage


@pytest.fixture
def db_url(tmp_path) -> str:
    """SQLite URL apontando para um arquivo temporário (isola os testes do DB real)."""
    return f"sqlite:///{(tmp_path / 'test.db').as_posix()}"


@pytest.fixture
def storage(db_url) -> SQLiteStorage:
    """SQLiteStorage recém-inicializado sobre um banco temporário."""
    return SQLiteStorage(db_url)
