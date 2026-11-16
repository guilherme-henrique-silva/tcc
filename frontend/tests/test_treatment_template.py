"""Testes do texto inicial do editor de tratamento (sem Streamlit)."""

import sys
from pathlib import Path

_FRONTEND_DIR = Path(__file__).resolve().parents[1]
if str(_FRONTEND_DIR) not in sys.path:
    sys.path.insert(0, str(_FRONTEND_DIR))

from components import treatment_template as tpl  # noqa: E402

URL = "https://g1/a"


def test_initial_text_prefers_saved_treated():
    assert tpl.initial_text(URL, "03-11-2026", "tratado", "original") == "tratado"


def test_initial_text_falls_back_to_original():
    assert tpl.initial_text(URL, "03-11-2026", None, "# Título") == "# Título"


def test_initial_text_without_original_is_empty_skeleton_not_example():
    text = tpl.initial_text(URL, "03-11-2026", None, "")

    assert "Banco do Brasil" not in text
    assert f"url: {URL}" in text
    assert "date: 03-11-2026" in text
    assert not tpl.is_example(text)


def test_is_example_detects_template_only():
    assert tpl.is_example(tpl.TEMPLATE_TRATADO)
    assert tpl.is_example(tpl.TEMPLATE_TRATADO + "\n")
    assert not tpl.is_example(tpl.skeleton(URL, "03-11-2026"))
