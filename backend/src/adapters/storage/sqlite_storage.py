"""SQLite Storage Adapter."""

import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd

from src.ports.data_source import StoragePort
from src.domain.models import ProcNewsRecord, PipelineProcRecord, TreatedNewsRecord
from app.core.logger import get_logger


# Colunas esperadas de PIPELINE_PROC_NEWS (usadas na verificação de schema desatualizado).
_PROC_NEWS_COLUMNS = frozenset(
    {"URL", "PROC_ID", "PROC_TS", "NM_SITE", "PROC_SUCCESS", "NEWS_DATE", "NEWS_TIME"}
)

# Colunas de PIPELINE_PROC_ID acrescentadas para recarregar uma execução (migração).
_PROC_RESTORE_COLUMNS = ("STATUS", "DATE_START", "DATE_END", "REQUEST", "RESULT")

# Ordem usada nos SELECTs de PIPELINE_PROC_ID (casa com `_row_to_pipeline_proc`).
_PROC_COLUMNS = (
    "PROC_ID, PROC_TS_START, PROC_TS_END, STATUS, DATE_START, DATE_END, REQUEST, RESULT"
)

logger = get_logger(__name__)


class SQLiteStorage(StoragePort):
    """Adapter for persisting features to SQLite database."""
    
    def __init__(self, database_url: str):
        """Initialize with database connection URL."""
        self.database_url = database_url
        self._initialize_database()
    
    def save_features(self, features: pd.DataFrame, dataset_id: str) -> None:
        """Save features to SQLite."""
        try:
            conn = self._get_connection()
            features.to_sql(
                f"features_{dataset_id}",
                conn,
                if_exists="replace",
                index=False,
            )
            conn.close()
        
        except sqlite3.Error:
            pass
    
    def load_features(self, dataset_id: str) -> Optional[pd.DataFrame]:
        """Load features from SQLite."""
        try:
            conn = self._get_connection()
            df = pd.read_sql(
                f"SELECT * FROM features_{dataset_id}",
                conn,
            )
            conn.close()
            
            return df if not df.empty else None
        
        except sqlite3.Error:
            return None
    
    def save_validation_results(self, results: Dict) -> None:
        """Save validation results to SQLite."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            results_json = json.dumps(results)
            cursor.execute(
                "INSERT INTO validation_results (data) VALUES (?)",
                (results_json,),
            )
            
            conn.commit()
            conn.close()
        
        except sqlite3.Error:
            pass
    
    def save_granger_test_results(
        self,
        results: Dict,
        proc_id: Optional[str] = None,
    ) -> None:
        """Save the Granger report (JSON) tagged with the execution's PROC_ID.

        Falhas de gravação não são silenciadas: ficam registradas em nível ERROR.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            results_json = json.dumps(results)
            cursor.execute(
                "INSERT INTO granger_results (data, PROC_ID) VALUES (?, ?)",
                (results_json, proc_id),
            )

            conn.commit()
            conn.close()

        except (sqlite3.Error, TypeError, ValueError) as exc:
            logger.error(
                "Falha ao gravar o relatório de Granger (PROC_ID=%s): %s", proc_id, exc
            )

    def get_granger_results(self, proc_id: Optional[str] = None) -> Optional[Dict]:
        """Return the stored Granger report for ``proc_id`` (latest run when None)."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            if proc_id:
                cursor.execute(
                    "SELECT data FROM granger_results WHERE PROC_ID = ? "
                    "ORDER BY id DESC LIMIT 1",
                    (proc_id,),
                )
            else:
                cursor.execute("SELECT data FROM granger_results ORDER BY id DESC LIMIT 1")

            row = cursor.fetchone()
            conn.close()

            return json.loads(row[0]) if row and row[0] else None

        except (sqlite3.Error, ValueError) as exc:
            logger.error("Falha ao ler o relatório de Granger (PROC_ID=%s): %s", proc_id, exc)
            return None

    def save_proc_news(self, record: ProcNewsRecord) -> None:
        """Persist a Docling processing record."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO PIPELINE_PROC_NEWS
                    (URL, PROC_ID, PROC_TS, NM_SITE, PROC_SUCCESS, NEWS_DATE, NEWS_TIME)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(URL) DO UPDATE SET
                    PROC_ID = excluded.PROC_ID,
                    PROC_TS = excluded.PROC_TS,
                    NM_SITE = excluded.NM_SITE,
                    PROC_SUCCESS = excluded.PROC_SUCCESS,
                    NEWS_DATE = excluded.NEWS_DATE,
                    NEWS_TIME = excluded.NEWS_TIME
                """,
                (
                    record.url,
                    record.proc_id,
                    record.proc_ts.isoformat(),
                    record.site_name,
                    int(record.proc_success),
                    record.news_date.isoformat() if record.news_date else None,
                    record.news_time.strftime("%H:%M") if record.news_time else None,
                ),
            )

            conn.commit()
            conn.close()

        except sqlite3.Error:
            pass

    def get_proc_news(self, url: str) -> Optional[ProcNewsRecord]:
        """Retrieve a processing record by URL."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT URL, PROC_ID, PROC_TS, NM_SITE, PROC_SUCCESS, NEWS_DATE, NEWS_TIME "
                "FROM PIPELINE_PROC_NEWS WHERE URL = ?",
                (url,),
            )
            row = cursor.fetchone()
            conn.close()

            if not row:
                return None

            return ProcNewsRecord.from_row(
                {
                    "URL": row[0],
                    "PROC_ID": row[1],
                    "PROC_TS": row[2],
                    "NM_SITE": row[3],
                    "PROC_SUCCESS": row[4],
                    "NEWS_DATE": row[5],
                    "NEWS_TIME": row[6],
                }
            )

        except sqlite3.Error:
            return None

    def save_pipeline_proc(self, record: PipelineProcRecord) -> None:
        """Persist a PIPELINE_PROC_ID row at the start of an execution."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO PIPELINE_PROC_ID
                    (PROC_ID, PROC_TS_START, PROC_TS_END, STATUS,
                     DATE_START, DATE_END, REQUEST, RESULT)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(PROC_ID) DO UPDATE SET
                    PROC_TS_START = excluded.PROC_TS_START,
                    PROC_TS_END = excluded.PROC_TS_END,
                    STATUS = excluded.STATUS,
                    DATE_START = excluded.DATE_START,
                    DATE_END = excluded.DATE_END,
                    REQUEST = excluded.REQUEST,
                    RESULT = excluded.RESULT
                """,
                (
                    record.proc_id,
                    record.proc_ts_start.isoformat(),
                    record.proc_ts_end.isoformat() if record.proc_ts_end else None,
                    record.status,
                    record.date_start.isoformat() if record.date_start else None,
                    record.date_end.isoformat() if record.date_end else None,
                    self._dump_json(record.request),
                    self._dump_json(record.result),
                ),
            )

            conn.commit()
            conn.close()

        except (sqlite3.Error, TypeError, ValueError) as exc:
            logger.error("Falha ao registrar a execução (PROC_ID=%s): %s", record.proc_id, exc)

    def finish_pipeline_proc(
        self,
        proc_id: str,
        end_ts: datetime,
        status: Optional[str] = None,
        result: Optional[Dict] = None,
    ) -> None:
        """Stamp PROC_TS_END (and STATUS/RESULT when given) when execution ends."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "UPDATE PIPELINE_PROC_ID SET PROC_TS_END = ?, "
                "STATUS = COALESCE(?, STATUS), RESULT = COALESCE(?, RESULT) "
                "WHERE PROC_ID = ?",
                (end_ts.isoformat(), status, self._dump_json(result), proc_id),
            )

            conn.commit()
            conn.close()

        except (sqlite3.Error, TypeError, ValueError) as exc:
            logger.error("Falha ao encerrar a execução (PROC_ID=%s): %s", proc_id, exc)

    def get_pipeline_proc(self, proc_id: str) -> Optional[PipelineProcRecord]:
        """Retrieve one execution by PROC_ID, or None."""
        try:
            conn = self._get_connection()
            row = conn.execute(
                f"SELECT {_PROC_COLUMNS} FROM PIPELINE_PROC_ID WHERE PROC_ID = ?",
                (proc_id,),
            ).fetchone()
            conn.close()

            return self._row_to_pipeline_proc(row) if row else None

        except (sqlite3.Error, ValueError) as exc:
            logger.error("Falha ao ler a execução (PROC_ID=%s): %s", proc_id, exc)
            return None

    def list_pipeline_procs(self, limit: int = 20) -> List[PipelineProcRecord]:
        """List executions, most recent first."""
        try:
            conn = self._get_connection()
            rows = conn.execute(
                f"SELECT {_PROC_COLUMNS} FROM PIPELINE_PROC_ID "
                "ORDER BY PROC_TS_START DESC LIMIT ?",
                (limit,),
            ).fetchall()
            conn.close()

            return [self._row_to_pipeline_proc(row) for row in rows]

        except (sqlite3.Error, ValueError) as exc:
            logger.error("Falha ao listar as execuções: %s", exc)
            return []

    def list_proc_news_by_proc_id(self, proc_id: str) -> List[ProcNewsRecord]:
        """List the PIPELINE_PROC_NEWS rows last tagged with ``proc_id``, oldest date first."""
        try:
            conn = self._get_connection()
            rows = conn.execute(
                "SELECT URL, PROC_ID, PROC_TS, NM_SITE, PROC_SUCCESS, NEWS_DATE, NEWS_TIME "
                "FROM PIPELINE_PROC_NEWS WHERE PROC_ID = ? ORDER BY NEWS_DATE, NEWS_TIME, URL",
                (proc_id,),
            ).fetchall()
            conn.close()

            return [ProcNewsRecord.from_row(self._proc_news_row_to_dict(r)) for r in rows]

        except (sqlite3.Error, ValueError) as exc:
            logger.error("Falha ao listar notícias da execução (PROC_ID=%s): %s", proc_id, exc)
            return []

    def _proc_news_row_to_dict(self, row) -> Dict[str, object]:
        """Map a PIPELINE_PROC_NEWS row tuple into a column dict."""
        return {
            "URL": row[0],
            "PROC_ID": row[1],
            "PROC_TS": row[2],
            "NM_SITE": row[3],
            "PROC_SUCCESS": row[4],
            "NEWS_DATE": row[5],
            "NEWS_TIME": row[6],
        }

    def _row_to_pipeline_proc(self, row) -> PipelineProcRecord:
        """Map a PIPELINE_PROC_ID row tuple (ordem de _PROC_COLUMNS) into the record."""
        return PipelineProcRecord.from_row(
            {
                "PROC_ID": row[0],
                "PROC_TS_START": row[1],
                "PROC_TS_END": row[2],
                "STATUS": row[3],
                "DATE_START": row[4],
                "DATE_END": row[5],
                "REQUEST": self._load_json(row[6]),
                "RESULT": self._load_json(row[7]),
            }
        )

    @staticmethod
    def _dump_json(value: Optional[Dict]) -> Optional[str]:
        """JSON text for a nullable dict column (None stays NULL)."""
        return None if value is None else json.dumps(value)

    @staticmethod
    def _load_json(text: Optional[str]) -> Optional[Dict]:
        """Inverse of ``_dump_json``; unreadable JSON is treated as absent."""
        if not text:
            return None

        try:
            return json.loads(text)
        except ValueError:
            return None

    def save_treated_news(self, record: TreatedNewsRecord) -> None:
        """Persist a treated news document with its frontmatter metadata."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO PIPELINE_TREATED_NEWS
                    (URL, PROC_ID, TITLE, SUBTITLE, NEWS_DATE, CATEGORY, CONTENT)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(URL) DO UPDATE SET
                    PROC_ID = excluded.PROC_ID,
                    TITLE = excluded.TITLE,
                    SUBTITLE = excluded.SUBTITLE,
                    NEWS_DATE = excluded.NEWS_DATE,
                    CATEGORY = excluded.CATEGORY,
                    CONTENT = excluded.CONTENT
                """,
                (
                    record.url,
                    record.proc_id,
                    record.title,
                    record.subtitle,
                    record.date,
                    record.category,
                    record.content,
                ),
            )

            conn.commit()
            conn.close()

        except sqlite3.Error:
            pass

    def get_treated_news(self, url: str) -> Optional[TreatedNewsRecord]:
        """Retrieve a treated news document by URL, or None."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT URL, PROC_ID, TITLE, SUBTITLE, NEWS_DATE, CATEGORY, CONTENT "
                "FROM PIPELINE_TREATED_NEWS WHERE URL = ?",
                (url,),
            )
            row = cursor.fetchone()
            conn.close()

            if not row:
                return None

            return TreatedNewsRecord.from_row(self._treated_row_to_dict(row))

        except sqlite3.Error:
            return None

    def list_treated_news(self, proc_id: str) -> List[TreatedNewsRecord]:
        """List treated documents for a given execution."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT URL, PROC_ID, TITLE, SUBTITLE, NEWS_DATE, CATEGORY, CONTENT "
                "FROM PIPELINE_TREATED_NEWS WHERE PROC_ID = ?",
                (proc_id,),
            )
            rows = cursor.fetchall()
            conn.close()

            return [TreatedNewsRecord.from_row(self._treated_row_to_dict(r)) for r in rows]

        except sqlite3.Error:
            return []

    def _treated_row_to_dict(self, row) -> Dict[str, object]:
        """Map a PIPELINE_TREATED_NEWS row tuple into a column dict."""
        return {
            "URL": row[0],
            "PROC_ID": row[1],
            "TITLE": row[2],
            "SUBTITLE": row[3],
            "NEWS_DATE": row[4],
            "CATEGORY": row[5],
            "CONTENT": row[6],
        }

    def _initialize_database(self) -> None:
        """Initialize database tables."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            self._create_validation_table(cursor)
            self._create_granger_table(cursor)
            self._create_pipeline_proc_table(cursor)
            self._create_proc_news_table(cursor)
            self._create_treated_news_table(cursor)

            conn.commit()
            conn.close()

        except sqlite3.Error:
            pass
    
    def _create_validation_table(self, cursor) -> None:
        """Create validation_results table."""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS validation_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    
    def _create_granger_table(self, cursor) -> None:
        """Create granger_results table."""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS granger_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PROC_ID TEXT
            )
        """)
        self._migrate_granger_schema(cursor)

    def _migrate_granger_schema(self, cursor) -> None:
        """Add PROC_ID to pre-existing granger_results tables (idempotente)."""
        columns = {row[1] for row in cursor.execute(
            "PRAGMA table_info(granger_results)"
        ).fetchall()}

        if "PROC_ID" not in columns:
            cursor.execute("ALTER TABLE granger_results ADD COLUMN PROC_ID TEXT")

    def _create_pipeline_proc_table(self, cursor) -> None:
        """Create PIPELINE_PROC_ID table — one row per execution."""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS PIPELINE_PROC_ID (
                PROC_ID       TEXT      PRIMARY KEY,
                PROC_TS_START TIMESTAMP NOT NULL,
                PROC_TS_END   TIMESTAMP,
                STATUS        TEXT,
                DATE_START    TEXT,
                DATE_END      TEXT,
                REQUEST       TEXT,
                RESULT        TEXT
            )
        """)
        self._migrate_pipeline_proc_schema(cursor)

    def _migrate_pipeline_proc_schema(self, cursor) -> None:
        """Add the run-restore columns to a pre-existing PIPELINE_PROC_ID (idempotente).

        Preserva as execuções antigas: elas ficam com as novas colunas NULL e são
        recarregadas pelo fallback de ``RunRestoreService``.
        """
        columns = {row[1] for row in cursor.execute(
            "PRAGMA table_info(PIPELINE_PROC_ID)"
        ).fetchall()}

        for name in _PROC_RESTORE_COLUMNS:
            if name not in columns:
                cursor.execute(f"ALTER TABLE PIPELINE_PROC_ID ADD COLUMN {name} TEXT")

    def _create_proc_news_table(self, cursor) -> None:
        """Create PIPELINE_PROC_NEWS, recreating it when the schema is outdated."""
        self._reset_proc_news_if_outdated(cursor)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS PIPELINE_PROC_NEWS (
                URL          TEXT      PRIMARY KEY,
                PROC_ID      TEXT,
                PROC_TS      TIMESTAMP NOT NULL,
                NM_SITE      TEXT,
                PROC_SUCCESS BOOLEAN   NOT NULL,
                NEWS_DATE    TEXT,
                NEWS_TIME    TEXT
            )
        """)

    def _reset_proc_news_if_outdated(self, cursor) -> None:
        """Migrate or drop PIPELINE_PROC_NEWS when its columns differ from the expected ones.

        Só falta NEWS_TIME (schema da versão anterior): acrescenta a coluna e preserva os
        dados. Qualquer outro schema desatualizado é descartado e recriado, pois não há
        dados de produção a preservar. Idempotente — com o schema atual nada é alterado.
        Necessário porque os métodos do adapter engolem sqlite3.Error e INSERTs num schema
        antigo falhariam em silêncio.
        """
        columns = {row[1] for row in cursor.execute(
            "PRAGMA table_info(PIPELINE_PROC_NEWS)"
        ).fetchall()}

        if not columns or columns == _PROC_NEWS_COLUMNS:
            return

        if columns == _PROC_NEWS_COLUMNS - {"NEWS_TIME"}:
            cursor.execute("ALTER TABLE PIPELINE_PROC_NEWS ADD COLUMN NEWS_TIME TEXT")
            return

        cursor.execute("DROP TABLE PIPELINE_PROC_NEWS")

    def _create_treated_news_table(self, cursor) -> None:
        """Create PIPELINE_TREATED_NEWS table for treated documents."""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS PIPELINE_TREATED_NEWS (
                URL       TEXT PRIMARY KEY,
                PROC_ID   TEXT,
                TITLE     TEXT,
                SUBTITLE  TEXT,
                NEWS_DATE TEXT,
                CATEGORY  TEXT,
                CONTENT   TEXT NOT NULL
            )
        """)
        self._migrate_treated_news_schema(cursor)

    def _migrate_treated_news_schema(self, cursor) -> None:
        """Add CATEGORY column to pre-existing PIPELINE_TREATED_NEWS tables (idempotente)."""
        columns = {row[1] for row in cursor.execute(
            "PRAGMA table_info(PIPELINE_TREATED_NEWS)"
        ).fetchall()}

        if "CATEGORY" not in columns:
            cursor.execute("ALTER TABLE PIPELINE_TREATED_NEWS ADD COLUMN CATEGORY TEXT")

    def check_connection(self) -> Optional[str]:
        """Test DB connectivity for health checks: None on success, reason on failure."""
        try:
            conn = self._get_connection()
            conn.execute("SELECT 1")
            conn.close()
            return None

        except sqlite3.Error as e:
            return str(e)

    def _get_connection(self):
        """Get SQLite connection."""
        db_path = self._parse_database_path()
        return sqlite3.connect(db_path)
    
    def _parse_database_path(self) -> str:
        """Parse database URL to file path."""
        # sqlite:////path/to/db.sqlite -> /path/to/db.sqlite
        if self.database_url.startswith("sqlite:///"):
            return self.database_url[10:]
        
        return self.database_url
