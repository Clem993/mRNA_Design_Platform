"""
Database import panel.

Lets the user:
1. Configure a new database connection (SQLite / PostgreSQL / CSV)
2. Choose a table from the connected database
3. Map database columns to mRNASequence fields (SchemaMapper)
4. Import selected records into the registry
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional

import pandas as pd
import panel as pn
import param

from core.database import ConnectionConfig, FieldMapping, SchemaMapper, create_connector
from core.database.base import SEQUENCE_FIELDS

if TYPE_CHECKING:
    from ui.state import AppState


_BACKEND_OPTIONS = ["SQLite", "PostgreSQL", "CSV / Excel"]

_FIELD_OPTIONS = ["(skip)"] + sorted(SEQUENCE_FIELDS)


class DatabaseImportPanel(param.Parameterized):
    """Step-by-step database import workflow."""

    def __init__(self, state: "AppState", **params: object) -> None:
        super().__init__(**params)
        self._state = state
        self._connector = None
        self._preview_df: Optional[pd.DataFrame] = None
        self._columns: List[str] = []
        self._field_selects: Dict[str, pn.widgets.Select] = {}
        self._status_pane = pn.pane.HTML("")

    # ── Widget builders ───────────────────────────────────────────────────────

    def _build_connection_form(self) -> pn.Column:
        self._backend_select = pn.widgets.Select(
            name="Backend",
            options=_BACKEND_OPTIONS,
            value="PostgreSQL",
            width=200,
        )
        self._display_name = pn.widgets.TextInput(
            name="Connection Name",
            placeholder="demo_db",
            value="demo_db",
            width=200,
        )
        self._sqlite_path = pn.widgets.TextInput(
            name="File Path",
            placeholder="/path/to/database.db",
            width=400,
        )
        self._pg_host = pn.widgets.TextInput(name="Host", value="localhost", width=200)
        self._pg_port = pn.widgets.IntInput(name="Port", value=5432, width=100)
        self._pg_dbname = pn.widgets.TextInput(name="Database", value="mrna_studio", width=200)
        self._pg_user = pn.widgets.TextInput(name="User", value="demo_user", width=200)
        self._pg_password = pn.widgets.PasswordInput(name="Password", value="demo_pass_2024", width=200)
        self._csv_path = pn.widgets.TextInput(
            name="File / Directory Path",
            value="demo/mrna_sequences.csv",
            placeholder="/path/to/file.csv",
            width=400,
        )

        connect_btn = pn.widgets.Button(name="Connect", button_type="primary", margin=(8, 0))
        connect_btn.on_click(self._on_connect)

        @param.depends(self._backend_select.param.value)
        def backend_specific_fields(backend: str) -> pn.Column:
            if backend == "SQLite":
                return pn.Column(self._sqlite_path)
            elif backend == "PostgreSQL":
                return pn.Column(
                    pn.Row(self._pg_host, self._pg_port),
                    pn.Row(self._pg_dbname, self._pg_user),
                    self._pg_password,
                )
            else:
                return pn.Column(self._csv_path)

        return pn.Column(
            pn.pane.HTML(
                '<div style="font-size:14px;font-weight:700;margin-bottom:8px;">'
                'Connect to Database</div>'
            ),
            pn.Row(self._backend_select, self._display_name),
            pn.panel(backend_specific_fields),
            connect_btn,
            self._status_pane,
        )

    def _build_table_selector(self) -> pn.Column:
        if not self._connector:
            return pn.Column()
        tables = self._connector.list_tables()
        self._table_select = pn.widgets.Select(
            name="Table / Sheet",
            options=tables,
            value=tables[0] if tables else None,
            width=300,
        )
        preview_btn = pn.widgets.Button(name="Preview", button_type="light", margin=(8, 4))
        preview_btn.on_click(self._on_preview)

        return pn.Column(
            pn.pane.HTML(
                '<div style="font-size:13px;font-weight:700;margin:12px 0 6px 0;">'
                'Select Table</div>'
            ),
            pn.Row(self._table_select, preview_btn),
        )

    def _build_mapping_form(self) -> pn.Column:
        if not self._columns:
            return pn.Column()

        # Worklist name input
        default_worklist_name = f"{self._connector.name}.{self._table_select.value}"
        self._worklist_name = pn.widgets.TextInput(
            name="Worklist Name",
            value=default_worklist_name,
            placeholder="e.g., demo_db.mrna_sequences",
            width=400,
        )

        self._field_selects = {}
        rows = []
        for col in self._columns:
            sel = pn.widgets.Select(
                name=col,
                options=_FIELD_OPTIONS,
                value=self._auto_suggest(col),
                width=200,
            )
            self._field_selects[col] = sel
            rows.append(pn.Row(
                pn.pane.HTML(
                    f'<div style="font-size:12px;font-family:monospace;'
                    f'padding-top:8px;min-width:180px;">{col}</div>'
                ),
                pn.pane.HTML(
                    '<div style="padding-top:8px;font-size:12px;color:#7F8C8D;">→</div>'
                ),
                sel,
            ))

        import_btn = pn.widgets.Button(
            name="Import Records", button_type="success", margin=(12, 0)
        )
        import_btn.on_click(self._on_import)

        return pn.Column(
            pn.pane.HTML(
                '<div style="font-size:13px;font-weight:700;margin:12px 0 6px 0;">'
                'Worklist Configuration</div>'
            ),
            self._worklist_name,
            pn.pane.HTML(
                '<div style="font-size:13px;font-weight:700;margin:12px 0 6px 0;">'
                'Map Columns to mRNA Fields</div>'
            ),
            pn.Column(*rows),
            import_btn,
        )

    def _build_preview_table(self) -> pn.viewable.Viewable:
        if self._preview_df is None:
            return pn.pane.HTML("")
        return pn.Column(
            pn.pane.HTML(
                '<div style="font-size:12px;font-weight:700;margin:8px 0 4px 0;">'
                f'Preview ({len(self._preview_df)} rows)</div>'
            ),
            pn.widgets.DataFrame(
                self._preview_df.head(20),
                sizing_mode="stretch_width",
                show_index=False,
                height=200,
            ),
        )

    # ── Reactive panel ─────────────────────────────────────────────────────────
    # Dynamic sections are held as mutable Column instances so we can clear
    # and refill them on button clicks without needing pn.bind(lambda: ...).

    def panel(self) -> pn.Column:
        self._table_section   = pn.Column(sizing_mode="stretch_width")
        self._preview_section = pn.Column(sizing_mode="stretch_width")
        self._mapping_section = pn.Column(sizing_mode="stretch_width")

        return pn.Column(
            pn.pane.HTML(
                '<div style="font-size:16px;font-weight:800;padding:8px 0 4px 0;">'
                'Import Database</div>'
                '<div style="font-size:12px;color:#64748B;margin-bottom:10px;">'
                'Connect to a database server (PostgreSQL, SQLite, or CSV), authenticate with '
                'credentials, then map schema fields to the mRNA sequence model.<br>'
                '<span style="color:#6366F1;">💡 Demo database pre-filled — or switch to SQLite/CSV.</span></div>'
            ),
            self._build_connection_form(),
            self._table_section,
            self._preview_section,
            self._mapping_section,
            sizing_mode="stretch_width",
            styles={"padding": "8px 16px"},
        )

    # ── Event handlers ─────────────────────────────────────────────────────────

    def _refresh_table_section(self) -> None:
        self._table_section.clear()
        self._table_section.append(self._build_table_selector())

    def _refresh_preview_section(self) -> None:
        self._preview_section.clear()
        self._preview_section.append(self._build_preview_table())

    def _refresh_mapping_section(self) -> None:
        self._mapping_section.clear()
        self._mapping_section.append(self._build_mapping_form())

    def _on_connect(self, event: object) -> None:
        backend = self._backend_select.value
        name = self._display_name.value or f"conn_{len(self._state.db_connections)+1}"

        if backend == "SQLite":
            params = {"path": self._sqlite_path.value}
            backend_key = "sqlite"
        elif backend == "PostgreSQL":
            params = {
                "host": self._pg_host.value,
                "port": self._pg_port.value,
                "dbname": self._pg_dbname.value,
                "user": self._pg_user.value,
                "password": self._pg_password.value,
            }
            backend_key = "postgres"
        else:
            params = {"path": self._csv_path.value}
            backend_key = "csv"

        config = ConnectionConfig(
            backend=backend_key,
            display_name=name,
            params=params,
        )
        try:
            connector = create_connector(config)
            connector.connect()
            self._connector = connector
            self._status_pane.object = (
                f'<div style="color:#10B981;font-size:12px;margin-top:4px;">'
                f'✓ Connected to {name}</div>'
            )
            self._refresh_table_section()
        except Exception as e:
            self._status_pane.object = (
                f'<div style="color:#EF4444;font-size:12px;margin-top:4px;">'
                f'✗ Connection failed: {e}</div>'
            )

    def _on_preview(self, event: object) -> None:
        if not self._connector:
            return
        table = self._table_select.value
        try:
            self._preview_df = self._connector.get_records(table, limit=50)
            self._columns = list(self._preview_df.columns)
            self._refresh_preview_section()
            self._refresh_mapping_section()
        except Exception as e:
            self._status_pane.object = (
                f'<div style="color:#EF4444;font-size:12px;">'
                f'Preview failed: {e}</div>'
            )

    def _on_import(self, event: object) -> None:
        import logging
        logger = logging.getLogger(__name__)

        if not self._connector or not self._columns:
            logger.warning("Import attempted with no connector or columns")
            return
        table = self._table_select.value
        mapping = {}
        for col, sel in self._field_selects.items():
            if sel.value and sel.value != "(skip)":
                mapping[col] = sel.value

        logger.info(f"Import mapping: {mapping}")

        if "name" not in mapping.values():
            self._status_pane.object = (
                '<div style="color:#E74C3C;">Must map at least one column to "name".</div>'
            )
            return

        try:
            logger.info(f"Starting import from table: {table}")
            df = self._connector.get_records(table)
            logger.info(f"Retrieved {len(df)} records from database")

            mapper = SchemaMapper.from_dict(mapping, db_source=self._connector.name)
            sequences = mapper.map_dataframe(df)
            logger.info(f"Mapped to {len(sequences)} mRNASequence objects")

            # Create NEW worklist for this import (don't add to existing)
            from core.models.worklist import Worklist
            worklist_name = self._worklist_name.value or f"{self._connector.name}.{table}"
            new_worklist = Worklist(name=worklist_name)
            new_worklist.add_many(sequences, origin="database_import")
            logger.info(f"Created worklist '{worklist_name}' with {len(sequences)} items")

            # Replace the current worklist with the new one
            self._state.worklist = new_worklist
            self._state.register_db_connection(self._connector, mapper)

            # Auto-extract parts from imported sequences
            total_parts = 0
            for seq in sequences:
                parts_count = self._state.extract_parts_from_sequence(seq, source="database_import")
                total_parts += parts_count
            logger.info(f"Extracted {total_parts} parts from {len(sequences)} sequences")

            # Trigger parameter update so UI refreshes
            self._state.param.trigger("worklist")
            self._state.param.trigger("parts_library")

            self._status_pane.object = (
                f'<div style="color:#10B981;font-size:12px;">'
                f'✓ Created new worklist "{worklist_name}" with {len(sequences)} sequences<br>'
                f'✓ Extracted {total_parts} parts to library</div>'
            )
            self._state.set_status(
                f"Created new worklist '{worklist_name}' with {len(sequences)} sequences. "
                f"Extracted {total_parts} reusable parts."
            )
            # Close modal and navigate to worklist tab to show imported data
            self._state.show_db_import_modal = False
            self._state.active_tab = "worklist"
        except Exception as e:
            self._status_pane.object = (
                f'<div style="color:#EF4444;">Import failed: {e}</div>'
            )

    @staticmethod
    def _auto_suggest(column_name: str) -> str:
        """Guess the target field from common column naming patterns."""
        col = column_name.lower().replace(" ", "_").replace("-", "_")
        hints = {
            "name": "name",
            "gene": "name",
            "id": "name",
            "label": "name",
            "utr5": "five_prime_utr",
            "5utr": "five_prime_utr",
            "five_prime": "five_prime_utr",
            "utr3": "three_prime_utr",
            "3utr": "three_prime_utr",
            "three_prime": "three_prime_utr",
            "cds": "cds",
            "orf": "cds",
            "coding": "cds",
            "kozak": "kozak",
            "polya": "poly_a",
            "poly_a": "poly_a",
            "mrna": "full_mrna",
            "sequence": "full_mrna",
            "seq": "full_mrna",
        }
        for hint, field in hints.items():
            if hint in col:
                return field
        return "(skip)"
