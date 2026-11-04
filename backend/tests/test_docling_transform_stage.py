"""Testes da DoclingTransformStage (etapa 0) com conversor Docling falso — offline."""

import json
from datetime import date

import pytest

from backend.src.domain.models import ProcNewsRecord
from backend.src.pipeline.stages import DoclingTransformStage

A = "https://g1.globo.com/economia/noticia/a.ghtml"
B = "https://www.infomoney.com.br/mercados/b/"
C = "https://g1.globo.com/economia/noticia/c.ghtml"
D = "https://www.infomoney.com.br/mercados/d/"

EXAMPLE = {"2026-11-03": [A, B], "2026-11-04": [C, D]}


class _FakeConverter:
    """Conversor falso: sem rede nem Docling; falha para URLs em `failing`."""

    def __init__(self, failing=()):
        self._failing = set(failing)

    def site_name(self, url):
        return "G1" if "g1" in url else "InfoMoney"

    def to_markdown(self, url):
        if url in self._failing:
            raise RuntimeError("falha de conversão")
        return f"# md de {url}"


class _FakeRepo:
    """Repositório em memória que guarda os ProcNewsRecord salvos."""

    def __init__(self):
        self.records = []

    def save_proc_news(self, record: ProcNewsRecord):
        self.records.append(record)


def _stage(failing=(), repo=None):
    return DoclingTransformStage(_FakeConverter(failing), repo)


def test_example_json_yields_four_entries_with_their_dates():
    result = _stage().execute({"news_links": EXAMPLE})

    assert result.status == "SUCCESS"
    dates_by_url = {e["url"]: e["news_date"] for e in result.data["news_markdowns"]}
    assert dates_by_url == {
        A: "2026-11-03", B: "2026-11-03", C: "2026-11-04", D: "2026-11-04",
    }


def test_json_string_is_equivalent_to_dict():
    from_dict = _stage().execute({"news_links": EXAMPLE})
    from_text = _stage().execute({"news_links": json.dumps(EXAMPLE)})

    assert [e["url"] for e in from_text.data["news_markdowns"]] == [
        e["url"] for e in from_dict.data["news_markdowns"]
    ]


def test_success_entry_shape():
    result = _stage().execute({"news_links": {"2026-11-03": [A]}})

    assert result.data["news_markdowns"] == [
        {
            "url": A, "site": "G1", "markdown": f"# md de {A}",
            "success": True, "news_date": "2026-11-03",
        }
    ]


def test_failed_conversion_keeps_news_date():
    result = _stage(failing=[B]).execute({"news_links": {"2026-11-03": [A, B]}})
    failed = next(e for e in result.data["news_markdowns"] if e["url"] == B)

    assert result.status == "SUCCESS"
    assert failed["success"] is False
    assert failed["markdown"] == ""
    assert failed["error"] == "falha de conversão"
    assert failed["news_date"] == "2026-11-03"


def test_proc_news_records_saved_with_news_date():
    repo = _FakeRepo()

    _stage(repo=repo).execute({"news_links": EXAMPLE, "pipeline_id": "run-1"})

    assert len(repo.records) == 4
    assert {r.url: r.news_date for r in repo.records} == {
        A: date(2026, 11, 3), B: date(2026, 11, 3),
        C: date(2026, 11, 4), D: date(2026, 11, 4),
    }
    assert all(r.proc_id == "run-1" for r in repo.records)


def test_failed_conversion_is_registered_with_news_date():
    repo = _FakeRepo()

    _stage(failing=[A], repo=repo).execute({"news_links": {"2026-11-03": [A]}})

    assert repo.records[0].proc_success is False
    assert repo.records[0].news_date == date(2026, 11, 3)


@pytest.mark.parametrize(
    "legacy",
    [[A, B], json.dumps([A, B]), {"links": [A, B]}, json.dumps({"links": [A]}), A],
)
def test_legacy_formats_fail_with_explanatory_message(legacy):
    repo = _FakeRepo()

    result = _stage(repo=repo).execute({"news_links": legacy})

    assert result.status == "FAILED"
    assert result.error_message
    assert repo.records == []


@pytest.mark.parametrize(
    "invalid, fragment",
    [
        ({"2099-01-01": [A]}, "futuro"),
        ({"03/11/2026": [A]}, "03/11/2026"),
        ({"2026-11-03": [A], "2026-11-04": [A]}, "mais de uma data"),
        ({"2026-11-03": A}, "lista"),
    ],
)
def test_invalid_structure_fails_with_value_object_message(invalid, fragment):
    result = _stage().execute({"news_links": invalid})

    assert result.status == "FAILED"
    assert fragment in result.error_message


@pytest.mark.parametrize("empty", [None, "", {}, "{}"])
def test_empty_input_succeeds_without_items(empty):
    result = _stage().execute({"news_links": empty})

    assert result.status == "SUCCESS"
    assert result.data["news_markdowns"] == []


def test_missing_key_succeeds_without_items():
    result = _stage().execute({})

    assert result.status == "SUCCESS"
    assert result.data["news_markdowns"] == []


def test_output_order_follows_date_then_given_order():
    result = _stage().execute({"news_links": {"2026-11-04": [D, C], "2026-11-03": [B, A]}})

    assert [e["url"] for e in result.data["news_markdowns"]] == [B, A, D, C]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
