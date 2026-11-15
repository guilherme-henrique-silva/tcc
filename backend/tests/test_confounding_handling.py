"""Testes dos controles e do dataset de análise (RF-08): sem mocks, sem filtro por p-valor."""

from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from backend.src.domain.models import StockPrice
from backend.src.domain.services import confounding_handler_service as module
from backend.src.domain.services.confounding_handler_service import (
    ConfoundingHandlerService,
    parse_dates,
)
from backend.src.domain.services.feature_engineering_service import FeatureEngineeringService
from backend.src.domain.value_objects import TickerSymbol
from backend.src.pipeline.stages import ConfoundingHandlerStage

SESSIONS = [
    date(2025, 3, 3), date(2025, 3, 4), date(2025, 3, 5),
    date(2025, 3, 6), date(2025, 3, 7), date(2025, 3, 10),
]


class _FakeBcb:
    """BCB falso: vários boletins por dia, alguns pregões sem PTAX."""

    def __init__(self, rows):
        self._rows = rows
        self.requested = None

    def dolar_dataframe(self, date_range):
        self.requested = date_range
        return pd.DataFrame(
            self._rows, columns=["date", "usd_brl_compra", "usd_brl_venda"]
        )


def _price(ticker, day, close):
    return StockPrice(
        ticker, datetime(day.year, day.month, day.day), close, close, close, close, 1
    )


def _service(rows=None, copom=()):
    return ConfoundingHandlerService(_FakeBcb(rows or []), list(copom))


class TestUsdBrl:
    def test_log_difference_with_forward_fill_on_missing_sessions(self):
        rows = [
            (SESSIONS[0], 5.0, 5.00),
            (SESSIONS[1], 5.0, 5.10),
            # 05/03 sem PTAX: repete 5.10
            (SESSIONS[3], 5.0, 5.20),
            (SESSIONS[4], 5.0, 5.20),
            (SESSIONS[5], 5.0, 5.00),
        ]

        series = _service(rows).usd_brl_control(SESSIONS)

        assert np.isnan(series.iloc[0])
        assert series.loc[SESSIONS[1]] == pytest.approx(np.log(5.10 / 5.00))
        assert series.loc[SESSIONS[2]] == pytest.approx(0.0)  # ffill antes da diferença
        assert series.loc[SESSIONS[3]] == pytest.approx(np.log(5.20 / 5.10))
        assert series.loc[SESSIONS[5]] == pytest.approx(np.log(5.00 / 5.20))

    def test_last_bulletin_of_the_day_wins(self):
        rows = [
            (SESSIONS[0], 5.0, 5.00), (SESSIONS[0], 5.0, 5.05),  # abertura, fechamento
            (SESSIONS[1], 5.0, 5.10), (SESSIONS[1], 5.0, 5.15),
        ]

        series = _service(rows).usd_brl_control(SESSIONS[:2])

        assert series.loc[SESSIONS[1]] == pytest.approx(np.log(5.15 / 5.05))

    def test_requests_exactly_the_session_span(self):
        bcb = _FakeBcb([(SESSIONS[0], 5.0, 5.0), (SESSIONS[-1], 5.0, 5.0)])

        ConfoundingHandlerService(bcb, []).usd_brl_control(SESSIONS)

        assert (bcb.requested.start_date, bcb.requested.end_date) == (SESSIONS[0], SESSIONS[-1])

    def test_empty_api_answer_raises(self):
        with pytest.raises(ValueError, match="PTAX"):
            _service([]).usd_brl_control(SESSIONS)


class TestCopom:
    def test_flag_goes_to_first_session_strictly_after_the_decision(self):
        # Decisão na quarta 05/03: comunicado após o fechamento -> quinta 06/03.
        flags = _service(copom=["2025-03-05"]).copom_indicator(SESSIONS)

        assert flags.loc[date(2025, 3, 5)] == 0
        assert flags.loc[date(2025, 3, 6)] == 1
        assert flags.sum() == 1

    def test_decision_on_weekend_goes_to_next_session(self):
        flags = _service(copom=["2025-03-08"]).copom_indicator(SESSIONS)

        assert flags.loc[date(2025, 3, 10)] == 1

    def test_decision_after_the_last_session_is_ignored(self):
        flags = _service(copom=["2025-03-10", "2025-12-10"]).copom_indicator(SESSIONS)

        assert flags.sum() == 0

    def test_sum_equals_decisions_with_a_later_session(self):
        decisions = ["2025-03-04", "2025-03-06", "2025-03-10", "2025-06-18"]

        flags = _service(copom=decisions).copom_indicator(SESSIONS)

        assert flags.sum() == 2  # 04/03 -> 05/03 e 06/03 -> 07/03; 10/03 e jun/18 não têm pregão depois

    def test_no_decisions_give_all_zeros(self):
        assert _service().copom_indicator(SESSIONS).sum() == 0

    def test_invalid_decision_date_raises(self):
        with pytest.raises(ValueError, match="COPOM_DECISION_DATES"):
            parse_dates(["29/01/2025"])


