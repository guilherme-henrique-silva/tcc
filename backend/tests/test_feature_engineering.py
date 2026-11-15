"""Testes do FeatureEngineeringService e do utilitário de log-retornos (RF-05, RF-06, RF-07)."""

from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from backend.src.domain.models import News, StockPrice
from backend.src.domain.services.feature_engineering_service import (
    FeatureEngineeringService,
    log_returns,
    log_returns_on_sessions,
    peer_column,
)
from backend.src.domain.value_objects import SentimentScore, TickerSymbol

BBAS = "BBAS3.SA"
START = date(2025, 3, 3)  # segunda


def _price(ticker, day, close, volume=100):
    return StockPrice(
        ticker, datetime(day.year, day.month, day.day), close, close, close, close, volume
    )


def _series(ticker, closes, volumes=None, start=START):
    """Preços em dias úteis consecutivos a partir de ``start``."""
    days, cursor = [], start
    while len(days) < len(closes):
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor += timedelta(days=1)

    volumes = volumes or [100] * len(closes)
    return [_price(ticker, d, c, v) for d, c, v in zip(days, closes, volumes)]


def _news(day, score=None, url="u"):
    item = News(
        title="t", content="c", source="s",
        published_date=datetime(day.year, day.month, day.day), url=url,
    )
    if score is not None:
        item.set_sentiment(SentimentScore(score))
    return item


SERVICE = FeatureEngineeringService()


class TestLogReturns:
    def test_log_return_matches_hand_calculation(self):
        prices = _series(BBAS, [100.0, 110.0, 99.0])

        series = log_returns(prices)

        assert np.isnan(series.iloc[0])
        assert series.iloc[1] == pytest.approx(np.log(1.10))
        assert series.iloc[2] == pytest.approx(np.log(0.90))

    def test_series_is_indexed_by_session_date(self):
        series = log_returns(_series(BBAS, [10.0, 11.0]))

        assert list(series.index) == [date(2025, 3, 3), date(2025, 3, 4)]

    def test_empty_prices_give_empty_series(self):
        assert log_returns([]).empty

    def test_stock_features_log_abs_and_pct(self):
        features = SERVICE.calculate_stock_features(
            TickerSymbol(BBAS), _series(BBAS, [100.0, 110.0, 99.0])
        )

        assert features["log_return"].iloc[1] == pytest.approx(np.log(1.1))
        assert features["abs_return"].iloc[2] == pytest.approx(abs(np.log(0.9)))
        assert features["daily_return_pct"].iloc[1] == pytest.approx(10.0)
        assert list(features["date"]) == [date(2025, 3, 3), date(2025, 3, 4), date(2025, 3, 5)]

    def test_empty_prices_give_empty_frame(self):
        assert SERVICE.calculate_stock_features(TickerSymbol(BBAS), []).empty

    def test_on_sessions_repeats_price_when_foreign_exchange_is_closed(self):
        sessions = [date(2025, 3, 3), date(2025, 3, 4), date(2025, 3, 5)]
        foreign = [_price("ZS=F", sessions[0], 10.0), _price("ZS=F", sessions[2], 12.0)]

        series = log_returns_on_sessions(foreign, sessions)

        assert series.loc[sessions[1]] == pytest.approx(0.0)     # fechado: preço repetido
        assert series.loc[sessions[2]] == pytest.approx(np.log(1.2))


