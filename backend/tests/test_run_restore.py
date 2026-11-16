"""Recarga de uma execução anterior: persistência em PIPELINE_PROC_ID, serviço e rotas."""

import asyncio
import sqlite3
from datetime import date, datetime, time
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
import httpx

from backend.src.adapters.storage import SQLiteStorage
from backend.src.domain.models import PipelineProcRecord, ProcNewsRecord, TreatedNewsRecord
from backend.src.domain.services.run_restore_service import RunRestoreService
from backend.src.pipeline import StageName

# Reaproveita a pipeline offline (fontes falsas) dos testes de integração do Granger.
from backend.tests.test_granger_pipeline_integration import PERIOD, _run, env  # noqa: F401

A, B, C = "https://g1/a", "https://info/b", "https://g1/c"
START = datetime(2026, 11, 15, 21, 0, 0)
END = datetime(2026, 11, 15, 21, 5, 0)
RESULT = {
    "stages_executed": ["docling_transform"],
    "stage_results": {
        "docling_transform": {
            "stage_name": "docling_transform", "status": "SUCCESS", "error_message": None,
        }
    },
    "error_message": None,
    "pending_treatment_urls": None,
}


def _finished_run(storage, proc_id="run-1", start=START, links=None, status="SUCCESS"):
    """Registra uma execução como a pipeline faz: entradas no início, resultado no fim."""
    storage.save_pipeline_proc(PipelineProcRecord(
        proc_id, start, None, status="RUNNING",
        date_start=date(2025, 1, 1), date_end=date(2025, 3, 31),
        request={"enabled_stages": ["docling_transform"], "news_links": links or {}},
    ))
    storage.finish_pipeline_proc(proc_id, END, status=status, result=RESULT)


class TestPipelineProcPersistence:
    def test_inputs_and_result_roundtrip(self, storage):
        links = {"2025-01-03": [A, {"url": B, "time": "18:42"}]}

        _finished_run(storage, links=links)
        got = storage.get_pipeline_proc("run-1")

        assert got.status == "SUCCESS"
        assert (got.date_start, got.date_end) == (date(2025, 1, 1), date(2025, 3, 31))
        assert got.request["news_links"] == links
        assert got.result == RESULT
        assert got.proc_ts_end == END

    def test_finish_without_status_keeps_the_recorded_one(self, storage):
        storage.save_pipeline_proc(
            PipelineProcRecord("run-1", START, None, status="RUNNING", request={"k": 1})
        )

        storage.finish_pipeline_proc("run-1", END)  # sem status/result: COALESCE preserva
        got = storage.get_pipeline_proc("run-1")

        assert got.status == "RUNNING" and got.request == {"k": 1}
        assert got.proc_ts_end == END

    def test_list_is_most_recent_first_and_honors_limit(self, storage):
        for index, hour in enumerate((9, 11, 10)):
            _finished_run(storage, f"run-{index}", start=datetime(2026, 11, 15, hour))

        listed = storage.list_pipeline_procs(limit=2)

        assert [r.proc_id for r in listed] == ["run-1", "run-2"]

    def test_unknown_run_is_none_and_empty_list_is_empty(self, storage):
        assert storage.get_pipeline_proc("nope") is None
        assert storage.list_pipeline_procs() == []

    def test_old_table_is_migrated_preserving_rows_idempotently(self, tmp_path):
        db = tmp_path / "old.db"
        conn = sqlite3.connect(db.as_posix())
        conn.execute(
            "CREATE TABLE PIPELINE_PROC_ID (PROC_ID TEXT PRIMARY KEY, "
            "PROC_TS_START TIMESTAMP NOT NULL, PROC_TS_END TIMESTAMP)"
        )
        conn.execute(
            "INSERT INTO PIPELINE_PROC_ID VALUES ('old', '2026-11-15T21:27:16', '2026-11-15T21:29:32')"
        )
        conn.commit()
        conn.close()
        url = f"sqlite:///{db.as_posix()}"

        SQLiteStorage(url)
        storage = SQLiteStorage(url)  # idempotente

        old = storage.get_pipeline_proc("old")
        assert old.proc_ts_end == datetime(2026, 11, 15, 21, 29, 32)
        assert old.status is None and old.request is None and old.date_start is None

    def test_proc_news_by_proc_id_filters_and_orders(self, storage):
        for url, proc_id, day in ((B, "run-1", date(2025, 1, 5)), (A, "run-1", date(2025, 1, 3)),
                                  (C, "run-2", date(2025, 1, 4))):
            storage.save_proc_news(
                ProcNewsRecord(url, datetime(2026, 11, 15), "G1", True, proc_id, day)
            )

        assert [r.url for r in storage.list_proc_news_by_proc_id("run-1")] == [A, B]


