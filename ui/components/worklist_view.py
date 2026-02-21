"""
Worklist panel.

Displays the worklist as a sortable table with scoring results.
Users can add sequences from the registry, remove items, run analysis,
and export the worklist as CSV.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd
import panel as pn
import param

if TYPE_CHECKING:
    from ui.state import AppState

logger = logging.getLogger(__name__)


class WorklistView(param.Parameterized):
    """Worklist management panel."""

    def __init__(self, state: "AppState", **params: object) -> None:
        super().__init__(**params)
        self._state = state

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
                "Status": item.status,
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
            columns=["Name", "Source", "Length (nt)", "Origin", "Status", "GC%", "CAI"]
        )

    @param.depends("_state.worklist", "_state.model_registry")
    def panel(self) -> pn.Column:
        wl = self._state.worklist
        df = self._to_dataframe()

        # Toolbar
        export_btn = pn.widgets.Button(name="Export CSV", button_type="light", margin=(4, 4))
        export_btn.on_click(self._export_csv)

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
            name="▶ Run",
            button_type="success",
            width=80,
            margin=(4, 4),
        )
        run_analysis_btn.on_click(lambda event: self._run_selected_analysis(analysis_select.value))

        toolbar = pn.Row(
            pn.pane.HTML(
                f'<div style="font-size:16px;font-weight:800;padding:8px 0;">'
                f'{wl.name} <span style="color:#7F8C8D;font-size:13px;">({wl.count} items)</span></div>'
            ),
            pn.layout.HSpacer(),
            analysis_select,
            run_analysis_btn,
            export_btn,
            sizing_mode="stretch_width",
        )

        if wl.count == 0:
            table_or_empty: pn.viewable.Viewable = pn.pane.HTML(
                '<div style="color:#7F8C8D;padding:30px;text-align:center;">'
                'Worklist is empty. Import sequences from a database to get started.</div>'
            )
        else:
            # Create table with row click handler (no editing)
            # Dynamic height based on number of rows (max 500px)
            row_height = 35  # approximate height per row
            header_height = 40
            calculated_height = min(len(df) * row_height + header_height, 500)

            table_widget = pn.widgets.Tabulator(
                df,
                hidden_columns=["id"],
                sizing_mode="stretch_width",
                show_index=False,
                height=calculated_height,
                selectable=False,
                page_size=20,
                editors={col: None for col in df.columns},  # Disable all editors
            )

            # Handle row click - click anywhere on the row to inspect
            def on_row_click(event: object) -> None:
                logger.info(f"Row click event fired: {event}")
                logger.info(f"Event row: {getattr(event, 'row', 'NO ROW ATTR')}")
                if event.row is not None:
                    # Get the item ID from the clicked row
                    row_data = df.iloc[event.row]
                    item_id = row_data["id"]
                    logger.info(f"Item ID: {item_id}")
                    # Find the item and set active sequence
                    item = next((i for i in wl.items if i.id == item_id), None)
                    if item:
                        logger.info(f"Setting active sequence: {item.sequence.name}")
                        self._state.active_sequence = item.sequence
                        self._state.show_sequence_modal = True
                        logger.info(f"Modal state set to: {self._state.show_sequence_modal}")
                    else:
                        logger.warning(f"No item found for ID: {item_id}")
                else:
                    logger.warning("Event row is None")

            table_widget.on_click(on_row_click)
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
            pn.pane.HTML(f'<div style="margin-bottom:8px;">{origin_chips}</div>') if origin_chips else pn.pane.HTML(""),
            table_or_empty,
            sizing_mode="stretch_width",
            styles={"padding": "8px 16px"},
        )

    def _export_csv(self, event: object) -> None:
        df = self._to_dataframe().drop(columns=["id"], errors="ignore")
        path = "worklist_export.csv"
        df.to_csv(path, index=False)
        self._state.set_status(f"Worklist exported to {path}")

    def _run_selected_analysis(self, analysis_name: str) -> None:
        """Run the selected analysis on all sequences that haven't been analyzed yet."""
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Running analysis: {analysis_name}")

        if analysis_name == "Run All Analyses":
            # Run all available analyses
            self._run_base_analysis()
            for model_reg in self._state.model_registry.scoring_models:
                self._run_model_analysis(model_reg.model.name)
        elif analysis_name == "Base Analysis":
            self._run_base_analysis()
        else:
            # It's a model name
            self._run_model_analysis(analysis_name)

    def _run_base_analysis(self) -> None:
        """Run base analysis on sequences that haven't been analyzed."""
        from core.analysis.analyzer import SequenceAnalyzer
        analyzer = SequenceAnalyzer()

        analyzed_count = 0
        skipped_count = 0

        for item in self._state.worklist.items:
            # Skip if already analyzed
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

        # Get the model from registry
        model_reg = next(
            (m for m in self._state.model_registry.all_models if m.model.name == model_name),
            None
        )

        if not model_reg:
            self._state.set_status(f"Model '{model_name}' not found")
            return

        for item in self._state.worklist.items:
            # Skip if already scored by this model
            if model_name in item.analyses:
                skipped_count += 1
                continue

            try:
                score = model_reg.model.score(item.sequence)
                # Store as a dict with the score
                item.analyses[model_name] = {"score": score}
                analyzed_count += 1
            except Exception as e:
                item.status = "error"
                item.notes = f"{model_name}: {str(e)}"

        self._state.param.trigger("worklist")
        self._state.set_status(
            f"{model_name} complete: {analyzed_count} scored, {skipped_count} skipped (already scored)"
        )
