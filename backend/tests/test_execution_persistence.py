"""Testes de persistência de execução: PIPELINE_PROC_ID, PROC_NEWS e tratadas (Requisito 13)."""

import sqlite3
from datetime import date, datetime

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
            news_date=date(2026, 6, 10),
        )
        storage.save_proc_news(record)

        got = storage.get_proc_news("https://g1/x")
        assert got is not None
        assert got.proc_id == "run-1"
        assert got.proc_ts == datetime(2026, 6, 12)
        assert got.proc_success is True
        assert got.news_date == date(2026, 6, 10)
        assert got.to_dict() == record.to_dict()  # roundtrip sem perda

    def test_proc_news_without_news_date_roundtrip(self, storage):
        record = ProcNewsRecord("https://g1/y", datetime(2026, 6, 12), "G1", False)
        storage.save_proc_news(record)

        got = storage.get_proc_news("https://g1/y")
        assert got.news_date is None
        assert got.to_dict()["NEWS_DATE"] is None

    def test_proc_news_upsert_updates_news_date(self, storage):
        first = ProcNewsRecord("u", datetime(2026, 6, 12), "G1", True, news_date=date(2026, 6, 1))
        second = ProcNewsRecord("u", datetime(2026, 6, 13), "G1", True, news_date=date(2026, 6, 2))
        storage.save_proc_news(first)
        storage.save_proc_news(second)

        assert storage.get_proc_news("u").news_date == date(2026, 6, 2)

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

    def test_outdated_proc_news_table_is_recreated_idempotently(self, tmp_path):
        db = tmp_path / "outdated.db"
        conn = sqlite3.connect(db.as_posix())
        conn.execute(
            "CREATE TABLE PIPELINE_PROC_NEWS ("
            "URL TEXT PRIMARY KEY, PROC_ID TEXT, PROC_TS TIMESTAMP NOT NULL, "
            "NM_SITE TEXT, PROC_SUCCESS BOOLEAN NOT NULL)"  # schema anterior: sem NEWS_DATE
        )
        conn.execute(
            "INSERT INTO PIPELINE_PROC_NEWS VALUES (?,?,?,?,?)",
            ("u", "run-0", "2025-01-02T10:00:00", "G1", 1),
        )
        conn.commit()
        conn.close()

        url = f"sqlite:///{db.as_posix()}"
        SQLiteStorage(url)  # 1ª passada: descarta e recria

        conn = sqlite3.connect(db.as_posix())
        cols = {r[1] for r in conn.execute("PRAGMA table_info(PIPELINE_PROC_NEWS)").fetchall()}
        count = conn.execute("SELECT COUNT(*) FROM PIPELINE_PROC_NEWS").fetchone()[0]
        conn.close()

        assert cols == {"URL", "PROC_ID", "PROC_TS", "NM_SITE", "PROC_SUCCESS", "NEWS_DATE"}
        assert count == 0  # dados antigos descartados (premissa: sem dados de produção)

        storage = SQLiteStorage(url)  # 2ª passada: não altera a tabela
        record = ProcNewsRecord("u2", datetime(2026, 6, 12), "G1", True, news_date=date(2026, 6, 1))
        storage.save_proc_news(record)
        SQLiteStorage(url)  # 3ª passada com dados: preservados

        assert storage.get_proc_news("u2").to_dict() == record.to_dict()

    def test_legacy_ts_proc_table_is_recreated_too(self, tmp_path):
        db = tmp_path / "legacy.db"
        conn = sqlite3.connect(db.as_posix())
        conn.execute(
            "CREATE TABLE PIPELINE_PROC_NEWS ("
            "URL TEXT PRIMARY KEY, TS_PROC TIMESTAMP NOT NULL, "
            "NM_SITE TEXT, PROC_SUCCESS BOOLEAN NOT NULL)"
        )
        conn.commit()
        conn.close()

        storage = SQLiteStorage(f"sqlite:///{db.as_posix()}")
        storage.save_proc_news(ProcNewsRecord("u", datetime(2026, 6, 12), "G1", True))

        assert storage.get_proc_news("u") is not None

    def test_up_to_date_table_is_left_untouched(self, storage, db_url):
        storage.save_proc_news(ProcNewsRecord("u", datetime(2026, 6, 12), "G1", True))

        SQLiteStorage(db_url)  # reinicialização com schema atual

        assert storage.get_proc_news("u") is not None

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
