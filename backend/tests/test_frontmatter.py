"""Testes do parser de frontmatter e do TreatedNewsRecord."""

import pytest

from backend.src.domain.models import parse_frontmatter, TreatedNewsRecord

_MARKDOWN = (
    "---\ntitle: A\nsubtitle: B\nurl: u\ndate: 12-06-2026\ncategory: finanças\n---\nCorpo principal."
)
_MARKDOWN_NO_CATEGORY = "---\ntitle: A\nsubtitle: B\nurl: u\ndate: 12-06-2026\n---\nCorpo principal."


def test_parse_frontmatter_full():
    meta, body = parse_frontmatter(_MARKDOWN)

    assert meta == {
        "title": "A",
        "subtitle": "B",
        "url": "u",
        "date": "12-06-2026",
        "category": "finanças",
    }
    assert body == "Corpo principal."


def test_parse_frontmatter_absent():
    meta, body = parse_frontmatter("Só texto, sem frontmatter.")

    assert meta == {"title": "", "subtitle": "", "url": "", "date": "", "category": ""}
    assert body == "Só texto, sem frontmatter."


def test_parse_frontmatter_without_closing_fence():
    meta, body = parse_frontmatter("---\ntitle: x\nsem fechamento")

    assert meta["title"] == ""  # sem fence de fechamento → trata tudo como corpo
    assert body.startswith("---")


def test_parse_frontmatter_without_category_returns_empty():
    """Frontmatter sem category não quebra; retorna string vazia."""
    meta, body = parse_frontmatter(_MARKDOWN_NO_CATEGORY)

    assert meta["category"] == ""
    assert meta["title"] == "A"
    assert body == "Corpo principal."


def test_treated_record_from_markdown_roundtrip():
    record = TreatedNewsRecord.from_treated_markdown("u", _MARKDOWN, proc_id="run-1")

    assert record.title == "A"
    assert record.subtitle == "B"
    assert record.date == "12-06-2026"
    assert record.category == "finanças"
    assert record.content == _MARKDOWN
    assert record.proc_id == "run-1"
    assert TreatedNewsRecord.from_row(record.to_dict()) == record


def test_treated_record_to_dict_includes_category():
    record = TreatedNewsRecord.from_treated_markdown("u", _MARKDOWN)

    d = record.to_dict()

    assert "CATEGORY" in d
    assert d["CATEGORY"] == "finanças"


def test_treated_record_from_row_without_category_defaults_empty():
    """from_row com linha legada (sem CATEGORY) não quebra."""
    row = {
        "URL": "http://example.com",
        "PROC_ID": None,
        "TITLE": "T",
        "SUBTITLE": "S",
        "NEWS_DATE": "01-01-2025",
        "CONTENT": "corpo",
    }
    record = TreatedNewsRecord.from_row(row)

    assert record.category == ""


def test_treated_record_roundtrip_with_category():
    record = TreatedNewsRecord(
        url="http://example.com",
        title="T",
        subtitle="S",
        date="01-01-2025",
        category="macroeconomia",
        content="---\ntitle: T\n---\ncorpo",
    )
    rebuilt = TreatedNewsRecord.from_row(record.to_dict())

    assert rebuilt == record


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
