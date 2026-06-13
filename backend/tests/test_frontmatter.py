"""Testes do parser de frontmatter e do TreatedNewsRecord (Requisito 13)."""

import pytest

from backend.src.domain.models import parse_frontmatter, TreatedNewsRecord

_MARKDOWN = "---\ntitle: A\nsubtitle: B\nurl: u\ndate: 12-06-2026\n---\nCorpo principal."


def test_parse_frontmatter_full():
    meta, body = parse_frontmatter(_MARKDOWN)

    assert meta == {"title": "A", "subtitle": "B", "url": "u", "date": "12-06-2026"}
    assert body == "Corpo principal."


def test_parse_frontmatter_absent():
    meta, body = parse_frontmatter("Só texto, sem frontmatter.")

    assert meta == {"title": "", "subtitle": "", "url": "", "date": ""}
    assert body == "Só texto, sem frontmatter."


def test_parse_frontmatter_without_closing_fence():
    meta, body = parse_frontmatter("---\ntitle: x\nsem fechamento")

    assert meta["title"] == ""  # sem fence de fechamento → trata tudo como corpo
    assert body.startswith("---")


def test_treated_record_from_markdown_roundtrip():
    record = TreatedNewsRecord.from_treated_markdown("u", _MARKDOWN, proc_id="run-1")

    assert record.title == "A"
    assert record.subtitle == "B"
    assert record.date == "12-06-2026"
    assert record.content == _MARKDOWN
    assert record.proc_id == "run-1"
    assert TreatedNewsRecord.from_row(record.to_dict()) == record


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