class TestRunRestoreService:
    def test_empty_database_has_no_latest_run(self, storage):
        service = RunRestoreService(storage)

        assert service.get_run() is None
        assert service.list_runs() == []

    def test_latest_run_is_returned_when_no_id_is_given(self, storage):
        _finished_run(storage, "older", start=datetime(2026, 11, 14))
        _finished_run(storage, "newer", start=datetime(2026, 11, 15))

        assert RunRestoreService(storage).get_run()["proc_id"] == "newer"

    def test_unknown_id_is_none(self, storage):
        assert RunRestoreService(storage).get_run("nope") is None

    def test_state_carries_links_result_period_and_stages(self, storage):
        links = {"2025-01-03": [A], "2025-01-05": [{"url": B, "time": "18:42"}]}
        _finished_run(storage, links=links)

        state = RunRestoreService(storage).get_run("run-1")

        assert state["news_links"] == links
        assert state["news_links_count"] == 2
        assert (state["date_start"], state["date_end"]) == ("2025-01-01", "2025-03-31")
        assert state["enabled_stages"] == ["docling_transform"]
        assert state["status"] == "SUCCESS"
        assert state["run_result"] == {
            "pipeline_id": "run-1", "status": "SUCCESS", **{
                k: RESULT[k] for k in ("stages_executed", "stage_results",
                                       "error_message", "pending_treatment_urls")
            },
        }

    def test_treated_news_only_for_the_runs_urls(self, storage):
        _finished_run(storage, links={"2025-01-03": [A, B]})
        markdown = "---\ntitle: T\nsubtitle: S\nurl: a\ndate: 03-01-2025\n---\nCorpo"
        storage.save_treated_news(TreatedNewsRecord.from_treated_markdown(A, markdown))
        storage.save_treated_news(TreatedNewsRecord.from_treated_markdown(C, markdown))  # de outra run

        state = RunRestoreService(storage).get_run("run-1")

        assert state["treated_news"] == {A: markdown}

    def test_granger_flag_follows_the_stored_report(self, storage):
        _finished_run(storage, "with", links={"2025-01-03": [A]})
        _finished_run(storage, "without", start=datetime(2026, 11, 16))
        storage.save_granger_test_results({"n_obs": 10}, proc_id="with")
        service = RunRestoreService(storage)

        assert service.get_run("with")["has_granger_report"] is True
        assert service.get_run("without")["has_granger_report"] is False

    def test_legacy_run_rebuilds_links_from_proc_news(self, storage):
        storage.save_pipeline_proc(PipelineProcRecord("legacy", START, END))  # sem STATUS/REQUEST
        for url, day, when in ((A, date(2025, 1, 3), time(12, 57)), (B, date(2025, 1, 3), None),
                               (C, date(2025, 1, 5), None)):
            storage.save_proc_news(ProcNewsRecord(
                url, datetime(2026, 11, 15), "G1", True, "legacy", day, when
            ))
        storage.save_proc_news(  # sem data de publicação: não tem grupo
            ProcNewsRecord("https://x/undated", datetime(2026, 11, 15), "G1", True, "legacy")
        )

        state = RunRestoreService(storage).get_run("legacy")

        # Ordem determinística por data/horário (sem horário primeiro); a de colagem se perdeu.
        assert state["news_links"] == {
            "2025-01-03": [B, {"url": A, "time": "12:57"}],
            "2025-01-05": [C],
        }
        assert state["status"] == "UNKNOWN"
        assert state["run_result"] is None  # sem resultado gravado
        assert state["date_start"] is None

    @pytest.mark.parametrize("status", ["RUNNING", None])
    def test_unfinished_or_unknown_run_has_no_result_to_render(self, storage, status):
        storage.save_pipeline_proc(
            PipelineProcRecord("r", START, None, status=status, request={"news_links": {}})
        )

        assert RunRestoreService(storage).get_run("r")["run_result"] is None

    def test_list_summaries_count_links(self, storage):
        _finished_run(storage, "r1", links={"2025-01-03": [A, B]})

        (summary,) = RunRestoreService(storage).list_runs()

        assert summary["proc_id"] == "r1" and summary["news_links_count"] == 2
        assert "news_links" not in summary and "treated_news" not in summary


