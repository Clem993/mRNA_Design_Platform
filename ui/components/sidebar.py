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
_SB = "#0B1120"          # deep navy sidebar bg
_SEP = "#1A2332"         # dark navy separator
_TEXT = "#8899AA"        # cool gray text
_HEAD = "#E8EDF2"        # near-white heading
_ACTIVE_BG = "#0F3D3E"  # dark teal selection
_ACTIVE_TEXT = "#5EEAD4" # teal-300 active text
_LOCAL_DOT = "#059669"   # emerald-600 — local
_DB_DOT = "#0D9488"      # teal-600 — database
_SECTION = "#5A6B7D"     # steel gray — section labels


class RegistrySidebar(param.Parameterized):
    def __init__(self, state: "AppState", **params: object) -> None:
        super().__init__(**params)
        self._state = state

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

    @param.depends("_state.worklist", "_state.db_connections", "_state.model_registry",
                    "_state.backbone_library", "_state.worklists")
    def panel(self) -> pn.Column:
        children = []

        # ── Logo / title ────────────────────────────────────────────────────
        children.append(pn.pane.HTML(
            f'<div style="padding:18px 14px 12px 14px;">'
            f'<div style="font-size:11px;font-weight:600;color:#5EEAD4;'
            f'letter-spacing:2px;text-transform:uppercase;margin-bottom:2px;">'
            f'mRNA</div>'
            f'<div style="font-size:15px;font-weight:700;color:{_HEAD};'
            f'letter-spacing:0.2px;">Design Studio</div>'
            f'<div style="font-size:9px;color:{_SECTION};margin-top:3px;'
            f'letter-spacing:1.5px;text-transform:uppercase;">'
            f'Sequence Engineering Platform</div></div>',
            sizing_mode="stretch_width",
            margin=0,
        ))
        children.append(self._divider())

        # ── WORKLIST section ─────────────────────────────────────────────────
        children.append(self._section_label("Worklists"))

        # Show all worklists if multiple exist
        if self._state.worklists:
            for i, wl in enumerate(self._state.worklists):
                is_active = (i == self._state.active_worklist_index)
                btn = pn.widgets.Button(
                    name=f"📋  {wl.name} ({wl.count})",
                    button_type="light",
                    sizing_mode="stretch_width",
                    margin=(2, 8),
                    stylesheets=[f"""
                        :host .bk-btn {{
                            background: {'#0F3D3E' if is_active else '#162032'};
                            color: {'#5EEAD4' if is_active else '#8899AA'};
                            border: {'1px solid #134E4A' if is_active else 'none'};
                            border-radius: 4px;
                            font-size: 11px;
                            text-align: left;
                            padding: 5px 10px;
                            font-weight: {'600' if is_active else '400'};
                        }}
                        :host .bk-btn:hover {{
                            background: #0F3D3E;
                        }}
                    """],
                )

                def _switch_worklist(event, idx=i):
                    self._state.active_worklist_index = idx
                    self._state.worklist = self._state.worklists[idx]
                    self._state.active_tab = "worklist"

                btn.on_click(_switch_worklist)
                children.append(btn)
        elif self._state.worklist and self._state.worklist.count > 0:
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
                            background: #162032;
                            color: #8899AA;
                            border: none;
                            border-radius: 4px;
                            font-size: 11px;
                            text-align: left;
                            padding: 5px 10px;
                        }
                        :host .bk-btn:hover {
                            background: #1A2B3E;
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

        # ── MODELS section ────────────────────────────────────────────────────
        children.append(self._divider())
        children.append(self._section_label("Models"))

        if self._state.model_registry and len(self._state.model_registry.all_models) > 0:
            for model_reg in self._state.model_registry.all_models:
                model_name = model_reg.model.name
                if model_reg.model_type == "scoring":
                    type_color, type_label, icon = "#0284C7", "ANALYTICAL", "📊"
                else:
                    type_color, type_label, icon = "#7C3AED", "GENERATIVE", "🧪"
                if model_reg.source == "catalog":
                    src_color, src_label = "#059669", "IMPORTED"
                elif model_reg.source == "api":
                    src_color, src_label = "#D97706", "API"
                else:
                    src_color, src_label = "#0D9488", "BUILTIN"
                repo_line = ""
                if model_reg.repository:
                    repo_line = (
                        f'<div style="font-size:9px;color:#475569;margin-top:1px;'
                        f'padding-left:10px;overflow:hidden;text-overflow:ellipsis;'
                        f'white-space:nowrap;">via {model_reg.repository}</div>'
                    )
                children.append(pn.pane.HTML(
                    f'<div style="background:#162032;border-radius:4px;padding:6px 10px;margin:2px 8px;">'
                    f'<div style="font-size:11px;color:#8899AA;">{icon} {model_name}</div>'
                    f'<div style="margin-top:3px;">'
                    f'<span style="background:{type_color}33;color:{type_color};padding:1px 5px;'
                    f'border-radius:8px;font-size:8px;font-weight:600;">{type_label}</span> '
                    f'<span style="background:{src_color}33;color:{src_color};padding:1px 5px;'
                    f'border-radius:8px;font-size:8px;font-weight:600;">{src_label}</span>'
                    f'</div>{repo_line}</div>',
                    sizing_mode="stretch_width",
                    margin=0,
                ))
        else:
            children.append(pn.pane.HTML(
                f'<div style="font-size:11px;color:{_SECTION};padding:3px 12px;">'
                f'No models loaded</div>',
                sizing_mode="stretch_width",
                margin=0,
            ))

        # ── BACKBONES section ─────────────────────────────────────────────────
        children.append(self._divider())
        children.append(self._section_label("Backbones"))

        if self._state.backbone_library:
            for bb in self._state.backbone_library:
                children.append(pn.pane.HTML(
                    f'<div style="background:#162032;border-radius:4px;padding:5px 10px;margin:2px 8px;">'
                    f'<div style="font-size:11px;color:#8899AA;">🧬 {bb.name}</div>'
                    f'<div style="font-size:9px;color:#5A6B7D;">{bb.length:,} bp</div>'
                    f'</div>',
                    sizing_mode="stretch_width",
                    margin=0,
                ))
        else:
            children.append(pn.pane.HTML(
                f'<div style="font-size:11px;color:{_SECTION};padding:3px 12px;">'
                f'No backbones imported</div>',
                sizing_mode="stretch_width",
                margin=0,
            ))

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
                    background: #0F3D3E;
                    color: #5EEAD4;
                    border: 1px solid #134E4A;
                    border-radius: 6px;
                    font-size: 12px;
                    font-weight: 600;
                    padding: 8px 12px;
                    text-align: left;
                }
                :host .bk-btn-light .bk-btn:hover {
                    background: #115E5B;
                }
            """],
        )

        def _go_to_worklist(event: object) -> None:
            self._state.active_tab = "worklist"

        btn.on_click(_go_to_worklist)
        return btn

