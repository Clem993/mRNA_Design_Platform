"""
mRNA Design Studio — Panel application entry point.

Uses Panel's FastListTemplate which gives a proper responsive sidebar +
main area that fits the viewport without horizontal overflow.

Password protection
-------------------
Set the ``MRNA_STUDIO_PASSWORD`` environment variable (or add it to a
``.env`` file) to require a password before anyone can access the app.
Optionally set ``MRNA_STUDIO_USERS`` to a JSON object mapping usernames
to passwords, e.g. ``{"alice": "pw1", "bob": "pw2"}``.
"""
from __future__ import annotations

import json
import logging
import os
import sys

import panel as pn
import param
from dotenv import load_dotenv

load_dotenv()  # read .env if present

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
    "sidebar_bg":      "#FFFFFF",   # white
    "sidebar_border":  "#E2E8F0",   # slate-200 border
    "sidebar_text":    "#334155",   # slate-700 — readable on white
    "sidebar_heading": "#0F172A",   # slate-950 heading
    "sidebar_hover":   "#F8FAFC",   # slate-50 hover
    "sidebar_active_bg": "#F0FDFA", # teal-50 selection
    "sidebar_active_text": "#0F766E", # teal-600 on white

    "accent":          "#0F766E",   # teal-700 — dark enough for white text on accent
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
#header .app-header a.title {{
    font-size: 15px !important;
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


# ── Logo (white DNA double-helix SVG, base64-encoded) ────────────────────────
_DNA_LOGO = (
    "data:image/svg+xml;base64,"
    "PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAzMiA2"
    "NCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjZmZmIiBzdHJva2Utd2lkdGg9IjIuMiIgc3Ryb2tlLWxp"
    "bmVjYXA9InJvdW5kIj48cGF0aCBkPSJNOCA0QzggMjAgMjQgMjAgMjQgMzJTOCA0NCA4IDYwIi8+"
    "PHBhdGggZD0iTTI0IDRDMjQgMjAgOCAyMCA4IDMyUzI0IDQ0IDI0IDYwIi8+PGxpbmUgeDE9IjgiIH"
    "kxPSIxNiIgeDI9IjI0IiB5Mj0iMTYiLz48bGluZSB4MT0iOCIgeTE9IjMyIiB4Mj0iMjQiIHkyPS"
    "IzMiIvPjxsaW5lIHgxPSI4IiB5MT0iNDgiIHgyPSIyNCIgeTI9IjQ4Ii8+PC9zdmc+Cg=="
)


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
            logo=_DNA_LOGO,
            sidebar=[pn.panel(self._sidebar_comp.panel)],
            sidebar_width=250,
            header_background="#0F172A",
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


def _get_auth_config() -> dict:
    """Build Panel basic-auth config from environment variables.

    Priority:
      1. ``MRNA_STUDIO_USERS`` — JSON ``{"user": "pass", …}``
      2. ``MRNA_STUDIO_PASSWORD`` — single shared password (username can
         be anything)
      3. Neither set → no auth (open access)
    """
    users_json = os.environ.get("MRNA_STUDIO_USERS", "").strip()
    if users_json:
        try:
            return json.loads(users_json)
        except json.JSONDecodeError:
            logger.warning("MRNA_STUDIO_USERS is not valid JSON — falling back")

    password = os.environ.get("MRNA_STUDIO_PASSWORD", "").strip()
    if password:
        # Panel accepts a plain string as "any-username + this password"
        return password

    return {}


def main() -> None:
    port = int(os.environ.get("PORT", 5007))          # Railway/Render set $PORT
    host = os.environ.get("HOST", "0.0.0.0")           # bind to all interfaces in containers
    auth = _get_auth_config()

    serve_kwargs: dict = dict(
        port=port,
        address=host,
        autoreload=os.environ.get("MRNA_STUDIO_RELOAD", "0") == "1",
        title="mRNA Design Studio",
        show=False,                                     # no browser in prod
        websocket_origin="*",
        allow_websocket_origin=["*"],
    )

    if auth:
        serve_kwargs["basic_auth"] = auth
        serve_kwargs["cookie_secret"] = os.environ.get(
            "MRNA_STUDIO_COOKIE_SECRET", "mrna-studio-change-me"
        )
        logger.info("Password protection enabled")
    else:
        logger.warning(
            "No MRNA_STUDIO_PASSWORD or MRNA_STUDIO_USERS set — app is OPEN"
        )

    pn.serve(create_app, **serve_kwargs)


if __name__ == "__main__":
    main()
