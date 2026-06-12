"""SQLite Storage Adapter."""

import sqlite3
import json
from typing import Dict, List, Optional
import pandas as pd
from pathlib import Path

from src.ports.data_source import StoragePort
from src.domain.models import ProcNewsRecord


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
        """Persist a Docling processing record (Seção 8.4 do spec)."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO PIPELINE_PROC_NEWS (URL, TS_PROC, NM_SITE, PROC_SUCCESS)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(URL) DO UPDATE SET
                    TS_PROC = excluded.TS_PROC,
                    NM_SITE = excluded.NM_SITE,
                    PROC_SUCCESS = excluded.PROC_SUCCESS
                """,
                (
                    record.url,
                    record.ts_proc.isoformat(),
                    record.site_name,
                    int(record.proc_success),
                ),
            )

            conn.commit()
            conn.close()

        except sqlite3.Error:
            pass

    def get_proc_news(self, url: str) -> Optional[ProcNewsRecord]:
        """Retrieve a processing record by URL (Seção 8.5 do spec)."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT URL, TS_PROC, NM_SITE, PROC_SUCCESS "
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
                    "TS_PROC": row[1],
                    "NM_SITE": row[2],
                    "PROC_SUCCESS": row[3],
                }
            )

        except sqlite3.Error:
            return None

    def _initialize_database(self) -> None:
        """Initialize database tables (Rule 1)."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            self._create_validation_table(cursor)
            self._create_granger_table(cursor)
            self._create_proc_news_table(cursor)

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

    def _create_proc_news_table(self, cursor) -> None:
        """Create PIPELINE_PROC_NEWS table (Seção 8.4 do spec)."""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS PIPELINE_PROC_NEWS (
                URL          TEXT      PRIMARY KEY,
                TS_PROC      TIMESTAMP NOT NULL,
                NM_SITE      TEXT,
                PROC_SUCCESS BOOLEAN   NOT NULL
            )
        """)
    
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