class TestVolumeNormalizationHasNoLookAhead:
    def test_value_at_t_does_not_change_when_future_data_is_added(self):
        closes = [10.0 + i for i in range(30)]
        volumes = [100, 300, 200, 900, 50, 400] * 5
        short = _series(BBAS, closes[:20], volumes[:20])
        full = _series(BBAS, closes, volumes)

        before = SERVICE.calculate_stock_features(TickerSymbol(BBAS), short)
        after = SERVICE.calculate_stock_features(TickerSymbol(BBAS), full)

        np.testing.assert_allclose(
            before["volume_normalized"].values, after["volume_normalized"].values[:20]
        )

    def test_uses_expanding_min_max(self):
        features = SERVICE.calculate_stock_features(
            TickerSymbol(BBAS), _series(BBAS, [10.0] * 4, [100, 200, 50, 400])
        )

        # t=0: max==min -> 0,5 | t=1: (200-100)/(200-100)=1 | t=2: (50-50)/(200-50)=0 | t=3: 1
        np.testing.assert_allclose(features["volume_normalized"].values, [0.5, 1.0, 0.0, 1.0])

    def test_constant_volume_is_half(self):
        features = SERVICE.calculate_stock_features(
            TickerSymbol(BBAS), _series(BBAS, [10.0, 11.0, 12.0], [100, 100, 100])
        )

        assert (features["volume_normalized"] == 0.5).all()


class TestAnomalyFlag:
    def test_uses_absolute_deviation_from_the_mean(self):
        closes = [100.0]
        for ret in [0.001] * 30 + [-0.2] + [0.001] * 10:
            closes.append(closes[-1] * np.exp(ret))

        features = SERVICE.calculate_stock_features(TickerSymbol(BBAS), _series(BBAS, closes))

        lr = features["log_return"]
        expected = (lr - lr.mean()).abs() > 2.0 * lr.std()
        assert features["anomaly_flag"].tolist() == expected.tolist()
        assert features["anomaly_flag"].sum() == 1
        assert bool(features["anomaly_flag"].iloc[31]) is True

    def test_negative_outlier_is_flagged_even_with_negative_mean(self):
        """Regressão: a fórmula antiga |r| − |μ| tratava mal desvios com média ≠ 0."""
        closes = [100.0]
        for ret in [-0.01] * 30 + [0.15]:
            closes.append(closes[-1] * np.exp(ret))

        features = SERVICE.calculate_stock_features(TickerSymbol(BBAS), _series(BBAS, closes))

        assert bool(features["anomaly_flag"].iloc[-1]) is True
        assert features["anomaly_flag"].iloc[1:-1].sum() == 0


class TestNewsFeatures:
    SESSIONS = [START + timedelta(days=i) for i in range(5)]

    def test_one_row_per_session_even_without_news(self):
        by_session = {
            self.SESSIONS[1]: [_news(self.SESSIONS[1], 1), _news(self.SESSIONS[1], -1)],
            self.SESSIONS[3]: [_news(self.SESSIONS[3], 1)],
        }

        frame = SERVICE.calculate_news_features(by_session, self.SESSIONS)

        assert len(frame) == 5
        assert list(frame["date"]) == self.SESSIONS

    def test_sent_net_and_presence(self):
        by_session = {
            self.SESSIONS[1]: [
                _news(self.SESSIONS[1], 1), _news(self.SESSIONS[1], 1),
                _news(self.SESSIONS[1], -1), _news(self.SESSIONS[1], 0),
            ],
            self.SESSIONS[3]: [_news(self.SESSIONS[3], -1)],
        }

        frame = SERVICE.calculate_news_features(by_session, self.SESSIONS)

        assert frame["n_news"].tolist() == [0, 4, 0, 1, 0]
        assert frame["n_pos"].tolist() == [0, 2, 0, 0, 0]
        assert frame["n_neg"].tolist() == [0, 1, 0, 1, 0]
        assert frame["n_neu"].tolist() == [0, 1, 0, 0, 0]
        assert frame["has_news"].tolist() == [0, 1, 0, 1, 0]
        assert frame["sent_net"].tolist() == pytest.approx([0.0, 0.25, 0.0, -1.0, 0.0])

    def test_session_without_news_has_zero_sentiment_not_nan(self):
        frame = SERVICE.calculate_news_features({}, self.SESSIONS)

        assert (frame["sent_net"] == 0.0).all()
        assert not frame.isna().any().any()

    def test_unscored_news_counts_in_volume_only(self):
        day = self.SESSIONS[0]
        by_session = {day: [_news(day, 1), _news(day, None)]}

        frame = SERVICE.calculate_news_features(by_session, [day])

        assert frame.loc[0, "n_news"] == 2
        assert frame.loc[0, "n_pos"] == 1 and frame.loc[0, "n_neg"] == 0
        assert frame.loc[0, "sent_net"] == pytest.approx(0.5)  # (1-0)/2
        assert SERVICE.count_unscored(by_session) == 1

    def test_five_sessions_with_news_in_two(self):
        by_session = {self.SESSIONS[0]: [_news(self.SESSIONS[0], 1)],
                      self.SESSIONS[4]: [_news(self.SESSIONS[4], -1)]}

        assert len(SERVICE.calculate_news_features(by_session, self.SESSIONS)) == 5


