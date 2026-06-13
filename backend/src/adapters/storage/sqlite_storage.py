"""SQLite Storage Adapter."""

import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd

from src.ports.data_source import StoragePort
from src.domain.models import ProcNewsRecord, PipelineProcRecord, TreatedNewsRecord


class SQLiteStorage(StoragePort):
    """Adapter for persisting features to SQLite database (Rule 7: small entity)."""
    
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
    
    def save_granger_test_results(self, results: Dict) -> None:
        """Save Granger test results to SQLite."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            results_json = json.dumps(results)
            cursor.execute(
                "INSERT INTO granger_results (data) VALUES (?)",
                (results_json,),
            )
            
            conn.commit()
            conn.close()
        
        except sqlite3.Error:
            pass
    
    def save_proc_news(self, record: ProcNewsRecord) -> None:
        """Persist a Docling processing record (Seção 9 do spec)."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO PIPELINE_PROC_NEWS (URL, PROC_ID, PROC_TS, NM_SITE, PROC_SUCCESS)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(URL) DO UPDATE SET
                    PROC_ID = excluded.PROC_ID,
                    PROC_TS = excluded.PROC_TS,
                    NM_SITE = excluded.NM_SITE,
                    PROC_SUCCESS = excluded.PROC_SUCCESS
                """,
                (
                    record.url,
                    record.proc_id,
                    record.proc_ts.isoformat(),
                    record.site_name,
                    int(record.proc_success),
                ),
            )

            conn.commit()
            conn.close()

        except sqlite3.Error:
            pass

    def get_proc_news(self, url: str) -> Optional[ProcNewsRecord]:
        """Retrieve a processing record by URL (Seção 9 do spec)."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT URL, PROC_ID, PROC_TS, NM_SITE, PROC_SUCCESS "
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
                }
            )

        except sqlite3.Error:
            return None

    def save_pipeline_proc(self, record: PipelineProcRecord) -> None:
        """Persist a PIPELINE_PROC_ID row at the start of an execution (Seção 9)."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO PIPELINE_PROC_ID (PROC_ID, PROC_TS_START, PROC_TS_END)
                VALUES (?, ?, ?)
                ON CONFLICT(PROC_ID) DO UPDATE SET
                    PROC_TS_START = excluded.PROC_TS_START,
                    PROC_TS_END = excluded.PROC_TS_END
                """,
                (
                    record.proc_id,
                    record.proc_ts_start.isoformat(),
                    record.proc_ts_end.isoformat() if record.proc_ts_end else None,
                ),
            )

            conn.commit()
            conn.close()

        except sqlite3.Error:
            pass

    def finish_pipeline_proc(self, proc_id: str, end_ts: datetime) -> None:
        """Stamp PROC_TS_END when execution ends, success or failure (Seção 9)."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "UPDATE PIPELINE_PROC_ID SET PROC_TS_END = ? WHERE PROC_ID = ?",
                (end_ts.isoformat(), proc_id),
            )

            conn.commit()
            conn.close()

        except sqlite3.Error:
            pass

    def save_treated_news(self, record: TreatedNewsRecord) -> None:
        """Persist a treated news document with its frontmatter metadata (Seção 10)."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO PIPELINE_TREATED_NEWS
                    (URL, PROC_ID, TITLE, SUBTITLE, NEWS_DATE, CONTENT)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(URL) DO UPDATE SET
                    PROC_ID = excluded.PROC_ID,
                    TITLE = excluded.TITLE,
                    SUBTITLE = excluded.SUBTITLE,
                    NEWS_DATE = excluded.NEWS_DATE,
                    CONTENT = excluded.CONTENT
                """,
                (
                    record.url,
                    record.proc_id,
                    record.title,
                    record.subtitle,
                    record.date,
                    record.content,
                ),
            )

            conn.commit()
            conn.close()

        except sqlite3.Error:
            pass

    def get_treated_news(self, url: str) -> Optional[TreatedNewsRecord]:
        """Retrieve a treated news document by URL, or None (Seção 10)."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT URL, PROC_ID, TITLE, SUBTITLE, NEWS_DATE, CONTENT "
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
        """List treated documents for a given execution (Seção 10)."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT URL, PROC_ID, TITLE, SUBTITLE, NEWS_DATE, CONTENT "
                "FROM PIPELINE_TREATED_NEWS WHERE PROC_ID = ?",
                (proc_id,),
            )
            rows = cursor.fetchall()
            conn.close()

            return [TreatedNewsRecord.from_row(self._treated_row_to_dict(r)) for r in rows]

        except sqlite3.Error:
            return []

    def _treated_row_to_dict(self, row) -> Dict[str, object]:
        """Map a PIPELINE_TREATED_NEWS row tuple into a column dict (Rule 1)."""
        return {
            "URL": row[0],
            "PROC_ID": row[1],
            "TITLE": row[2],
            "SUBTITLE": row[3],
            "NEWS_DATE": row[4],
            "CONTENT": row[5],
        }

    def _initialize_database(self) -> None:
        """Initialize database tables (Rule 1)."""
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
        """Create validation_results table (Rule 1)."""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS validation_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    
    def _create_granger_table(self, cursor) -> None:
        """Create granger_results table (Rule 1)."""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS granger_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    def _create_pipeline_proc_table(self, cursor) -> None:
        """Create PIPELINE_PROC_ID table — one row per execution (Seção 9 do spec)."""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS PIPELINE_PROC_ID (
                PROC_ID       TEXT      PRIMARY KEY,
                PROC_TS_START TIMESTAMP NOT NULL,
                PROC_TS_END   TIMESTAMP
            )
        """)

    def _create_proc_news_table(self, cursor) -> None:
        """Create PIPELINE_PROC_NEWS with PROC_ID/PROC_TS, migrating legacy rows (Seção 9)."""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS PIPELINE_PROC_NEWS (
                URL          TEXT      PRIMARY KEY,
                PROC_ID      TEXT,
                PROC_TS      TIMESTAMP NOT NULL,
                NM_SITE      TEXT,
                PROC_SUCCESS BOOLEAN   NOT NULL
            )
        """)
        self._migrate_proc_news_schema(cursor)

    def _migrate_proc_news_schema(self, cursor) -> None:
        """Recreate the legacy schema (TS_PROC, sem PROC_ID) preservando dados (idempotente)."""
        columns = {row[1] for row in cursor.execute(
            "PRAGMA table_info(PIPELINE_PROC_NEWS)"
        ).fetchall()}

        if "PROC_TS" in columns and "PROC_ID" in columns:
            return  # já está no schema novo

        cursor.execute("ALTER TABLE PIPELINE_PROC_NEWS RENAME TO PIPELINE_PROC_NEWS_OLD")
        cursor.execute("""
            CREATE TABLE PIPELINE_PROC_NEWS (
                URL          TEXT      PRIMARY KEY,
                PROC_ID      TEXT,
                PROC_TS      TIMESTAMP NOT NULL,
                NM_SITE      TEXT,
                PROC_SUCCESS BOOLEAN   NOT NULL
            )
        """)
        cursor.execute("""
            INSERT INTO PIPELINE_PROC_NEWS (URL, PROC_ID, PROC_TS, NM_SITE, PROC_SUCCESS)
            SELECT URL, NULL, TS_PROC, NM_SITE, PROC_SUCCESS FROM PIPELINE_PROC_NEWS_OLD
        """)
        cursor.execute("DROP TABLE PIPELINE_PROC_NEWS_OLD")

    def _create_treated_news_table(self, cursor) -> None:
        """Create PIPELINE_TREATED_NEWS table for treated documents (Seção 10 do spec)."""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS PIPELINE_TREATED_NEWS (
                URL       TEXT PRIMARY KEY,
                PROC_ID   TEXT,
                TITLE     TEXT,
                SUBTITLE  TEXT,
                NEWS_DATE TEXT,
                CONTENT   TEXT NOT NULL
            )
        """)

    def check_connection(self) -> Optional[str]:
        """Test DB connectivity for health checks: None on success, reason on failure (Seção 7)."""
        try:
            conn = self._get_connection()
            conn.execute("SELECT 1")
            conn.close()
            return None

        except sqlite3.Error as e:
            return str(e)

    def _get_connection(self):
        """Get SQLite connection (Rule 1)."""
        db_path = self._parse_database_path()
        return sqlite3.connect(db_path)
    
    def _parse_database_path(self) -> str:
        """Parse database URL to file path (Rule 1)."""
        # sqlite:////path/to/db.sqlite -> /path/to/db.sqlite
        if self.database_url.startswith("sqlite:///"):
            return self.database_url[10:]
        
        return self.database_url
