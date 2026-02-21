"""Database connectors and schema mapper."""
from core.database.base import (
    ConnectionConfig,
    DatabaseConnector,
    FieldMapping,
    SchemaMapper,
    SEQUENCE_FIELDS,
)
from core.database.sqlite import SQLiteConnector
from core.database.postgres import PostgreSQLConnector
from core.database.csv_importer import CSVConnector


def create_connector(config: ConnectionConfig) -> DatabaseConnector:
    """Factory: return the appropriate connector for config.backend."""
    backends = {
        "sqlite": SQLiteConnector,
        "postgres": PostgreSQLConnector,
        "postgresql": PostgreSQLConnector,
        "csv": CSVConnector,
        "excel": CSVConnector,
    }
    cls = backends.get(config.backend.lower())
    if cls is None:
        raise ValueError(
            f"Unknown backend '{config.backend}'. "
            f"Supported: {list(backends.keys())}"
        )
    return cls(config)


__all__ = [
    "ConnectionConfig",
    "DatabaseConnector",
    "FieldMapping",
    "SchemaMapper",
    "SEQUENCE_FIELDS",
    "SQLiteConnector",
    "PostgreSQLConnector",
    "CSVConnector",
    "create_connector",
]
