"""Testes do value object NewsLinksByDate e da validação de news_links na API."""

import json
from datetime import date

import pytest
from pydantic import ValidationError

from backend.src.domain.value_objects import DateRange, NewsLinksByDate

TODAY = date(2026, 11, 4)

A = "https://g1.globo.com/economia/noticia/a.ghtml"
B = "https://www.infomoney.com.br/mercados/b/"
C = "https://g1.globo.com/economia/noticia/c.ghtml"
D = "https://www.infomoney.com.br/mercados/d/"

EXAMPLE = {"2026-11-03": [A, B], "2026-11-04": [C, D]}


def _build(raw):
    return NewsLinksByDate.from_raw(raw, today=TODAY)


class TestConstruction:
    def test_dict_and_json_string_are_equivalent(self):
        from_dict = _build(EXAMPLE)
        from_text = _build(json.dumps(EXAMPLE))

        assert from_dict == from_text
        assert from_dict.to_dict() == EXAMPLE

    @pytest.mark.parametrize("raw", [None, "", "   ", {}, "{}"])
    def test_empty_inputs_give_empty_collection(self, raw):
        links = _build(raw)

        assert links.is_empty()
        assert len(links) == 0
        assert links.items() == []

    def test_dates_with_empty_list_are_ignored(self):
        links = _build({"2026-11-03": [], "2026-11-04": [C]})

        assert links.to_dict() == {"2026-11-04": [C]}

    def test_today_is_accepted(self):
        assert len(_build({"2026-11-04": [A]})) == 1

    def test_default_today_is_real_today(self):
        links = NewsLinksByDate.from_raw({date.today().isoformat(): [A]})

        assert len(links) == 1


class TestLegacyFormatsRejected:
    @pytest.mark.parametrize(
        "raw",
        [
            [A, B],
            json.dumps([A, B]),
            {"links": [A, B]},
            json.dumps({"links": [A, B]}),
            A,
            42,
        ],
    )
    def test_legacy_formats_raise(self, raw):
        with pytest.raises(ValueError):
            _build(raw)

    def test_non_json_string_is_not_a_single_link(self):
        with pytest.raises(ValueError, match="JSON"):
            _build("https://g1.globo.com/a")

    def test_list_root_message_mentions_object(self):
        with pytest.raises(ValueError, match="objeto JSON"):
            _build([A])


class TestValidation:
    @pytest.mark.parametrize(
        "key", ["03/11/2026", "2026-02-30", "20261103", "2026-W45-2", "2026-11-3", "ontem"]
    )
    def test_malformed_date_raises_naming_the_key(self, key):
        with pytest.raises(ValueError) as exc:
            _build({key: [A]})

        assert key in str(exc.value)

    def test_future_date_raises(self):
        with pytest.raises(ValueError, match="2099-01-01"):
            _build({"2099-01-01": [A]})

    def test_day_after_today_raises(self):
        with pytest.raises(ValueError, match="futuro"):
            _build({"2026-11-05": [A]})

    def test_non_list_value_raises(self):
        with pytest.raises(ValueError, match="2026-11-03"):
            _build({"2026-11-03": A})

    @pytest.mark.parametrize("item", [123, "", "   ", None, ["x"]])
    def test_invalid_item_raises(self, item):
        with pytest.raises(ValueError, match="2026-11-03"):
            _build({"2026-11-03": [A, item]})

    def test_url_repeated_across_dates_raises_naming_url(self):
        with pytest.raises(ValueError) as exc:
            _build({"2026-11-03": [A], "2026-11-04": [A]})

        assert A in str(exc.value)
        assert "2026-11-03" in str(exc.value) and "2026-11-04" in str(exc.value)

    def test_url_repeated_across_dates_after_strip_raises(self):
        with pytest.raises(ValueError):
            _build({"2026-11-03": [A], "2026-11-04": [f"  {A}  "]})


