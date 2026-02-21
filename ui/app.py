"""
mRNA Design Studio — Panel application entry point.

Uses Panel's FastListTemplate which gives a proper responsive sidebar +
main area that fits the viewport without horizontal overflow.
"""
from __future__ import annotations

import panel as pn
import param

from ui.state import AppState
from ui.components.sidebar import RegistrySidebar
from ui.components.sequence_view import SequenceView
from ui.components.analysis_dashboard import AnalysisDashboard
from ui.components.worklist_view import WorklistView
from ui.components.model_runner import ModelRunnerPanel
from ui.components.db_import import DatabaseImportPanel
from ui.components.plasmid_view import PlasmidView


# ── Design tokens ─────────────────────────────────────────────────────────────
# Shared across all components via this module-level dict.
THEME = {
    "sidebar_bg":      "#0F172A",   # slate-950
    "sidebar_border":  "#1E293B",   # slate-800
    "sidebar_text":    "#94A3B8",   # slate-400
    "sidebar_heading": "#F1F5F9",   # slate-100
    "sidebar_hover":   "#1E293B",   # slate-800
    "sidebar_active_bg": "#312E81", # indigo-900
    "sidebar_active_text": "#A5B4FC", # indigo-300

    "accent":          "#6366F1",   # indigo-500
    "accent_light":    "#818CF8",   # indigo-400
    "success":         "#10B981",   # emerald-500
    "warning":         "#F59E0B",   # amber-500
    "danger":          "#EF4444",   # red-500

    "bg":              "#F8FAFC",   # slate-50
    "card_bg":         "#FFFFFF",
    "card_border":     "#E2E8F0",   # slate-200
    "text_primary":    "#0F172A",   # slate-950
    "text_secondary":  "#64748B",   # slate-500
    "text_muted":      "#94A3B8",   # slate-400

    "component_utr5":  "#3B82F6",   # blue-500
    "component_kozak": "#F59E0B",   # amber-500
    "component_cds":   "#10B981",   # emerald-500
    "component_utr3":  "#8B5CF6",   # violet-500
    "component_polya": "#EF4444",   # red-500
}

_GLOBAL_CSS = f"""
/* Aggressive horizontal overflow prevention for Safari and all browsers */
:root {{
    overflow-x: hidden !important;
    overscroll-behavior: none !important;
    max-width: 100vw !important;
}}
html, body {{
    overflow-x: hidden !important;
    max-width: 100vw !important;
    width: 100%;
    position: relative;
    box-sizing: border-box;
    margin: 0;
    padding: 0;
    -webkit-overflow-scrolling: touch;
}}
*, *::before, *::after {{
    box-sizing: border-box;
    max-width: 100%;
}}
.bk-root {{
    font-family: -apple-system, BlinkMacSystemFont, 'Inter', 'Segoe UI', sans-serif;
    max-width: 100vw !important;
    overflow-x: hidden !important;
}}
/* Prevent all Bokeh containers from overflowing */
.bk, .bk-Canvas, .bk-GridBox, .bk-Row, .bk-Column {{
    max-width: 100% !important;
    overflow-x: hidden !important;
}}
/* Tab styling */
.bk-tab {{
    font-size: 13px;
    font-weight: 600;
    color: {THEME['text_secondary']};
    border-bottom: 2px solid transparent;
    padding: 8px 16px;
    transition: color 0.15s;
}}
.bk-tab.bk-active {{
    color: {THEME['accent']};
    border-bottom: 2px solid {THEME['accent']};
}}
.bk-tab:hover {{
    color: {THEME['accent_light']};
}}
/* Card-style panels */
.studio-card {{
    background: {THEME['card_bg']};
    border: 1px solid {THEME['card_border']};
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 12px;
    max-width: 100%;
}}
/* Scrollable sidebar */
.sidebar-scroll {{
    overflow-y: auto;
    height: calc(100vh - 60px);
    overflow-x: hidden;
}}
"""

pn.extension(
    "plotly",
    "tabulator",
    sizing_mode="stretch_width",
    raw_css=[_GLOBAL_CSS],
)


# ── Tab names & index ─────────────────────────────────────────────────────────
_TAB_NAMES  = ["Worklist", "Parts Workshop"]
_TAB_KEYS   = ["worklist", "parts"]


