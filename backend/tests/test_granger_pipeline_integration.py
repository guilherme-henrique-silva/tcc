"""Pipeline completa (7 etapas) com fontes falsas, offline: do JSON de links ao relatório de Granger."""

import json
import zlib
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from backend.app.core.config import Config
from backend.src.adapters.storage import SQLiteStorage
from backend.src.domain.models import StockPrice, TreatedNewsRecord
from backend.src.domain.value_objects import SentimentScore
from backend.src.pipeline import DataPipeline, DependencyContainer, StageName

PERIOD = (date(2025, 1, 1), date(2025, 12, 31))
HOLIDAYS = {date(2025, 1, 1), date(2025, 3, 3), date(2025, 3, 4), date(2025, 4, 18),
            date(2025, 4, 21), date(2025, 5, 1), date(2025, 9, 7), date(2025, 11, 20),
            date(2025, 12, 25)}

STAGES = [
    "docling_transform", "news_treatment", "data_collection", "feature_engineering",
    "confounding_handling", "granger_causality", "modeling_preparation",
]


class _FakeSource:
    """yfinance falso: passeio aleatório por ticker, só em dias úteis fora de feriados B3."""

    def __init__(self, empty=()):
        self.empty = set(empty)
        self.calls = []

    def get_stock_prices(self, ticker, date_range):
        name = str(ticker)
        self.calls.append(name)
        if name in self.empty:
            return []

        rng = np.random.default_rng(zlib.crc32(name.encode()))
        us_only = name.endswith("=F")
        day, price, prices = date_range.start_date, 100.0, []
        while day <= date_range.end_date:
            closed = day.weekday() >= 5 or (day in HOLIDAYS and not us_only)
            if not closed:
                price *= float(np.exp(rng.normal(0, 0.01)))
                prices.append(StockPrice(
                    ticker, datetime(day.year, day.month, day.day),
                    price, price, price, price, int(rng.integers(1_000, 9_000)),
                ))
            day += timedelta(days=1)
        return prices

    def get_news(self, date_range):
        return []

    def get_macroeconomic_data(self, indicators, date_range):
        return []


class _FakeBcb:
    def dolar_dataframe(self, date_range):
        rng = np.random.default_rng(1)
        days = pd.bdate_range(date_range.start_date, date_range.end_date)
        ptax = 5.0 * np.exp(np.cumsum(rng.normal(0, 0.004, len(days))))
        return pd.DataFrame({
            "date": [d.date() for d in days],
            "usd_brl_compra": ptax, "usd_brl_venda": ptax * 1.001,
        })


class _FakeConverter:
    def site_name(self, url):
        return "Portal"

    def to_markdown(self, url):
        return f"# {url}"


class _FakeSentiment:
    def analyze_sentiment(self, text):
        return SentimentScore([-1, 0, 1][zlib.crc32(text.encode()) % 3])


def _markdown(url, day):
    return (
        f"---\ntitle: Notícia {url[-6:]}\nsubtitle: Sub\nurl: {url}\n"
        f"date: {day.strftime('%d-%m-%Y')}\n---\nCorpo único da notícia {url}"
    )


def _news_links():
    """~1 notícia a cada 2 dias, com fins de semana, feriados e horários pós-fechamento."""
    links, day, index = {}, date(2025, 1, 2), 0
    while day <= date(2025, 12, 30):
        url = f"https://portal.example/{day.isoformat()}/n{index}"
        item = url if index % 3 else {"url": url, "time": "18:42" if index % 2 else "10:15"}
        links.setdefault(day.isoformat(), []).append(item)
        day += timedelta(days=2)
        index += 1
    return links


@pytest.fixture
def env(tmp_path):
    config = type("TestConfig", (Config,), {
        "DATA_DIR": str(tmp_path / "data"),
        "CHECKPOINT_DIR": str(tmp_path / "ckpt"),
        "DATABASE_URL": f"sqlite:///{(tmp_path / 'pipeline.db').as_posix()}",
        "COPOM_DECISION_DATES": ["2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18",
                                 "2025-07-30", "2025-09-17", "2025-11-05", "2025-12-10"],
    })
    storage = SQLiteStorage(config.DATABASE_URL)
    links = _news_links()

    for day_key, items in links.items():
        for item in items:
            url = item if isinstance(item, str) else item["url"]
            storage.save_treated_news(TreatedNewsRecord.from_treated_markdown(
                url, _markdown(url, date.fromisoformat(day_key))
            ))

    container = DependencyContainer(config)
    container._data_source_adapter = _FakeSource()
    container._storage_adapter = storage
    container._docling_converter = _FakeConverter()
    container._bcb_adapter = _FakeBcb()
    container._processors["sentiment"] = _FakeSentiment()

    pipeline = DataPipeline(config=config, checkpoint_manager=object(), dependency_container=container)
    return pipeline, storage, config, links, container


def _run(pipeline, links, **kwargs):
    return pipeline.execute(*PERIOD, news_links=links, **kwargs)


