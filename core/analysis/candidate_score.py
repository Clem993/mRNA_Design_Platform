"""
Candidate objective scoring for mRNA design.

Condenses a full AnalysisReport into the four objectives an mRNA designer
trades off, each on a 0–100 scale where **higher is better**:

  - **Expression**       — translation potential (CAI, Kozak strength)
  - **Stability**        — predicted durability (GC balance, structure, homopolymers)
  - **Immunogenicity**   — *inverse* of innate-immune risk (uridine content)
  - **Manufacturability**— clean synthesis/IVT (restriction sites, homopolymers, GC extremes)

These are transparent heuristics, not trained predictors — they exist to rank and
shortlist candidates from the metrics already computed. The function reads the
report by duck typing and degrades gracefully when a metric is unavailable (e.g.
ViennaRNA not installed → structure ignored rather than penalised).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


def _clamp(x: float) -> float:
    return max(0.0, min(100.0, x))


@dataclass
class ObjectiveScores:
    expression: float
    stability: float
    immunogenicity: float
    manufacturability: float
    overall: float
    details: Dict[str, str] = field(default_factory=dict)

    def as_row(self) -> Dict[str, float]:
        return {
            "Expression": round(self.expression),
            "Stability": round(self.stability),
            "Immunogenicity": round(self.immunogenicity),
            "Manufacturability": round(self.manufacturability),
            "Overall": round(self.overall),
        }


# objective -> weight in the overall score
OBJECTIVE_WEIGHTS = {
    "expression": 0.30,
    "stability": 0.25,
    "immunogenicity": 0.20,
    "manufacturability": 0.25,
}

_KOZAK_SCORE = {"strong": 100.0, "adequate": 70.0, "weak": 35.0}


def _liability_categories(report: Any) -> Dict[str, str]:
    """Map liability category -> worst severity seen (from report.liability.flags)."""
    out: Dict[str, str] = {}
    lia = getattr(report, "liability", None)
    order = {"critical": 0, "warning": 1, "info": 2}
    for f in getattr(lia, "flags", []) or []:
        cur = out.get(f.category)
        if cur is None or order.get(f.severity, 9) < order.get(cur, 9):
            out[f.category] = f.severity
    return out


def score_objectives(report: Any) -> ObjectiveScores:
    """Compute the four 0–100 objective scores from an analysis report."""
    details: Dict[str, str] = {}
    cats = _liability_categories(report)

    # ── Expression ────────────────────────────────────────────────────────────
    cai = getattr(report, "cai", None)
    cai_score = cai * 100.0 if cai is not None else 60.0
    kz = getattr(report, "kozak", None)
    kz_strength = getattr(kz, "strength", None)
    kozak_score = _KOZAK_SCORE.get(kz_strength, 60.0)
    expression = _clamp(0.6 * cai_score + 0.4 * kozak_score)
    details["expression"] = (
        f"CAI {('%.2f' % cai) if cai is not None else 'n/a'}, "
        f"Kozak {kz_strength or 'n/a'}"
    )

    # ── Stability ─────────────────────────────────────────────────────────────
    gc = getattr(report, "gc_percent_global", None)
    if gc:
        # full marks in 50–60%, falling off outside
        gc_score = 100.0 - 3.0 * max(0.0, abs(gc - 55.0) - 5.0)
    else:
        gc_score = 60.0
    hp_sev = cats.get("Homopolymer")
    hp_pen = 25.0 if hp_sev == "critical" else 10.0 if hp_sev == "warning" else 0.0
    struct = getattr(report, "structure", None)
    struct_note = ""
    if struct is not None and not getattr(struct, "is_stub", True):
        length = max(len(getattr(struct, "sequence", "") or ""), 1)
        per_nt = getattr(struct, "mfe", 0.0) / length
        # moderate structure is stabilising; reward down to ~-0.4/nt, then taper
        struct_bonus = max(-10.0, min(10.0, (-per_nt) * 25.0 - 5.0))
        gc_score += struct_bonus
        struct_note = f", MFE {per_nt:.2f}/nt"
    stability = _clamp(gc_score - hp_pen)
    details["stability"] = f"GC {gc:.0f}%" if gc else "GC n/a"
    details["stability"] += struct_note + (f", homopolymer {hp_sev}" if hp_sev else "")

    # ── Immunogenicity (higher = less immunogenic) ────────────────────────────
    uri = getattr(report, "uridine", None)
    u_pct = getattr(uri, "u_percent", None)
    n_stretch = len(getattr(uri, "high_u_stretches", []) or [])
    if u_pct is None:
        immunogenicity = 60.0
        details["immunogenicity"] = "uridine n/a"
    else:
        base = 100.0 - max(0.0, u_pct - 20.0) * 3.0
        immunogenicity = _clamp(base - 8.0 * n_stretch)
        details["immunogenicity"] = f"U {u_pct:.0f}%, {n_stretch} high-U stretch(es)"

    # ── Manufacturability ─────────────────────────────────────────────────────
    manuf = 100.0
    n_re = len(getattr(report, "restriction_enzymes_present", []) or [])
    manuf -= min(36.0, 12.0 * n_re)
    if hp_sev == "critical":
        manuf -= 25.0
    elif hp_sev == "warning":
        manuf -= 12.0
    gc_sev = cats.get("GC")
    manuf -= 20.0 if gc_sev == "critical" else 8.0 if gc_sev == "warning" else 0.0
    if cats.get("Motif"):
        manuf -= 5.0
    manufacturability = _clamp(manuf)
    details["manufacturability"] = (
        f"{n_re} restriction site(s)"
        + (f", homopolymer {hp_sev}" if hp_sev else "")
        + (f", GC {gc_sev}" if gc_sev else "")
    )

    overall = (
        OBJECTIVE_WEIGHTS["expression"] * expression
        + OBJECTIVE_WEIGHTS["stability"] * stability
        + OBJECTIVE_WEIGHTS["immunogenicity"] * immunogenicity
        + OBJECTIVE_WEIGHTS["manufacturability"] * manufacturability
    )

    return ObjectiveScores(
        expression=expression, stability=stability,
        immunogenicity=immunogenicity, manufacturability=manufacturability,
        overall=_clamp(overall), details=details,
    )
