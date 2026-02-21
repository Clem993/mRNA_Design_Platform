"""PostgreSQL database connector (via SQLAlchemy + psycopg2)."""
from __future__ import annotations

from typing import List, Optional

import pandas as pd
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

from core.database.base import ConnectionConfig, DatabaseConnector


class PostgreSQLConnector(DatabaseConnector):
    """Connects to a PostgreSQL database."""

    def __init__(self, config: ConnectionConfig) -> None:
        super().__init__(config)
        self._engine: Optional[Engine] = None

    def _build_url(self) -> str:
        p = self.config.params
        user = p.get("user", "")
        password = p.get("password", "")
        host = p.get("host", "localhost")
        port = p.get("port", 5432)
        dbname = p.get("dbname", "")
        if password:
            return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}"
        return f"postgresql+psycopg2://{user}@{host}:{port}/{dbname}"

    def connect(self) -> None:
        try:
            url = self._build_url()
            self._engine = create_engine(url, pool_pre_ping=True)
            # Test the connection
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            self._connected = True
        except Exception as e:
            raise ConnectionError(f"PostgreSQL connection failed: {e}") from e

    def disconnect(self) -> None:
        if self._engine:
            self._engine.dispose()
            self._engine = None
        self._connected = False

    def list_tables(self) -> List[str]:
        self._require_connected()
        inspector = inspect(self._engine)
        return inspector.get_table_names()

    def get_columns(self, table: str) -> List[str]:
        self._require_connected()
        inspector = inspect(self._engine)
        return [col["name"] for col in inspector.get_columns(table)]

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
        with self._engine.connect() as conn:  # type: ignore[union-attr]
            return pd.read_sql_query(text(sql), conn)

    def execute_raw(self, sql: str) -> pd.DataFrame:
        """Run arbitrary read-only SQL."""
        self._require_connected()
        with self._engine.connect() as conn:  # type: ignore[union-attr]
            return pd.read_sql_query(text(sql), conn)

    def _require_connected(self) -> None:
        if not self._connected or self._engine is None:
            raise RuntimeError("Not connected. Call connect() first.")
