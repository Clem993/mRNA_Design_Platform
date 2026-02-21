"""SQLite database connector."""
from __future__ import annotations

import sqlite3
from typing import List, Optional

import pandas as pd

from core.database.base import ConnectionConfig, DatabaseConnector


class SQLiteConnector(DatabaseConnector):
    """Connects to a local SQLite database file."""

    def __init__(self, config: ConnectionConfig) -> None:
        super().__init__(config)
        self._conn: Optional[sqlite3.Connection] = None

    def connect(self) -> None:
        path = self.config.params.get("path")
        if not path:
            raise ValueError("SQLite config must include 'path'.")
        try:
            self._conn = sqlite3.connect(path, check_same_thread=False)
            self._connected = True
        except sqlite3.Error as e:
            raise ConnectionError(f"SQLite connection failed: {e}") from e

    def disconnect(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
        self._connected = False

    def list_tables(self) -> List[str]:
        self._require_connected()
        cursor = self._conn.execute(  # type: ignore[union-attr]
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
        )
        return [row[0] for row in cursor.fetchall()]

    def get_columns(self, table: str) -> List[str]:
        self._require_connected()
        cursor = self._conn.execute(f'PRAGMA table_info("{table}");')  # type: ignore[union-attr]
        return [row[1] for row in cursor.fetchall()]

    def get_records(
        self,
        table: str,
        query: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> pd.DataFrame:
        self._require_connected()
        sql = f'SELECT * FROM "{table}"'
        if query:
            sql += f" WHERE {query}"
        if limit:
            sql += f" LIMIT {limit}"
        return pd.read_sql_query(sql, self._conn)  # type: ignore[arg-type]

    def execute_raw(self, sql: str) -> pd.DataFrame:
        """Run arbitrary read-only SQL and return a DataFrame."""
        self._require_connected()
        return pd.read_sql_query(sql, self._conn)  # type: ignore[arg-type]

    def _require_connected(self) -> None:
        if not self._connected or self._conn is None:
            raise RuntimeError("Not connected. Call connect() first.")