class TestCommodities:
    def test_mean_of_log_returns_with_forward_fill(self):
        soy = [_price("ZS=F", d, p) for d, p in zip(SESSIONS, [10, 11, 12, 13, 14, 15])]
        # Milho: sem preço na quarta 05/03 (bolsa americana fechada).
        corn = [_price("ZC=F", d, p) for d, p in zip(
            [SESSIONS[0], SESSIONS[1], SESSIONS[3], SESSIONS[4], SESSIONS[5]], [20, 22, 22, 24, 24]
        )]

        series = _service().commodity_control({"ZS=F": soy, "ZC=F": corn}, SESSIONS)

        corn_03_05 = 0.0                                  # preço repetido
        assert series.loc[SESSIONS[2]] == pytest.approx((np.log(12 / 11) + corn_03_05) / 2)

    def test_no_commodities_return_none(self):
        assert _service().commodity_control({}, SESSIONS) is None
        assert _service().commodity_control({"ZS=F": []}, SESSIONS) is None


def _target_frame(sessions):
    rng = np.random.default_rng(3)
    closes = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, len(sessions))))
    prices = [_price("BBAS3.SA", d, c) for d, c in zip(sessions, closes)]
    return FeatureEngineeringService().calculate_stock_features(TickerSymbol("BBAS3.SA"), prices)


def _news_frame(sessions):
    return pd.DataFrame({
        "date": sessions,
        "n_news": [0, 2, 0, 1, 0, 3][: len(sessions)],
        "n_pos": [0, 1, 0, 1, 0, 1][: len(sessions)],
        "n_neg": [0, 1, 0, 0, 0, 2][: len(sessions)],
        "n_neu": [0] * len(sessions),
        "sent_net": [0.0, 0.0, 0.0, 1.0, 0.0, -1 / 3][: len(sessions)],
        "has_news": [0, 1, 0, 1, 0, 1][: len(sessions)],
    })


class TestAnalysisDataset:
    def _controls(self):
        index = pd.Index(SESSIONS, name="date")
        return {
            "ret_ibov": pd.Series([np.nan, .01, -.01, .02, 0.0, .01], index=index),
            "ret_peers": pd.Series([np.nan, .0, .01, -.01, .02, .0], index=index),
            "d_usdbrl": pd.Series([np.nan, .0, .01, .0, -.01, .0], index=index),
            "ret_commod": pd.Series([np.nan, .0, .0, .01, .0, .0], index=index),
            "copom": pd.Series([0, 0, 0, 1, 0, 0], index=index),
        }

    def test_one_row_per_session_minus_one_without_nan(self):
        dataset, warnings = _service().build_analysis_dataset(
            _target_frame(SESSIONS), _news_frame(SESSIONS), self._controls()
        )

        assert len(dataset) == len(SESSIONS) - 1
        assert dataset["date"].tolist() == SESSIONS[1:]
        required = ["log_return", "n_news", "n_pos", "n_neg", "sent_net", "has_news",
                    "ret_ibov", "ret_peers", "d_usdbrl", "ret_commod", "copom"]
        assert not dataset[required].isna().any().any()
        assert warnings == []

    def test_contract_columns_are_present(self):
        dataset, _ = _service().build_analysis_dataset(
            _target_frame(SESSIONS), _news_frame(SESSIONS), self._controls()
        )

        for column in ("date", "log_return", "abs_return", "n_news", "n_pos", "n_neg", "n_neu",
                       "sent_net", "has_news", "ret_ibov", "ret_peers", "d_usdbrl",
                       "ret_commod", "copom", "volatility_20d", "volume_normalized",
                       "anomaly_flag"):
            assert column in dataset.columns

    def test_missing_news_rows_are_filled_with_zero(self):
        dataset, _ = _service().build_analysis_dataset(
            _target_frame(SESSIONS), pd.DataFrame(), self._controls()
        )

        assert (dataset["n_news"] == 0).all() and (dataset["sent_net"] == 0).all()
        assert (dataset["has_news"] == 0).all()

    def test_incomplete_sessions_are_dropped_with_a_warning(self):
        controls = self._controls()
        controls["d_usdbrl"].iloc[3] = np.nan

        dataset, warnings = _service().build_analysis_dataset(
            _target_frame(SESSIONS), _news_frame(SESSIONS), controls
        )

        assert len(dataset) == len(SESSIONS) - 2
        assert any("removido" in w for w in warnings)

    def test_copom_total_matches_decisions_inside_the_period(self):
        service = _service(copom=["2025-03-05", "2025-03-07", "2025-04-30"])
        controls = self._controls()
        controls["copom"] = service.copom_indicator(SESSIONS)

        dataset, _ = service.build_analysis_dataset(
            _target_frame(SESSIONS), _news_frame(SESSIONS), controls
        )

        assert dataset["copom"].sum() == 2


