"""
Analysis dashboard.

Runs SequenceAnalyzer against the active sequence and displays:
  - GC content sliding window (Plotly)
  - CAI score + codon usage heatmap
  - Homopolymer summary
  - Restriction site hits
  - Kozak context evaluation
  - ViennaRNA secondary structure (MFE)
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import panel as pn
import param
import plotly.graph_objects as go

from core.analysis.analyzer import SequenceAnalyzer, AnalysisReport

if TYPE_CHECKING:
    from ui.state import AppState


_analyzer = SequenceAnalyzer()


def _gc_plot(report: AnalysisReport) -> pn.pane.Plotly:
    """Interactive GC% sliding window Plotly chart."""
    pos = report.gc_sliding_positions
    vals = report.gc_sliding_values

    if pos is None or len(pos) == 0:
        return pn.pane.HTML('<div style="color:#64748B;">Insufficient sequence length for GC plot.</div>')

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=pos,
        y=vals,
        mode="lines",
        line={"color": "#0F766E", "width": 1.5},
        name="GC%",
        hovertemplate="Position: %{x}<br>GC: %{y:.1f}%<extra></extra>",
    ))
    fig.add_hline(y=50, line_dash="dash", line_color="#DC2626", opacity=0.5,
                  annotation_text="50%", annotation_position="bottom right")
    fig.update_layout(
        title=dict(text="GC Content (sliding window)", font=dict(size=13)),
        xaxis_title="Position (nt)",
        yaxis_title="GC (%)",
        yaxis=dict(range=[0, 100]),
        height=260,
        margin=dict(l=50, r=20, t=40, b=40),
        plot_bgcolor="#F8FAFC",
        paper_bgcolor="white",
    )
    return pn.pane.Plotly(fig, sizing_mode="stretch_width")


def _cai_card(report: AnalysisReport) -> pn.pane.HTML:
    cai = report.cai
    if cai is None:
        return pn.pane.HTML('<div style="color:#64748B;font-size:12px;">No CDS available for CAI.</div>')
    pct = int(cai * 100)
    color = "#059669" if cai >= 0.7 else "#D97706" if cai >= 0.4 else "#DC2626"
    bar = f'<div style="height:8px;background:#E2E8F0;border-radius:4px;">' \
          f'<div style="height:8px;width:{pct}%;background:{color};border-radius:4px;"></div></div>'
    org = report.cai_organism or "unknown"
    return pn.pane.HTML(f"""
        <div style="margin-bottom:8px;">
            <span style="font-size:22px;font-weight:800;color:{color};">{cai:.3f}</span>
            <span style="font-size:11px;color:#64748B;margin-left:6px;">
                CAI ({org})</span>
        </div>
        {bar}
        <div style="font-size:10px;color:#94A3B8;margin-top:3px;">
            0.7+ = high adaptation · 0.4–0.7 = moderate · &lt;0.4 = poor</div>
    """)


def _validation_card(report: AnalysisReport) -> pn.pane.HTML:
    checks = [
        ("Start codon (ATG)", report.has_start_codon),
        ("Stop codon present", report.has_stop_codon),
        ("In-frame CDS (÷3)", report.in_frame),
    ]
    rows = ""
    for label, ok in checks:
        if ok is None:
            icon, color = "—", "#94A3B8"
        elif ok:
            icon, color = "Pass", "#059669"
        else:
            icon, color = "Fail", "#DC2626"
        rows += (
            f'<div style="display:flex;gap:8px;align-items:center;margin-bottom:4px;">'
            f'<span style="font-weight:700;color:{color};width:32px;font-size:11px;">{icon}</span>'
            f'<span style="font-size:12px;">{label}</span></div>'
        )
    return pn.pane.HTML(rows)


def _homopolymer_card(report: AnalysisReport) -> pn.pane.HTML:
    if report.homopolymer_count == 0:
        return pn.pane.HTML(
            '<div style="color:#059669;font-size:12px;">No homopolymers detected '
            f'(min run ≥ 5 nt)</div>'
        )
    runs = report.homopolymer_runs
    rows = "".join(
        f'<tr><td style="font-family:monospace;font-size:11px;padding:2px 8px;">'
        f'{r.nucleotide}×{r.length}</td>'
        f'<td style="font-size:11px;padding:2px 8px;color:#64748B;">pos {r.start}</td></tr>'
        for r in sorted(runs, key=lambda r: -r.length)[:10]
    )
    return pn.pane.HTML(
        f'<div style="color:#DC2626;font-size:12px;margin-bottom:6px;">'
        f'{report.homopolymer_count} homopolymer run(s) — '
        f'longest: {report.longest_homopolymer} nt</div>'
        f'<table style="border-collapse:collapse;">{rows}</table>'
    )


def _restriction_card(report: AnalysisReport) -> pn.pane.HTML:
    present = report.restriction_enzymes_present
    if not present:
        return pn.pane.HTML(
            '<div style="color:#059669;font-size:12px;">No common restriction sites found.</div>'
        )
    chips = " ".join(
        f'<span style="background:#DC2626;color:white;border-radius:3px;'
        f'padding:2px 6px;font-size:10px;margin:2px;">{e}</span>'
        for e in sorted(present)
    )
    return pn.pane.HTML(f'<div>Sites present: {chips}</div>')


def _kozak_card(report: AnalysisReport) -> pn.pane.HTML:
    kz = report.kozak
    if kz is None:
        return pn.pane.HTML('<div style="color:#64748B;font-size:12px;">No Kozak context available.</div>')
    color = {"strong": "#059669", "adequate": "#D97706", "weak": "#DC2626"}.get(kz.strength, "#94A3B8")
    r3_ok = "Yes" if kz.has_optimal_r3 else "No"
    return pn.pane.HTML(f"""
        <div>
            <span style="font-weight:700;color:{color};">{kz.strength.upper()}</span>
            <span style="font-size:11px;color:#64748B;margin-left:6px;">
                score {kz.score:.2f}</span>
        </div>
        <div style="font-family:monospace;font-size:12px;margin:4px 0;
                    background:#F1F5F9;padding:4px 6px;border-radius:3px;">
            {kz.context}
        </div>
        <div style="font-size:10px;color:#64748B;">
            -3 purine (R): {r3_ok} · ATG pos: {kz.atg_position}
        </div>
    """)


def _structure_card(report: AnalysisReport) -> pn.pane.HTML:
    s = report.structure
    if s is None or s.is_stub:
        return pn.pane.HTML(
            '<div style="color:#64748B;font-size:12px;">'
            'ViennaRNA not installed. Install with: conda install -c bioconda viennarna</div>'
        )
    color = "#059669" if s.mfe > -50 else "#D97706" if s.mfe > -200 else "#DC2626"
    return pn.pane.HTML(f"""
        <div>
            <span style="font-size:18px;font-weight:700;color:{color};">
                {s.mfe:.1f} kcal/mol</span>
            <span style="font-size:11px;color:#64748B;margin-left:6px;">MFE</span>
        </div>
        <div style="font-family:monospace;font-size:10px;
                    word-break:break-all;color:#0F172A;
                    background:#F1F5F9;padding:6px;border-radius:3px;
                    max-height:80px;overflow-y:auto;margin-top:4px;">
            {s.structure[:300]}{'…' if len(s.structure) > 300 else ''}
        </div>
    """)


def _metric_panel(title: str, content: pn.viewable.Viewable) -> pn.Column:
    return pn.Column(
        pn.pane.HTML(
            f'<div style="font-size:12px;font-weight:700;color:#0F172A;'
            f'margin-bottom:6px;">{title}</div>'
        ),
        content,
        styles={
            "background": "white",
            "border": "1px solid #CBD5E1",
            "border-radius": "6px",
            "padding": "12px 14px",
        },
        sizing_mode="stretch_width",
        margin=(0, 0, 10, 0),
    )


class AnalysisDashboard(param.Parameterized):
    """Analysis dashboard panel."""

    def __init__(self, state: "AppState", **params: object) -> None:
        super().__init__(**params)
        self._state = state
        self._report: Optional[AnalysisReport] = None

    @param.depends("_state.active_sequence", "_state.active_tab")
    def panel(self) -> pn.Column:
        seq = self._state.active_sequence
        if seq is None:
            return pn.Column(
                pn.pane.HTML(
                    '<div style="color:#64748B;padding:40px;">Select a sequence first.</div>'
                )
            )

        # Run analysis (cached on sequence object)
        try:
            report = _analyzer.run_full_analysis(seq)
            self._report = report
        except Exception as e:
            return pn.Column(
                pn.pane.HTML(
                    f'<div style="color:#DC2626;padding:20px;">Analysis error: {e}</div>'
                )
            )

        warnings_html = ""
        if report.warnings:
            warn_items = "".join(f"<li>{w}</li>" for w in report.warnings)
            warnings_html = (
                f'<div style="background:#FEF3C7;border:1px solid #FDE68A;'
                f'border-radius:4px;padding:8px 12px;margin-bottom:10px;">'
                f'<b>Warnings:</b><ul style="margin:4px 0 0 16px;font-size:12px;">'
                f'{warn_items}</ul></div>'
            )

        # Summary bar
        gc_str = f"{report.gc_percent_global:.1f}%"
        cai_str = f"{report.cai:.3f}" if report.cai is not None else "N/A"
        mfe_str = (
            f"{report.structure.mfe:.1f} kcal/mol"
            if report.structure and not report.structure.is_stub
            else "N/A"
        )
        summary_html = f"""
        <div style="display:flex;gap:20px;padding:12px 0;flex-wrap:wrap;">
            <div><div style="font-size:10px;color:#64748B;">LENGTH</div>
                 <div style="font-size:16px;font-weight:700;">{report.sequence_length} nt</div></div>
            <div><div style="font-size:10px;color:#64748B;">GC%</div>
                 <div style="font-size:16px;font-weight:700;">{gc_str}</div></div>
            <div><div style="font-size:10px;color:#64748B;">CAI</div>
                 <div style="font-size:16px;font-weight:700;">{cai_str}</div></div>
            <div><div style="font-size:10px;color:#64748B;">MFE</div>
                 <div style="font-size:16px;font-weight:700;">{mfe_str}</div></div>
        </div>
        """

        return pn.Column(
            pn.pane.HTML(
                f'<div style="font-size:16px;font-weight:800;padding:8px 0 4px 0;">'
                f'Analysis: {seq.name}</div>'
            ),
            pn.pane.HTML(warnings_html) if warnings_html else pn.pane.HTML(""),
            pn.pane.HTML(summary_html),
            pn.layout.Divider(),
            _gc_plot(report),
            pn.GridBox(
                _metric_panel("Codon Adaptation Index", _cai_card(report)),
                _metric_panel("CDS Validation", _validation_card(report)),
                _metric_panel("Kozak Context", _kozak_card(report)),
                _metric_panel("Homopolymers", _homopolymer_card(report)),
                _metric_panel("Restriction Sites", _restriction_card(report)),
                _metric_panel("Secondary Structure (MFE)", _structure_card(report)),
                ncols=2,
                sizing_mode="stretch_width",
            ),
            sizing_mode="stretch_width",
            styles={"padding": "8px 16px"},
        )
