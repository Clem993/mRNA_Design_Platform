"""Tests for the database ingestion layer."""
import os
import sqlite3
import tempfile

import pandas as pd
import pytest

from core.database import ConnectionConfig, SQLiteConnector, CSVConnector
from core.database.base import FieldMapping, SchemaMapper, SEQUENCE_FIELDS


# ── SchemaMapper ──────────────────────────────────────────────────────────────

class TestSchemaMapper:
    def test_from_dict(self):
        mapper = SchemaMapper.from_dict({
            "gene_name": "name",
            "mrna_seq": "full_mrna",
        })
        assert len(mapper.mappings) == 2

    def test_requires_name_mapping(self):
        with pytest.raises(ValueError, match="name"):
            SchemaMapper.from_dict({"mrna_seq": "full_mrna"})

    def test_invalid_target_field(self):
        with pytest.raises(ValueError):
            FieldMapping("col", "not_a_real_field")

    def test_map_row(self):
        mapper = SchemaMapper.from_dict({
            "gene": "name",
            "sequence": "full_mrna",
            "utr": "five_prime_utr",
        }, db_source="test_db")
        row = {"gene": "GFP", "sequence": "ATGCCC", "utr": "AAAA", "extra": "foo"}
        seq = mapper.map_row(row)
        assert seq.name == "GFP"
        assert seq.full_mrna == "ATGCCC"
        assert seq.five_prime_utr == "AAAA"
        assert seq.source == "database"
        assert seq.db_source == "test_db"
        assert seq.raw_metadata["extra"] == "foo"

    def test_map_dataframe(self):
        mapper = SchemaMapper.from_dict({"name_col": "name", "cds_col": "cds"})
        df = pd.DataFrame({
            "name_col": ["seq1", "seq2"],
            "cds_col": ["ATGCCC", "ATGTTT"],
        })
        seqs = mapper.map_dataframe(df)
        assert len(seqs) == 2
        assert seqs[0].name == "seq1"
        assert seqs[1].cds == "ATGTTT"

    def test_transform_applied(self):
        mapper = SchemaMapper([
            FieldMapping("gene", "name"),
            FieldMapping("seq", "full_mrna", transform=str.upper),
        ])
        row = {"gene": "test", "seq": "atgccc"}
        seq = mapper.map_row(row)
        assert seq.full_mrna == "ATGCCC"


# ── SQLite Connector ──────────────────────────────────────────────────────────

@pytest.fixture
def sqlite_db():
    """Create a temporary SQLite database with sample sequence data."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE sequences (
            id INTEGER PRIMARY KEY,
            gene_name TEXT,
            mrna_sequence TEXT,
            gc_target REAL
        )
    """)
    conn.execute("INSERT INTO sequences VALUES (1, 'GFP', 'ATGCCCATG', 0.55)")
    conn.execute("INSERT INTO sequences VALUES (2, 'RFP', 'ATGTTTGGG', 0.45)")
    conn.commit()
    conn.close()
    yield db_path
    os.unlink(db_path)


class TestSQLiteConnector:
    def test_connect(self, sqlite_db):
        config = ConnectionConfig("sqlite", "test", {"path": sqlite_db})
        connector = SQLiteConnector(config)
        connector.connect()
        assert connector.is_connected
        connector.disconnect()

    def test_list_tables(self, sqlite_db):
        config = ConnectionConfig("sqlite", "test", {"path": sqlite_db})
        connector = SQLiteConnector(config)
        connector.connect()
        tables = connector.list_tables()
        assert "sequences" in tables
        connector.disconnect()

    def test_get_records(self, sqlite_db):
        config = ConnectionConfig("sqlite", "test", {"path": sqlite_db})
        connector = SQLiteConnector(config)
        connector.connect()
        df = connector.get_records("sequences")
        assert len(df) == 2
        assert "gene_name" in df.columns
        connector.disconnect()

    def test_get_records_with_limit(self, sqlite_db):
        config = ConnectionConfig("sqlite", "test", {"path": sqlite_db})
        connector = SQLiteConnector(config)
        connector.connect()
        df = connector.get_records("sequences", limit=1)
        assert len(df) == 1
        connector.disconnect()

    def test_get_columns(self, sqlite_db):
        config = ConnectionConfig("sqlite", "test", {"path": sqlite_db})
        connector = SQLiteConnector(config)
        connector.connect()
        cols = connector.get_columns("sequences")
        assert "gene_name" in cols
        assert "mrna_sequence" in cols
        connector.disconnect()

    def test_not_connected_raises(self):
        config = ConnectionConfig("sqlite", "test", {"path": "/nonexistent.db"})
        connector = SQLiteConnector(config)
        with pytest.raises(RuntimeError):
            connector.list_tables()

    def test_full_import_pipeline(self, sqlite_db):
        """Full end-to-end: connect → get records → map → mRNASequence list."""
        config = ConnectionConfig("sqlite", "test_lims", {"path": sqlite_db})
        connector = SQLiteConnector(config)
        connector.connect()

        df = connector.get_records("sequences")
        mapper = SchemaMapper.from_dict({
            "gene_name": "name",
            "mrna_sequence": "full_mrna",
        }, db_source="test_lims")
        sequences = mapper.map_dataframe(df)
        connector.disconnect()

        assert len(sequences) == 2
        assert sequences[0].name == "GFP"
        assert sequences[0].full_mrna == "ATGCCCATG"
        assert sequences[0].db_source == "test_lims"


# ── CSV Connector ─────────────────────────────────────────────────────────────

@pytest.fixture
def csv_file():
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".csv", delete=False
    ) as f:
        f.write("name,cds,utr5\n")
        f.write("GFP,ATGCCCATG,AAAA\n")
        f.write("RFP,ATGTTTGGG,TTTT\n")
        path = f.name
    yield path
    os.unlink(path)


class TestCSVConnector:
    def test_connect(self, csv_file):
        config = ConnectionConfig("csv", "test_csv", {"path": csv_file})
        connector = CSVConnector(config)
        connector.connect()
        assert connector.is_connected
        connector.disconnect()

    def test_list_tables(self, csv_file):
        config = ConnectionConfig("csv", "test_csv", {"path": csv_file})
        connector = CSVConnector(config)
        connector.connect()
        tables = connector.list_tables()
        # Table name = filename stem
        assert len(tables) == 1
        connector.disconnect()

    def test_get_records(self, csv_file):
        config = ConnectionConfig("csv", "test_csv", {"path": csv_file})
        connector = CSVConnector(config)
        connector.connect()
        table = connector.list_tables()[0]
        df = connector.get_records(table)
        assert len(df) == 2
        assert "name" in df.columns
        connector.disconnect()

    def test_get_records_with_query(self, csv_file):
        config = ConnectionConfig("csv", "test_csv", {"path": csv_file})
        connector = CSVConnector(config)
        connector.connect()
        table = connector.list_tables()[0]
        df = connector.get_records(table, query="name == 'GFP'")
        assert len(df) == 1
        assert df.iloc[0]["name"] == "GFP"
        connector.disconnect()
