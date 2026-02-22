"""
Plasmid Assembly tab — assemble mRNA inserts into expression vectors.

Provides backbone selection, cloning strategy configuration, worklist
selection, QC checks, and assembly preview.
"""
from __future__ import annotations

import io
import logging
from typing import TYPE_CHECKING, List, Optional

import pandas as pd
import panel as pn
import param

from core.models.plasmid import PlasmidBackbone, AssembledPlasmid, PlasmidFeature
from core.analysis.restriction_sites import scan_restriction_sites

if TYPE_CHECKING:
    from ui.state import AppState

logger = logging.getLogger(__name__)


class PlasmidAssemblyPanel(param.Parameterized):
    """Plasmid assembly workflow panel."""

    def __init__(self, state: "AppState", **params: object) -> None:
        super().__init__(**params)
        self._state = state
        self._result_pane = pn.pane.HTML("")
        self._qc_pane = pn.pane.HTML("")
        self._preview_pane = pn.pane.HTML("")
        self._assembled_plasmids: List[AssembledPlasmid] = []

        # Load seed backbones if empty
        if not self._state.backbone_library:
            from core.data.seed_backbones import get_seed_backbones
            self._state.backbone_library = get_seed_backbones()

    @param.depends("_state.worklist", "_state.backbone_library", "_state.worklists")
    def panel(self) -> pn.Column:
        # ── Header ────────────────────────────────────────────────────────────
        header = pn.pane.HTML(
            '<div style="font-size:16px;font-weight:800;padding:8px 0 4px 0;">'
            'Assemble Plasmid</div>'
            '<div style="font-size:12px;color:#64748B;margin-bottom:16px;">'
            'Assemble mRNA sequences from the worklist into expression vectors. '
            'Select a backbone, cloning strategy, and worklist to generate assembled plasmids.</div>'
        )

        # ── Section 1: Select Backbone ────────────────────────────────────────
        backbone_names = {bb.name: bb for bb in self._state.backbone_library}
        backbone_select = pn.widgets.Select(
            name="Backbone",
            options=backbone_names if backbone_names else {"No backbones available": None},
            width=250,
        )

        backbone_info = pn.pane.HTML("", sizing_mode="stretch_width")

        def update_backbone_info(event):
            bb = event.new
            if bb and isinstance(bb, PlasmidBackbone):
                features_html = " ".join(
                    f'<span style="background:#F1F5F9;color:#475569;padding:1px 6px;'
                    f'border-radius:8px;font-size:10px;margin:1px;">{f.label}</span>'
                    for f in bb.features
                )
                sites_html = ", ".join(bb.cloning_sites[:8])
                if len(bb.cloning_sites) > 8:
                    sites_html += f" +{len(bb.cloning_sites) - 8} more"
                backbone_info.object = (
                    f'<div style="background:#F8FAFC;border:1px solid #E2E8F0;border-radius:6px;'
                    f'padding:10px;margin-top:8px;">'
                    f'<div style="font-size:12px;font-weight:600;color:#0F172A;">{bb.name}</div>'
                    f'<div style="font-size:11px;color:#64748B;margin:4px 0;">{bb.description or ""}</div>'
                    f'<div style="font-size:11px;color:#475569;">Size: {bb.length:,} bp</div>'
                    f'<div style="margin:4px 0;">{features_html}</div>'
                    f'<div style="font-size:10px;color:#94A3B8;">Cloning sites: {sites_html}</div>'
                    f'</div>'
                )
            else:
                backbone_info.object = ""

        backbone_select.param.watch(update_backbone_info, "value")
        # Trigger initial display
        if backbone_select.value and isinstance(backbone_select.value, PlasmidBackbone):
            backbone_info.object = ""
            update_backbone_info(type("Event", (), {"new": backbone_select.value})())

        backbone_section = pn.Column(
            pn.pane.HTML('<div style="font-size:14px;font-weight:700;color:#0F172A;margin-bottom:4px;">1. Select Backbone</div>'),
            backbone_select,
            backbone_info,
            sizing_mode="stretch_width",
            styles={"background": "#FFFFFF", "padding": "12px", "border-radius": "6px", "border": "1px solid #E2E8F0"},
        )

        # ── Section 2: Cloning Strategy ──────────────────────────────────────
        strategy_select = pn.widgets.RadioBoxGroup(
            name="Strategy",
            options=["Golden Gate", "Gibson Assembly", "Restriction Digest"],
            value="Golden Gate",
        )

        # Strategy-specific options
        gg_enzyme = pn.widgets.Select(
            name="Type IIS Enzyme", options=["BsaI", "BbsI", "Esp3I", "SapI", "BsmBI"],
            value="BsaI", width=150,
        )
        gibson_overlap = pn.widgets.IntSlider(
            name="Overlap (bp)", start=15, end=40, value=20, width=200,
        )
        re_5prime = pn.widgets.Select(
            name="5' Enzyme", options=["EcoRI", "NheI", "NcoI", "BamHI", "XbaI", "HindIII", "KpnI", "XhoI"],
            value="NheI", width=150,
        )
        re_3prime = pn.widgets.Select(
            name="3' Enzyme", options=["EcoRI", "NheI", "NcoI", "BamHI", "XbaI", "HindIII", "KpnI", "XhoI", "NotI"],
            value="XhoI", width=150,
        )

        strategy_options = pn.Column(sizing_mode="stretch_width")

        def update_strategy_options(event):
            strategy_options.clear()
            if event.new == "Golden Gate":
                strategy_options.append(gg_enzyme)
            elif event.new == "Gibson Assembly":
                strategy_options.append(gibson_overlap)
            else:
                strategy_options.append(pn.Row(re_5prime, re_3prime))

        strategy_select.param.watch(update_strategy_options, "value")
        strategy_options.append(gg_enzyme)  # Default

        strategy_section = pn.Column(
            pn.pane.HTML('<div style="font-size:14px;font-weight:700;color:#0F172A;margin-bottom:4px;">2. Cloning Strategy</div>'),
            strategy_select,
            strategy_options,
            sizing_mode="stretch_width",
            styles={"background": "#FFFFFF", "padding": "12px", "border-radius": "6px", "border": "1px solid #E2E8F0"},
        )

        # ── Section 3: Select Worklist ────────────────────────────────────────
        wl = self._state.worklist
        worklist_info = ""
        if wl and wl.count > 0:
            seq_names = [item.sequence.name for item in wl.items[:5]]
            preview = ", ".join(seq_names)
            if wl.count > 5:
                preview += f" ... +{wl.count - 5} more"
            worklist_info = (
                f'<div style="font-size:11px;color:#64748B;margin-top:4px;">'
                f'{wl.count} sequences: {preview}</div>'
            )

        worklist_section = pn.Column(
            pn.pane.HTML('<div style="font-size:14px;font-weight:700;color:#0F172A;margin-bottom:4px;">3. Select Worklist</div>'),
            pn.pane.HTML(
                f'<div style="font-size:12px;color:#0F172A;font-weight:600;">'
                f'📋 {wl.name if wl else "No worklist"} ({wl.count if wl else 0} sequences)</div>'
                f'{worklist_info}'
            ),
            sizing_mode="stretch_width",
            styles={"background": "#FFFFFF", "padding": "12px", "border-radius": "6px", "border": "1px solid #E2E8F0"},
        )

        # ── Assemble Button ───────────────────────────────────────────────────
        assemble_btn = pn.widgets.Button(
            name="▶ Assemble",
            button_type="success",
            width=150,
            margin=(12, 4),
        )

        def on_assemble(event):
            self._run_assembly(
                backbone_select.value,
                strategy_select.value,
                gg_enzyme.value,
                gibson_overlap.value,
                re_5prime.value,
                re_3prime.value,
            )

        assemble_btn.on_click(on_assemble)

        # ── Layout ────────────────────────────────────────────────────────────
        left_panel = pn.Column(
            backbone_section,
            strategy_section,
            worklist_section,
            assemble_btn,
            width=400,
            margin=(0, 16, 0, 0),
        )

        # ── Add to Worklist / Export section (shown after assembly) ────────
        self._worklist_name_input = pn.widgets.TextInput(
            name="Worklist Name",
            placeholder="e.g. Assembly Batch 1",
            width=250,
        )
        add_to_wl_btn = pn.widgets.Button(
            name="Save to Worklist",
            button_type="primary",
            width=160,
            margin=(20, 4, 4, 4),
        )
        add_to_wl_btn.on_click(self._on_add_to_worklist)

        self._export_csv_btn = pn.widgets.FileDownload(
            callback=lambda: self._make_assembly_csv(),
            filename="assembly_export.csv",
            button_type="light",
            label="Export CSV",
            width=120,
            margin=(20, 4, 4, 4),
        )

        self._add_to_wl_section = pn.Column(
            pn.pane.HTML(
                '<div style="font-size:13px;font-weight:700;color:#0F172A;margin-bottom:4px;">'
                'Save Results</div>'
                '<div style="font-size:11px;color:#64748B;margin-bottom:6px;">'
                'Create a new worklist from the assembled plasmids, or export to CSV.</div>'
            ),
            pn.Row(self._worklist_name_input, add_to_wl_btn, self._export_csv_btn),
            sizing_mode="stretch_width",
            styles={"background": "#F8FAFC", "padding": "12px", "border-radius": "6px",
                    "border": "1px solid #E2E8F0", "margin-top": "8px"},
            visible=False,
        )

        right_panel = pn.Column(
            pn.pane.HTML('<div style="font-size:14px;font-weight:700;color:#0F172A;margin-bottom:8px;">Assembly Preview</div>'),
            self._preview_pane,
            self._qc_pane,
            self._result_pane,
            self._add_to_wl_section,
            sizing_mode="stretch_width",
            styles={"background": "#FFFFFF", "padding": "12px", "border-radius": "6px", "border": "1px solid #E2E8F0"},
        )

        return pn.Column(
            header,
            pn.Row(left_panel, right_panel, sizing_mode="stretch_width"),
            sizing_mode="stretch_width",
            styles={"padding": "8px 16px"},
        )

    def _run_assembly(self, backbone, strategy, gg_enzyme, gibson_overlap, re_5, re_3) -> None:
        """Run assembly workflow."""
        if not backbone or not isinstance(backbone, PlasmidBackbone):
            self._result_pane.object = '<div style="color:#EF4444;">Please select a backbone.</div>'
            return

        wl = self._state.worklist
        if not wl or wl.count == 0:
            self._result_pane.object = '<div style="color:#EF4444;">Worklist is empty.</div>'
            return

        # Determine cloning enzyme(s)
        if strategy == "Golden Gate":
            cloning_enzymes = [gg_enzyme]
            strategy_key = "golden_gate"
            strategy_desc = f"Golden Gate ({gg_enzyme})"
        elif strategy == "Gibson Assembly":
            cloning_enzymes = []
            strategy_key = "gibson"
            strategy_desc = f"Gibson Assembly ({gibson_overlap} bp overlap)"
        else:
            cloning_enzymes = [re_5, re_3]
            strategy_key = "restriction"
            strategy_desc = f"Restriction Digest ({re_5} / {re_3})"

        # Assembly preview
        min_size = backbone.length + min(item.sequence.length for item in wl.items)
        max_size = backbone.length + max(item.sequence.length for item in wl.items)

        features_html = " ".join(
            f'<span style="background:{f.color or "#94A3B8"}22;color:{f.color or "#94A3B8"};'
            f'padding:2px 6px;border-radius:8px;font-size:10px;">{f.label}</span>'
            for f in backbone.features
        )

        self._preview_pane.object = (
            f'<div style="background:#F0FDFA;border:1px solid #0D9488;border-radius:6px;padding:14px;margin-bottom:8px;">'
            f'<div style="font-weight:700;color:#0F766E;margin-bottom:6px;">🧬 {backbone.name}</div>'
            f'<div style="margin-bottom:6px;">{features_html}</div>'
            f'<div style="font-size:12px;color:#134E4A;">↕ Insert: {wl.name} ({wl.count} sequences)</div>'
            f'<div style="font-size:12px;color:#134E4A;margin-top:4px;">Strategy: {strategy_desc}</div>'
            f'<div style="font-size:12px;color:#134E4A;">Estimated size: {min_size:,} - {max_size:,} bp</div>'
            f'</div>'
        )

        # QC checks
        qc_items = []
        warnings = 0

        if cloning_enzymes:
            # Check inserts for conflicting restriction sites
            conflicts = 0
            for item in wl.items:
                try:
                    seq = item.sequence.assembled_sequence
                    hits = scan_restriction_sites(seq, cloning_enzymes)
                    if hits:
                        conflicts += 1
                except (ValueError, Exception):
                    pass

            if conflicts == 0:
                qc_items.append(f'<div style="color:#10B981;font-size:12px;">✓ No {"/".join(cloning_enzymes)} sites in inserts</div>')
            else:
                qc_items.append(f'<div style="color:#EF4444;font-size:12px;">✗ {conflicts} insert(s) contain {"/".join(cloning_enzymes)} sites</div>')
                warnings += conflicts

        # Check CDS in-frame
        not_in_frame = sum(1 for item in wl.items if item.sequence.cds and len(item.sequence.cds) % 3 != 0)
        if not_in_frame == 0:
            qc_items.append('<div style="color:#10B981;font-size:12px;">✓ All inserts in frame</div>')
        else:
            qc_items.append(f'<div style="color:#F59E0B;font-size:12px;">⚠ {not_in_frame} insert(s) not in frame (CDS not divisible by 3)</div>')
            warnings += not_in_frame

        # Check for stop codons
        stop_codons = {"TAA", "TAG", "TGA"}
        missing_stop = 0
        for item in wl.items:
            if item.sequence.cds:
                last3 = item.sequence.cds[-3:].upper().replace("U", "T")
                if last3 not in stop_codons:
                    missing_stop += 1

        if missing_stop == 0:
            qc_items.append('<div style="color:#10B981;font-size:12px;">✓ All inserts have stop codon</div>')
        else:
            qc_items.append(f'<div style="color:#F59E0B;font-size:12px;">⚠ {missing_stop} insert(s) lack stop codon</div>')
            warnings += missing_stop

        # Size validation
        oversized = sum(1 for item in wl.items if backbone.length + item.sequence.length > 15000)
        if oversized == 0:
            qc_items.append('<div style="color:#10B981;font-size:12px;">✓ All assemblies within size limits</div>')
        else:
            qc_items.append(f'<div style="color:#F59E0B;font-size:12px;">⚠ {oversized} assembly(ies) exceed 15 kb</div>')

        self._qc_pane.object = (
            f'<div style="background:#F8FAFC;border:1px solid #E2E8F0;border-radius:6px;padding:12px;margin-bottom:8px;">'
            f'<div style="font-weight:700;color:#0F172A;margin-bottom:6px;">QC Checks</div>'
            f'{"".join(qc_items)}'
            f'</div>'
        )

        # Create assembled plasmids
        self._assembled_plasmids = []
        for item in wl.items:
            try:
                assembled = AssembledPlasmid(
                    name=f"{backbone.name}_{item.sequence.name}",
                    backbone=backbone,
                    insert=item.sequence,
                    assembly_strategy=strategy_key,
                    assembly_mode="qc",
                    full_sequence=backbone.sequence + item.sequence.assembled_sequence,
                )
                self._assembled_plasmids.append(assembled)
            except Exception as e:
                logger.warning(f"Assembly failed for {item.sequence.name}: {e}")

        assembled_count = len(self._assembled_plasmids)

        self._result_pane.object = (
            f'<div style="background:#ECFDF5;border:1px solid #10B981;border-radius:6px;padding:12px;">'
            f'<div style="font-weight:700;color:#065F46;">Assembly Complete</div>'
            f'<div style="font-size:12px;color:#047857;margin-top:4px;">'
            f'✓ {assembled_count} plasmid(s) assembled'
            f'{f", {warnings} QC warning(s)" if warnings else ""}</div>'
            f'</div>'
        )

        # Show "Save Results" section with a default name
        if assembled_count > 0:
            self._worklist_name_input.value = f"{backbone.name} Assembly"
            self._export_csv_btn.filename = f"{backbone.name.replace(' ', '_')}_assembly.csv"
            self._add_to_wl_section.visible = True

        self._state.set_status(f"Assembled {assembled_count} plasmids using {strategy_desc}")

    def _make_assembly_csv(self) -> io.BytesIO:
        """Build CSV bytes for the FileDownload widget."""
        rows = []
        for p in self._assembled_plasmids:
            rows.append({
                "Plasmid Name": p.name,
                "Backbone": p.backbone.name,
                "Insert": p.insert.name,
                "Strategy": p.assembly_strategy,
                "Backbone Length (bp)": p.backbone.length,
                "Insert Length (bp)": p.insert.length,
                "Total Length (bp)": len(p.full_sequence) if p.full_sequence else "",
                "Full Sequence": p.full_sequence or "",
            })
        df = pd.DataFrame(rows) if rows else pd.DataFrame(
            columns=["Plasmid Name", "Backbone", "Insert", "Strategy",
                     "Backbone Length (bp)", "Insert Length (bp)", "Total Length (bp)"]
        )
        buf = io.BytesIO()
        df.to_csv(buf, index=False)
        buf.seek(0)
        return buf

    def _on_add_to_worklist(self, event) -> None:
        """Create a new worklist from assembled plasmids."""
        if not self._assembled_plasmids:
            self._state.set_status("No assembled plasmids to add.", level="warning")
            return

        from core.models.worklist import Worklist

        name = self._worklist_name_input.value.strip()
        if not name:
            name = "Assembly Worklist"

        new_wl = Worklist(name=name)
        for plasmid in self._assembled_plasmids:
            new_wl.add(plasmid.insert, origin="generated")

        # Add to worklists list and switch to it
        updated = list(self._state.worklists) + [new_wl]
        self._state.worklists = updated
        self._state.active_worklist_index = len(updated) - 1
        self._state.worklist = new_wl
        self._state.active_tab = "worklist"

        self._add_to_wl_section.visible = False
        self._state.set_status(f"Created worklist '{name}' with {new_wl.count} sequences")
