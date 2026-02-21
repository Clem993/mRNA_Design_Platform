"""
Abstract database connector interface and SchemaMapper.

Every database backend (SQLite, PostgreSQL, CSV) implements DatabaseConnector.
SchemaMapper translates arbitrary column names to the mRNASequence model fields.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pandas as pd

from core.models.sequence import mRNASequence


# Fields in mRNASequence that can be mapped from a database
SEQUENCE_FIELDS = {
    "name",
    "five_prime_utr",
    "kozak",
    "cds",
    "three_prime_utr",
    "poly_a",
    "full_mrna",
}


@dataclass
class ConnectionConfig:
    """Generic connection configuration (fields vary by backend)."""
    backend: str                        # "sqlite", "postgres", "csv", "excel"
    display_name: str                   # User-facing label for the connection
    params: Dict[str, Any] = field(default_factory=dict)
    # e.g. sqlite: {"path": "/data/seqs.db"}
    # e.g. postgres: {"host": "...", "port": 5432, "dbname": "...", "user": "...", "password": "..."}
    # e.g. csv: {"path": "/data/seqs.csv"}


class DatabaseConnector(ABC):
    """Abstract database connector. One instance per active connection."""

    def __init__(self, config: ConnectionConfig) -> None:
        self.config = config
        self._connected = False

    @abstractmethod
    def connect(self) -> None:
        """Open the connection. Raises ConnectionError on failure."""
        ...

    @abstractmethod
    def disconnect(self) -> None:
        """Close the connection."""
        ...

    @abstractmethod
    def list_tables(self) -> List[str]:
        """Return available table / sheet names."""
        ...

    @abstractmethod
    def get_records(
        self,
        table: str,
        query: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Fetch records from a table.

        Parameters
        ----------
        table : str
            Table name (from list_tables).
        query : str, optional
            Backend-specific filter string (SQL WHERE clause for SQL backends,
            pandas query string for file backends).
        limit : int, optional
            Max rows to return.
        """
        ...

    @abstractmethod
    def get_columns(self, table: str) -> List[str]:
        """Return column names for a table."""
        ...

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def name(self) -> str:
        return self.config.display_name

    def __repr__(self) -> str:
        status = "connected" if self._connected else "disconnected"
        return f"{self.__class__.__name__}({self.name!r}, {status})"


# ── Schema Mapper ────────────────────────────────────────────────────────────

@dataclass
class FieldMapping:
    """
    Describes how one database column maps to a mRNASequence field.

    source_column : str
        Column name in the database.
    target_field : str
        Field name in mRNASequence. Must be in SEQUENCE_FIELDS.
    transform : callable, optional
        Optional transform applied to the raw value before assignment.
        E.g. str.upper, lambda x: x.replace(" ", "")
    """
    source_column: str
    target_field: str
    transform: Optional[Any] = None   # callable or None

    def __post_init__(self) -> None:
        if self.target_field not in SEQUENCE_FIELDS:
            raise ValueError(
                f"'{self.target_field}' is not a valid mRNASequence field. "
                f"Valid fields: {sorted(SEQUENCE_FIELDS)}"
            )


class SchemaMapper:
    """
    Maps a DataFrame (from any DatabaseConnector) to a list of mRNASequence
    objects using a user-configured field mapping.

    Example
    -------
    mapper = SchemaMapper([
        FieldMapping("mrna_sequence", "full_mrna"),
        FieldMapping("gene_name", "name"),
        FieldMapping("utr5_sequence", "five_prime_utr", transform=str.upper),
    ])
    sequences = mapper.map_dataframe(df, db_source="my_lims")
    """

    def __init__(self, mappings: List[FieldMapping], db_source: str = "") -> None:
        self.mappings = mappings
        self.db_source = db_source
        # Validate: exactly one mapping targeting 'name' must exist
        name_targets = [m for m in mappings if m.target_field == "name"]
        if not name_targets:
            raise ValueError(
                "SchemaMapper requires at least one FieldMapping targeting 'name'."
            )

    def map_row(self, row: Dict[str, Any]) -> mRNASequence:
        """Map a single row dict to an mRNASequence."""
        kwargs: Dict[str, Any] = {
            "source": "database",
            "db_source": self.db_source,
            "raw_metadata": dict(row),
        }
        for mapping in self.mappings:
            value = row.get(mapping.source_column)
            # Skip None and NaN values (pandas often returns NaN for SQL NULL)
            if value is None or (isinstance(value, float) and pd.isna(value)):
                continue
            if mapping.transform is not None:
                try:
                    value = mapping.transform(value)
                except Exception:
                    pass
            kwargs[mapping.target_field] = value
        return mRNASequence(**kwargs)  # type: ignore[arg-type]

    def map_dataframe(self, df: pd.DataFrame) -> List[mRNASequence]:
        """Map every row in df to an mRNASequence."""
        return [self.map_row(row.to_dict()) for _, row in df.iterrows()]

    @classmethod
    def from_dict(cls, mapping_dict: Dict[str, str], db_source: str = "") -> "SchemaMapper":
        """
        Convenience constructor from a plain {db_column: sequence_field} dict.

        Example
        -------
        mapper = SchemaMapper.from_dict({
            "gene_name": "name",
            "mrna_seq": "full_mrna",
            "utr": "five_prime_utr",
        })
        """
        mappings = [
            FieldMapping(source_column=col, target_field=field_)
            for col, field_ in mapping_dict.items()
        ]
        return cls(mappings, db_source=db_source)
