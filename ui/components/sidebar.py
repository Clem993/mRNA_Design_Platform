"""
Registry sidebar component — modern indigo/slate theme.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import panel as pn
import param

from core.models.sequence import mRNASequence

if TYPE_CHECKING:
    from ui.state import AppState


# ── Colours (mirror THEME from app.py without importing it to avoid circulars)
_SB = "#0F172A"          # sidebar bg
_SEP = "#1E293B"         # separator / border
_TEXT = "#94A3B8"        # muted text
_HEAD = "#F1F5F9"        # heading text
_ACTIVE_BG = "#1E3A5F"  # selected row
_ACTIVE_TEXT = "#93C5FD" # selected text (blue-300)
_LOCAL_DOT = "#10B981"   # emerald — local
_DB_DOT = "#6366F1"      # indigo — database
_SECTION = "#475569"     # slate-600 — section labels


class RegistrySidebar(param.Parameterized):
    def __init__(self, state: "AppState", **params: object) -> None:
        super().__init__(**params)
        self._state = state
        self._db_import_panel = None  # Will be set by app.py

    def _section_label(self, text: str) -> pn.pane.HTML:
        return pn.pane.HTML(
            f'<div style="font-size:10px;font-weight:700;letter-spacing:1.2px;'
            f'color:{_SECTION};text-transform:uppercase;padding:10px 10px 4px 10px;">'
            f'{text}</div>',
            sizing_mode="stretch_width",
            margin=0,
        )

    def _divider(self) -> pn.pane.HTML:
        return pn.pane.HTML(
            f'<hr style="border:none;border-top:1px solid {_SEP};margin:6px 8px;">',
            sizing_mode="stretch_width",
            margin=0,
        )

    @param.depends("_state.worklist", "_state.db_connections", "_state.model_registry")
    def panel(self) -> pn.Column:
        children = []

        # ── Logo / title ────────────────────────────────────────────────────
        children.append(pn.pane.HTML(
            f'<div style="padding:16px 12px 10px 12px;">'
            f'<div style="font-size:14px;font-weight:800;color:{_HEAD};'
            f'letter-spacing:0.3px;">mRNA Studio</div>'
            f'<div style="font-size:10px;color:{_SECTION};margin-top:1px;">'
            f'Design · Analyze · Assemble</div></div>',
            sizing_mode="stretch_width",
            margin=0,
        ))
        children.append(self._divider())

        # ── WORKLIST section ─────────────────────────────────────────────────
        children.append(self._section_label("Worklist"))
        if self._state.worklist and self._state.worklist.count > 0:
            children.append(self._worklist_button())
        else:
            children.append(pn.pane.HTML(
                f'<div style="font-size:11px;color:{_SECTION};padding:3px 12px;">'
                f'No worklist loaded</div>',
                sizing_mode="stretch_width",
                margin=0,
            ))

        # ── DATABASES section ────────────────────────────────────────────────
        children.append(self._divider())
        children.append(self._section_label("Databases"))

        if self._state.db_connections:
            for db_name in self._state.db_connections.keys():
                db_btn = pn.widgets.Button(
                    name=f"🗄  {db_name}",
                    button_type="light",
                    sizing_mode="stretch_width",
                    margin=(2, 8),
                    stylesheets=["""
                        :host .bk-btn {
                            background: #1E293B;
                            color: #94A3B8;
                            border: none;
                            border-radius: 4px;
                            font-size: 11px;
                            text-align: left;
                            padding: 5px 10px;
                        }
                        :host .bk-btn:hover {
                            background: #334155;
                        }
                    """],
                )
                children.append(db_btn)
        else:
            children.append(pn.pane.HTML(
                f'<div style="font-size:11px;color:{_SECTION};padding:3px 12px;">'
                f'No databases connected</div>',
                sizing_mode="stretch_width",
                margin=0,
            ))

        import_btn = pn.widgets.Button(
            name="⊕ Import Database",
            button_type="light",
            sizing_mode="stretch_width",
            margin=(6, 8),
            stylesheets=["""
                :host .bk-btn {
                    background: transparent;
                    color: #6366F1;
                    border: 1px solid #312E81;
                    border-radius: 6px;
                    font-size: 11px;
                    font-weight: 600;
                    padding: 6px 12px;
                }
                :host .bk-btn:hover {
                    background: #1E293B;
                }
            """],
        )
        import_btn.on_click(self._on_import_db)
        children.append(import_btn)

        # ── MODELS section ────────────────────────────────────────────────────
        children.append(self._divider())
        children.append(self._section_label("Models"))

        # Show loaded models
        if self._state.model_registry and len(self._state.model_registry.all_models) > 0:
            for model_reg in self._state.model_registry.all_models:
                model_name = model_reg.model.name
                model_btn = pn.widgets.Button(
                    name=f"📊 {model_name}",
                    button_type="light",
                    sizing_mode="stretch_width",
                    margin=(2, 8),
                    stylesheets=["""
                        :host .bk-btn {
                            background: #1E293B;
                            color: #94A3B8;
                            border: none;
                            border-radius: 4px;
                            font-size: 11px;
                            text-align: left;
                            padding: 5px 10px;
                        }
                        :host .bk-btn:hover {
                            background: #334155;
                        }
                    """],
                )
                children.append(model_btn)
        else:
            children.append(pn.pane.HTML(
                f'<div style="font-size:11px;color:{_SECTION};padding:3px 12px;">'
                f'No models loaded</div>',
                sizing_mode="stretch_width",
                margin=0,
            ))

        load_model_btn = pn.widgets.Button(
            name="⊕ Load Built-in Models",
            button_type="light",
            sizing_mode="stretch_width",
            margin=(6, 8),
            stylesheets=["""
                :host .bk-btn {
                    background: transparent;
                    color: #10B981;
                    border: 1px solid #064E3B;
                    border-radius: 6px;
                    font-size: 11px;
                    font-weight: 600;
                    padding: 6px 12px;
                }
                :host .bk-btn:hover {
                    background: #1E293B;
                }
            """],
        )
        load_model_btn.on_click(self._on_load_model)
        children.append(load_model_btn)

        return pn.Column(
            *children,
            sizing_mode="stretch_width",
            styles={
                "background": _SB,
                "min-height": "100vh",
                "overflow-y": "auto",
            },
            margin=0,
        )

    def _worklist_button(self) -> pn.widgets.Button:
        count = self._state.worklist.count
        name = self._state.worklist.name
        btn = pn.widgets.Button(
            name=f"📋  {name} ({count} sequences)",
            button_type="light",
            sizing_mode="stretch_width",
            margin=(4, 8),
            stylesheets=["""
                :host .bk-btn-light .bk-btn {
                    background: #1E293B;
                    color: #93C5FD;
                    border: 1px solid #312E81;
                    border-radius: 6px;
                    font-size: 12px;
                    font-weight: 600;
                    padding: 8px 12px;
                    text-align: left;
                }
                :host .bk-btn-light .bk-btn:hover {
                    background: #1E3A5F;
                }
            """],
        )

        def _go_to_worklist(event: object) -> None:
            self._state.active_tab = "worklist"

        btn.on_click(_go_to_worklist)
        return btn

    def _on_import_db(self, event: object) -> None:
        # Show database import modal
        self._state.show_db_import_modal = True

    def _on_load_model(self, event: object) -> None:
        """Load built-in scoring models into the registry."""
        from models import RNAStructureMFEScorer, mRNAStabilityScorer

        # Check if models are already loaded
        existing_models = {m.model.name for m in self._state.model_registry.all_models}

        models_loaded = []

        # Load RNAstructure MFE scorer
        if "RNAstructure MFE" not in existing_models:
            self._state.model_registry._register(
                RNAStructureMFEScorer(),
                "scoring",
                "builtin",
                "models/rna_structure_scorer.py"
            )
            models_loaded.append("RNAstructure MFE")

        # Load mRNA Stability scorer
        if "mRNA Stability" not in existing_models:
            self._state.model_registry._register(
                mRNAStabilityScorer(organism="human"),
                "scoring",
                "builtin",
                "models/mrna_stability_scorer.py"
            )
            models_loaded.append("mRNA Stability")

        if models_loaded:
            self._state.set_status(f"Loaded {len(models_loaded)} model(s): {', '.join(models_loaded)}")
            # Trigger update
            self._state.param.trigger("model_registry")
        else:
            self._state.set_status("All built-in models already loaded")
