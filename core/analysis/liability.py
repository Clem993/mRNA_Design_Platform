"""
Liability / QC aggregator.

Rolls the individual analysis results (GC, homopolymers, restriction sites,
uridine, CDS validation, Kozak, secondary structure, sequence motifs) into a
single severity-ranked liability report with an overall QC score (0–100) and a
pass / review / fail verdict — analogous to a developability/liability overlay.

This module is a pure aggregator: it reads attributes off an already-computed
analysis report (duck-typed) and the sequence object, so it imports neither the
analyzer nor the Panel UI. It only depends on the homopolymer detector (to
re-scan the construct *body*, excluding the legitimate poly-A tail).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional

from core.analysis.homopolymers import detect_homopolymers

# Severity levels, ordered most→least severe
CRITICAL = "critical"
WARNING = "warning"
INFO = "info"

_SEVERITY_ORDER = {CRITICAL: 0, WARNING: 1, INFO: 2}
_PENALTY = {CRITICAL: 25, WARNING: 10, INFO: 3}

# Thresholds
_GC_LOW, _GC_HIGH = 40.0, 65.0          # warning band
_GC_LOW_CRIT, _GC_HIGH_CRIT = 30.0, 70.0  # critical band
_HOMOPOLYMER_WARN = 10                    # body run length → warning
_HOMOPOLYMER_CRIT = 15                    # body run length → critical
_URIDINE_WARN_PCT = 40.0
_MFE_PER_NT_INFO = -0.45                  # very negative → highly structured


@dataclass
class LiabilityFlag:
    """A single liability finding."""
    id: str
    category: str          # "GC", "Homopolymer", "Restriction", "Uridine",
                           # "CDS", "Kozak", "Structure", "Motif"
    severity: str          # CRITICAL | WARNING | INFO
    title: str
    detail: str
    location: str = ""     # human-readable location, e.g. "CDS pos 123"
    recommendation: str = ""


@dataclass
class LiabilityReport:
    """Aggregated liability assessment for one sequence."""
    flags: List[LiabilityFlag] = field(default_factory=list)
    score: int = 100              # 0–100, higher is cleaner
    verdict: str = "pass"         # "pass" | "review" | "fail"
    n_critical: int = 0
    n_warning: int = 0
    n_info: int = 0
    checks_run: int = 0

    @property
    def flag_count(self) -> int:
        return len(self.flags)

    def sorted_flags(self) -> List[LiabilityFlag]:
        return sorted(self.flags, key=lambda f: _SEVERITY_ORDER.get(f.severity, 9))


def _body_sequence(seq: Any) -> str:
    """Construct body = everything except the legitimate poly-A tail."""
    parts = [
        getattr(seq, "five_prime_utr", None),
        getattr(seq, "kozak", None),
        getattr(seq, "cds", None),
        getattr(seq, "three_prime_utr", None),
    ]
    return "".join(p for p in parts if p).upper().replace("U", "T")


def assess_liabilities(report: Any, seq: Any) -> LiabilityReport:
    """
    Build a LiabilityReport from an analysis ``report`` and its ``seq``.

    ``report`` is duck-typed: it is expected to expose the attributes set by
    SequenceAnalyzer (gc_percent_global, restriction_enzymes_present, uridine,
    has_start_codon/has_stop_codon/in_frame, kozak, structure, motif_hits).
    """
    flags: List[LiabilityFlag] = []
    checks = 0

    def add(category, severity, title, detail, location="", recommendation=""):
        flags.append(LiabilityFlag(
            id=f"{category.lower()}-{len(flags)}",
            category=category, severity=severity, title=title,
            detail=detail, location=location, recommendation=recommendation,
        ))

    # ── GC content ────────────────────────────────────────────────────────────
    checks += 1
    gc = getattr(report, "gc_percent_global", None)
    if gc is not None and gc > 0:
        if gc < _GC_LOW_CRIT or gc > _GC_HIGH_CRIT:
            add("GC", CRITICAL, "GC content far outside optimal range",
                f"Global GC is {gc:.1f}% (optimal {_GC_LOW:.0f}–{_GC_HIGH:.0f}%).",
                "global",
                "Re-balance GC; extremes hurt synthesis, translation, and stability.")
        elif gc < _GC_LOW or gc > _GC_HIGH:
            add("GC", WARNING, "GC content outside optimal range",
                f"Global GC is {gc:.1f}% (optimal {_GC_LOW:.0f}–{_GC_HIGH:.0f}%).",
                "global",
                "Nudge GC toward 40–65% during codon optimisation.")

    # ── Homopolymers in the body (exclude poly-A tail) ────────────────────────
    checks += 1
    body = _body_sequence(seq)
    if body:
        body_runs = detect_homopolymers(body, min_run=_HOMOPOLYMER_WARN)
        if body_runs:
            longest = max(body_runs, key=lambda r: r.length)
            sev = CRITICAL if longest.length >= _HOMOPOLYMER_CRIT else WARNING
            add("Homopolymer", sev, "Homopolymer run in construct body",
                f"{len(body_runs)} run(s) ≥{_HOMOPOLYMER_WARN} nt; longest "
                f"{longest.nucleotide}×{longest.length}.",
                f"body pos {longest.start}",
                "Break up long single-base runs to avoid synthesis errors and "
                "polymerase slippage.")

    # ── Restriction sites ─────────────────────────────────────────────────────
    checks += 1
    enzymes = getattr(report, "restriction_enzymes_present", None) or []
    if enzymes:
        add("Restriction", WARNING, "Internal restriction sites present",
            f"Sites for: {', '.join(sorted(enzymes))}.",
            "construct",
            "Remove internal sites or pick a cloning strategy that avoids them.")

    # ── Uridine content / high-U stretches ────────────────────────────────────
    checks += 1
    uri = getattr(report, "uridine", None)
    if uri is not None:
        stretches = getattr(uri, "high_u_stretches", []) or []
        u_pct = getattr(uri, "u_percent", 0.0)
        if u_pct >= _URIDINE_WARN_PCT or stretches:
            detail = f"Uridine {u_pct:.1f}%"
            if stretches:
                detail += f"; {len(stretches)} high-U stretch(es)"
            add("Uridine", WARNING, "Elevated uridine content",
                detail + ".",
                "construct",
                "High U is immunostimulatory — optimise sequence and/or use "
                "modified nucleotides (e.g. N1-methylpseudouridine).")

    # ── CDS integrity ─────────────────────────────────────────────────────────
    if getattr(report, "has_start_codon", None) is not None:
        checks += 1
        if report.has_start_codon is False:
            add("CDS", CRITICAL, "CDS missing start codon",
                "CDS does not begin with ATG.", "CDS 5' end",
                "Ensure the CDS starts with ATG.")
        if getattr(report, "has_stop_codon", None) is False:
            add("CDS", CRITICAL, "CDS missing stop codon",
                "CDS does not end with a stop codon.", "CDS 3' end",
                "Append a stop codon (TAA/TAG/TGA).")
        if getattr(report, "in_frame", None) is False:
            add("CDS", CRITICAL, "CDS not in frame",
                "CDS length is not divisible by 3.", "CDS",
                "Fix indels so the CDS length is a multiple of 3.")

    # ── Kozak context ─────────────────────────────────────────────────────────
    kz = getattr(report, "kozak", None)
    if kz is not None:
        checks += 1
        strength = getattr(kz, "strength", None)
        if strength == "weak":
            add("Kozak", WARNING, "Weak Kozak context",
                f"Kozak score {getattr(kz, 'score', 0):.2f} (weak).",
                "around start codon",
                "Strengthen Kozak: purine (A/G) at -3 and G at +4.")
        elif strength == "adequate":
            add("Kozak", INFO, "Sub-optimal Kozak context",
                f"Kozak score {getattr(kz, 'score', 0):.2f} (adequate).",
                "around start codon",
                "Optional: optimise -3/+4 positions for stronger initiation.")

    # ── Secondary structure (if computed) ─────────────────────────────────────
    struct = getattr(report, "structure", None)
    if struct is not None and not getattr(struct, "is_stub", True):
        checks += 1
        length = max(len(getattr(struct, "sequence", "") or ""), 1)
        per_nt = getattr(struct, "mfe", 0.0) / length
        if per_nt < _MFE_PER_NT_INFO:
            add("Structure", INFO, "Highly structured mRNA",
                f"MFE {struct.mfe:.1f} kcal/mol ({per_nt:.2f}/nt).",
                "global",
                "Strong structure (esp. near the 5' cap/start) can impede "
                "translation initiation.")

    # ── Sequence motifs ───────────────────────────────────────────────────────
    motif_hits = getattr(report, "motif_hits", None) or []
    if motif_hits:
        checks += 1
        # group by motif name
        by_name: dict = {}
        for h in motif_hits:
            by_name.setdefault(h.name, []).append(h)
        for name, group in by_name.items():
            first = group[0]
            sev = min((h.severity for h in group), key=lambda s: _SEVERITY_ORDER.get(s, 9))
            positions = ", ".join(f"{h.region}:{h.start}" for h in group[:5])
            if len(group) > 5:
                positions += f" (+{len(group) - 5} more)"
            add("Motif", sev, first.label,
                f"{len(group)} occurrence(s). {first.description}",
                positions,
                first.recommendation)

    # ── Score & verdict ───────────────────────────────────────────────────────
    n_crit = sum(1 for f in flags if f.severity == CRITICAL)
    n_warn = sum(1 for f in flags if f.severity == WARNING)
    n_info = sum(1 for f in flags if f.severity == INFO)

    penalty = sum(_PENALTY.get(f.severity, 0) for f in flags)
    score = max(0, min(100, 100 - penalty))

    if n_crit > 0:
        verdict = "fail"
    elif n_warn > 0:
        verdict = "review"
    else:
        verdict = "pass"

    return LiabilityReport(
        flags=flags, score=score, verdict=verdict,
        n_critical=n_crit, n_warning=n_warn, n_info=n_info,
        checks_run=checks,
    )
