"""
mRNA Design Studio — Panel application entry point.

Uses Panel's FastListTemplate which gives a proper responsive sidebar +
main area that fits the viewport without horizontal overflow.
"""
from __future__ import annotations

import logging
import sys

import panel as pn
import param

# ── Logging configuration ─────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stderr,
)

from ui.state import AppState
from ui.components.sidebar import RegistrySidebar
from ui.components.sequence_view import SequenceView
from ui.components.analysis_dashboard import AnalysisDashboard
from ui.components.worklist_view import WorklistView
from ui.components.model_runner import ModelRunnerPanel
from ui.components.db_import import DatabaseImportPanel
from ui.components.plasmid_view import PlasmidView
from ui.components.model_repository import ModelRepositoryPanel
from ui.components.plasmid_assembly import PlasmidAssemblyPanel
from ui.components.generate_sequences import GenerateSequencesPanel
from ui.components.analysis_settings import AnalysisSettingsPanel


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
_TAB_NAMES  = ["Worklist", "Parts Workshop", "Assemble Plasmid", "Generate Sequences"]
_TAB_KEYS   = ["worklist", "parts", "assemble", "generate"]


logger = logging.getLogger(__name__)


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
        self._model_repo    = ModelRepositoryPanel(self.state)
        self._assembly      = PlasmidAssemblyPanel(self.state)
        self._generate      = GenerateSequencesPanel(self.state)
        self._analysis_settings = AnalysisSettingsPanel(self.state)

        # ── Build persistent widgets once ─────────────────────────────────────
        self._status_html = pn.pane.HTML("", height=0, margin=0, sizing_mode="stretch_width")

        # Modal containers — simple visibility toggle, no CSS overlay tricks
        self._seq_modal_container = pn.Column(visible=False, sizing_mode="stretch_width")
        self._db_modal_container = pn.Column(visible=False, sizing_mode="stretch_width")
        self._model_modal_container = pn.Column(visible=False, sizing_mode="stretch_width")
        self._settings_modal_container = pn.Column(visible=False, sizing_mode="stretch_width")

        # Modals sit above tab content — they're only visible when open, so
        # on other tabs they collapse to zero height (visible=False).
        self._modal_layer = pn.Column(
            self._seq_modal_container,
            self._db_modal_container,
            self._model_modal_container,
            self._settings_modal_container,
            sizing_mode="stretch_width",
            margin=0,
        )

        self._tabs = pn.Tabs(
            (_TAB_NAMES[0], pn.Column(
                self._status_html,
                pn.panel(self._worklist.panel),
                sizing_mode="stretch_width",
            )),
            (_TAB_NAMES[1], pn.panel(self._parts.panel)),
            (_TAB_NAMES[2], pn.panel(self._assembly.panel)),
            (_TAB_NAMES[3], pn.panel(self._generate.panel)),
            active=0,
            sizing_mode="stretch_width",
        )

        # ── Wire up watchers (update in place, no widget rebuilds) ────────────
        self.state.param.watch(self._on_active_tab_changed, "active_tab")
        self._tabs.param.watch(self._on_tab_widget_changed, "active")
        self.state.param.watch(self._on_status_changed, "status_message")
        self.state.param.watch(self._on_seq_modal_changed, ["show_sequence_modal", "active_sequence"])
        self.state.param.watch(self._on_db_modal_changed, "show_db_import_modal")
        self.state.param.watch(self._on_model_modal_changed, "show_model_repo_modal")
        self.state.param.watch(self._on_settings_modal_changed, "show_analysis_settings_modal")

    # ── Tab sync (update .active property, no rebuild) ────────────────────────

    def _on_active_tab_changed(self, event: param.parameterized.Event) -> None:
        idx = _TAB_KEYS.index(event.new) if event.new in _TAB_KEYS else 0
        if self._tabs.active != idx:
            self._tabs.active = idx

    def _on_tab_widget_changed(self, event: param.parameterized.Event) -> None:
        if hasattr(event, "new") and 0 <= event.new < len(_TAB_KEYS):
            key = _TAB_KEYS[event.new]
            if self.state.active_tab != key:
                self.state.active_tab = key

    # ── Status bar (update HTML in place) ─────────────────────────────────────

    def _on_status_changed(self, event: param.parameterized.Event) -> None:
        msg = event.new
        if not msg:
            self._status_html.object = ""
            self._status_html.height = 0
        else:
            self._status_html.object = (
                f'<div style="background:{THEME["success"]};color:white;'
                f'font-size:12px;padding:6px 16px;border-radius:4px;margin:4px 0;">'
                f'✓ {msg}</div>'
            )
            self._status_html.height = None

    # ── Modals (toggle visibility on persistent containers) ───────────────────

    def _on_seq_modal_changed(self, *events: param.parameterized.Event) -> None:
        show = self.state.show_sequence_modal and self.state.active_sequence is not None
        if show:
            close_btn = pn.widgets.Button(name="✕ Close", button_type="primary", width=100)
            close_btn.on_click(lambda e: setattr(self.state, "show_sequence_modal", False))
            modal = pn.Card(
                pn.panel(self._seq_view.panel),
                title=f"Sequence Inspection: {self.state.active_sequence.name}",
                header=close_btn,
                collapsed=False, collapsible=False,
                min_width=1000, styles={"background": "white"},
            )
            self._seq_modal_container.clear()
            self._seq_modal_container.append(modal)
            self._seq_modal_container.visible = True
        else:
            self._seq_modal_container.visible = False

    def _on_db_modal_changed(self, event: param.parameterized.Event) -> None:
        if event.new:
            close_btn = pn.widgets.Button(name="✕ Close", button_type="primary", width=100)
            close_btn.on_click(lambda e: setattr(self.state, "show_db_import_modal", False))
            modal = pn.Card(
                pn.panel(self._db_import.panel),
                title="Import Database",
                header=close_btn,
                collapsed=False, collapsible=False,
                min_width=900, styles={"background": "white"},
            )
            self._db_modal_container.clear()
            self._db_modal_container.append(modal)
            self._db_modal_container.visible = True
        else:
            self._db_modal_container.visible = False

    def _on_model_modal_changed(self, event: param.parameterized.Event) -> None:
        if event.new:
            close_btn = pn.widgets.Button(name="✕ Close", button_type="primary", width=100)
            close_btn.on_click(lambda e: setattr(self.state, "show_model_repo_modal", False))
            modal = pn.Card(
                self._model_repo.panel(),
                title="Model Repository",
                header=close_btn,
                collapsed=False, collapsible=False,
                min_width=1000, styles={"background": "white"},
            )
            self._model_modal_container.clear()
            self._model_modal_container.append(modal)
            self._model_modal_container.visible = True
        else:
            self._model_modal_container.visible = False

    def _on_settings_modal_changed(self, event: param.parameterized.Event) -> None:
        if event.new:
            close_btn = pn.widgets.Button(name="✕ Close", button_type="primary", width=100)
            close_btn.on_click(lambda e: setattr(self.state, "show_analysis_settings_modal", False))
            modal = pn.Card(
                self._analysis_settings.panel(),
                title="Analysis Settings",
                header=close_btn,
                collapsed=False, collapsible=False,
                min_width=900, styles={"background": "white"},
            )
            self._settings_modal_container.clear()
            self._settings_modal_container.append(modal)
            self._settings_modal_container.visible = True
        else:
            self._settings_modal_container.visible = False

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
            self._modal_layer,
            self._tabs,
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
