"""
Cluster & tree explorer.

Clusters the current worklist's sequences by k-mer distance and renders an
interactive dendrogram (UPGMA tree) with a distance cutoff that splits the tree
into flat clusters — an exploration view analogous to repertoire clustering.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List, Tuple

import panel as pn
import param
import plotly.graph_objects as go

from core.analysis.clustering import (
    kmer_distance_matrix, upgma, flat_clusters, dendrogram_layout,
)

if TYPE_CHECKING:
    from ui.state import AppState


# Categorical palette for clusters (cycled)
_PALETTE = [
    "#0F766E", "#2563EB", "#D97706", "#DC2626", "#7C3AED",
    "#059669", "#DB2777", "#0891B2", "#CA8A04", "#4F46E5",
]


def _empty(msg: str) -> pn.pane.HTML:
    return pn.pane.HTML(f'<div style="color:#64748B;padding:30px;text-align:center;">{msg}</div>')


class ClusterView(param.Parameterized):
    """Worklist clustering + dendrogram panel."""

    def __init__(self, state: "AppState", **params: object) -> None:
        super().__init__(**params)
        self._state = state
        self._k = pn.widgets.IntSlider(
            name="k-mer size", start=2, end=6, value=4, width=160, margin=(4, 10))
        self._threshold = pn.widgets.FloatSlider(
            name="Distance cutoff", start=0.0, end=1.0, step=0.02, value=0.30,
            width=260, margin=(4, 10))
        self._region = pn.widgets.Select(
            name="Compare", options=["Full sequence", "CDS only"],
            value="Full sequence", width=150, margin=(4, 10))

    # ── data ────────────────────────────────────────────────────────────────
    def _sequences(self) -> Tuple[List[str], List[str]]:
        names: List[str] = []
        seqs: List[str] = []
        for item in self._state.worklist.items:
            s = item.sequence
            if self._region.value == "CDS only":
                txt = s.cds or ""
            else:
                try:
                    txt = s.assembled_sequence
                except Exception:
                    txt = s.cds or ""
            if txt:
                names.append(s.name)
                seqs.append(txt)
        return names, seqs

    # ── rendering ─────────────────────────────────────────────────────────────
    def _render(self, k: int, threshold: float, region: str) -> pn.viewable.Viewable:
        names, seqs = self._sequences()
        n = len(seqs)
        if n < 2:
            return _empty("Add at least 2 sequences (with content) to the worklist to cluster.")

        D = kmer_distance_matrix(seqs, k=k)
        link, order = upgma(D)
        clusters = flat_clusters(link, n, threshold)
        layout = dendrogram_layout(link, order)
        n_clusters = len(set(clusters))

        fig = go.Figure()

        # dendrogram branches as a single trace (None-separated segments)
        xs: List = []
        ys: List = []
        for (x0, x1, y0, y1) in layout.segments:
            xs += [x0, x1, None]
            ys += [y0, y1, None]
        fig.add_trace(go.Scatter(
            x=xs, y=ys, mode="lines",
            line={"color": "#94A3B8", "width": 1.2},
            hoverinfo="skip", showlegend=False,
        ))

        # cutoff line
        fig.add_hline(
            y=threshold, line_dash="dash", line_color="#DC2626", opacity=0.7,
            annotation_text=f"cutoff {threshold:.2f}", annotation_position="top left",
        )

        # leaf markers grouped per cluster (legend = clusters)
        for c in range(n_clusters):
            cx = [layout.leaf_x[leaf] for leaf in order if clusters[leaf] == c]
            ctext = [names[leaf] for leaf in order if clusters[leaf] == c]
            if not cx:
                continue
            fig.add_trace(go.Scatter(
                x=cx, y=[0] * len(cx), mode="markers",
                marker={"size": 11, "color": _PALETTE[c % len(_PALETTE)],
                        "line": {"color": "white", "width": 1}},
                name=f"Cluster {c}", text=ctext,
                hovertemplate="%{text}<br>cluster " + str(c) + "<extra></extra>",
            ))

        fig.update_layout(
            title={"text": f"UPGMA dendrogram — {n} sequences, {n_clusters} cluster(s)",
                   "font": {"size": 13}},
            xaxis={"tickmode": "array",
                   "tickvals": [layout.leaf_x[leaf] for leaf in order],
                   "ticktext": [names[leaf] for leaf in order],
                   "tickangle": -40, "tickfont": {"size": 10}},
            yaxis={"title": "k-mer distance", "rangemode": "tozero"},
            height=440, margin={"l": 60, "r": 20, "t": 40, "b": 130},
            plot_bgcolor="#F8FAFC", paper_bgcolor="white",
            legend={"orientation": "h", "y": -0.45, "font": {"size": 10}},
        )

        # cluster membership summary
        groups: dict = {}
        for leaf in order:
            groups.setdefault(clusters[leaf], []).append(names[leaf])
        rows = ""
        for c in sorted(groups):
            color = _PALETTE[c % len(_PALETTE)]
            members = ", ".join(groups[c])
            rows += (
                f'<tr>'
                f'<td style="padding:4px 10px;"><span style="display:inline-block;width:10px;'
                f'height:10px;border-radius:2px;background:{color};margin-right:6px;"></span>'
                f'Cluster {c}</td>'
                f'<td style="padding:4px 10px;color:#475569;font-size:12px;">{len(groups[c])}</td>'
                f'<td style="padding:4px 10px;color:#334155;font-size:12px;">{members}</td>'
                f'</tr>'
            )
        table = pn.pane.HTML(
            '<div style="font-size:12px;font-weight:700;margin:10px 0 4px 0;">Cluster membership</div>'
            '<table style="border-collapse:collapse;width:100%;">'
            '<tr style="border-bottom:1px solid #E2E8F0;font-size:11px;color:#64748B;">'
            '<td style="padding:4px 10px;">Cluster</td><td style="padding:4px 10px;">Size</td>'
            '<td style="padding:4px 10px;">Members</td></tr>'
            f'{rows}</table>'
        )

        return pn.Column(pn.pane.Plotly(fig, sizing_mode="stretch_width"), table,
                         sizing_mode="stretch_width")

    @param.depends("_state.worklist")
    def panel(self) -> pn.Column:
        wl = self._state.worklist
        if wl is None or wl.count == 0:
            return pn.Column(
                pn.pane.HTML('<div style="font-size:16px;font-weight:800;padding:8px 0;">'
                             'Cluster &amp; Tree</div>'),
                _empty("Worklist is empty. Import sequences to cluster them."),
                styles={"padding": "8px 16px"},
            )

        controls = pn.Row(
            self._region, self._k, self._threshold,
            sizing_mode="stretch_width",
            styles={"background": "#F8FAFC", "border": "1px solid #E2E8F0",
                    "border-radius": "6px", "padding": "4px 8px", "margin": "0 0 8px 0"},
        )
        body = pn.bind(self._render, self._k, self._threshold, self._region)
        return pn.Column(
            pn.pane.HTML('<div style="font-size:16px;font-weight:800;padding:8px 0;">'
                         f'Cluster &amp; Tree <span style="color:#64748B;font-size:13px;">'
                         f'({wl.count} sequences)</span></div>'),
            controls,
            pn.panel(body),
            sizing_mode="stretch_width",
            styles={"padding": "8px 16px"},
        )