class TestNormalization:
    def test_urls_are_stripped(self):
        assert _build({"2026-11-03": [f"  {A}\n"]}).urls() == [A]

    def test_duplicates_in_same_date_collapse_keeping_first_order(self):
        links = _build({"2026-11-03": [B, A, B, A]})

        assert links.to_dict() == {"2026-11-03": [B, A]}
        assert len(links) == 2

    def test_items_sorted_by_date_then_given_order(self):
        links = _build({"2026-11-04": [D, C], "2026-11-01": [B, A]})

        assert links.items() == [
            (B, date(2026, 11, 1)),
            (A, date(2026, 11, 1)),
            (D, date(2026, 11, 4)),
            (C, date(2026, 11, 4)),
        ]
        assert links.urls() == [B, A, D, C]

    def test_items_have_no_duplicates(self):
        links = _build({"2026-11-03": [A, A, B]})

        assert len(links.items()) == len(set(links.urls())) == 2

    def test_collection_is_immutable(self):
        links = _build(EXAMPLE)

        with pytest.raises(Exception):
            links._groups = ()  # type: ignore[misc]

    def test_to_dict_returns_independent_copy(self):
        links = _build(EXAMPLE)
        links.to_dict()["2026-11-03"].append("x")

        assert links.to_dict() == EXAMPLE


class TestDatesOutside:
    def test_returns_only_dates_outside_range(self):
        links = _build({"2026-10-01": [A], "2026-11-03": [B], "2026-11-04": [C]})
        analysis = DateRange(date(2026, 11, 1), date(2026, 11, 3))

        assert links.dates_outside(analysis) == [date(2026, 10, 1), date(2026, 11, 4)]

    def test_empty_when_all_inside(self):
        links = _build(EXAMPLE)

        assert links.dates_outside(DateRange(date(2026, 1, 1), date(2026, 12, 31))) == []

    def test_does_not_invalidate_collection(self):
        links = _build({"2020-01-01": [A]})
        links.dates_outside(DateRange(date(2026, 1, 1), date(2026, 12, 31)))

        assert len(links) == 1


class TestExecuteRequestSchema:
    """PipelineExecuteRequest.news_links valida via NewsLinksByDate (HTTP 422)."""

    @staticmethod
    def _request(news_links):
        from app.api.schemas.pipeline_schema import PipelineExecuteRequest

        return PipelineExecuteRequest(
            date_range={"start_date": "2026-01-01", "end_date": "2026-12-31"},
            news_links=news_links,
        )

    def test_accepts_new_format_and_normalizes(self):
        request = self._request({"2026-11-03": [f" {A} ", A, B]})

        assert request.news_links == {"2026-11-03": [A, B]}

    def test_omitted_is_none(self):
        assert self._request(None).news_links is None

    def test_empty_object_is_accepted(self):
        assert self._request({}).news_links == {}

    def test_future_date_rejected(self):
        with pytest.raises(ValidationError, match="futuro"):
            self._request({"2099-01-01": [A]})

    def test_malformed_date_rejected(self):
        with pytest.raises(ValidationError, match="03/11/2026"):
            self._request({"03/11/2026": [A]})

    def test_url_in_two_dates_rejected(self):
        with pytest.raises(ValidationError, match="mais de uma data"):
            self._request({"2026-11-03": [A], "2026-11-04": [A]})

    def test_flat_list_rejected(self):
        with pytest.raises(ValidationError, match="objeto JSON"):
            self._request([A, B])

    def test_proc_news_dto_exposes_news_date(self):
        from app.api.schemas.pipeline_schema import ProcNewsDTO

        dto = ProcNewsDTO(
            URL=A, PROC_TS="2026-11-04T10:00:00", PROC_SUCCESS=True, NEWS_DATE="2026-11-03"
        )

        assert dto.NEWS_DATE == "2026-11-03"
        assert ProcNewsDTO(URL=A, PROC_TS="x", PROC_SUCCESS=True).NEWS_DATE is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
