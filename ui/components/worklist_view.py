"""
Worklist panel.

Displays the worklist as a sortable table with scoring results.
Users can add sequences from the registry, remove items, run analysis,
select rows to create new worklists, and export as CSV.
"""
from __future__ import annotations

import io
import logging
from typing import TYPE_CHECKING, List

import pandas as pd
import panel as pn
import param

if TYPE_CHECKING:
    from ui.state import AppState
    from ui.components.analysis_settings import AnalysisSettingsPanel

logger = logging.getLogger(__name__)


class WorklistView(param.Parameterized):
    """Worklist management panel."""

    def __init__(self, state: "AppState", **params: object) -> None:
        super().__init__(**params)
        self._state = state
        self._table_widget = None
        self._create_wl_section = pn.Column(visible=False, sizing_mode="stretch_width")
        self._settings_visible = False
        self._settings_section = pn.Column(visible=False, sizing_mode="stretch_width")
        # Lazy-init settings panel on first toggle
        self._settings_panel: "AnalysisSettingsPanel | None" = None

    def _to_dataframe(self) -> pd.DataFrame:
        wl = self._state.worklist
        rows = []
        for item in wl.items:
            seq = item.sequence
            row = {
                "id": item.id,
                "Name": seq.name,
                "Source": seq.source,
                "Length (nt)": seq.length,
                "Origin": item.origin,
            }

            # Add base analysis metrics if available
            if "base_analysis" in item.analyses:
                base = item.analyses["base_analysis"]
                row["GC%"] = f"{base.get('gc_content', 0):.1f}" if base.get('gc_content') else "—"
                row["CAI"] = f"{base.get('cai', 0):.3f}" if base.get('cai') else "—"
                row["Homopolymers"] = base.get('homopolymer_count', 0)
                row["Restriction Sites"] = base.get('restriction_site_count', 0)
            else:
                row["GC%"] = "—"
                row["CAI"] = "—"
                row["Homopolymers"] = "—"
                row["Restriction Sites"] = "—"

            # Add model score columns from analyses
            for analysis_name, analysis_data in item.analyses.items():
                if analysis_name != "base_analysis" and isinstance(analysis_data, dict) and "score" in analysis_data:
                    row[analysis_name] = f"{analysis_data['score']:.1f}"

            row["Notes"] = item.notes or ""
            rows.append(row)
        return pd.DataFrame(rows) if rows else pd.DataFrame(
            columns=["Name", "Source", "Length (nt)", "Origin", "GC%", "CAI"]
        )

    @param.depends("_state.worklist", "_state.model_registry")
    def panel(self) -> pn.Column:
        wl = self._state.worklist
        df = self._to_dataframe()

        # Toolbar
        export_btn = pn.widgets.FileDownload(
            callback=lambda: self._make_csv(),
            filename=f"{wl.name.replace(' ', '_')}_export.csv",
            button_type="light",
            label="Export CSV",
            margin=(4, 4),
        )

        # Build analysis options: base analysis + loaded models + "Run All"
        analysis_options = ["Base Analysis"]

        # Add loaded scoring models
        if self._state.model_registry:
            for model_reg in self._state.model_registry.scoring_models:
                analysis_options.append(model_reg.model.name)

        analysis_options.append("Run All Analyses")

        analysis_select = pn.widgets.Select(
            name="Analysis",
            options=analysis_options,
            value="Base Analysis",
            width=180,
            margin=(4, 4),
        )

        run_analysis_btn = pn.widgets.Button(
            name="Run",
            button_type="success",
            width=80,
            margin=(4, 4),
        )
        run_analysis_btn.on_click(lambda event: self._run_selected_analysis(analysis_select.value))

        # Analysis settings gear button
        settings_btn = pn.widgets.Button(
            name="Settings",
            button_type="light",
            width=70,
            margin=(4, 0),
            stylesheets=["""
                :host .bk-btn {
                    font-size: 11px;
                    padding: 4px;
                    border-radius: 4px;
                }
            """],
        )
        def _open_settings(e):
            self._settings_visible = not self._settings_visible
            if self._settings_visible and self._settings_panel is None:
                from ui.components.analysis_settings import AnalysisSettingsPanel
                self._settings_panel = AnalysisSettingsPanel(self._state)
                self._settings_section.append(self._settings_panel.panel())
            self._settings_section.visible = self._settings_visible
        settings_btn.on_click(_open_settings)

        # Create worklist from selection button
        create_wl_btn = pn.widgets.Button(
            name="Create Worklist from Selection",
            button_type="light",
            width=220,
            margin=(4, 4),
            stylesheets=["""
                :host .bk-btn {
                    font-size: 11px;
                    color: #0D9488;
                    border: 1px solid #0D9488;
                    border-radius: 4px;
                }
                :host .bk-btn:hover {
                    background: #F0FDFA;
                }
            """],
        )

        toolbar = pn.Row(
            pn.pane.HTML(
                f'<div style="font-size:16px;font-weight:800;padding:8px 0;">'
                f'{wl.name} <span style="color:#64748B;font-size:13px;">({wl.count} items)</span></div>'
            ),
            pn.layout.HSpacer(),
            create_wl_btn,
            analysis_select,
            run_analysis_btn,
            settings_btn,
            export_btn,
            sizing_mode="stretch_width",
        )

        # Create worklist inline form
        self._create_wl_section = pn.Column(visible=False, sizing_mode="stretch_width")
        wl_name_input = pn.widgets.TextInput(
            name="New Worklist Name",
            value=f"Selection from {wl.name}",
            width=300,
            margin=(4, 4),
        )
        create_confirm_btn = pn.widgets.Button(name="Create", button_type="success", width=80, margin=(4, 4))
        create_cancel_btn = pn.widgets.Button(name="Cancel", button_type="light", width=80, margin=(4, 4))

        self._create_wl_section.extend([
            pn.Row(
                wl_name_input,
                create_confirm_btn,
                create_cancel_btn,
                sizing_mode="stretch_width",
                styles={"background": "#F0FDFA", "padding": "8px", "border-radius": "6px", "margin": "4px 0"},
            ),
        ])

        if wl.count == 0:
            table_or_empty: pn.viewable.Viewable = pn.pane.HTML(
                '<div style="color:#64748B;padding:30px;text-align:center;">'
                'Worklist is empty. Import sequences from a database to get started.</div>'
            )
            create_wl_btn.visible = False
        else:
            # Create table with checkbox selection
            row_height = 35
            header_height = 40
            calculated_height = min(len(df) * row_height + header_height, 500)

            table_widget = pn.widgets.Tabulator(
                df,
                hidden_columns=["id"],
                sizing_mode="stretch_width",
                show_index=False,
                height=calculated_height,
                selectable="checkbox",
                page_size=20,
                editors={col: None for col in df.columns},
            )
            self._table_widget = table_widget

            # Handle row click for inspection
            def on_row_click(event: object) -> None:
                logger.info(f"Row click event fired: {event}")
                if event.row is not None:
                    row_data = df.iloc[event.row]
                    item_id = row_data["id"]
                    item = next((i for i in wl.items if i.id == item_id), None)
                    if item:
                        self._state.active_sequence = item.sequence
                        logger.debug("Row clicked: %s", item.sequence.name)

            table_widget.on_click(on_row_click)

            # Create worklist button handler
            def on_create_wl(event):
                self._create_wl_section.visible = True

            create_wl_btn.on_click(on_create_wl)

            def on_create_confirm(event):
                self._create_worklist_from_selection(
                    wl_name_input.value,
                    table_widget.selection,
                    df,
                )
                self._create_wl_section.visible = False

            def on_create_cancel(event):
                self._create_wl_section.visible = False

            create_confirm_btn.on_click(on_create_confirm)
            create_cancel_btn.on_click(on_create_cancel)

            table_or_empty = table_widget

        # Origin summary chips
        origin_counts = df["Origin"].value_counts() if "Origin" in df.columns else {}
        origin_chips = " ".join(
            f'<span style="background:#2C3E50;color:white;border-radius:3px;'
            f'padding:2px 8px;font-size:11px;margin:2px;">{k}: {v}</span>'
            for k, v in origin_counts.items()
        )

        return pn.Column(
            toolbar,
            self._settings_section,
            self._create_wl_section,
            pn.pane.HTML(f'<div style="margin-bottom:8px;">{origin_chips}</div>') if origin_chips else pn.pane.HTML(""),
            table_or_empty,
            sizing_mode="stretch_width",
            styles={"padding": "8px 16px"},
        )

    def _create_worklist_from_selection(self, name: str, selection: List[int], df: pd.DataFrame) -> None:
        """Create a new worklist from selected rows."""
        if not selection:
            self._state.set_status("No rows selected. Use checkboxes to select sequences.")
            return

        from core.models.worklist import Worklist

        wl = self._state.worklist
        new_wl = Worklist(name=name or f"Selection ({len(selection)} items)")

        for idx in selection:
            if 0 <= idx < len(df):
                item_id = df.iloc[idx]["id"]
                item = next((i for i in wl.items if i.id == item_id), None)
                if item:
                    new_wl.add(item.sequence, origin=item.origin)

        # Add to worklists list
        worklists = list(self._state.worklists)
        if not worklists:
            # Add current worklist first
            worklists.append(wl)
        worklists.append(new_wl)
        self._state.worklists = worklists
        self._state.active_worklist_index = len(worklists) - 1
        self._state.worklist = new_wl
        self._state.set_status(f"Created worklist '{name}' with {new_wl.count} sequences")

    def _make_csv(self) -> io.BytesIO:
        """Build CSV bytes for the FileDownload widget."""
        df = self._to_dataframe().drop(columns=["id"], errors="ignore")
        buf = io.BytesIO()
        df.to_csv(buf, index=False)
        buf.seek(0)
        return buf

    def _run_selected_analysis(self, analysis_name: str) -> None:
        """Run the selected analysis on all sequences that haven't been analyzed yet."""
        logger.info(f"Running analysis: {analysis_name}")

        if analysis_name == "Run All Analyses":
            self._run_base_analysis()
            for model_reg in self._state.model_registry.scoring_models:
                self._run_model_analysis(model_reg.model.name)
        elif analysis_name == "Base Analysis":
            self._run_base_analysis()
        else:
            self._run_model_analysis(analysis_name)

    def _run_base_analysis(self) -> None:
        """Run base analysis on sequences that haven't been analyzed, using current settings."""
        from core.analysis.analyzer import SequenceAnalyzer

        # Get settings from state
        settings = self._state.analysis_settings or {}

        # Build analyzer with settings
        analyzer = SequenceAnalyzer(
            gc_window=settings.get("gc_window", 100),
            gc_step=settings.get("gc_step", 1),
            homopolymer_min_run=settings.get("homopolymer_min_run", 5),
            restriction_enzymes=settings.get("restriction_enzymes"),
            cai_organism=settings.get("cai_organism", "human").lower().replace(" ", "").replace(".", ""),
        )

        analyzed_count = 0
        skipped_count = 0

        for item in self._state.worklist.items:
            if "base_analysis" in item.analyses:
                skipped_count += 1
                continue

            try:
                report = analyzer.run_full_analysis(item.sequence)
                item.analyses["base_analysis"] = report.to_dict()
                analyzed_count += 1
            except Exception as e:
                item.status = "error"
                item.notes = str(e)

        self._state.param.trigger("worklist")
        self._state.set_status(
            f"Base analysis complete: {analyzed_count} analyzed, {skipped_count} skipped (already analyzed)"
        )

    def _run_model_analysis(self, model_name: str) -> None:
        """Run a scoring model on sequences that haven't been scored by this model."""
        analyzed_count = 0
        skipped_count = 0

        model_reg = next(
            (m for m in self._state.model_registry.all_models if m.model.name == model_name),
            None
        )

        if not model_reg:
            self._state.set_status(f"Model '{model_name}' not found")
            return

        for item in self._state.worklist.items:
            if model_name in item.analyses:
                skipped_count += 1
                continue

            try:
                score = model_reg.model.score(item.sequence)
                item.analyses[model_name] = {"score": score}
                analyzed_count += 1
            except Exception as e:
                item.status = "error"
                item.notes = f"{model_name}: {str(e)}"

        self._state.param.trigger("worklist")
        self._state.set_status(
            f"{model_name} complete: {analyzed_count} scored, {skipped_count} skipped (already scored)"
        )
