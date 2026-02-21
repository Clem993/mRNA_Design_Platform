"""
Import Data panel.

Lets the user:
1. Choose a data source (CSV / Excel or PostgreSQL)
2. Connect / load the source
3. Preview and map columns to mRNASequence fields
4. Import into a new or existing worklist
"""
from __future__ import annotations

import logging
import os
import time
from typing import TYPE_CHECKING, Dict, List, Optional

import pandas as pd
import panel as pn
import param

from core.database import ConnectionConfig, FieldMapping, SchemaMapper, create_connector
from core.database.base import SEQUENCE_FIELDS

if TYPE_CHECKING:
    from ui.state import AppState

logger = logging.getLogger(__name__)


def _log_resources(label: str) -> None:
    """Log current process memory and CPU usage."""
    try:
        import psutil
        proc = psutil.Process(os.getpid())
        mem = proc.memory_info()
        logger.info(
            f"[PERF] {label} | RSS={mem.rss / 1024 / 1024:.1f}MB "
            f"VMS={mem.vms / 1024 / 1024:.1f}MB "
            f"CPU={proc.cpu_percent(interval=None):.1f}%"
        )
    except ImportError:
        pass


_SOURCE_OPTIONS = ["CSV / Excel", "PostgreSQL"]

_FIELD_OPTIONS = ["(skip)"] + sorted(SEQUENCE_FIELDS)