class TestCompetitors:
    def _prices(self):
        n = 30
        rng = np.random.default_rng(5)
        data = {BBAS: _series(BBAS, list(100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))))}
        for ticker in ("ITUB4.SA", "BBDC4.SA", "SANB11.SA"):
            data[ticker] = _series(ticker, list(50 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))))
        return data

    def test_three_competitors_give_three_rows_without_error(self):
        prices = self._prices()
        tickers = [TickerSymbol(t) for t in prices]

        frame = SERVICE.calculate_competitor_features(tickers, prices, BBAS)

        assert frame["ticker"].tolist() == ["ITUB4.SA", "BBDC4.SA", "SANB11.SA"]
        assert len(frame["correlation_with_bbas3"]) == 3
        assert frame["sync_score"].between(0, 1).all()

    def test_correlation_is_aligned_by_date_not_by_position(self):
        base = _series(BBAS, [100, 101, 103, 102, 105, 107, 106, 108, 111, 110])
        # O concorrente começa 2 pregões depois: por posição o par ficaria desalinhado.
        rival = _series("ITUB4.SA", [x * 2 for x in [103, 102, 105, 107, 106, 108, 111, 110]],
                        start=base[2].date)
        prices = {BBAS: base, "ITUB4.SA": rival}

        frame = SERVICE.calculate_competitor_features(
            [TickerSymbol(BBAS), TickerSymbol("ITUB4.SA")], prices, BBAS
        )

        assert frame["correlation_with_bbas3"].iloc[0] == pytest.approx(1.0)

    def test_ret_peers_is_the_mean_of_the_three_series(self):
        prices = self._prices()
        sessions = [p.date.date() for p in prices[BBAS]]

        frame = SERVICE.calculate_peer_returns(prices, BBAS, sessions)

        individual = pd.DataFrame({
            t: log_returns_on_sessions(prices[t], sessions)
            for t in ("ITUB4.SA", "BBDC4.SA", "SANB11.SA")
        })
        np.testing.assert_allclose(
            frame["ret_peers"].values[1:], individual.mean(axis=1).values[1:]
        )
        assert list(frame.columns) == ["date", "ret_peers"]

    def test_separate_aggregation_keeps_one_column_per_peer(self):
        prices = self._prices()
        sessions = [p.date.date() for p in prices[BBAS]]

        frame = SERVICE.calculate_peer_returns(prices, BBAS, sessions, "separate")

        assert list(frame.columns) == ["date", "ret_itub4", "ret_bbdc4", "ret_sanb11"]
        assert peer_column("SANB11.SA") == "ret_sanb11"

    def test_target_is_excluded_and_empty_peers_are_ignored(self):
        prices = self._prices()
        prices["ITUB4.SA"] = []
        sessions = [p.date.date() for p in prices[BBAS]]

        frame = SERVICE.calculate_peer_returns(prices, BBAS, sessions, "separate")

        assert "ret_itub4" not in frame.columns and "ret_bbas3" not in frame.columns

    def test_no_peers_give_empty_frame(self):
        prices = {BBAS: _series(BBAS, [10.0, 11.0])}

        assert SERVICE.calculate_peer_returns(prices, BBAS, [START]).empty