class TestFullPipeline:
    def test_runs_seven_stages_in_order_and_succeeds(self, env):
        pipeline, _, _, links, _ = env

        result = _run(pipeline, links)

        assert result.status == "SUCCESS", result.error_message or {
            n: r.error_message for n, r in result.stage_results.items()
        }
        assert result.stages_executed == STAGES
        assert all(r.status == "SUCCESS" for r in result.stage_results.values())

    def test_produces_a_valid_granger_report_with_the_four_tests(self, env):
        pipeline, _, _, links, _ = env

        result = _run(pipeline, links)
        report = result.stage_results["granger_causality"].data["granger_report"]

        main = [t for t in report["tests"] if t["model"] == "principal"]
        assert [t["test_id"] for t in main] == [
            "sent_to_ret", "news_to_ret", "ret_to_sent", "ret_to_news"
        ]
        assert all(t["status"] == "ok" for t in main)
        assert report["n_obs"] > 200
        assert set(report["variables"]) >= {"log_return", "sent_net", "n_news", "ret_ibov",
                                            "ret_peers", "d_usdbrl", "ret_commod"}
        assert report["exog"] == ["copom"]
        assert report["lag_selection"]["maxlags_effective"] <= 10
        assert report["alpha"] == 0.05 and report["multitest_method"] == "holm"
        json.dumps(report, allow_nan=False)  # estritamente serializável

    def test_alignment_audit_is_in_the_report(self, env):
        pipeline, _, _, links, _ = env

        report = _run(pipeline, links).stage_results["granger_causality"].data["granger_report"]
        audit = report["alignment_audit"]

        assert audit["total"] == sum(len(v) for v in links.values())
        assert audit["moved_after_close"] > 0           # horário 18:42
        assert audit["moved_weekend_holiday"] > 0       # sábados/domingos/feriados
        assert audit["without_time"] > 0
        assert audit["total"] == (
            audit["same_day"] + audit["moved_weekend_holiday"] + audit["moved_after_close"]
            + audit["before_first_session"] + audit["discarded_after_last_session"]
        )
        assert any("sem horário" in w for w in report["warnings"])

    def test_report_persisted_by_proc_id_and_files_exported(self, env):
        pipeline, storage, config, links, _ = env

        _run(pipeline, links)

        stored = storage.get_granger_results(pipeline.pipeline_id)
        assert stored is not None and stored["proc_id"] == pipeline.pipeline_id
        folder = f"{config.DATA_DIR}/granger"
        dataset = pd.read_csv(f"{folder}/analysis_dataset_{pipeline.pipeline_id}.csv")
        assert {"date", "log_return", "sent_net", "has_news", "copom"} <= set(dataset.columns)
        with open(f"{folder}/granger_report_{pipeline.pipeline_id}.json", encoding="utf-8") as fh:
            assert json.load(fh)["n_obs"] == stored["n_obs"]

    def test_dataset_has_one_row_per_session_minus_one_and_no_nan(self, env):
        pipeline, _, _, links, container = env

        _run(pipeline, links)
        target_sessions = {
            p.date.date() for p in container._data_source_adapter.get_stock_prices(
                type("T", (), {"__str__": lambda s: "BBAS3.SA"})(),
                type("R", (), {"start_date": PERIOD[0], "end_date": PERIOD[1]})(),
            )
        }
        dataset = pd.read_csv(
            f"{pipeline.config.DATA_DIR}/granger/analysis_dataset_{pipeline.pipeline_id}.csv"
        )

        assert len(dataset) == len(target_sessions) - 1
        assert not dataset[["log_return", "sent_net", "n_news", "ret_ibov", "ret_peers",
                            "d_usdbrl", "ret_commod", "copom"]].isna().any().any()
        assert dataset["copom"].sum() == 8
        assert not set(dataset["date"]) & {d.isoformat() for d in HOLIDAYS - {date(2025, 1, 1)}}

    def test_news_time_reaches_proc_news_table(self, env):
        pipeline, storage, _, links, _ = env
        timed = next(i for items in links.values() for i in items if isinstance(i, dict))

        _run(pipeline, links)

        assert storage.get_proc_news(timed["url"]).news_time.strftime("%H:%M") == timed["time"]
        untimed = next(i for items in links.values() for i in items if isinstance(i, str))
        assert storage.get_proc_news(untimed).news_time is None


class TestToggles:
    def test_disabled_granger_stage_is_skipped(self, env):
        pipeline, _, _, links, _ = env
        enabled = {s for s in StageName if s is not StageName.GRANGER_CAUSALITY}

        result = _run(pipeline, links, enabled_stages=enabled)

        assert result.status == "SUCCESS"
        assert result.stage_results["granger_causality"].status == "SKIPPED"
        assert result.stages_executed == STAGES

    def test_granger_without_dataset_fails_with_clear_message(self, env):
        pipeline, _, _, links, _ = env
        enabled = {s for s in StageName if s is not StageName.CONFOUNDING_HANDLING}

        result = _run(pipeline, links, enabled_stages=enabled)

        assert result.status == "FAILED"
        assert result.stage_results["granger_causality"].status == "FAILED"
        assert result.error_message == "dataset de análise ausente — habilite confounding_handling"


class TestFailureModes:
    def test_missing_index_fails_data_collection(self, env):
        pipeline, _, _, links, container = env
        container._data_source_adapter.empty = {"^BVSP"}

        result = _run(pipeline, links)

        assert result.status == "FAILED"
        assert result.stage_results["data_collection"].status == "FAILED"
        assert "^BVSP" in result.error_message

    def test_missing_commodities_only_removes_the_control(self, env):
        pipeline, _, _, links, container = env
        container._data_source_adapter.empty = {"ZS=F", "ZC=F", "LE=F"}

        result = _run(pipeline, links)
        report = result.stage_results["granger_causality"].data["granger_report"]

        assert result.status == "SUCCESS"
        assert "ret_commod" not in report["variables"]
        assert any("ret_commod" in w for w in report["warnings"])

    def test_no_news_at_all_marks_news_tests_as_not_tested(self, env):
        pipeline, _, _, _, _ = env

        result = _run(pipeline, {})
        report = result.stage_results["granger_causality"].data["granger_report"]

        assert result.status == "SUCCESS"
        main = [t for t in report["tests"] if t["model"] == "principal"]
        assert {t["status"] for t in main} == {"not_tested"}
        assert any("has_news" in w or "sem variância" in w for w in report["warnings"])