class TestPipelineRecordsWhatItNeedsToBeRestored:
    def test_toggled_run_persists_inputs_and_per_stage_result(self, env):  # noqa: F811
        pipeline, storage, _, links, _ = env

        result = _run(pipeline, links, enabled_stages={StageName.DOCLING_TRANSFORM})
        record = storage.get_pipeline_proc(pipeline.pipeline_id)

        assert record.status == result.status == "SUCCESS"
        assert (record.date_start, record.date_end) == PERIOD
        assert record.request["enabled_stages"] == ["docling_transform"]
        assert record.request["news_links"] == links
        assert record.proc_ts_end is not None
        assert record.result["stage_results"]["granger_causality"]["status"] == "SKIPPED"

        state = RunRestoreService(storage).get_run(pipeline.pipeline_id)
        assert state["news_links"] == links
        assert state["run_result"]["stages_executed"] == result.stages_executed
        assert len(state["treated_news"]) == sum(len(v) for v in links.values())

    def test_full_run_is_restorable_with_its_granger_report(self, env):  # noqa: F811
        pipeline, storage, _, links, _ = env

        _run(pipeline, links)
        state = RunRestoreService(storage).get_run()

        assert state["proc_id"] == pipeline.pipeline_id
        assert state["status"] == "SUCCESS"
        assert state["has_granger_report"] is True
        assert all(r["status"] == "SUCCESS" for r in state["run_result"]["stage_results"].values())

    def test_unexpected_exception_leaves_the_run_failed_not_running(self, env):  # noqa: F811
        pipeline, storage, _, links, _ = env
        pipeline._run_stages = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))

        with pytest.raises(RuntimeError):
            _run(pipeline, links)

        record = storage.get_pipeline_proc(pipeline.pipeline_id)
        assert record.status == "FAILED" and record.proc_ts_end is not None


class _Api:
    """Cliente HTTP em processo (ASGI) sobre o router, sem rede nem TestClient."""

    def __init__(self, app):
        self._app = app

    def get(self, path):
        async def call():
            transport = httpx.ASGITransport(app=self._app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                return await client.get(path)

        return asyncio.run(call())


class TestRunRoutes:
    @pytest.fixture
    def client(self, storage, monkeypatch):
        from app.api.routes import pipeline_routes

        monkeypatch.setattr(
            pipeline_routes, "_container", SimpleNamespace(get_storage=lambda: storage)
        )
        app = FastAPI()
        app.include_router(pipeline_routes.router)
        return _Api(app)

    def test_latest_is_null_when_there_are_no_runs(self, client):
        response = client.get("/pipeline/runs/latest")

        assert response.status_code == 200 and response.json() is None

    def test_latest_is_not_mistaken_for_a_run_id(self, client, storage):
        _finished_run(storage, "run-1", links={"2025-01-03": [A]})

        body = client.get("/pipeline/runs/latest").json()

        assert body["proc_id"] == "run-1"
        assert body["news_links"] == {"2025-01-03": [A]}
        assert body["run_result"]["stage_results"]["docling_transform"]["status"] == "SUCCESS"

    def test_get_run_by_id_and_404_for_unknown(self, client, storage):
        _finished_run(storage, "run-1")

        assert client.get("/pipeline/runs/run-1").json()["proc_id"] == "run-1"
        assert client.get("/pipeline/runs/nope").status_code == 404

    def test_list_runs_respects_limit_and_validates_it(self, client, storage):
        for index in range(3):
            _finished_run(storage, f"run-{index}", start=datetime(2026, 11, 15, index))

        assert [r["proc_id"] for r in client.get("/pipeline/runs?limit=2").json()] == [
            "run-2", "run-1"
        ]
        assert client.get("/pipeline/runs?limit=0").status_code == 422
