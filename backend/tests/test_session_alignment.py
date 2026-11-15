"""Testes do calendário de pregões e do alinhamento das notícias (RF-04)."""

from datetime import date, datetime, time

import pytest

from backend.src.domain.models import News, StockPrice
from backend.src.domain.services.session_alignment import (
    align_news_to_sessions,
    align_news_with_audit,
    parse_close_time,
    session_calendar,
)

CLOSE = time(17, 0)

# Calendário de teste: 19/03/2025 (quarta) é "feriado" — ausente do calendário.
SESSIONS = [
    date(2025, 3, 13),  # quinta
    date(2025, 3, 14),  # sexta
    date(2025, 3, 17),  # segunda
    date(2025, 3, 18),  # terça
    date(2025, 3, 20),  # quinta (quarta 19 é feriado)
]


def _news(day: date, when=None, url="u") -> News:
    return News(
        title="t", content="c", source="s",
        published_date=datetime(day.year, day.month, day.day),
        url=url, published_time=when,
    )


def _target(items):
    """Pregão atribuído à única notícia."""
    assigned = align_news_to_sessions(items, SESSIONS, CLOSE)
    assert len(assigned) == 1
    return next(iter(assigned))


class TestAssignment:
    def test_saturday_goes_to_next_monday(self):
        assert _target([_news(date(2025, 3, 15))]) == date(2025, 3, 17)

    def test_sunday_goes_to_next_monday(self):
        assert _target([_news(date(2025, 3, 16), time(10, 0))]) == date(2025, 3, 17)

    def test_holiday_goes_to_next_session(self):
        assert _target([_news(date(2025, 3, 19), time(10, 0))]) == date(2025, 3, 20)

    def test_before_close_stays_on_the_same_day(self):
        assert _target([_news(date(2025, 3, 14), time(16, 59))]) == date(2025, 3, 14)

    def test_exactly_at_close_stays_on_the_same_day(self):
        assert _target([_news(date(2025, 3, 14), time(17, 0))]) == date(2025, 3, 14)

    def test_after_close_goes_to_next_session(self):
        assert _target([_news(date(2025, 3, 14), time(17, 1))]) == date(2025, 3, 17)

    def test_after_close_before_holiday_skips_it(self):
        assert _target([_news(date(2025, 3, 18), time(18, 30))]) == date(2025, 3, 20)

    def test_without_time_on_business_day_stays_on_the_same_day(self):
        assert _target([_news(date(2025, 3, 18))]) == date(2025, 3, 18)

    def test_before_first_session_goes_to_first_session(self):
        assert _target([_news(date(2025, 3, 5), time(9, 0))]) == date(2025, 3, 13)

    def test_weekend_before_first_session_goes_to_first_session(self):
        assert _target([_news(date(2025, 3, 8))]) == date(2025, 3, 13)

    def test_after_last_session_is_discarded(self):
        assigned, audit = align_news_with_audit(
            [_news(date(2025, 3, 20), time(18, 0))], SESSIONS, CLOSE
        )

        assert assigned == {}
        assert audit["discarded_after_last_session"] == 1
        assert audit["assigned"] == 0

    def test_weekend_after_last_session_is_discarded(self):
        assigned, audit = align_news_with_audit([_news(date(2025, 3, 22))], SESSIONS, CLOSE)

        assert assigned == {}
        assert audit["discarded_after_last_session"] == 1

    def test_empty_calendar_discards_everything(self):
        assigned, audit = align_news_with_audit([_news(date(2025, 3, 14))], [], CLOSE)

        assert assigned == {}
        assert audit["total"] == 1 and audit["discarded_after_last_session"] == 1

    def test_groups_several_news_in_the_same_session(self):
        items = [
            _news(date(2025, 3, 15), url="a"),                 # sábado -> 17
            _news(date(2025, 3, 14), time(18, 0), url="b"),    # após fechamento -> 17
            _news(date(2025, 3, 17), time(9, 0), url="c"),     # mesmo dia
        ]

        assigned = align_news_to_sessions(items, SESSIONS, CLOSE)

        assert [n.url for n in assigned[date(2025, 3, 17)]] == ["a", "b", "c"]


class TestAudit:
    def test_counters(self):
        items = [
            _news(date(2025, 3, 5), url="antes"),                       # antes do 1º pregão
            _news(date(2025, 3, 13), time(10, 0), url="mesmo-dia"),
            _news(date(2025, 3, 14), time(17, 30), url="apos-fechamento"),
            _news(date(2025, 3, 15), url="fim-de-semana"),
            _news(date(2025, 3, 19), time(11, 0), url="feriado"),
            _news(date(2025, 3, 18), url="sem-horario-util"),
            _news(date(2025, 3, 22), url="depois-do-fim"),
        ]

        _, audit = align_news_with_audit(items, SESSIONS, CLOSE)

        assert audit["total"] == 7
        assert audit["assigned"] == 6
        assert audit["same_day"] == 2
        assert audit["moved_weekend_holiday"] == 2
        assert audit["moved_after_close"] == 1
        assert audit["before_first_session"] == 1
        assert audit["discarded_after_last_session"] == 1
        assert audit["without_time"] == 4

    def test_every_news_falls_in_exactly_one_bucket(self):
        items = [_news(date(2025, 3, d), time(h, 0)) for d in range(10, 25) for h in (9, 18)]

        _, audit = align_news_with_audit(items, SESSIONS, CLOSE)

        buckets = (
            audit["same_day"] + audit["moved_weekend_holiday"] + audit["moved_after_close"]
            + audit["before_first_session"] + audit["discarded_after_last_session"]
        )
        assert buckets == audit["total"] == len(items)


class TestCalendar:
    def test_session_calendar_is_sorted_distinct_dates(self):
        def price(day):
            return StockPrice("BBAS3.SA", day, 10.0, 10.0, 10.0, 10.0, 1)

        prices = [
            price(datetime(2025, 3, 17)),
            price(datetime(2025, 3, 14)),
            price(datetime(2025, 3, 14)),
        ]

        assert session_calendar(prices) == [date(2025, 3, 14), date(2025, 3, 17)]

    def test_timezone_aware_timestamps_use_the_local_calendar_date(self):
        from datetime import timedelta, timezone

        sao_paulo = timezone(timedelta(hours=-3))
        stamp = datetime(2025, 3, 14, 0, 0, tzinfo=sao_paulo)

        assert session_calendar(
            [StockPrice("BBAS3.SA", stamp, 10.0, 10.0, 10.0, 10.0, 1)]
        ) == [date(2025, 3, 14)]


class TestCloseTime:
    def test_parses_hh_mm(self):
        assert parse_close_time("17:00") == time(17, 0)
        assert parse_close_time("18:30") == time(18, 30)

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError, match="MARKET_CLOSE_TIME"):
            parse_close_time("5pm")

    def test_custom_cutoff_is_honoured(self):
        assigned = align_news_to_sessions(
            [_news(date(2025, 3, 14), time(17, 30))], SESSIONS, time(18, 0)
        )

        assert list(assigned) == [date(2025, 3, 14)]
