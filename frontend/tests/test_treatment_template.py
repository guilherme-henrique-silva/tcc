"""Testes do texto inicial do editor de tratamento (sem Streamlit)."""

import sys
from pathlib import Path

_FRONTEND_DIR = Path(__file__).resolve().parents[1]
if str(_FRONTEND_DIR) not in sys.path:
    sys.path.insert(0, str(_FRONTEND_DIR))

from components import treatment_template as tpl  # noqa: E402
from backend.src.domain.models import parse_frontmatter  # noqa: E402

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


_ORIGINAL = """\
# Selic sobe e dólar recua: o que muda para o investidor

## Copom elevou os juros em 0,25 ponto e o Banco Central sinalizou novo ajuste.

Por [Redação g1](https://g1.globo.com/autores/redacao-g1/) - São Paulo

10/06/2026 11h44 Atualizado 10/06/2026

A inflação segue pressionada e o dólar caiu frente ao real.
"""


def test_formatted_fills_every_frontmatter_field():
    text = tpl.formatted(URL, "03-11-2026", _ORIGINAL)
    meta, body = parse_frontmatter(text)

    assert meta["title"] == "Selic sobe e dólar recua: o que muda para o investidor"
    assert meta["subtitle"].startswith("Copom elevou os juros")
    assert meta["url"] == URL
    assert meta["date"] == "03-11-2026"
    assert meta["category"] == "macroeconomia"
    assert not tpl.is_example(text)
    assert "# Selic" not in body and "## Copom" not in body
    assert "Por [Redação g1]" in body  # só título/subtítulo saem; o resto do corpo é mantido
    assert "A inflação segue pressionada" in body


def test_formatted_falls_back_to_article_date_and_empty_subtitle():
    text = tpl.formatted(URL, "", "# Título\n\nTexto de 05/01/2025 sobre bolsa.\n")
    meta, _ = parse_frontmatter(text)

    assert meta["date"] == "05-01-2025"
    assert meta["subtitle"] == ""
    assert meta["category"] == "finanças"


def test_guess_category_defaults_to_financas():
    assert tpl.guess_category("", "", "nada relevante aqui") == "finanças"