class TestNoMocksRemain:
    def test_module_has_no_mock_generators_or_granger_leftovers(self):
        for name in ("_load_commodity_data", "_generate_mock_commodity_values",
                     "_generate_business_days", "apply_granger_test",
                     "_compute_granger_statistic", "_f_statistic_to_p_value",
                     "GrangerTestResult"):
            assert not hasattr(module, name) and not hasattr(ConfoundingHandlerService, name)

    def test_building_the_dataset_never_calls_numpy_random(self, monkeypatch):
        def boom(*args, **kwargs):
            raise AssertionError("np.random não deve ser usado")

        for name in ("uniform", "normal", "rand", "randn", "random"):
            monkeypatch.setattr(np.random, name, boom)

        service = _service([(d, 5.0, 5.0 + i * 0.01) for i, d in enumerate(SESSIONS)])
        service.usd_brl_control(SESSIONS)
        service.commodity_control({"ZS=F": [_price("ZS=F", d, 10.0 + i) for i, d in enumerate(SESSIONS)]}, SESSIONS)


class TestStage:
    def _input(self):
        target = _target_frame(SESSIONS)
        return {
            "sessions": SESSIONS,
            "target_ticker": "BBAS3.SA",
            "stock_features": {"BBAS3.SA": target.to_dict(orient="records")},
            "news_features": _news_frame(SESSIONS).to_dict(orient="records"),
            "index_returns": [{"date": d, "ret_ibov": 0.001 * i} for i, d in enumerate(SESSIONS)],
            "peer_returns": [{"date": d, "ret_peers": 0.002 * i} for i, d in enumerate(SESSIONS)],
            "commodity_prices": {
                "ZS=F": [_price("ZS=F", d, 10.0 + i) for i, d in enumerate(SESSIONS)]
            },
        }

    def _stage(self, rows=None):
        rows = rows if rows is not None else [
            (d, 5.0, 5.0 + 0.01 * i) for i, d in enumerate(SESSIONS)
        ]
        return ConfoundingHandlerStage(_FakeBcb(rows), ["2025-03-05"])

    def test_outputs_analysis_dataset_and_control_variables(self):
        tags = []

        result = self._stage().execute(self._input(), on_substage=tags.append)

        assert result.status == "SUCCESS"
        assert [t.substage_name for t in tags] == [
            "coletar_dolar", "indicador_copom", "montar_dataset"
        ]
        dataset = result.data["analysis_dataset"]
        assert len(dataset) == len(SESSIONS) - 1
        assert dataset[0]["date"] == "2025-03-04"            # ISO: serializável
        assert sum(row["copom"] for row in dataset) == 1
        assert result.data["control_variables"]
        assert result.data["analysis_warnings"] == []

    def test_selic_level_is_not_part_of_the_dataset(self):
        result = self._stage().execute(self._input())

        assert "selic" not in result.data["analysis_dataset"][0]
        assert "usd_brl" not in result.data["analysis_dataset"][0]

    def test_ptax_failure_degrades_with_warning_instead_of_failing(self):
        stage = self._stage(rows=[])

        result = stage.execute(self._input())

        assert result.status == "SUCCESS"
        assert "d_usdbrl" not in result.data["analysis_dataset"][0]
        assert any("d_usdbrl" in w for w in result.data["analysis_warnings"])

    def test_missing_commodities_are_removed_with_warning(self):
        data = self._input()
        data["commodity_prices"] = {}

        result = self._stage().execute(data)

        assert "ret_commod" not in result.data["analysis_dataset"][0]
        assert any("ret_commod" in w for w in result.data["analysis_warnings"])

    def test_fails_clearly_without_feature_engineering_output(self):
        result = self._stage().execute({})

        assert result.status == "FAILED"
        assert "feature_engineering" in result.error_message
