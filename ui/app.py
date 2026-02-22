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
from ui.components.worklist_view import WorklistView
from ui.components.db_import import DatabaseImportPanel
from ui.components.plasmid_view import PlasmidView
from ui.components.model_repository import ModelRepositoryPanel
from ui.components.plasmid_assembly import PlasmidAssemblyPanel
from ui.components.generate_sequences import GenerateSequencesPanel


# ── Design tokens ─────────────────────────────────────────────────────────────
THEME = {
    "sidebar_bg":      "#0B1120",   # deep navy
    "sidebar_border":  "#1A2332",   # dark navy border
    "sidebar_text":    "#8899AA",   # cool gray text
    "sidebar_heading": "#E8EDF2",   # near-white heading
    "sidebar_hover":   "#162032",   # subtle hover
    "sidebar_active_bg": "#0F3D3E", # dark teal selection
    "sidebar_active_text": "#5EEAD4", # teal-300

    "accent":          "#0D9488",   # teal-600 — primary science accent
    "accent_light":    "#14B8A6",   # teal-500
    "success":         "#059669",   # emerald-600
    "warning":         "#D97706",   # amber-600
    "danger":          "#DC2626",   # red-600

    "bg":              "#F1F5F9",   # slate-100
    "card_bg":         "#FFFFFF",
    "card_border":     "#CBD5E1",   # slate-300
    "text_primary":    "#0F172A",   # slate-950
    "text_secondary":  "#475569",   # slate-600
    "text_muted":      "#64748B",   # slate-500

    "component_utr5":  "#0284C7",   # sky-600
    "component_kozak": "#D97706",   # amber-600
    "component_cds":   "#059669",   # emerald-600
    "component_utr3":  "#7C3AED",   # violet-600
    "component_polya": "#DC2626",   # red-600
}

_GLOBAL_CSS = f"""
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
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', sans-serif;
    max-width: 100vw !important;
    overflow-x: hidden !important;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
}}
.bk, .bk-Canvas, .bk-GridBox, .bk-Row, .bk-Column {{
    max-width: 100% !important;
    overflow-x: hidden !important;
}}
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
.studio-card {{
    background: {THEME['card_bg']};
    border: 1px solid {THEME['card_border']};
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 12px;
    max-width: 100%;
}}
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
    notifications=True,
)


# ── Tab names & index ─────────────────────────────────────────────────────────
_TAB_NAMES = [
    "Import Data",
    "Model Repository",
    "Worklist",
    "Parts Workshop",
    "Assemble Plasmid",
    "Generate Sequences",
]
_TAB_KEYS = ["import_db", "model_repo", "worklist", "parts", "assemble", "generate"]


logger = logging.getLogger(__name__)


class StudioApp(param.Parameterized):
    """Root application object — one instance per browser session."""

    def __init__(self, **params: object) -> None:
        super().__init__(**params)
        self.state = AppState()
        self._sidebar_comp  = RegistrySidebar(self.state)
        self._worklist      = WorklistView(self.state)
        self._db_import     = DatabaseImportPanel(self.state)
        self._parts         = PlasmidView(self.state)
        self._model_repo    = ModelRepositoryPanel(self.state)
        self._assembly      = PlasmidAssemblyPanel(self.state)
        self._generate      = GenerateSequencesPanel(self.state)

        # ── Build persistent widgets once ─────────────────────────────────────
        self._tabs = pn.Tabs(
            (_TAB_NAMES[0], pn.Column(
                self._db_import.panel(),
                sizing_mode="stretch_width",
            )),
            (_TAB_NAMES[1], pn.Column(
                self._model_repo.panel(),
                sizing_mode="stretch_width",
            )),
            (_TAB_NAMES[2], pn.Column(
                pn.panel(self._worklist.panel),
                sizing_mode="stretch_width",
            )),
            (_TAB_NAMES[3], pn.panel(self._parts.panel)),
            (_TAB_NAMES[4], pn.panel(self._assembly.panel)),
            (_TAB_NAMES[5], pn.panel(self._generate.panel)),
            active=0,
            sizing_mode="stretch_width",
        )

        # ── Wire up watchers ──────────────────────────────────────────────────
        self.state.param.watch(self._on_active_tab_changed, "active_tab")
        self._tabs.param.watch(self._on_tab_widget_changed, "active")

    # ── Tab sync ──────────────────────────────────────────────────────────────

    def _on_active_tab_changed(self, event: param.parameterized.Event) -> None:
        idx = _TAB_KEYS.index(event.new) if event.new in _TAB_KEYS else 0
        if self._tabs.active != idx:
            self._tabs.active = idx

    def _on_tab_widget_changed(self, event: param.parameterized.Event) -> None:
        if hasattr(event, "new") and 0 <= event.new < len(_TAB_KEYS):
            key = _TAB_KEYS[event.new]
            if self.state.active_tab != key:
                self.state.active_tab = key

    # ── Template ──────────────────────────────────────────────────────────────

    def build_template(self) -> pn.template.FastListTemplate:
        template = pn.template.FastListTemplate(
            title="mRNA Design Studio",
            sidebar=[pn.panel(self._sidebar_comp.panel)],
            sidebar_width=250,
            header_background=THEME["sidebar_bg"],
            accent_base_color=THEME["accent"],
            theme_toggle=False,
        )
        template.main.append(pn.Column(
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
