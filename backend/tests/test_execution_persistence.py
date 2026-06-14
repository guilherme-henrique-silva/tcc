"""Testes de persistência de execução: PIPELINE_PROC_ID, PROC_NEWS e tratadas (Requisito 13)."""

import sqlite3
from datetime import datetime

import pytest

from backend.src.adapters.storage import SQLiteStorage
from backend.src.domain.models import (
    ProcNewsRecord,
    PipelineProcRecord,
    TreatedNewsRecord,
)


def _raw_path(db_url: str) -> str:
    """Strip the sqlite:/// prefix to read the file directly in assertions."""
    return db_url[10:]


class TestExecutionPersistence:
    """Cobertura das novas tabelas e da migração idempotente."""

    def test_pipeline_proc_create_and_finish(self, storage, db_url):
        start = datetime(2026, 6, 12, 10, 0, 0)
        storage.save_pipeline_proc(PipelineProcRecord("run-1", start, None))

        conn = sqlite3.connect(_raw_path(db_url))
        row = conn.execute(
            "SELECT PROC_ID, PROC_TS_START, PROC_TS_END "
            "FROM PIPELINE_PROC_ID WHERE PROC_ID = 'run-1'"
        ).fetchone()
        assert row[0] == "run-1"
        assert row[1] == start.isoformat()
        assert row[2] is None  # NULL enquanto roda

        end = datetime(2026, 6, 12, 10, 5, 0)
        storage.finish_pipeline_proc("run-1", end)
        ended = conn.execute(
            "SELECT PROC_TS_END FROM PIPELINE_PROC_ID WHERE PROC_ID = 'run-1'"
        ).fetchone()[0]
        conn.close()

        assert ended == end.isoformat()

    def test_proc_news_has_proc_id_and_proc_ts(self, storage):
        record = ProcNewsRecord(
            url="https://g1/x",
            proc_ts=datetime(2026, 6, 12),
            site_name="G1",
            proc_success=True,
            proc_id="run-1",
        )
        storage.save_proc_news(record)

        got = storage.get_proc_news("https://g1/x")
        assert got is not None
        assert got.proc_id == "run-1"
        assert got.proc_ts == datetime(2026, 6, 12)
        assert got.proc_success is True

    def test_treated_news_roundtrip_and_list(self, storage):
        markdown = "---\ntitle: T\nsubtitle: S\nurl: u\ndate: 12-06-2026\n---\nCorpo"
        record = TreatedNewsRecord.from_treated_markdown("u", markdown, proc_id="run-1")
        storage.save_treated_news(record)

        got = storage.get_treated_news("u")
        assert got.title == "T"
        assert got.content == markdown
        assert got.proc_id == "run-1"

        listed = storage.list_treated_news("run-1")
        assert len(listed) == 1
        assert listed[0].url == "u"

    def test_legacy_migration_idempotent(self, tmp_path):
        db = tmp_path / "legacy.db"
        conn = sqlite3.connect(db.as_posix())
        conn.execute(
            "CREATE TABLE PIPELINE_PROC_NEWS ("
            "URL TEXT PRIMARY KEY, TS_PROC TIMESTAMP NOT NULL, "
            "NM_SITE TEXT, PROC_SUCCESS BOOLEAN NOT NULL)"
        )
        conn.execute(
            "INSERT INTO PIPELINE_PROC_NEWS VALUES (?,?,?,?)",
            ("u", "2025-01-02T10:00:00", "G1", 1),
        )
        conn.commit()
        conn.close()

        url = f"sqlite:///{db.as_posix()}"
        SQLiteStorage(url)  # 1ª passada: migra
        SQLiteStorage(url)  # 2ª passada: idempotente

        conn = sqlite3.connect(db.as_posix())
        cols = {r[1] for r in conn.execute("PRAGMA table_info(PIPELINE_PROC_NEWS)").fetchall()}
        row = conn.execute(
            "SELECT URL, PROC_ID, PROC_TS, NM_SITE, PROC_SUCCESS FROM PIPELINE_PROC_NEWS"
        ).fetchone()
        conn.close()

        assert cols == {"URL", "PROC_ID", "PROC_TS", "NM_SITE", "PROC_SUCCESS"}
        assert row == ("u", None, "2025-01-02T10:00:00", "G1", 1)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
