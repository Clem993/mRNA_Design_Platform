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
    "Import Database",
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
            sidebar_width=240,
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
