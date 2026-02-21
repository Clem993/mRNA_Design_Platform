"""CSV and Excel flat-file connector."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from core.database.base import ConnectionConfig, DatabaseConnector


class CSVConnector(DatabaseConnector):
    """
    Connector for CSV and Excel flat files.

    For CSV: treats the single file as one 'table' named by the filename stem.
    For Excel: each worksheet is a 'table'.
    A directory of CSV files is also supported — each file becomes a table.
    """

    def __init__(self, config: ConnectionConfig) -> None:
        super().__init__(config)
        self._dataframes: Dict[str, pd.DataFrame] = {}

    def connect(self) -> None:
        path_str = self.config.params.get("path")
        if not path_str:
            raise ValueError("CSV/Excel config must include 'path'.")
        path = Path(path_str)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        self._dataframes = {}

        if path.is_dir():
            # Load all CSVs in directory
            for csv_file in sorted(path.glob("*.csv")):
                df = pd.read_csv(csv_file)
                self._dataframes[csv_file.stem] = df
            if not self._dataframes:
                raise ValueError(f"No CSV files found in directory: {path}")

        elif path.suffix.lower() in (".xlsx", ".xls"):
            xl = pd.ExcelFile(path)
            for sheet in xl.sheet_names:
                self._dataframes[sheet] = xl.parse(sheet)

        elif path.suffix.lower() == ".csv":
            df = pd.read_csv(path)
            self._dataframes[path.stem] = df

        else:
            raise ValueError(
                f"Unsupported file type: {path.suffix}. Use .csv, .xlsx, or .xls."
            )

        self._connected = True

    def disconnect(self) -> None:
        self._dataframes.clear()
        self._connected = False

    def list_tables(self) -> List[str]:
        return list(self._dataframes.keys())

    def get_columns(self, table: str) -> List[str]:
        self._require_connected()
        df = self._get_table(table)
        return list(df.columns)

    def get_records(
        self,
        table: str,
        query: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> pd.DataFrame:
        self._require_connected()
        df = self._get_table(table).copy()
        if query:
            try:
                df = df.query(query)
            except Exception as e:
                raise ValueError(f"Query error: {e}") from e
        if limit:
            df = df.head(limit)
        return df.reset_index(drop=True)

    def _get_table(self, table: str) -> pd.DataFrame:
        if table not in self._dataframes:
            raise KeyError(
                f"Table '{table}' not found. Available: {self.list_tables()}"
            )
        return self._dataframes[table]

    def _require_connected(self) -> None:
        if not self._connected:
            raise RuntimeError("Not connected. Call connect() first.")
