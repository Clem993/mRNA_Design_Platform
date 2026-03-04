"""
Generate Sequences tab — tools for sequence manipulation and generation.

Provides:
1. Clean for Cloning — prepare sequences for cloning vectors
2. Codon Optimization — optimize CDS for target organism
3. Imported generative models — apply models from the repository
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

import panel as pn
import param

from core.models.sequence import mRNASequence

if TYPE_CHECKING:
    from ui.state import AppState

logger = logging.getLogger(__name__)


class GenerateSequencesPanel(param.Parameterized):
    """Generate Sequences tab panel."""

    def __init__(self, state: "AppState", **params: object) -> None:
        super().__init__(**params)
        self._state = state
        self._output_pane = pn.Column(sizing_mode="stretch_width")

    @param.depends("_state.worklist", "_state.model_registry")
    def panel(self) -> pn.Column:
        # ── Header ────────────────────────────────────────────────────────────
        header = pn.pane.HTML(
            '<div style="font-size:16px;font-weight:800;padding:8px 0 4px 0;">'
            'Generate Sequences</div>'
            '<div style="font-size:12px;color:#64748B;margin-bottom:16px;">'
            'Clean, optimize, and generate mRNA sequences using built-in tools '
            'and imported generative models.</div>'
        )

        # ── Input selector ────────────────────────────────────────────────────
        input_mode = pn.widgets.Select(
            name="Input", options=["Worklist", "Single Sequence"],
            value="Worklist", width=200,
        )

        single_seq_input = pn.widgets.TextAreaInput(
            name="Sequence (DNA)",
            placeholder="Paste CDS sequence here...",
            height=80,
            width=500,
            visible=False,
        )

        def toggle_input(event):
            single_seq_input.visible = (event.new == "Single Sequence")

        input_mode.param.watch(toggle_input, "value")

        input_section = pn.Row(input_mode, single_seq_input, sizing_mode="stretch_width")

        # ── Built-in Tools ────────────────────────────────────────────────────
        clean_btn = pn.widgets.Button(
            name="Clean for Cloning",
            button_type="primary",
            width=180,
            margin=(4, 4),
        )
        clean_btn.on_click(lambda e: self._run_clean_for_cloning(input_mode.value, single_seq_input.value))

        optimize_btn = pn.widgets.Button(
            name="Codon Optimization",
            button_type="primary",
            width=180,
            margin=(4, 4),
        )
        optimize_btn.on_click(lambda e: self._run_codon_optimization(input_mode.value, single_seq_input.value))

        # Clean for Cloning settings
        clean_settings = pn.Column(
            pn.pane.HTML('<div style="font-size:12px;font-weight:600;margin:8px 0 4px 0;">Clean for Cloning Settings</div>'),
            sizing_mode="stretch_width",
            visible=False,
        )

        self._enzyme_avoid = pn.widgets.MultiChoice(
            name="Enzymes to avoid",
            options=["BsaI", "BbsI", "Esp3I", "BsmBI", "EcoRI", "BamHI", "HindIII", "NotI", "XhoI"],
            value=["BsaI"],
            width=400,
        )
        self._preferred_stop = pn.widgets.Select(
            name="Preferred stop", options=["TAA", "TAG", "TGA"], value="TAA", width=100,
        )
        self._double_stop = pn.widgets.Toggle(name="Double stop codon", value=True, width=150)
        self._max_homopolymer = pn.widgets.IntSlider(name="Max homopolymer", start=4, end=10, value=6, width=200)

        clean_settings.extend([
            pn.Row(self._enzyme_avoid),
            pn.Row(self._preferred_stop, self._double_stop, self._max_homopolymer),
        ])

        def toggle_clean_settings(event):
            clean_settings.visible = not clean_settings.visible

        clean_settings_toggle = pn.widgets.Button(name="Settings", button_type="light", width=70, margin=(4, 0))
        clean_settings_toggle.on_click(toggle_clean_settings)

        # Codon optimization settings
        opt_settings = pn.Column(
            pn.pane.HTML('<div style="font-size:12px;font-weight:600;margin:8px 0 4px 0;">Codon Optimization Settings</div>'),
            sizing_mode="stretch_width",
            visible=False,
        )

        self._opt_organism = pn.widgets.Select(
            name="Target organism",
            options=["Human", "Mouse", "E. coli", "CHO", "Yeast", "Zebrafish"],
            value="Human", width=200,
        )
        self._opt_strategy = pn.widgets.Select(
            name="Strategy",
            options=["Match host CAI", "Harmonize", "Balance"],
            value="Match host CAI", width=200,
        )
        self._opt_min_cai = pn.widgets.FloatSlider(name="Min CAI target", start=0.5, end=1.0, value=0.8, step=0.05, width=250)

        opt_settings.extend([
            pn.Row(self._opt_organism, self._opt_strategy),
            self._opt_min_cai,
        ])

        opt_settings_toggle = pn.widgets.Button(name="Settings", button_type="light", width=70, margin=(4, 0))
        opt_settings_toggle.on_click(lambda e: setattr(opt_settings, "visible", not opt_settings.visible))

        builtin_section = pn.Column(
            pn.pane.HTML(
                '<div style="font-size:14px;font-weight:700;color:#0F172A;margin-bottom:8px;">'
                'Built-in Tools</div>'
            ),
            pn.Row(clean_btn, clean_settings_toggle, optimize_btn, opt_settings_toggle),
            clean_settings,
            opt_settings,
            sizing_mode="stretch_width",
            styles={"background": "#FFFFFF", "padding": "12px", "border-radius": "6px",
                     "border": "1px solid #E2E8F0", "margin-bottom": "12px"},
        )

        # ── Imported Generative Models ────────────────────────────────────────
        gen_models = []
        if self._state.model_registry:
            gen_models = self._state.model_registry.generative_models

        if gen_models:
            model_buttons = []
            for model_reg in gen_models:
                btn = pn.widgets.Button(
                    name=f"{model_reg.model.name}",
                    button_type="light",
                    width=180,
                    margin=(4, 4),
                    stylesheets=["""
                        :host .bk-btn {
                            border: 1px solid #6D28D9;
                            color: #6D28D9;
                            font-size: 11px;
                        }
                    """],
                )
                btn.on_click(lambda e, m=model_reg: self._run_generative_model(m, input_mode.value, single_seq_input.value))
                model_buttons.append(btn)

            gen_section = pn.Column(
                pn.pane.HTML(
                    '<div style="font-size:14px;font-weight:700;color:#0F172A;margin-bottom:8px;">'
                    'Imported Generative Models</div>'
                ),
                pn.Row(*model_buttons, sizing_mode="stretch_width"),
                sizing_mode="stretch_width",
                styles={"background": "#FFFFFF", "padding": "12px", "border-radius": "6px",
                         "border": "1px solid #E2E8F0", "margin-bottom": "12px"},
            )
        else:
            gen_section = pn.Column(
                pn.pane.HTML(
                    '<div style="font-size:14px;font-weight:700;color:#0F172A;margin-bottom:8px;">'
                    'Imported Generative Models</div>'
                    '<div style="font-size:12px;color:#94A3B8;margin-bottom:8px;">'
                    'No generative models imported. Use the '
                    '<span style="color:#0F766E;font-weight:600;">Model Repository</span> '
                    'tab to import models.</div>'
                ),
                sizing_mode="stretch_width",
                styles={"background": "#FFFFFF", "padding": "12px", "border-radius": "6px",
                         "border": "1px solid #E2E8F0", "margin-bottom": "12px"},
            )

        # ── Output Section ────────────────────────────────────────────────────
        self._generated_sequences = []

        self._worklist_name_input = pn.widgets.TextInput(
            name="Worklist Name",
            placeholder="e.g. Optimized Batch 1",
            width=250,
        )
        add_to_worklist_btn = pn.widgets.Button(
            name="＋ Add to Worklist",
            button_type="success",
            width=160,
            margin=(20, 4, 4, 4),
        )
        self._add_btn = add_to_worklist_btn

        add_to_worklist_btn.on_click(self._on_add_to_worklist)

        self._add_to_wl_section = pn.Column(
            pn.pane.HTML(
                '<div style="font-size:13px;font-weight:700;color:#0F172A;margin-bottom:4px;">'
                'Save to Worklist</div>'
                '<div style="font-size:11px;color:#64748B;margin-bottom:6px;">'
                'Create a new worklist from the generated sequences.</div>'
            ),
            pn.Row(self._worklist_name_input, add_to_worklist_btn),
            sizing_mode="stretch_width",
            styles={"background": "#F8FAFC", "padding": "12px", "border-radius": "6px",
                    "border": "1px solid #E2E8F0", "margin-top": "8px"},
            visible=False,
        )

        output_section = pn.Column(
            pn.pane.HTML(
                '<div style="font-size:14px;font-weight:700;color:#0F172A;margin-bottom:8px;">'
                'Output</div>'
            ),
            self._output_pane,
            self._add_to_wl_section,
            sizing_mode="stretch_width",
            styles={"background": "#FFFFFF", "padding": "12px", "border-radius": "6px",
                     "border": "1px solid #E2E8F0"},
        )

        return pn.Column(
            header,
            input_section,
            builtin_section,
            gen_section,
            output_section,
            sizing_mode="stretch_width",
            styles={"padding": "8px 16px"},
        )

    def _get_input_sequences(self, mode: str, single_text: str):
        """Get sequences based on input mode."""
        if mode == "Single Sequence" and single_text.strip():
            seq = mRNASequence(
                name="input_sequence",
                source="local",
                cds=single_text.strip().upper().replace("U", "T"),
            )
            return [seq]
        elif self._state.worklist and self._state.worklist.count > 0:
            return [item.sequence for item in self._state.worklist.items]
        return []

    def _run_clean_for_cloning(self, mode: str, single_text: str) -> None:
        """Run Clean for Cloning on input sequences."""
        from core.sequence_tools.clean_for_cloning import clean_for_cloning

        sequences = self._get_input_sequences(mode, single_text)
        if not sequences:
            self._output_pane.clear()
            self._output_pane.append(pn.pane.HTML('<div style="color:#EF4444;">No input sequences available.</div>'))
            return

        self._output_pane.clear()
        self._generated_sequences = []
        results_html = []

        for seq in sequences:
            cds = seq.cds or seq.assembled_sequence
            if not cds:
                continue

            result = clean_for_cloning(
                cds=cds,
                enzymes_to_avoid=self._enzyme_avoid.value,
                preferred_stop=self._preferred_stop.value,
                use_double_stop=self._double_stop.value,
                max_homopolymer=self._max_homopolymer.value,
            )

            # Create cleaned sequence
            cleaned_seq = mRNASequence(
                name=f"{seq.name}_cleaned",
                source="local",
                cds=result.cleaned,
                five_prime_utr=seq.five_prime_utr,
                kozak=seq.kozak,
                three_prime_utr=seq.three_prime_utr,
                poly_a=seq.poly_a,
            )
            self._generated_sequences.append(cleaned_seq)

            # Build diff summary
            changes_html = "".join(
                f'<div style="font-size:10px;color:#475569;margin:1px 0;">• {c}</div>'
                for c in result.changes[:10]
            )
            if len(result.changes) > 10:
                changes_html += f'<div style="font-size:10px;color:#94A3B8;">... +{len(result.changes) - 10} more</div>'

            len_diff = len(result.cleaned) - len(result.original)
            len_str = f"+{len_diff}" if len_diff > 0 else str(len_diff)

            results_html.append(
                f'<div style="border:1px solid #E2E8F0;border-radius:6px;padding:10px;margin:4px 0;">'
                f'<div style="font-weight:600;font-size:12px;color:#0F172A;">{seq.name}</div>'
                f'<div style="font-size:11px;color:#64748B;margin:2px 0;">'
                f'Length: {len(result.original)} → {len(result.cleaned)} ({len_str}) | '
                f'Sites removed: {result.restriction_sites_removed} | '
                f'Homopolymers flagged: {result.homopolymers_shortened}'
                f'{"| Double stop: Yes" if result.double_stop_added else ""}'
                f'</div>'
                f'{changes_html}'
                f'</div>'
            )

        summary = (
            f'<div style="font-weight:700;color:#10B981;margin-bottom:8px;">'
            f'Cleaned {len(self._generated_sequences)} sequence(s) for cloning</div>'
        )
        self._output_pane.append(pn.pane.HTML(summary + "".join(results_html), sizing_mode="stretch_width"))
        if self._generated_sequences:
            self._worklist_name_input.value = "Cleaned Sequences"
            self._add_to_wl_section.visible = True

    def _run_codon_optimization(self, mode: str, single_text: str) -> None:
        """Run codon optimization on input sequences."""
        from core.sequence_tools.codon_optimizer import optimize_codons

        sequences = self._get_input_sequences(mode, single_text)
        if not sequences:
            self._output_pane.clear()
            self._output_pane.append(pn.pane.HTML('<div style="color:#EF4444;">No input sequences available.</div>'))
            return

        strategy_map = {"Match host CAI": "match_host", "Harmonize": "harmonize", "Balance": "balance"}
        strategy = strategy_map.get(self._opt_strategy.value, "match_host")

        self._output_pane.clear()
        self._generated_sequences = []
        results_html = []

        for seq in sequences:
            cds = seq.cds or seq.assembled_sequence
            if not cds:
                continue

            result = optimize_codons(
                cds=cds,
                organism=self._opt_organism.value,
                min_cai_target=self._opt_min_cai.value,
                strategy=strategy,
            )

            # Create optimized sequence
            opt_seq = mRNASequence(
                name=f"{seq.name}_optimized",
                source="local",
                cds=result.optimized_cds,
                five_prime_utr=seq.five_prime_utr,
                kozak=seq.kozak,
                three_prime_utr=seq.three_prime_utr,
                poly_a=seq.poly_a,
            )
            self._generated_sequences.append(opt_seq)

            results_html.append(
                f'<div style="border:1px solid #E2E8F0;border-radius:6px;padding:10px;margin:4px 0;">'
                f'<div style="font-weight:600;font-size:12px;color:#0F172A;">{seq.name}</div>'
                f'<div style="font-size:11px;color:#64748B;margin:2px 0;">'
                f'CAI: {result.original_cai:.3f} → {result.optimized_cai:.3f} | '
                f'Codons changed: {result.codons_changed}/{result.total_codons} | '
                f'Organism: {result.organism}'
                f'</div>'
                f'</div>'
            )

        summary = (
            f'<div style="font-weight:700;color:#10B981;margin-bottom:8px;">'
            f'Optimized {len(self._generated_sequences)} sequence(s) for {self._opt_organism.value}</div>'
        )
        self._output_pane.append(pn.pane.HTML(summary + "".join(results_html), sizing_mode="stretch_width"))
        if self._generated_sequences:
            self._worklist_name_input.value = f"Optimized ({self._opt_organism.value})"
            self._add_to_wl_section.visible = True

    def _run_generative_model(self, model_reg, mode: str, single_text: str) -> None:
        """Run an imported generative model."""
        self._output_pane.clear()

        model = model_reg.model
        self._output_pane.append(pn.pane.HTML(
            f'<div style="font-size:12px;color:#0F766E;margin-bottom:8px;">'
            f'Running {model.name}...</div>'
        ))

        try:
            results = model.generate(constraints={}, n=5)
            if results:
                self._generated_sequences = results
                results_html = "".join(
                    f'<div style="border:1px solid #E2E8F0;border-radius:6px;padding:8px;margin:4px 0;">'
                    f'<div style="font-size:12px;font-weight:600;">{seq.name}</div>'
                    f'<div style="font-size:11px;color:#64748B;">Length: {seq.length} nt</div>'
                    f'</div>'
                    for seq in results
                )
                self._output_pane.clear()
                self._output_pane.append(pn.pane.HTML(
                    f'<div style="font-weight:700;color:#10B981;margin-bottom:8px;">'
                    f'Generated {len(results)} sequence(s) with {model.name}</div>'
                    f'{results_html}'
                ))
                self._worklist_name_input.value = f"{model.name} Output"
                self._add_to_wl_section.visible = True
            else:
                self._output_pane.clear()
                self._output_pane.append(pn.pane.HTML(
                    f'<div style="color:#64748B;">{model.name} (demo mode): '
                    f'Model registered but not running actual inference. '
                    f'In production, this would generate sequences using the model.</div>'
                ))
                self._add_to_wl_section.visible = False
        except Exception as e:
            self._output_pane.clear()
            self._output_pane.append(pn.pane.HTML(
                f'<div style="color:#EF4444;">Error: {e}</div>'
            ))

    def _on_add_to_worklist(self, event) -> None:
        """Create a new worklist from generated sequences."""
        if not self._generated_sequences:
            return

        from core.models.worklist import Worklist

        name = self._worklist_name_input.value.strip()
        if not name:
            name = "Generated Sequences"

        new_wl = Worklist(name=name)
        new_wl.add_many(self._generated_sequences, origin="generated")

        updated = list(self._state.worklists) + [new_wl]
        self._state.worklists = updated
        self._state.active_worklist_index = len(updated) - 1
        self._state.worklist = new_wl
        self._state.active_tab = "worklist"

        count = len(self._generated_sequences)
        self._add_to_wl_section.visible = False
        self._generated_sequences = []
        self._state.set_status(f"Created worklist '{name}' with {count} sequence(s)")
