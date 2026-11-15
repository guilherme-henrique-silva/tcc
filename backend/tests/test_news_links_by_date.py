"""Testes do value object NewsLinksByDate e da validação de news_links na API."""

import json
from datetime import date, time

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
            (B, date(2026, 11, 1), None),
            (A, date(2026, 11, 1), None),
            (D, date(2026, 11, 4), None),
            (C, date(2026, 11, 4), None),
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


class TestPublicationTime:
    """Item como string (horário desconhecido) ou objeto {"url", "time"} (HH:MM, Brasília)."""

    def test_string_item_has_unknown_time(self):
        links = _build({"2026-11-03": [A]})

        assert links.items() == [(A, date(2026, 11, 3), None)]
        assert links.time_of(A) is None

    def test_object_item_with_time(self):
        links = _build({"2026-11-03": [{"url": A, "time": "18:42"}]})

        assert links.items() == [(A, date(2026, 11, 3), time(18, 42))]
        assert links.time_of(A) == time(18, 42)

    def test_object_item_without_time_is_allowed(self):
        links = _build({"2026-11-03": [{"url": A}]})

        assert links.items() == [(A, date(2026, 11, 3), None)]

    def test_null_time_is_unknown(self):
        links = _build({"2026-11-03": [{"url": A, "time": None}]})

        assert links.time_of(A) is None

    def test_mixed_formats_in_the_same_date(self):
        links = _build({"2026-11-03": [A, {"url": B, "time": "09:05"}]})

        assert links.items() == [
            (A, date(2026, 11, 3), None),
            (B, date(2026, 11, 3), time(9, 5)),
        ]

    def test_time_of_unknown_url_is_none(self):
        assert _build({"2026-11-03": [A]}).time_of(B) is None

    @pytest.mark.parametrize("bad", ["7:5", "25:00", "12:60", "18h42", "18:42:10", "", 1842])
    def test_invalid_time_raises_naming_date_and_url(self, bad):
        with pytest.raises(ValueError) as exc:
            _build({"2026-11-03": [{"url": A, "time": bad}]})

        assert "2026-11-03" in str(exc.value)
        assert A in str(exc.value)

    def test_unknown_key_in_object_raises(self):
        with pytest.raises(ValueError, match="desconhecida"):
            _build({"2026-11-03": [{"url": A, "hora": "10:00"}]})

    def test_object_without_url_raises(self):
        with pytest.raises(ValueError, match="url"):
            _build({"2026-11-03": [{"time": "10:00"}]})

    def test_round_trip_through_to_dict(self):
        raw = {"2026-11-03": [A, {"url": B, "time": "18:42"}], "2026-11-04": [C]}
        links = _build(raw)

        assert links.to_dict() == raw
        assert _build(links.to_dict()) == links

    def test_json_string_with_objects(self):
        raw = {"2026-11-03": [{"url": A, "time": "18:42"}]}

        assert _build(json.dumps(raw)).to_dict() == raw

    def test_url_in_two_dates_still_rejected_with_objects(self):
        with pytest.raises(ValueError, match="mais de uma data"):
            _build({
                "2026-11-03": [{"url": A, "time": "10:00"}],
                "2026-11-04": [A],
            })

    def test_repeated_url_keeps_known_time(self):
        links = _build({"2026-11-03": [A, {"url": A, "time": "10:00"}]})

        assert links.items() == [(A, date(2026, 11, 3), time(10, 0))]


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

    def test_accepts_object_items_with_time(self):
        request = self._request({"2026-11-03": [A, {"url": B, "time": "18:42"}]})

        assert request.news_links == {"2026-11-03": [A, {"url": B, "time": "18:42"}]}

    def test_invalid_time_rejected(self):
        with pytest.raises(ValidationError, match="25:10"):
            self._request({"2026-11-03": [{"url": A, "time": "25:10"}]})

    def test_proc_news_dto_exposes_news_date(self):
        from app.api.schemas.pipeline_schema import ProcNewsDTO

        dto = ProcNewsDTO(
            URL=A, PROC_TS="2026-11-04T10:00:00", PROC_SUCCESS=True, NEWS_DATE="2026-11-03"
        )

        assert dto.NEWS_DATE == "2026-11-03"
        assert ProcNewsDTO(URL=A, PROC_TS="x", PROC_SUCCESS=True).NEWS_DATE is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