class StudioApp(param.Parameterized):
    """Root application object — one instance per browser session."""

    def __init__(self, **params: object) -> None:
        super().__init__(**params)
        self.state = AppState()
        self._sidebar_comp  = RegistrySidebar(self.state)
        self._seq_view      = SequenceView(self.state)
        self._analysis      = AnalysisDashboard(self.state)
        self._worklist      = WorklistView(self.state)
        self._models        = ModelRunnerPanel(self.state)
        self._db_import     = DatabaseImportPanel(self.state)
        self._parts         = PlasmidView(self.state)

    # ── Sequence Inspection Modal ─────────────────────────────────────────────

    @param.depends("state.show_sequence_modal", "state.active_sequence")
    def _sequence_modal(self) -> pn.viewable.Viewable:
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Modal render: show={self.state.show_sequence_modal}, seq={self.state.active_sequence}")

        if not self.state.show_sequence_modal or not self.state.active_sequence:
            return pn.Column(visible=False)

        # Close button
        close_btn = pn.widgets.Button(
            name="✕ Close",
            button_type="primary",
            width=100,
        )

        def close_modal(event: object) -> None:
            logger.info("Close button clicked")
            self.state.show_sequence_modal = False

        close_btn.on_click(close_modal)

        # Modal content using Card
        modal = pn.Card(
            pn.panel(self._seq_view.panel),
            title=f"Sequence Inspection: {self.state.active_sequence.name}",
            header=close_btn,
            collapsed=False,
            collapsible=False,
            sizing_mode="stretch_width",
            width=1000,
            styles={"background": "white"},
        )

        return modal

    # ── Database Import Modal ─────────────────────────────────────────────────

    @param.depends("state.show_db_import_modal")
    def _db_import_modal(self) -> pn.viewable.Viewable:
        if not self.state.show_db_import_modal:
            return pn.Column(visible=False)

        # Close button
        close_btn = pn.widgets.Button(
            name="✕ Close",
            button_type="primary",
            width=100,
        )

        def close_modal(event: object) -> None:
            self.state.show_db_import_modal = False

        close_btn.on_click(close_modal)

        # Modal content using Card
        modal = pn.Card(
            pn.panel(self._db_import.panel),
            title="Import Database",
            header=close_btn,
            collapsed=False,
            collapsible=False,
            sizing_mode="stretch_width",
            width=900,
            styles={"background": "white"},
        )

        return modal

    # ── Status bar ────────────────────────────────────────────────────────────

    @param.depends("state.status_message")
    def _status_bar(self) -> pn.pane.HTML:
        msg = self.state.status_message
        if not msg:
            return pn.pane.HTML("", height=0, margin=0)
        return pn.pane.HTML(
            f'<div style="background:{THEME["success"]};color:white;'
            f'font-size:12px;padding:6px 16px;border-radius:4px;margin:4px 0;">'
            f'✓ {msg}</div>',
            sizing_mode="stretch_width",
            margin=(0, 0, 4, 0),
        )

    # ── Main tabs ─────────────────────────────────────────────────────────────

    @param.depends("state.active_tab")
    def _main_tabs(self) -> pn.Tabs:
        active_idx = _TAB_KEYS.index(self.state.active_tab) if self.state.active_tab in _TAB_KEYS else 0

        tabs = pn.Tabs(
            (_TAB_NAMES[0], pn.Column(
                pn.panel(self._status_bar),
                pn.panel(self._worklist.panel),
                pn.panel(self._sequence_modal),
                pn.panel(self._db_import_modal),
                sizing_mode="stretch_width",
            )),
            (_TAB_NAMES[1], pn.panel(self._parts.panel)),
            active=active_idx,
            sizing_mode="stretch_width",
        )

        def _sync_tab(event: object) -> None:
            if hasattr(event, "new") and 0 <= event.new < len(_TAB_KEYS):
                self.state.active_tab = _TAB_KEYS[event.new]

        tabs.param.watch(_sync_tab, "active")
        return tabs

    # ── Template ──────────────────────────────────────────────────────────────

    def build_template(self) -> pn.template.FastListTemplate:
        template = pn.template.FastListTemplate(
            title="mRNA Design Studio",
            sidebar=[pn.panel(self._sidebar_comp.panel)],
            sidebar_width=240,
            header_background=THEME["sidebar_bg"],
            accent_base_color=THEME["accent"],
            theme_toggle=False,
        )
        template.main.append(pn.Column(
            pn.panel(self._main_tabs),
            sizing_mode="stretch_width",
            styles={"overflow-x": "hidden"},
        ))
        return template


def create_app() -> pn.template.FastListTemplate:
    return StudioApp().build_template()


def main() -> None:
    pn.serve(
        create_app,
        port=5007,
        autoreload=True,
        title="mRNA Design Studio",
        show=True,
        websocket_origin="*",
    )


if __name__ == "__main__":
    main()