class DatabaseImportPanel(param.Parameterized):
    """Step-by-step data import workflow."""

    def __init__(self, state: "AppState", **params: object) -> None:
        super().__init__(**params)
        self._state = state
        self._connector = None
        self._preview_df: Optional[pd.DataFrame] = None
        self._columns: List[str] = []
        self._field_selects: Dict[str, pn.widgets.Select] = {}
        self._status_pane = pn.pane.HTML("")

    # ── Source selector ────────────────────────────────────────────────────────

    def _build_source_selector(self) -> pn.Column:
        self._source_select = pn.widgets.RadioButtonGroup(
            name="Source",
            options=_SOURCE_OPTIONS,
            value="CSV / Excel",
            button_type="primary",
            button_style="outline",
        )

        return pn.Column(
            pn.pane.HTML(
                '<div style="font-size:14px;font-weight:700;color:#0F172A;'
                'margin-bottom:8px;">Data Source</div>'
            ),
            self._source_select,
            sizing_mode="stretch_width",
            styles={
                "background": "#FFFFFF",
                "padding": "16px",
                "border-radius": "8px",
                "border": "1px solid #E2E8F0",
                "margin-bottom": "12px",
            },
        )

    # ── Connection forms ───────────────────────────────────────────────────────

    def _build_connection_section(self) -> pn.Column:
        """Dynamic section that changes based on the selected source."""
        # -- CSV fields --
        self._csv_path = pn.widgets.TextInput(
            name="File / Directory Path",
            value="demo/mrna_sequences.csv",
            placeholder="/path/to/file.csv  or  /path/to/directory/",
            width=460,
        )
        self._csv_name = pn.widgets.TextInput(
            name="Connection Name",
            placeholder="my_data",
            value="demo_csv",
            width=200,
        )
        csv_import_btn = pn.widgets.Button(
            name="Import",
            button_type="primary",
            width=100,
            margin=(20, 4, 4, 4),
        )
        csv_import_btn.on_click(self._on_connect)

        csv_form = pn.Column(
            pn.pane.HTML(
                '<div style="font-size:11px;color:#64748B;margin-bottom:8px;">'
                'Point to a .csv, .xlsx, or a directory of CSV files.</div>'
            ),
            pn.Row(self._csv_path, self._csv_name),
            csv_import_btn,
            sizing_mode="stretch_width",
        )

        # -- PostgreSQL fields --
        self._pg_host = pn.widgets.TextInput(name="Host", value="localhost", width=200)
        self._pg_port = pn.widgets.IntInput(name="Port", value=5432, width=100)
        self._pg_dbname = pn.widgets.TextInput(name="Database", value="mrna_studio", width=200)
        self._pg_user = pn.widgets.TextInput(name="User", value="demo_user", width=200)
        self._pg_password = pn.widgets.PasswordInput(name="Password", value="demo_pass_2024", width=200)
        self._pg_name = pn.widgets.TextInput(
            name="Connection Name",
            placeholder="demo_db",
            value="demo_db",
            width=200,
        )
        pg_connect_btn = pn.widgets.Button(
            name="Connect",
            button_type="primary",
            width=100,
            margin=(20, 4, 4, 4),
        )
        pg_connect_btn.on_click(self._on_connect)

        pg_form = pn.Column(
            pn.pane.HTML(
                '<div style="font-size:11px;color:#64748B;margin-bottom:8px;">'
                'Enter your PostgreSQL connection details.</div>'
            ),
            pn.Row(self._pg_host, self._pg_port, self._pg_dbname),
            pn.Row(self._pg_user, self._pg_password, self._pg_name),
            pg_connect_btn,
            sizing_mode="stretch_width",
        )

        @param.depends(self._source_select.param.value)
        def _active_form(source: str) -> pn.Column:
            if source == "PostgreSQL":
                return pg_form
            return csv_form

        return pn.Column(
            pn.panel(_active_form),
            self._status_pane,
            sizing_mode="stretch_width",
            styles={
                "background": "#FFFFFF",
                "padding": "16px",
                "border-radius": "8px",
                "border": "1px solid #E2E8F0",
                "margin-bottom": "12px",
            },
        )

    # ── Table selector (PostgreSQL / multi-file) ──────────────────────────────

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
                '<div style="font-size:13px;font-weight:700;margin:4px 0 6px 0;">'
                'Select Table</div>'
            ),
            pn.Row(self._table_select, preview_btn),
        )

    # ── Column mapping form ───────────────────────────────────────────────────

    def _build_mapping_form(self) -> pn.Column:
        if not self._columns:
            return pn.Column()

        # Worklist destination
        default_worklist_name = f"{self._connector.name}.{self._table_select.value}"

        self._wl_mode = pn.widgets.RadioButtonGroup(
            name="Destination",
            options=["New Worklist", "Add to Existing"],
            value="New Worklist",
            button_type="default",
            button_style="outline",
        )

        self._wl_new_name = pn.widgets.TextInput(
            name="Worklist Name",
            value=default_worklist_name,
            placeholder="e.g. My Sequences",
            width=300,
        )

        # Existing worklist selector
        existing_names = []
        if self._state.worklist and self._state.worklist.count > 0:
            existing_names.append(self._state.worklist.name)
        for wl in self._state.worklists:
            if wl.name not in existing_names:
                existing_names.append(wl.name)

        self._wl_existing_select = pn.widgets.Select(
            name="Worklist",
            options=existing_names if existing_names else ["(no worklists yet)"],
            width=300,
        )

        @param.depends(self._wl_mode.param.value)
        def _wl_destination_fields(mode: str) -> pn.Column:
            if mode == "New Worklist":
                return pn.Column(self._wl_new_name)
            return pn.Column(self._wl_existing_select)

        # Column mapping rows
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
                    '<div style="padding-top:8px;font-size:12px;color:#7F8C8D;">'
                    '&rarr;</div>'
                ),
                sel,
            ))

        import_btn = pn.widgets.Button(
            name="Import Records", button_type="success", margin=(12, 0)
        )
        import_btn.on_click(self._on_import)

        return pn.Column(
            pn.pane.HTML(
                '<div style="font-size:13px;font-weight:700;margin:4px 0 6px 0;">'
                'Destination Worklist</div>'
            ),
            self._wl_mode,
            pn.panel(_wl_destination_fields),
            pn.layout.Divider(),
            pn.pane.HTML(
                '<div style="font-size:13px;font-weight:700;margin:4px 0 6px 0;">'
                'Map Columns to mRNA Fields</div>'
            ),
            pn.Column(*rows),
            import_btn,
        )

    # ── Preview table ─────────────────────────────────────────────────────────

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

    # ── Main panel ────────────────────────────────────────────────────────────

    def panel(self) -> pn.Column:
        self._table_section   = pn.Column(sizing_mode="stretch_width")
        self._preview_section = pn.Column(sizing_mode="stretch_width")
        self._mapping_section = pn.Column(sizing_mode="stretch_width")

        return pn.Column(
            pn.pane.HTML(
                '<div style="font-size:16px;font-weight:800;padding:8px 0 4px 0;">'
                'Import Data</div>'
                '<div style="font-size:12px;color:#64748B;margin-bottom:10px;">'
                'Load sequences from a CSV file or PostgreSQL database, '
                'map columns to the mRNA model, and import into a worklist.</div>'
            ),
            self._build_source_selector(),
            self._build_connection_section(),
            self._table_section,
            self._preview_section,
            self._mapping_section,
            sizing_mode="stretch_width",
            styles={"padding": "8px 16px"},
        )

    # ── Section refreshers ────────────────────────────────────────────────────

    def _refresh_table_section(self) -> None:
        self._table_section.clear()
        self._table_section.append(self._build_table_selector())

    def _refresh_preview_section(self) -> None:
        self._preview_section.clear()
        self._preview_section.append(self._build_preview_table())

    def _refresh_mapping_section(self) -> None:
        self._mapping_section.clear()
        self._mapping_section.append(self._build_mapping_form())

    # ── Event handlers ────────────────────────────────────────────────────────

    def _on_connect(self, event: object) -> None:
        t_start = time.perf_counter()
        _log_resources("connect:start")
        source = self._source_select.value

        if source == "PostgreSQL":
            name = self._pg_name.value or f"conn_{len(self._state.db_connections)+1}"
            params = {
                "host": self._pg_host.value,
                "port": self._pg_port.value,
                "dbname": self._pg_dbname.value,
                "user": self._pg_user.value,
                "password": self._pg_password.value,
            }
            backend_key = "postgres"
        else:
            name = self._csv_name.value or "csv_import"
            params = {"path": self._csv_path.value}
            backend_key = "csv"

        config = ConnectionConfig(
            backend=backend_key,
            display_name=name,
            params=params,
        )
        try:
            t0 = time.perf_counter()
            connector = create_connector(config)
            logger.info(f"[PERF] create_connector took {time.perf_counter()-t0:.4f}s")

            t0 = time.perf_counter()
            connector.connect()
            logger.info(f"[PERF] connector.connect() took {time.perf_counter()-t0:.4f}s")

            self._connector = connector
            self._status_pane.object = (
                f'<div style="color:#10B981;font-size:12px;margin-top:4px;">'
                f'&#10003; Connected to {name}</div>'
            )

            t0 = time.perf_counter()
            self._refresh_table_section()
            logger.info(f"[PERF] _refresh_table_section took {time.perf_counter()-t0:.4f}s")

            # Auto-preview the first table for CSV (single-file imports)
            tables = connector.list_tables()
            if backend_key == "csv" and len(tables) == 1:
                self._table_select.value = tables[0]
                self._on_preview(None)

            _log_resources("connect:end")
            logger.info(f"[PERF] Total _on_connect took {time.perf_counter()-t_start:.4f}s")
        except Exception as e:
            self._status_pane.object = (
                f'<div style="color:#EF4444;font-size:12px;margin-top:4px;">'
                f'&#10007; Connection failed: {e}</div>'
            )

    def _on_preview(self, event: object) -> None:
        if not self._connector:
            return
        table = self._table_select.value
        t_start = time.perf_counter()
        _log_resources("preview:start")
        try:
            t0 = time.perf_counter()
            self._preview_df = self._connector.get_records(table, limit=50)
            logger.info(f"[PERF] get_records(limit=50) took {time.perf_counter()-t0:.4f}s, "
                        f"shape={self._preview_df.shape}")
            self._columns = list(self._preview_df.columns)

            t0 = time.perf_counter()
            self._refresh_preview_section()
            logger.info(f"[PERF] _refresh_preview_section took {time.perf_counter()-t0:.4f}s")

            t0 = time.perf_counter()
            self._refresh_mapping_section()
            logger.info(f"[PERF] _refresh_mapping_section took {time.perf_counter()-t0:.4f}s")

            _log_resources("preview:end")
            logger.info(f"[PERF] Total _on_preview took {time.perf_counter()-t_start:.4f}s")
        except Exception as e:
            self._status_pane.object = (
                f'<div style="color:#EF4444;font-size:12px;">'
                f'Preview failed: {e}</div>'
            )

    def _on_import(self, event: object) -> None:
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
                '<div style="color:#EF4444;">Must map at least one column to "name".</div>'
            )
            return

        t_total = time.perf_counter()
        _log_resources("import:start")

        try:
            # Step 1: Fetch records
            t0 = time.perf_counter()
            logger.info(f"[PERF] Starting import from table: {table}")
            df = self._connector.get_records(table)
            logger.info(f"[PERF] get_records() took {time.perf_counter()-t0:.4f}s, "
                        f"{len(df)} records, {df.memory_usage(deep=True).sum()/1024:.1f}KB")

            # Step 2: Schema mapping
            t0 = time.perf_counter()
            mapper = SchemaMapper.from_dict(mapping, db_source=self._connector.name)
            sequences = mapper.map_dataframe(df)
            logger.info(f"[PERF] SchemaMapper.map_dataframe() took {time.perf_counter()-t0:.4f}s, "
                        f"produced {len(sequences)} mRNASequence objects")

            # Step 3: Determine target worklist
            t0 = time.perf_counter()
            from core.models.worklist import Worklist

            add_to_existing = (
                self._wl_mode.value == "Add to Existing"
                and self._wl_existing_select.value
                and self._wl_existing_select.value != "(no worklists yet)"
            )

            if add_to_existing:
                target_name = self._wl_existing_select.value
                # Find the existing worklist
                target_wl = None
                if self._state.worklist and self._state.worklist.name == target_name:
                    target_wl = self._state.worklist
                else:
                    for wl in self._state.worklists:
                        if wl.name == target_name:
                            target_wl = wl
                            break
                if target_wl is None:
                    target_wl = Worklist(name=target_name)
                target_wl.add_many(sequences, origin="import")
                new_worklist = target_wl
            else:
                worklist_name = self._wl_new_name.value or f"{self._connector.name}.{table}"
                new_worklist = Worklist(name=worklist_name)
                new_worklist.add_many(sequences, origin="import")
                target_name = worklist_name
            logger.info(f"[PERF] Worklist creation took {time.perf_counter()-t0:.4f}s")

            # Step 4: Collect parts candidates
            t0 = time.perf_counter()
            from core.models.parts import create_part_from_component
            all_candidates = []
            for seq in sequences:
                for value, part_type, suffix in [
                    (seq.five_prime_utr, "5_utr", "5UTR"),
                    (seq.kozak, "kozak", "Kozak"),
                    (seq.cds, "cds", "CDS"),
                    (seq.three_prime_utr, "3_utr", "3UTR"),
                    (seq.poly_a, "polya", "PolyA"),
                ]:
                    if value:
                        all_candidates.append(create_part_from_component(
                            sequence=value,
                            part_type=part_type,
                            name=f"{seq.name}_{suffix}",
                            source="import",
                            origin_sequence_id=seq.id,
                        ))
            logger.info(f"[PERF] Parts collection took {time.perf_counter()-t0:.4f}s, "
                        f"{len(all_candidates)} candidates")

            # Step 5: Batched state update
            t0 = time.perf_counter()
            import param as pm
            with pn.io.hold():
                with pm.parameterized.batch_call_watchers(self._state):
                    self._state.worklist = new_worklist
                    # Track in worklists list if it's a new worklist
                    if not add_to_existing:
                        worklists = list(self._state.worklists)
                        worklists.append(new_worklist)
                        self._state.worklists = worklists
                        self._state.active_worklist_index = len(worklists) - 1
                    self._state.register_db_connection(self._connector, mapper)
                    total_parts = self._state.add_parts_batch(all_candidates)
                    self._state.active_tab = "worklist"
                    self._state.set_status(
                        f"Imported {len(sequences)} sequences into '{target_name}'. "
                        f"Extracted {total_parts} reusable parts."
                    )
            logger.info(f"[PERF] Batched state update + render took {time.perf_counter()-t0:.4f}s")

            _log_resources("import:end")
            logger.info(f"[PERF] *** Total _on_import took {time.perf_counter()-t_total:.4f}s ***")

            verb = "Added to" if add_to_existing else "Created"
            self._status_pane.object = (
                f'<div style="color:#10B981;font-size:12px;">'
                f'&#10003; {verb} worklist "{target_name}" with {len(sequences)} sequences<br>'
                f'&#10003; Extracted {total_parts} parts to library</div>'
            )
        except Exception as e:
            logger.exception(f"[PERF] Import failed after {time.perf_counter()-t_total:.4f}s")
            self._status_pane.object = (
                f'<div style="color:#EF4444;">Import failed: {e}</div>'
            )

    @staticmethod
    def _auto_suggest(column_name: str) -> str:
        """Guess the target field from common column naming patterns."""
        col = column_name.lower().replace(" ", "_").replace("-", "_")
        exact = {
            "gene_name": "name",
            "name": "name",
            "cds": "cds",
            "kozak": "kozak",
            "poly_a": "poly_a",
            "poly_a_tail": "poly_a",
            "full_mrna": "full_mrna",
            "five_prime_utr": "five_prime_utr",
            "three_prime_utr": "three_prime_utr",
        }
        if col in exact:
            return exact[col]
        hints = {
            "gene": "name",
            "label": "name",
            "utr5": "five_prime_utr",
            "5utr": "five_prime_utr",
            "five_prime": "five_prime_utr",
            "utr3": "three_prime_utr",
            "3utr": "three_prime_utr",
            "three_prime": "three_prime_utr",
            "orf": "cds",
            "coding": "cds",
            "polya": "poly_a",
            "mrna": "full_mrna",
            "sequence": "full_mrna",
            "seq": "full_mrna",
        }
        for hint, field in hints.items():
            if hint in col:
                return field
        return "(skip)"
