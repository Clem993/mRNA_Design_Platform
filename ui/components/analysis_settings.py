"""
Analysis Settings panel — configurable parameters for sequence analysis.

Provides a comprehensive settings modal for controlling all analysis modules:
GC content, CAI, homopolymers, restriction enzymes, CDS validation,
Kozak, secondary structure, uridine, and dinucleotide analysis.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict

import panel as pn
import param

from core.analysis.restriction_sites import COMMON_ENZYMES

if TYPE_CHECKING:
    from ui.state import AppState


# Extended enzyme library organized by category
ENZYME_CATEGORIES = {
    "Type IIS / Golden Gate": ["BsaI", "BbsI", "Esp3I", "SapI", "BsmBI"],
    "Classic 6-cutters": [
        "EcoRI", "HindIII", "BamHI", "XhoI", "XbaI", "NcoI", "NheI",
        "SpeI", "NotI", "SalI", "PstI", "KpnI",
    ],
    "Blunt cutters": ["SmaI", "EcoRV", "HpaI", "StuI", "ScaI"],
    "Methylation-sensitive": ["DpnI", "MboI", "Sau3AI"],
    "Rare cutters (8+ bp)": ["NotI", "SfiI", "PacI", "AscI", "FseI", "SwaI", "PmeI"],
    "IVT cleanup": ["DpnI"],
}

# Extended recognition sequences (adding missing ones to COMMON_ENZYMES)
EXTENDED_ENZYMES: Dict[str, str] = {
    **COMMON_ENZYMES,
    "BsmBI": "CGTCTC",
    "EcoRV": "GATATC",
    "HpaI": "GTTAAC",
    "StuI": "AGGCCT",
    "ScaI": "AGTACT",
    "MboI": "GATC",
    "Sau3AI": "GATC",
    "SfiI": "GGCCNNNNNGGCC",
    "PacI": "TTAATTAA",
    "AscI": "GGCGCGCC",
    "FseI": "GGCCGGCC",
    "SwaI": "ATTTAAAT",
    "PmeI": "GTTTAAAC",
}

DEFAULT_SETTINGS: Dict[str, Any] = {
    # GC Content
    "gc_enabled": True,
    "gc_window": 100,
    "gc_step": 1,
    "gc_target_min": 45.0,
    "gc_target_max": 65.0,
    "gc_flag_outside_target": True,
    "gc_by_codon_position": True,

    # CAI
    "cai_enabled": True,
    "cai_organism": "Human",
    "cai_min_acceptable": 0.7,
    "cai_rare_codon_threshold": 0.1,

    # Homopolymers
    "homopolymer_enabled": True,
    "homopolymer_min_run": 5,
    "homopolymer_max_allowed": 8,
    "homopolymer_bases": ["A", "T", "G", "C"],

    # Restriction enzymes
    "restriction_enabled": True,
    "restriction_enzymes": list(COMMON_ENZYMES.keys()),
    "restriction_mode": "Report all sites found",

    # CDS Validation
    "cds_enabled": True,
    "cds_check_start": True,
    "cds_check_stop": True,
    "cds_double_stop": False,
    "cds_accepted_stops": ["TAA", "TAG", "TGA"],
    "cds_check_frame": True,

    # Kozak
    "kozak_enabled": True,
    "kozak_min_strength": "Adequate",
    "kozak_flag_r3": True,

    # Structure
    "structure_enabled": True,
    "structure_engine": "ViennaRNA",
    "structure_temperature": 37.0,

    # Uridine
    "uridine_enabled": False,
    "uridine_flag_threshold": 0.40,

    # Dinucleotide
    "dinucleotide_enabled": False,
    "dinucleotide_flag_cpg": True,
    "dinucleotide_flag_upa": True,
}


class AnalysisSettingsPanel(param.Parameterized):
    """Analysis settings configuration panel."""

    def __init__(self, state: "AppState", **params: object) -> None:
        super().__init__(**params)
        self._state = state
        # Initialize settings from state or defaults
        if not self._state.analysis_settings:
            self._state.analysis_settings = dict(DEFAULT_SETTINGS)

    def _get(self, key: str) -> Any:
        return self._state.analysis_settings.get(key, DEFAULT_SETTINGS.get(key))

    def _section_header(self, title: str, toggle_key: str) -> pn.Row:
        """Build a collapsible section header with enable toggle."""
        toggle = pn.widgets.Toggle(
            name="",
            value=self._get(toggle_key),
            width=40,
            margin=(4, 8),
        )

        def on_toggle(event):
            settings = dict(self._state.analysis_settings)
            settings[toggle_key] = event.new
            self._state.analysis_settings = settings

        toggle.param.watch(on_toggle, "value")

        return pn.Row(
            pn.pane.HTML(
                f'<div style="font-size:14px;font-weight:700;color:#0F172A;padding:8px 0;">'
                f'{title}</div>'
            ),
            pn.layout.HSpacer(),
            toggle,
            sizing_mode="stretch_width",
        )

    def _build_gc_section(self) -> pn.Column:
        s = self._state.analysis_settings
        window = pn.widgets.IntSlider(name="Sliding window size", start=20, end=500, value=self._get("gc_window"), step=10, width=300)
        step = pn.widgets.IntSlider(name="Sliding window step", start=1, end=50, value=self._get("gc_step"), width=300)
        target_min = pn.widgets.FloatSlider(name="Target GC min %", start=20, end=80, value=self._get("gc_target_min"), step=1, width=300)
        target_max = pn.widgets.FloatSlider(name="Target GC max %", start=20, end=80, value=self._get("gc_target_max"), step=1, width=300)
        flag_outside = pn.widgets.Toggle(name="Flag outside target", value=self._get("gc_flag_outside_target"), width=150)
        by_codon = pn.widgets.Toggle(name="GC by codon position", value=self._get("gc_by_codon_position"), width=150)

        for w, k in [(window, "gc_window"), (step, "gc_step"), (target_min, "gc_target_min"),
                      (target_max, "gc_target_max"), (flag_outside, "gc_flag_outside_target"),
                      (by_codon, "gc_by_codon_position")]:
            def _update(event, key=k):
                s = dict(self._state.analysis_settings)
                s[key] = event.new
                self._state.analysis_settings = s
            w.param.watch(_update, "value")

        return pn.Column(
            self._section_header("GC Content", "gc_enabled"),
            pn.Row(window, step),
            pn.Row(target_min, target_max),
            pn.Row(flag_outside, by_codon),
            pn.layout.Divider(),
            sizing_mode="stretch_width",
        )

    def _build_cai_section(self) -> pn.Column:
        organism = pn.widgets.Select(
            name="Organism", options=["Human", "Mouse", "E. coli", "CHO", "Yeast", "Custom"],
            value=self._get("cai_organism"), width=200,
        )
        min_cai = pn.widgets.FloatSlider(name="Min acceptable CAI", start=0.0, end=1.0, value=self._get("cai_min_acceptable"), step=0.05, width=300)
        rare_threshold = pn.widgets.FloatSlider(name="Rare codon threshold", start=0.0, end=1.0, value=self._get("cai_rare_codon_threshold"), step=0.05, width=300)

        for w, k in [(organism, "cai_organism"), (min_cai, "cai_min_acceptable"), (rare_threshold, "cai_rare_codon_threshold")]:
            def _update(event, key=k):
                s = dict(self._state.analysis_settings)
                s[key] = event.new
                self._state.analysis_settings = s
            w.param.watch(_update, "value")

        return pn.Column(
            self._section_header("Codon Adaptation Index", "cai_enabled"),
            pn.Row(organism, min_cai),
            rare_threshold,
            pn.layout.Divider(),
            sizing_mode="stretch_width",
        )

    def _build_homopolymer_section(self) -> pn.Column:
        min_run = pn.widgets.IntSlider(name="Min run length to report", start=3, end=10, value=self._get("homopolymer_min_run"), width=300)
        max_allowed = pn.widgets.IntSlider(name="Max allowed run length", start=4, end=15, value=self._get("homopolymer_max_allowed"), width=300)
        bases = pn.widgets.MultiChoice(
            name="Flag bases", options=["A", "T", "G", "C"],
            value=self._get("homopolymer_bases"), width=300,
        )

        for w, k in [(min_run, "homopolymer_min_run"), (max_allowed, "homopolymer_max_allowed"), (bases, "homopolymer_bases")]:
            def _update(event, key=k):
                s = dict(self._state.analysis_settings)
                s[key] = event.new
                self._state.analysis_settings = s
            w.param.watch(_update, "value")

        return pn.Column(
            self._section_header("Homopolymer Detection", "homopolymer_enabled"),
            pn.Row(min_run, max_allowed),
            bases,
            pn.layout.Divider(),
            sizing_mode="stretch_width",
        )

    def _build_restriction_section(self) -> pn.Column:
        # Enzyme categories as expandable sections
        all_enzymes = sorted(set(
            e for enzymes in ENZYME_CATEGORIES.values() for e in enzymes
        ))

        enzyme_select = pn.widgets.MultiChoice(
            name="Active enzymes",
            options=all_enzymes,
            value=self._get("restriction_enzymes"),
            width=600,
        )

        mode = pn.widgets.Select(
            name="Mode",
            options=["Report all sites found", "Flag only unwanted sites"],
            value=self._get("restriction_mode"),
            width=300,
        )

        # Category quick-select buttons
        category_buttons = []
        for cat_name, cat_enzymes in ENZYME_CATEGORIES.items():
            btn = pn.widgets.Button(name=cat_name, button_type="light", width=180, margin=(2, 2),
                                    stylesheets=[":host .bk-btn { font-size: 10px; padding: 3px 8px; }"])

            def _add_category(event, enzymes=cat_enzymes):
                current = list(enzyme_select.value)
                for e in enzymes:
                    if e not in current:
                        current.append(e)
                enzyme_select.value = current

            btn.on_click(_add_category)
            category_buttons.append(btn)

        def _update_enzymes(event):
            s = dict(self._state.analysis_settings)
            s["restriction_enzymes"] = event.new
            self._state.analysis_settings = s

        def _update_mode(event):
            s = dict(self._state.analysis_settings)
            s["restriction_mode"] = event.new
            self._state.analysis_settings = s

        enzyme_select.param.watch(_update_enzymes, "value")
        mode.param.watch(_update_mode, "value")

        return pn.Column(
            self._section_header("Restriction Enzyme Library", "restriction_enabled"),
            pn.pane.HTML('<div style="font-size:11px;color:#64748B;margin-bottom:4px;">Quick add by category:</div>'),
            pn.Row(*category_buttons, sizing_mode="stretch_width"),
            enzyme_select,
            mode,
            pn.layout.Divider(),
            sizing_mode="stretch_width",
        )

    def _build_cds_section(self) -> pn.Column:
        check_start = pn.widgets.Toggle(name="Check start codon (ATG)", value=self._get("cds_check_start"), width=200)
        check_stop = pn.widgets.Toggle(name="Check stop codon", value=self._get("cds_check_stop"), width=200)
        double_stop = pn.widgets.Toggle(name="Require double stop codon", value=self._get("cds_double_stop"), width=200)
        accepted_stops = pn.widgets.MultiChoice(
            name="Accepted stop codons", options=["TAA", "TAG", "TGA"],
            value=self._get("cds_accepted_stops"), width=300,
        )
        check_frame = pn.widgets.Toggle(name="Check reading frame (div by 3)", value=self._get("cds_check_frame"), width=250)

        for w, k in [(check_start, "cds_check_start"), (check_stop, "cds_check_stop"),
                      (double_stop, "cds_double_stop"), (accepted_stops, "cds_accepted_stops"),
                      (check_frame, "cds_check_frame")]:
            def _update(event, key=k):
                s = dict(self._state.analysis_settings)
                s[key] = event.new
                self._state.analysis_settings = s
            w.param.watch(_update, "value")

        return pn.Column(
            self._section_header("CDS Validation", "cds_enabled"),
            pn.Row(check_start, check_stop, double_stop),
            accepted_stops,
            check_frame,
            pn.layout.Divider(),
            sizing_mode="stretch_width",
        )

    def _build_kozak_section(self) -> pn.Column:
        min_strength = pn.widgets.Select(
            name="Min strength threshold", options=["Strong", "Adequate", "Weak"],
            value=self._get("kozak_min_strength"), width=200,
        )
        flag_r3 = pn.widgets.Toggle(name="Flag non-consensus -3", value=self._get("kozak_flag_r3"), width=200)

        for w, k in [(min_strength, "kozak_min_strength"), (flag_r3, "kozak_flag_r3")]:
            def _update(event, key=k):
                s = dict(self._state.analysis_settings)
                s[key] = event.new
                self._state.analysis_settings = s
            w.param.watch(_update, "value")

        return pn.Column(
            self._section_header("Kozak Context", "kozak_enabled"),
            pn.Row(min_strength, flag_r3),
            pn.layout.Divider(),
            sizing_mode="stretch_width",
        )

    def _build_structure_section(self) -> pn.Column:
        engine = pn.widgets.Select(
            name="Engine", options=["ViennaRNA", "LinearFold (if available)"],
            value=self._get("structure_engine"), width=250,
        )
        temp = pn.widgets.FloatInput(name="Temperature (°C)", value=self._get("structure_temperature"), step=0.5, width=150)

        for w, k in [(engine, "structure_engine"), (temp, "structure_temperature")]:
            def _update(event, key=k):
                s = dict(self._state.analysis_settings)
                s[key] = event.new
                self._state.analysis_settings = s
            w.param.watch(_update, "value")

        return pn.Column(
            self._section_header("Secondary Structure", "structure_enabled"),
            pn.Row(engine, temp),
            pn.layout.Divider(),
            sizing_mode="stretch_width",
        )

    def _build_uridine_section(self) -> pn.Column:
        threshold = pn.widgets.FloatSlider(
            name="High-U stretch threshold", start=0.2, end=0.6, value=self._get("uridine_flag_threshold"), step=0.05, width=300,
        )

        def _update(event):
            s = dict(self._state.analysis_settings)
            s["uridine_flag_threshold"] = event.new
            self._state.analysis_settings = s
        threshold.param.watch(_update, "value")

        return pn.Column(
            self._section_header("Uridine Content", "uridine_enabled"),
            pn.pane.HTML('<div style="font-size:11px;color:#64748B;">Report U/A ratio and flag high-uridine stretches.</div>'),
            threshold,
            pn.layout.Divider(),
            sizing_mode="stretch_width",
        )

    def _build_dinucleotide_section(self) -> pn.Column:
        flag_cpg = pn.widgets.Toggle(name="Flag CpG dinucleotides", value=self._get("dinucleotide_flag_cpg"), width=200)
        flag_upa = pn.widgets.Toggle(name="Flag UpA dinucleotides", value=self._get("dinucleotide_flag_upa"), width=200)

        for w, k in [(flag_cpg, "dinucleotide_flag_cpg"), (flag_upa, "dinucleotide_flag_upa")]:
            def _update(event, key=k):
                s = dict(self._state.analysis_settings)
                s[key] = event.new
                self._state.analysis_settings = s
            w.param.watch(_update, "value")

        return pn.Column(
            self._section_header("Dinucleotide Frequency", "dinucleotide_enabled"),
            pn.pane.HTML('<div style="font-size:11px;color:#64748B;">CpG = immunostimulatory; UpA = mRNA instability.</div>'),
            pn.Row(flag_cpg, flag_upa),
            sizing_mode="stretch_width",
        )

    def panel(self) -> pn.Column:
        """Build the full settings panel."""
        reset_btn = pn.widgets.Button(name="Reset to Defaults", button_type="warning", width=150, margin=(8, 0))

        def on_reset(event):
            self._state.analysis_settings = dict(DEFAULT_SETTINGS)
            self._state.set_status("Analysis settings reset to defaults")

        reset_btn.on_click(on_reset)

        apply_btn = pn.widgets.Button(name="Apply & Close", button_type="success", width=150, margin=(8, 8))

        def on_apply(event):
            self._state.set_status("Analysis settings updated")

        apply_btn.on_click(on_apply)

        return pn.Column(
            pn.pane.HTML(
                '<div style="font-size:16px;font-weight:800;padding:8px 0 4px 0;">'
                'Analysis Settings</div>'
                '<div style="font-size:12px;color:#64748B;margin-bottom:10px;">'
                'Configure parameters for each analysis module. Changes apply '
                'to the next analysis run.</div>'
            ),
            self._build_gc_section(),
            self._build_cai_section(),
            self._build_homopolymer_section(),
            self._build_restriction_section(),
            self._build_cds_section(),
            self._build_kozak_section(),
            self._build_structure_section(),
            self._build_uridine_section(),
            self._build_dinucleotide_section(),
            pn.Row(reset_btn, apply_btn),
            sizing_mode="stretch_width",
            styles={"padding": "8px 16px", "max-height": "70vh", "overflow-y": "auto"},
        )
