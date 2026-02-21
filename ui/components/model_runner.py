"""
Model runner panel.

Lets users:
  - Load a local .py model or register a remote API endpoint
  - Run scoring models against the worklist or a subset of sequences
  - Run generative models to create new sequences (added to worklist)
  - View results in a sortable table
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import panel as pn
import param

if TYPE_CHECKING:
    from ui.state import AppState


class ModelRunnerPanel(param.Parameterized):
    """Model loading and execution panel."""

    def __init__(self, state: "AppState", **params: object) -> None:
        super().__init__(**params)
        self._state = state
        self._status_pane = pn.pane.HTML("")

    # ── Load section ──────────────────────────────────────────────────────────

    def _build_load_section(self) -> pn.Column:
        # Local file
        self._local_path = pn.widgets.TextInput(
            name="Local model path (.py)",
            placeholder="/path/to/my_model.py",
            width=380,
        )
        load_local_btn = pn.widgets.Button(name="Load", button_type="primary", margin=(8, 4))
        load_local_btn.on_click(self._on_load_local)

        # API endpoint
        self._api_endpoint = pn.widgets.TextInput(
            name="API Endpoint URL",
            placeholder="https://model.example.com/api/v1",
            width=300,
        )
        self._api_name = pn.widgets.TextInput(name="Model Name", placeholder="my_scorer", width=180)
        self._api_key_input = pn.widgets.PasswordInput(name="API Key (optional)", width=220)
        self._api_type = pn.widgets.Select(
            name="Type", options=["Scoring", "Generative"], value="Scoring", width=130
        )
        load_api_btn = pn.widgets.Button(name="Register", button_type="primary", margin=(8, 4))
        load_api_btn.on_click(self._on_register_api)

        return pn.Column(
            pn.pane.HTML(
                '<div style="font-size:13px;font-weight:700;margin-bottom:6px;">'
                'Load Model</div>'
            ),
            pn.Tabs(
                ("Local File", pn.Column(pn.Row(self._local_path, load_local_btn))),
                ("API Endpoint", pn.Column(
                    pn.Row(self._api_endpoint, self._api_name),
                    pn.Row(self._api_key_input, self._api_type, load_api_btn),
                )),
            ),
        )

    # ── Loaded models list ─────────────────────────────────────────────────────

    @param.depends("_state.model_registry")
    def _loaded_models_view(self) -> pn.Column:
        registry = self._state.model_registry
        all_models = registry.all_models

        if not all_models:
            return pn.pane.HTML(
                '<div style="color:#7F8C8D;font-size:12px;padding:8px 0;">'
                'No models loaded yet.</div>'
            )

        rows = []
        for reg in all_models:
            type_badge_color = "#3498DB" if reg.model_type == "scoring" else "#9B59B6"
            source_badge = (
                '<span style="background:#2ECC71;color:white;border-radius:3px;'
                'padding:1px 5px;font-size:9px;">LOCAL</span>'
                if reg.source == "local" else
                '<span style="background:#F39C12;color:white;border-radius:3px;'
                'padding:1px 5px;font-size:9px;">API</span>'
            )
            type_badge = (
                f'<span style="background:{type_badge_color};color:white;'
                f'border-radius:3px;padding:1px 5px;font-size:9px;">'
                f'{reg.model_type.upper()}</span>'
            )
            remove_btn = pn.widgets.Button(
                name="✕",
                button_type="danger",
                width=30,
                margin=(1, 2),
            )
            model_name_captured = reg.model.name

            def _remove(event: object, mn: str = model_name_captured) -> None:
                self._state.model_registry.unregister(mn)
                self._state.param.trigger("model_registry")

            remove_btn.on_click(_remove)
            rows.append(pn.Row(
                pn.pane.HTML(
                    f'<div style="font-size:12px;min-width:160px;padding-top:6px;">'
                    f'{reg.model.name}</div>'
                ),
                pn.pane.HTML(f'<div style="padding-top:6px;">{type_badge} {source_badge}</div>'),
                pn.pane.HTML(
                    f'<div style="font-size:10px;color:#7F8C8D;padding-top:7px;'
                    f'max-width:200px;overflow:hidden;text-overflow:ellipsis;">'
                    f'{reg.model.description}</div>'
                ),
                remove_btn,
            ))
        return pn.Column(*rows)

    # ── Run section ────────────────────────────────────────────────────────────

    def _build_run_section(self) -> pn.Column:
        registry = self._state.model_registry
        scoring_names = [r.model.name for r in registry.scoring_models]
        gen_names = [r.model.name for r in registry.generative_models]

        self._score_model_select = pn.widgets.Select(
            name="Scoring Model",
            options=scoring_names or ["(none loaded)"],
            width=240,
        )
        run_score_btn = pn.widgets.Button(
            name="Score Worklist", button_type="success", margin=(8, 4)
        )
        run_score_btn.on_click(self._on_run_scoring)

        self._gen_model_select = pn.widgets.Select(
            name="Generative Model",
            options=gen_names or ["(none loaded)"],
            width=240,
        )
        self._gen_n = pn.widgets.IntInput(name="# sequences", value=10, width=100)
        run_gen_btn = pn.widgets.Button(
            name="Generate Sequences", button_type="primary", margin=(8, 4)
        )
        run_gen_btn.on_click(self._on_run_generation)

        return pn.Column(
            pn.pane.HTML(
                '<div style="font-size:13px;font-weight:700;margin:12px 0 6px 0;">'
                'Run Models</div>'
            ),
            pn.Tabs(
                ("Score Sequences", pn.Column(
                    pn.Row(self._score_model_select, run_score_btn),
                    pn.pane.HTML(
                        '<div style="font-size:11px;color:#7F8C8D;">'
                        'Scores all items currently in the worklist.</div>'
                    ),
                )),
                ("Generate Sequences", pn.Column(
                    pn.Row(self._gen_model_select, self._gen_n, run_gen_btn),
                    pn.pane.HTML(
                        '<div style="font-size:11px;color:#7F8C8D;">'
                        'New sequences are added to the worklist.</div>'
                    ),
                )),
            ),
        )

    # ── Full panel ─────────────────────────────────────────────────────────────

    def panel(self) -> pn.Column:
        return pn.Column(
            pn.pane.HTML(
                '<div style="font-size:16px;font-weight:800;padding:8px 0;">'
                'Models</div>'
            ),
            self._build_load_section(),
            pn.layout.Divider(),
            pn.pane.HTML(
                '<div style="font-size:13px;font-weight:700;margin-bottom:6px;">'
                'Loaded Models</div>'
            ),
            pn.panel(self._loaded_models_view),
            pn.layout.Divider(),
            self._build_run_section(),
            self._status_pane,
            sizing_mode="stretch_width",
            styles={"padding": "8px 16px"},
        )

    # ── Event handlers ─────────────────────────────────────────────────────────

    def _on_load_local(self, event: object) -> None:
        path = self._local_path.value.strip()
        if not path:
            return
        try:
            loaded = self._state.model_registry.load_local(path)
            self._state.param.trigger("model_registry")
            names = ", ".join(m.name for m in loaded)
            self._status_pane.object = (
                f'<div style="color:#2ECC71;font-size:12px;">✓ Loaded: {names}</div>'
            )
        except Exception as e:
            self._status_pane.object = (
                f'<div style="color:#E74C3C;font-size:12px;">✗ {e}</div>'
            )

    def _on_register_api(self, event: object) -> None:
        endpoint = self._api_endpoint.value.strip()
        name = self._api_name.value.strip() or "api_model"
        key = self._api_key_input.value or None
        model_type = self._api_type.value

        if not endpoint:
            return
        try:
            if model_type == "Scoring":
                self._state.model_registry.register_api_scorer(endpoint, name, key)
            else:
                self._state.model_registry.register_api_generator(endpoint, name, key)
            self._state.param.trigger("model_registry")
            self._status_pane.object = (
                f'<div style="color:#2ECC71;font-size:12px;">✓ Registered API: {name}</div>'
            )
        except Exception as e:
            self._status_pane.object = (
                f'<div style="color:#E74C3C;font-size:12px;">✗ {e}</div>'
            )

    def _on_run_scoring(self, event: object) -> None:
        model_name = self._score_model_select.value
        if not model_name or model_name == "(none loaded)":
            return
        sequences = self._state.worklist.sequences
        if not sequences:
            self._status_pane.object = (
                '<div style="color:#F39C12;font-size:12px;">Worklist is empty.</div>'
            )
            return
        try:
            df = self._state.model_registry.run_scoring(model_name, sequences)
            score_map = dict(zip(df["id"], df["score"]))
            for item in self._state.worklist.items:
                if item.sequence.id in score_map:
                    item.scores[model_name] = score_map[item.sequence.id]
            self._state.param.trigger("worklist")
            self._status_pane.object = (
                f'<div style="color:#2ECC71;font-size:12px;">'
                f'✓ Scored {len(sequences)} sequences with {model_name}</div>'
            )
        except Exception as e:
            self._status_pane.object = (
                f'<div style="color:#E74C3C;font-size:12px;">✗ Scoring failed: {e}</div>'
            )

    def _on_run_generation(self, event: object) -> None:
        model_name = self._gen_model_select.value
        if not model_name or model_name == "(none loaded)":
            return
        n = self._gen_n.value or 10
        try:
            new_seqs = self._state.model_registry.run_generation(model_name, constraints={}, n=n)
            self._state.worklist.add_many(new_seqs, origin="generated")
            self._state.param.trigger("worklist")
            self._status_pane.object = (
                f'<div style="color:#2ECC71;font-size:12px;">'
                f'✓ Generated {len(new_seqs)} sequences → added to worklist</div>'
            )
        except Exception as e:
            self._status_pane.object = (
                f'<div style="color:#E74C3C;font-size:12px;">✗ Generation failed: {e}</div>'
            )
