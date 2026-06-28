"""
Candidate Analysis.

Two authentic mRNA-design views over the current worklist:

  A. **Comparison scorecard** — every candidate scored on the four objectives a
     designer trades off (Expression, Stability, Immunogenicity, Manufacturability)
     plus an overall, ranked, with a top-N shortlist.
  B. **Sequence/structure track** — for a selected candidate, a per-position map:
     region bands (5'UTR/Kozak/CDS/3'UTR/polyA), GC sliding window, and markers
     for restriction sites, homopolymers, and liability motifs — i.e. *where* the
     problems are.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List, Tuple

import panel as pn
import param
import plotly.graph_objects as go

from core.analysis.candidate_score import score_objectives, ObjectiveScores

if TYPE_CHECKING:
    from ui.state import AppState


_OBJECTIVES = ["Expression", "Stability", "Immunogenicity", "Manufacturability", "Overall"]
_REGION_COLORS = {
    "5'UTR": "#3B82F6", "Kozak": "#D97706", "CDS": "#10B981",
    "3'UTR": "#8B5CF6", "PolyA": "#EF4444",
}


def _empty(msg: str) -> pn.pane.HTML:
    return pn.pane.HTML(f'<div style="color:#64748B;padding:30px;text-align:center;">{msg}</div>')


def _score_color(v: float) -> Tuple[str, str]:
    """(background, text) for a 0–100 score."""
    if v >= 80:
        return "#DCFCE7", "#166534"
    if v >= 60:
        return "#FEF9C3", "#854D0E"
    if v >= 40:
        return "#FFEDD5", "#9A3412"
    return "#FEE2E2", "#991B1B"


class CandidateView(param.Parameterized):
    """Multi-objective candidate comparison + per-candidate track."""

    def __init__(self, state: "AppState", **params: object) -> None:
        super().__init__(**params)
        self._state = state
        self._shortlist = pn.widgets.IntSlider(
            name="Shortlist top N", start=1, end=10, value=3, width=220, margin=(4, 10))
        self._candidate = pn.widgets.Select(name="Inspect candidate", width=340, margin=(4, 10))

    # ── analysis ──────────────────────────────────────────────────────────────
    def _analyzed(self) -> List[tuple]:
        """Return [(item, report, ObjectiveScores), …] for worklist items with content."""
        from core.analysis.analyzer import SequenceAnalyzer
        az = SequenceAnalyzer()
        out = []
        for item in self._state.worklist.items:
            try:
                rep = az.run_full_analysis(item.sequence)
                out.append((item, rep, score_objectives(rep)))
            except Exception:
                continue
        return out

    # ── A. comparison scorecard ───────────────────────────────────────────────
    def _comparison_table(self, analyzed: List[tuple], top_n: int) -> pn.pane.HTML:
        if not analyzed:
            return _empty("No analyzable sequences in the worklist.")
        ranked = sorted(analyzed, key=lambda t: t[2].overall, reverse=True)

        head = (
            '<tr style="font-size:11px;color:#64748B;border-bottom:1px solid #E2E8F0;">'
            '<td style="padding:5px 10px;">#</td><td style="padding:5px 10px;">Candidate</td>'
            + "".join(f'<td style="padding:5px 10px;text-align:center;">{o}</td>' for o in _OBJECTIVES)
            + '</tr>'
        )
        rows = ""
        for i, (item, _rep, s) in enumerate(ranked, 1):
            shortlisted = i <= top_n
            mark = '★' if shortlisted else ''
            name_bg = "background:#F0FDFA;" if shortlisted else ""
            cells = ""
            for obj in _OBJECTIVES:
                val = s.as_row()[obj]
                bg, fg = _score_color(val)
                weight = "800" if obj == "Overall" else "600"
                cells += (
                    f'<td style="padding:4px 8px;text-align:center;">'
                    f'<span style="display:inline-block;min-width:34px;background:{bg};color:{fg};'
                    f'border-radius:4px;padding:2px 6px;font-weight:{weight};font-size:12px;">{val}</span></td>'
                )
            rows += (
                f'<tr style="border-bottom:1px solid #F1F5F9;{name_bg}">'
                f'<td style="padding:4px 10px;color:#94A3B8;font-size:12px;">{i}</td>'
                f'<td style="padding:4px 10px;font-size:12px;font-weight:600;">{mark} {item.sequence.name}</td>'
                f'{cells}</tr>'
            )
        legend = (
            '<div style="font-size:11px;color:#64748B;margin-top:8px;">'
            'Higher is better (0–100). ★ = shortlisted. '
            'Overall = weighted blend (Expression 30% · Stability 25% · '
            'Immunogenicity 20% · Manufacturability 25%). Heuristic scores from computed metrics.'
            '</div>'
        )
        return pn.pane.HTML(
            f'<table style="border-collapse:collapse;width:100%;">{head}{rows}</table>{legend}'
        )

    # ── B. per-candidate sequence/structure track ──────────────────────────────
    def _track(self, analyzed: List[tuple], candidate_name: str) -> pn.viewable.Viewable:
        match = next((t for t in analyzed if t[0].sequence.name == candidate_name), None)
        if match is None:
            return _empty("Select a candidate to inspect.")
        item, report, _scores = match
        seq = item.sequence

        # region bands from component lengths (offsets line up with assembled_sequence)
        comps = [("5'UTR", seq.five_prime_utr), ("Kozak", seq.kozak), ("CDS", seq.cds),
                 ("3'UTR", seq.three_prime_utr), ("PolyA", seq.poly_a)]
        bands: List[Tuple[str, int, int]] = []
        region_off = {}
        offset = 0
        for nm, s in comps:
            if s:
                bands.append((nm, offset, offset + len(s)))
                region_off[nm] = offset
                offset += len(s)
        polya_start = region_off.get("PolyA", 10 ** 12)

        fig = go.Figure()
        for nm, a, b in bands:
            fig.add_vrect(x0=a, x1=b, fillcolor=_REGION_COLORS.get(nm, "#94A3B8"),
                          opacity=0.12, line_width=0,
                          annotation_text=nm, annotation_position="top left",
                          annotation_font_size=10)

        pos = report.gc_sliding_positions
        vals = report.gc_sliding_values
        if pos is not None and len(pos):
            fig.add_trace(go.Scatter(x=list(pos), y=list(vals), mode="lines",
                                     line={"color": "#0F766E", "width": 1.4}, name="GC%",
                                     hovertemplate="pos %{x}<br>GC %{y:.0f}%<extra></extra>"))
        fig.add_hline(y=50, line_dash="dot", line_color="#CBD5E1", opacity=0.7)

        # restriction sites
        rx, rt = [], []
        for enz, hits in (report.restriction_hits or {}).items():
            for h in hits:
                rx.append(h.position); rt.append(enz)
        if rx:
            fig.add_trace(go.Scatter(x=rx, y=[96] * len(rx), mode="markers",
                marker={"symbol": "triangle-down", "size": 10, "color": "#DC2626"},
                name="Restriction site", text=rt,
                hovertemplate="%{text}<br>pos %{x}<extra></extra>"))

        # homopolymers (exclude the legitimate poly-A tail)
        hx = [r.start for r in report.homopolymer_runs if r.start < polya_start]
        ht = [f"{r.nucleotide}×{r.length}" for r in report.homopolymer_runs if r.start < polya_start]
        if hx:
            fig.add_trace(go.Scatter(x=hx, y=[89] * len(hx), mode="markers",
                marker={"symbol": "square", "size": 9, "color": "#D97706"},
                name="Homopolymer", text=ht,
                hovertemplate="%{text}<br>pos %{x}<extra></extra>"))

        # liability motifs
        mx, mt = [], []
        for h in (report.motif_hits or []):
            mx.append(region_off.get(h.region, 0) + h.start); mt.append(h.label)
        if mx:
            fig.add_trace(go.Scatter(x=mx, y=[82] * len(mx), mode="markers",
                marker={"symbol": "diamond", "size": 9, "color": "#7C3AED"},
                name="Liability motif", text=mt,
                hovertemplate="%{text}<br>pos %{x}<extra></extra>"))

        fig.update_layout(
            title={"text": f"{seq.name} — sequence map", "font": {"size": 13}},
            xaxis_title="position (nt)", yaxis={"title": "GC %", "range": [0, 100]},
            height=340, margin={"l": 55, "r": 20, "t": 40, "b": 45},
            plot_bgcolor="#F8FAFC", paper_bgcolor="white",
            legend={"orientation": "h", "y": -0.3, "font": {"size": 10}},
        )

        # reuse the liability scorecard for this candidate
        from ui.components.analysis_dashboard import render_liability_panel
        return pn.Column(
            pn.pane.Plotly(fig, sizing_mode="stretch_width"),
            render_liability_panel(report),
            self._codon_panel(seq),
            sizing_mode="stretch_width",
        )

    def _codon_panel(self, seq) -> pn.viewable.Viewable:
        """Codon-optimization analysis: %MinMax profile + rare codons + optimize projection."""
        if not seq.cds:
            return pn.pane.HTML(
                '<div style="color:#64748B;font-size:12px;margin-top:10px;">'
                'No CDS available for codon analysis.</div>')
        from core.analysis.codon_analysis import analyze_codons
        ca = analyze_codons(seq.cds, organism="human")

        fig = go.Figure()
        if ca.minmax_positions:
            fig.add_trace(go.Scatter(
                x=ca.minmax_positions, y=ca.minmax_values, mode="lines",
                line={"color": "#0F766E", "width": 1.4}, fill="tozeroy",
                fillcolor="rgba(15,118,110,0.10)", name="%MinMax",
                hovertemplate="codon %{x}<br>%MinMax %{y:.0f}<extra></extra>"))
        fig.add_hline(y=0, line_color="#94A3B8", opacity=0.6)
        for (s, e) in ca.rare_clusters:
            fig.add_vrect(x0=s, x1=e, fillcolor="#DC2626", opacity=0.12, line_width=0)
        fig.update_layout(
            title={"text": "Codon usage (%MinMax: + common / − rare)", "font": {"size": 13}},
            xaxis_title="codon position", yaxis_title="%MinMax",
            height=260, margin={"l": 55, "r": 20, "t": 40, "b": 40},
            plot_bgcolor="#F8FAFC", paper_bgcolor="white", showlegend=False)

        cai_str = f"{ca.cai:.3f}" if ca.cai is not None else "—"
        proj = ""
        if ca.optimized_cai is not None:
            d = ca.optimized_cai - (ca.cai or 0)
            proj = (
                f'<div style="font-size:12px;color:#475569;margin-top:6px;">'
                f'If codon-optimized for human: CAI <b>{cai_str} → {ca.optimized_cai:.3f}</b> '
                f'(<span style="color:{"#059669" if d>=0 else "#DC2626"};">{d:+.3f}</span>), '
                f'rare codons <b>{ca.rare_count} → {ca.optimized_rare_count}</b>, '
                f'{ca.codons_changed} codon(s) changed.</div>'
            )
        summary = pn.pane.HTML(
            f'<div style="font-size:12px;color:#334155;margin-top:8px;">'
            f'<b>CAI</b> {cai_str} · <b>{ca.rare_count}</b> rare codons '
            f'({ca.rare_fraction*100:.0f}%) · <b>{len(ca.rare_clusters)}</b> rare cluster(s) '
            f'over {ca.n_codons} codons.</div>{proj}'
        )
        return pn.Column(summary, pn.pane.Plotly(fig, sizing_mode="stretch_width"),
                         sizing_mode="stretch_width")

    # ── panel ─────────────────────────────────────────────────────────────────
    @param.depends("_state.worklist")
    def panel(self) -> pn.Column:
        wl = self._state.worklist
        if wl is None or wl.count == 0:
            return pn.Column(
                pn.pane.HTML('<div style="font-size:16px;font-weight:800;padding:8px 0;">'
                             'Candidate Analysis</div>'),
                _empty("Worklist is empty. Import sequences to compare candidates."),
                styles={"padding": "8px 16px"},
            )

        analyzed = self._analyzed()
        names = [t[0].sequence.name for t in analyzed]
        self._candidate.options = names
        if names and (self._candidate.value not in names):
            self._candidate.value = names[0]

        self._shortlist.end = max(1, len(analyzed))
        table = pn.bind(lambda n: self._comparison_table(analyzed, n), self._shortlist)
        track = pn.bind(lambda nm: self._track(analyzed, nm), self._candidate)

        def card(title, body, controls=None):
            inner = [pn.pane.HTML(f'<div style="font-size:13px;font-weight:700;margin:6px 0;">{title}</div>')]
            if controls is not None:
                inner.append(controls)
            inner.append(body)
            return pn.Column(*inner, styles={"background": "white", "border": "1px solid #CBD5E1",
                             "border-radius": "8px", "padding": "12px 14px"},
                             margin=(0, 0, 12, 0), sizing_mode="stretch_width")

        return pn.Column(
            pn.pane.HTML(
                '<div style="font-size:16px;font-weight:800;padding:8px 0 2px 0;">'
                f'Candidate Analysis <span style="color:#64748B;font-size:13px;">'
                f'({wl.count} sequences)</span></div>'
                '<div style="font-size:12px;color:#64748B;margin-bottom:8px;">'
                'Rank candidates across the four mRNA design objectives, then inspect where '
                'a candidate&#39;s features and liabilities sit along the molecule.</div>'
            ),
            card("Comparison scorecard", pn.panel(table), self._shortlist),
            card("Sequence / structure map", pn.panel(track), self._candidate),
            sizing_mode="stretch_width",
            styles={"padding": "8px 16px", "max-height": "82vh", "overflow-y": "auto"},
        )
