"""
Experiments / model lifecycle view.

Surfaces the model lifecycle that sits on top of the registry:
  - registered models and their versions,
  - a run history (every scoring run, with version + score statistics),
  - a run-vs-run comparison (e.g. two versions of the same model) showing how
    per-sequence scores shifted.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional

import panel as pn
import param

if TYPE_CHECKING:
    from ui.state import AppState


def _fmt(x: Optional[float]) -> str:
    return "—" if x is None or (isinstance(x, float) and x != x) else f"{x:.3f}"


class ExperimentView(param.Parameterized):
    """Model lifecycle / experiment tracking panel."""

    def __init__(self, state: "AppState", **params: object) -> None:
        super().__init__(**params)
        self._state = state
        self._run_a = pn.widgets.Select(name="Run A (baseline)", width=320, margin=(4, 10))
        self._run_b = pn.widgets.Select(name="Run B (compare)", width=320, margin=(4, 10))

    # ── registered models ─────────────────────────────────────────────────────
    def _models_table(self) -> pn.pane.HTML:
        reg = self._state.model_registry
        models = reg.all_models if reg else []
        if not models:
            return pn.pane.HTML('<div style="color:#64748B;font-size:12px;">No models registered yet.</div>')
        rows = ""
        for m in models:
            try:
                ver = m.model.version
            except Exception:
                ver = "—"
            rows += (
                f'<tr style="border-bottom:1px solid #F1F5F9;">'
                f'<td style="padding:4px 10px;font-size:12px;">{m.model.name}</td>'
                f'<td style="padding:4px 10px;font-size:12px;color:#475569;">{m.model_type}</td>'
                f'<td style="padding:4px 10px;font-size:12px;"><span style="background:#F0FDFA;'
                f'color:#0F766E;border-radius:3px;padding:1px 6px;">v{ver}</span></td>'
                f'<td style="padding:4px 10px;font-size:12px;color:#64748B;">{m.source}</td>'
                f'</tr>'
            )
        return pn.pane.HTML(
            '<table style="border-collapse:collapse;width:100%;">'
            '<tr style="font-size:11px;color:#64748B;border-bottom:1px solid #E2E8F0;">'
            '<td style="padding:4px 10px;">Model</td><td style="padding:4px 10px;">Type</td>'
            '<td style="padding:4px 10px;">Version</td><td style="padding:4px 10px;">Source</td></tr>'
            f'{rows}</table>'
        )

    # ── run history ───────────────────────────────────────────────────────────
    def _runs_table(self) -> pn.pane.HTML:
        runs = self._state.run_history.runs
        if not runs:
            return pn.pane.HTML(
                '<div style="color:#64748B;font-size:12px;">No runs yet. Score a worklist '
                'with a model (Worklist → Run) to record an experiment.</div>'
            )
        rows = ""
        for r in reversed(runs):  # newest first
            rows += (
                f'<tr style="border-bottom:1px solid #F1F5F9;">'
                f'<td style="padding:4px 10px;font-size:11px;color:#64748B;">{r.timestamp}</td>'
                f'<td style="padding:4px 10px;font-size:12px;">{r.model_name}</td>'
                f'<td style="padding:4px 10px;font-size:12px;">v{r.model_version}</td>'
                f'<td style="padding:4px 10px;font-size:12px;">{r.n_sequences}</td>'
                f'<td style="padding:4px 10px;font-size:12px;">{_fmt(r.score_mean)}</td>'
                f'<td style="padding:4px 10px;font-size:12px;color:#64748B;">'
                f'{_fmt(r.score_min)}–{_fmt(r.score_max)}</td>'
                f'<td style="padding:4px 10px;font-size:11px;color:#94A3B8;">{r.worklist_name}</td>'
                f'</tr>'
            )
        return pn.pane.HTML(
            '<table style="border-collapse:collapse;width:100%;">'
            '<tr style="font-size:11px;color:#64748B;border-bottom:1px solid #E2E8F0;">'
            '<td style="padding:4px 10px;">Time</td><td style="padding:4px 10px;">Model</td>'
            '<td style="padding:4px 10px;">Version</td><td style="padding:4px 10px;">N</td>'
            '<td style="padding:4px 10px;">Mean</td><td style="padding:4px 10px;">Range</td>'
            '<td style="padding:4px 10px;">Worklist</td></tr>'
            f'{rows}</table>'
        )

    # ── comparison ────────────────────────────────────────────────────────────
    def _run_options(self) -> Dict[str, object]:
        return {f"{r.run_id} · {r.label}": r.run_id for r in reversed(self._state.run_history.runs)}

    def _name_lookup(self) -> Dict[str, str]:
        names: Dict[str, str] = {}
        for item in self._state.worklist.items:
            names[item.sequence.id] = item.sequence.name
        return names

    def _render_comparison(self, run_a_id: str, run_b_id: str) -> pn.viewable.Viewable:
        from models.runs import RunHistory
        runs = {r.run_id: r for r in self._state.run_history.runs}
        ra, rb = runs.get(run_a_id), runs.get(run_b_id)
        if not ra or not rb:
            return pn.pane.HTML('<div style="color:#64748B;font-size:12px;">Pick two runs to compare.</div>')
        if ra.run_id == rb.run_id:
            return pn.pane.HTML('<div style="color:#64748B;font-size:12px;">Pick two different runs.</div>')

        cmp = RunHistory.compare(ra, rb)
        if not cmp.shared_ids:
            return pn.pane.HTML(
                '<div style="color:#D97706;font-size:12px;">No shared sequences between these runs.</div>'
            )
        d = cmp.mean_delta
        dcolor = "#059669" if d > 0 else "#DC2626" if d < 0 else "#64748B"
        summary = pn.pane.HTML(f"""
            <div style="display:flex;gap:18px;align-items:center;flex-wrap:wrap;
                        border:1px solid #E2E8F0;border-radius:8px;padding:10px 14px;margin:6px 0;">
                <div><div style="font-size:10px;color:#64748B;">MEAN Δ (B − A)</div>
                     <div style="font-size:22px;font-weight:800;color:{dcolor};">{d:+.3f}</div></div>
                <div style="font-size:12px;color:#059669;">▲ {cmp.n_improved} improved</div>
                <div style="font-size:12px;color:#DC2626;">▼ {cmp.n_worsened} worsened</div>
                <div style="font-size:12px;color:#64748B;">= {cmp.n_unchanged} unchanged</div>
                <div style="font-size:11px;color:#94A3B8;margin-left:auto;">
                    {len(cmp.shared_ids)} shared sequences</div>
            </div>
        """)

        names = self._name_lookup()
        ordered = sorted(cmp.deltas.items(), key=lambda kv: kv[1])  # worst→best
        rows = ""
        for sid, delta in ordered[:50]:
            c = "#059669" if delta > 0 else "#DC2626" if delta < 0 else "#64748B"
            nm = names.get(sid, sid[:8])
            rows += (
                f'<tr style="border-bottom:1px solid #F1F5F9;">'
                f'<td style="padding:3px 10px;font-size:12px;">{nm}</td>'
                f'<td style="padding:3px 10px;font-size:12px;color:#64748B;">{_fmt(ra.scores.get(sid))}</td>'
                f'<td style="padding:3px 10px;font-size:12px;color:#64748B;">{_fmt(rb.scores.get(sid))}</td>'
                f'<td style="padding:3px 10px;font-size:12px;font-weight:700;color:{c};">{delta:+.3f}</td>'
                f'</tr>'
            )
        table = pn.pane.HTML(
            '<table style="border-collapse:collapse;width:100%;">'
            '<tr style="font-size:11px;color:#64748B;border-bottom:1px solid #E2E8F0;">'
            '<td style="padding:3px 10px;">Sequence</td>'
            f'<td style="padding:3px 10px;">A (v{ra.model_version})</td>'
            f'<td style="padding:3px 10px;">B (v{rb.model_version})</td>'
            '<td style="padding:3px 10px;">Δ</td></tr>'
            f'{rows}</table>'
        )
        return pn.Column(summary, table, sizing_mode="stretch_width")

    # ── panel ─────────────────────────────────────────────────────────────────
    @param.depends("_state.run_history", "_state.model_registry")
    def panel(self) -> pn.Column:
        # refresh comparison dropdown options
        opts = self._run_options()
        self._run_a.options = opts
        self._run_b.options = opts
        run_ids = list(opts.values())
        if len(run_ids) >= 2:
            self._run_a.value = run_ids[1]   # older of the two newest
            self._run_b.value = run_ids[0]   # newest
        elif run_ids:
            self._run_a.value = self._run_b.value = run_ids[0]

        comparison = pn.bind(self._render_comparison, self._run_a, self._run_b)

        def card(title: str, body: pn.viewable.Viewable) -> pn.Column:
            return pn.Column(
                pn.pane.HTML(f'<div style="font-size:13px;font-weight:700;margin:6px 0;">{title}</div>'),
                body,
                styles={"background": "white", "border": "1px solid #CBD5E1",
                        "border-radius": "8px", "padding": "12px 14px"},
                margin=(0, 0, 12, 0), sizing_mode="stretch_width",
            )

        return pn.Column(
            pn.pane.HTML(
                '<div style="font-size:16px;font-weight:800;padding:8px 0 2px 0;">Experiments</div>'
                '<div style="font-size:12px;color:#64748B;margin-bottom:10px;">'
                'Model versions, scoring-run history, and version-to-version comparison.</div>'
            ),
            card("Registered models", self._models_table()),
            card("Run history", self._runs_table()),
            card("Compare runs (version A → B)",
                 pn.Column(pn.Row(self._run_a, self._run_b), pn.panel(comparison),
                           sizing_mode="stretch_width")),
            sizing_mode="stretch_width",
            styles={"padding": "8px 16px", "max-height": "78vh", "overflow-y": "auto"},
        )
