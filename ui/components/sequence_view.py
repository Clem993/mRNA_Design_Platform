"""
Sequence detail view.

Shows the active sequence's components, raw sequence text, and
component annotations in a colour-coded track.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import panel as pn
import param

from core.models.sequence import mRNASequence

if TYPE_CHECKING:
    from ui.state import AppState

# Component colours — science palette
_COMPONENT_COLORS = {
    "5'UTR":  "#0284C7",    # sky-600
    "Kozak":  "#D97706",    # amber-600
    "CDS":    "#059669",    # emerald-600
    "3'UTR":  "#7C3AED",    # violet-600
    "PolyA":  "#DC2626",    # red-600
}


def _component_track_html(seq: mRNASequence) -> str:
    """Render an SVG-like horizontal bar showing sequence components."""
    if not seq.has_components:
        return '<div style="color:#64748B;font-size:12px;">No component breakdown available.</div>'

    annotations = seq.component_annotations
    total_len = seq.length or 1
    bar_width = 560

    rects = []
    for ann in annotations:
        x = int(ann.start / total_len * bar_width)
        w = max(2, int(ann.length / total_len * bar_width))
        color = ann.color or "#94A3B8"
        rects.append(
            f'<rect x="{x}" y="0" width="{w}" height="28" fill="{color}" rx="3"/>'
            f'<text x="{x + w//2}" y="19" text-anchor="middle" '
            f'font-size="10" fill="white" font-family="monospace">'
            f'{ann.label}</text>'
        )

    svg = (
        f'<svg width="{bar_width}" height="28" xmlns="http://www.w3.org/2000/svg">'
        + "".join(rects)
        + "</svg>"
    )
    ticks = (
        f'<div style="display:flex;justify-content:space-between;'
        f'font-size:9px;color:#64748B;width:{bar_width}px;">'
        f'<span>0</span><span>{total_len} nt</span></div>'
    )
    return f'<div style="overflow-x:auto;">{svg}{ticks}</div>'


def _derive_component_name(seq: mRNASequence, component_type: str) -> str:
    """Derive a descriptive name for a component from sequence metadata."""
    meta = seq.raw_metadata or {}
    seq_name = seq.name or ""

    if component_type == "CDS":
        # Try target_protein or gene name
        protein = meta.get("target_protein") or meta.get("protein") or meta.get("gene")
        if protein:
            return f"{component_type}: {protein}"
        return f"{component_type}: {seq_name}"
    elif component_type == "5' UTR":
        # Look for UTR-specific metadata
        utr_name = meta.get("utr5_name") or meta.get("five_prime_utr_name")
        if utr_name:
            return f"{component_type}: {utr_name}"
        return f"{component_type} ({seq_name})"
    elif component_type == "3' UTR":
        utr_name = meta.get("utr3_name") or meta.get("three_prime_utr_name")
        if utr_name:
            return f"{component_type}: {utr_name}"
        return f"{component_type} ({seq_name})"
    elif component_type == "Kozak":
        return f"{component_type} ({seq_name})"
    elif component_type == "Poly-A":
        return f"{component_type} ({seq_name})"
    elif component_type == "Full mRNA":
        return f"{component_type}: {seq_name}"
    return component_type


def _component_fields_html(seq: mRNASequence) -> str:
    """Render component sequences in labelled code blocks with specific names."""
    components = [
        ("5' UTR", seq.five_prime_utr),
        ("Kozak", seq.kozak),
        ("CDS", seq.cds),
        ("3' UTR", seq.three_prime_utr),
        ("Poly-A", seq.poly_a),
        ("Full mRNA", seq.full_mrna),
    ]
    blocks = []
    for label, value in components:
        if not value:
            continue
        display_name = _derive_component_name(seq, label)
        preview = value[:120] + ("…" if len(value) > 120 else "")
        color = _COMPONENT_COLORS.get(label.replace(" ", ""), "#94A3B8")
        blocks.append(f"""
        <div style="margin-bottom:10px;">
            <div style="font-size:11px;font-weight:700;color:{color};
                        text-transform:uppercase;letter-spacing:1px;
                        margin-bottom:3px;">{display_name}</div>
            <div style="font-family:monospace;font-size:11px;background:#F1F5F9;
                        border:1px solid #CBD5E1;border-radius:4px;padding:6px 8px;
                        word-break:break-all;color:#0F172A;">{preview}</div>
            <div style="font-size:10px;color:#64748B;margin-top:2px;">
                {len(value)} nt</div>
        </div>
        """)
    return "".join(blocks) if blocks else '<div style="color:#64748B;">No sequence data.</div>'


class SequenceView(param.Parameterized):
    """Detail panel for the active sequence."""

    def __init__(self, state: "AppState", **params: object) -> None:
        super().__init__(**params)
        self._state = state

    @param.depends("_state.active_sequence")
    def panel(self) -> pn.Column:
        seq = self._state.active_sequence
        if seq is None:
            return pn.Column(
                pn.pane.HTML(
                    '<div style="color:#64748B;padding:40px;font-size:14px;">'
                    'Select a sequence from the registry to view details.</div>'
                )
            )

        # Header with metadata
        source_badge = (
            '<span style="background:#059669;color:white;border-radius:3px;'
            'padding:2px 6px;font-size:10px;font-weight:700;">LOCAL</span>'
            if seq.source == "local" else
            f'<span style="background:#0D9488;color:white;border-radius:3px;'
            f'padding:2px 6px;font-size:10px;font-weight:700;">DB: {seq.db_source}</span>'
        )

        # Show key metadata fields
        meta = seq.raw_metadata or {}
        meta_badges = ""
        protein = meta.get("target_protein") or meta.get("protein")
        organism = meta.get("organism")
        expr_sys = meta.get("expression_system")
        if protein:
            meta_badges += (
                f'<span style="background:#05966933;color:#059669;border-radius:3px;'
                f'padding:2px 6px;font-size:10px;font-weight:600;">{protein}</span> '
            )
        if organism:
            meta_badges += (
                f'<span style="background:#7C3AED33;color:#7C3AED;border-radius:3px;'
                f'padding:2px 6px;font-size:10px;font-weight:600;">{organism}</span> '
            )
        if expr_sys:
            meta_badges += (
                f'<span style="background:#D9770633;color:#D97706;border-radius:3px;'
                f'padding:2px 6px;font-size:10px;font-weight:600;">{expr_sys}</span> '
            )

        # Component summary line
        component_parts = []
        if seq.five_prime_utr:
            component_parts.append("5'UTR")
        if seq.kozak:
            component_parts.append("Kozak")
        if seq.cds:
            component_parts.append("CDS")
        if seq.three_prime_utr:
            component_parts.append("3'UTR")
        if seq.poly_a:
            component_parts.append("PolyA")
        if seq.full_mrna and not component_parts:
            component_parts.append("Full mRNA")
        components_str = " + ".join(component_parts) if component_parts else "No components"

        header_html = f"""
        <div style="padding:16px 0 8px 0;">
            <div style="font-size:20px;font-weight:800;">{seq.name}</div>
            <div style="margin-top:4px;display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
                {source_badge}
                <span style="font-size:12px;color:#64748B;">{seq.length} nt total</span>
                <span style="font-size:12px;color:#64748B;">ID: {seq.id[:8]}…</span>
            </div>
            <div style="margin-top:6px;display:flex;gap:4px;align-items:center;flex-wrap:wrap;">
                {meta_badges}
            </div>
            <div style="margin-top:4px;font-size:11px;color:#64748B;">
                Components: {components_str}
            </div>
        </div>
        """

        # Component track
        track_html = _component_track_html(seq)

        # Component fields
        fields_html = _component_fields_html(seq)

        # Metadata (raw DB fields)
        meta_rows = ""
        if seq.raw_metadata:
            rows = "".join(
                f'<tr><td style="font-size:11px;color:#64748B;padding:2px 8px;">'
                f'{k}</td><td style="font-size:11px;font-family:monospace;">'
                f'{str(v)[:80]}</td></tr>'
                for k, v in seq.raw_metadata.items()
            )
            meta_rows = f"""
            <details style="margin-top:12px;">
                <summary style="font-size:12px;cursor:pointer;color:#0D9488;">
                    Raw metadata ({len(seq.raw_metadata)} fields)
                </summary>
                <table style="margin-top:6px;border-collapse:collapse;">{rows}</table>
            </details>
            """

        add_to_worklist_btn = pn.widgets.Button(
            name="Add to Worklist",
            button_type="primary",
            margin=(8, 0),
        )
        add_to_worklist_btn.on_click(self._add_to_worklist)

        run_analysis_btn = pn.widgets.Button(
            name="Run Analysis",
            button_type="success",
            margin=(8, 4),
        )
        run_analysis_btn.on_click(self._run_analysis)

        return pn.Column(
            pn.pane.HTML(header_html),
            pn.Row(add_to_worklist_btn, run_analysis_btn),
            pn.layout.Divider(),
            pn.pane.HTML(
                '<div style="font-size:12px;font-weight:700;margin-bottom:6px;">'
                'Component Map</div>'
            ),
            pn.pane.HTML(track_html),
            pn.layout.Divider(),
            pn.pane.HTML(
                '<div style="font-size:12px;font-weight:700;margin-bottom:8px;">'
                'Sequence Components</div>'
            ),
            pn.pane.HTML(fields_html),
            pn.pane.HTML(meta_rows) if meta_rows else pn.pane.HTML(""),
            sizing_mode="stretch_width",
            styles={"padding": "8px 16px"},
        )

    def _add_to_worklist(self, event: object) -> None:
        seq = self._state.active_sequence
        if seq:
            self._state.worklist.add(seq, origin="manual")
            self._state.set_status(f"'{seq.name}' added to worklist.")

    def _run_analysis(self, event: object) -> None:
        self._state.active_tab = "analysis"
