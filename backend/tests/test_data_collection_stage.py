"""Testes de RF-02/RF-03: horário na News, tickers e coleta de índice/commodities."""

from datetime import date, datetime, time, timedelta

import pytest

from backend.src.adapters.data_sources.yfinance_adapter import YFinanceAdapter
from backend.src.domain.models import StockPrice
from backend.src.domain.value_objects import DateRange, TickerSymbol
from backend.src.pipeline.stages import DataCollectionStage


class TestTickerSymbol:
    @pytest.mark.parametrize(
        "value", ["BBAS3.SA", "ITUB4.SA", "SANB11.SA", "^BVSP", "ZS=F", "ZC=F", "LE=F"]
    )
    def test_accepts_stocks_index_and_futures(self, value):
        assert str(TickerSymbol(value)) == value

    @pytest.mark.parametrize("value", ["zs=f", "bbas3.sa", "^bvsp"])
    def test_rejects_lowercase(self, value):
        with pytest.raises(ValueError, match="uppercase"):
            TickerSymbol(value)

    @pytest.mark.parametrize("value", ["", "BBAS3.SAAA", "ZS=X", "BB AS3", "^^BVSP", "ZS=F=F"])
    def test_rejects_malformed(self, value):
        with pytest.raises(ValueError):
            TickerSymbol(value)


class _RecordingSource:
    """DataSource falso: guarda as chamadas e devolve 3 pregões para os tickers 'cheios'."""

    def __init__(self, empty=()):
        self.calls = []
        self.empty = set(empty)

    def get_stock_prices(self, ticker, date_range):
        self.calls.append(str(ticker))
        if str(ticker) in self.empty:
            return []

        return [
            StockPrice(ticker, datetime(2025, 3, d), 10.0 + d, 10.0 + d, 10.0 + d, 10.0 + d, 100)
            for d in (3, 4, 5)
        ]


def _stage(source, **kwargs):
    return DataCollectionStage(
        source,
        ["BBAS3.SA", "ITUB4.SA", "BBDC4.SA", "SANB11.SA"],
        target_ticker="BBAS3.SA",
        index_ticker="^BVSP",
        commodity_tickers=["ZS=F", "ZC=F", "LE=F"],
        **kwargs,
    )


def _input():
    return {"date_range": {"start_date": date(2025, 3, 1), "end_date": date(2025, 3, 31)}}


class TestCollection:
    def test_collects_the_three_groups_in_order(self):
        source = _RecordingSource()
        tags = []

        result = _stage(source).execute(_input(), on_substage=tags.append)

        assert result.status == "SUCCESS"
        assert [t.substage_name for t in tags] == [
            "coletar_precos", "coletar_indice", "coletar_commodities", "consolidar_noticias",
        ]
        assert source.calls == [
            "BBAS3.SA", "ITUB4.SA", "BBDC4.SA", "SANB11.SA", "^BVSP", "ZS=F", "ZC=F", "LE=F",
        ]
        assert set(result.data["stock_prices"]) == {
            "BBAS3.SA", "ITUB4.SA", "BBDC4.SA", "SANB11.SA"
        }
        assert len(result.data["index_prices"]) == 3
        assert set(result.data["commodity_prices"]) == {"ZS=F", "ZC=F", "LE=F"}

    @pytest.mark.parametrize("missing", ["BBAS3.SA", "^BVSP"])
    def test_empty_target_or_index_fails_the_stage(self, missing):
        result = _stage(_RecordingSource(empty=[missing])).execute(_input())

        assert result.status == "FAILED"
        assert missing in result.error_message

    def test_empty_commodity_is_dropped_with_a_warning(self, caplog):
        with caplog.at_level("WARNING"):
            result = _stage(_RecordingSource(empty=["LE=F"])).execute(_input())

        assert result.status == "SUCCESS"
        assert set(result.data["commodity_prices"]) == {"ZS=F", "ZC=F"}
        assert any("LE=F" in r.getMessage() for r in caplog.records)

    def test_empty_competitor_only_warns(self, caplog):
        with caplog.at_level("WARNING"):
            result = _stage(_RecordingSource(empty=["ITUB4.SA"])).execute(_input())

        assert result.status == "SUCCESS"
        assert result.data["stock_prices"]["ITUB4.SA"] == []
        assert any("ITUB4.SA" in r.getMessage() for r in caplog.records)

    def test_all_commodities_empty_still_succeeds(self):
        result = _stage(_RecordingSource(empty=["ZS=F", "ZC=F", "LE=F"])).execute(_input())

        assert result.status == "SUCCESS"
        assert result.data["commodity_prices"] == {}


class TestYFinanceEndIsExclusive:
    def test_adapter_asks_for_end_date_plus_one_day_with_adjusted_prices(self):
        captured = {}

        class _Ticker:
            def history(self, **kwargs):
                captured.update(kwargs)
                import pandas as pd

                return pd.DataFrame()

        YFinanceAdapter()._fetch_history(_Ticker(), date(2025, 1, 1), date(2025, 12, 31))

        assert captured["start"] == date(2025, 1, 1)
        assert captured["end"] == date(2025, 12, 31) + timedelta(days=1)
        assert captured["auto_adjust"] is True


def _markdown(date_line=""):
    lines = ["---", "title: Título", "subtitle: Sub", "url: https://g1/x"]
    if date_line:
        lines.append(f"date: {date_line}")
    lines += ["---", "Corpo da notícia."]
    return "\n".join(lines)


class TestPublishedTime:
    def _collect(self, **entry_extra):
        entry = {
            "url": "https://g1/x", "site": "G1", "markdown": _markdown(),
            "success": True, "news_date": "2025-03-14", **entry_extra,
        }
        data = {**_input(), "news_markdowns": [entry]}
        result = _stage(_RecordingSource()).execute(data)
        assert result.status == "SUCCESS"
        return result.data["news_items"]

    def test_news_time_fills_published_time(self):
        (news,) = self._collect(news_time="18:42")

        assert news.published_time == time(18, 42)
        assert news.published_date == datetime(2025, 3, 14)  # data à meia-noite

    def test_missing_time_is_none(self):
        (news,) = self._collect()

        assert news.published_time is None

    def test_explicit_none_time_is_none(self):
        (news,) = self._collect(news_time=None)

        assert news.published_time is None

    def test_invalid_time_is_ignored(self):
        (news,) = self._collect(news_time="tarde")

        assert news.published_time is None
