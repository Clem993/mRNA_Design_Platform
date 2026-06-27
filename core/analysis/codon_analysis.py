"""
Codon-optimization analysis for an mRNA CDS.

Goes beyond a single CAI number to show *where* codon usage helps or hurts
expression:

  - **Per-codon optimality** — each codon's relative adaptiveness (0–1) vs the
    best synonymous codon for that amino acid in the host.
  - **%MinMax profile** — the classic sliding-window measure (Clarke & Clark):
    positive = a run of common/fast codons, negative = rare/slow codons (the
    kind of cluster that stalls ribosomes).
  - **Rare-codon clusters** — runs of low-optimality codons worth recoding.
  - **Original vs optimized** — projected CAI gain and rare-codon reduction if
    the CDS were codon-optimized for the host (reuses the existing optimizer).

Pure-Python (stdlib only); reuses the host codon tables already in the project.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from core.analysis.cai import CODON_TABLES, calculate_cai
from core.sequence_tools.codon_optimizer import CODON_TABLE, AA_TO_CODONS

_STOP = {"TAA", "TAG", "TGA"}
RARE_THRESHOLD = 0.20          # optimality below this = rare codon
RARE_CLUSTER_MIN = 3           # consecutive rare codons → a cluster
DEFAULT_WINDOW = 17            # codons, for the %MinMax sliding window


def resolve_organism(organism: Optional[str]) -> str:
    key = (organism or "human").lower().replace(" ", "").replace(".", "")
    if key in ("ecoli", "escherichiacoli"):
        return "ecoli"
    return "human" if key not in CODON_TABLES else key


def _codons(cds: str) -> List[str]:
    s = (cds or "").upper().replace("U", "T")
    return [s[i:i + 3] for i in range(0, len(s) - len(s) % 3, 3)]


def _freq_stats(table: Dict[str, float]) -> Tuple[Dict[str, float], Dict[str, float], Dict[str, float], Dict[str, float]]:
    """Per-codon synonymous frequency, and per-AA max/min/avg of those freqs."""
    freq: Dict[str, float] = {}
    aa_max: Dict[str, float] = {}
    aa_min: Dict[str, float] = {}
    aa_avg: Dict[str, float] = {}
    for aa, syns in AA_TO_CODONS.items():
        if aa in ("*", "Stop"):
            continue
        ws = [max(table.get(c, 0.0), 0.0) for c in syns]
        tot = sum(ws)
        fs = [w / tot if tot > 0 else 0.0 for w in ws]
        for c, f in zip(syns, fs):
            freq[c] = f
        aa_max[aa] = max(fs) if fs else 0.0
        aa_min[aa] = min(fs) if fs else 0.0
        aa_avg[aa] = (sum(fs) / len(fs)) if fs else 0.0
    return freq, aa_max, aa_min, aa_avg


def per_codon_optimality(cds: str, organism: str = "human") -> List[float]:
    """Relative adaptiveness (0–1) per non-stop codon."""
    table = CODON_TABLES[resolve_organism(organism)]
    # max synonymous weight per AA
    aa_maxw = {aa: max((table.get(c, 0.0) for c in syns), default=0.0)
               for aa, syns in AA_TO_CODONS.items()}
    out: List[float] = []
    for c in _codons(cds):
        aa = CODON_TABLE.get(c)
        if aa is None or aa in ("*", "Stop") or c in _STOP:
            continue
        mx = aa_maxw.get(aa, 0.0)
        out.append((table.get(c, 0.0) / mx) if mx > 0 else 0.0)
    return out


def min_max_profile(cds: str, organism: str = "human",
                    window: int = DEFAULT_WINDOW) -> Tuple[List[int], List[float]]:
    """%MinMax per sliding window; x positions are codon indices (window centres)."""
    table = CODON_TABLES[resolve_organism(organism)]
    freq, aa_max, aa_min, aa_avg = _freq_stats(table)
    codons = [c for c in _codons(cds) if CODON_TABLE.get(c) not in (None, "*", "Stop")]
    positions: List[int] = []
    values: List[float] = []
    n = len(codons)
    if n < window:
        return positions, values
    for i in range(n - window + 1):
        win = codons[i:i + window]
        actual = sum(freq.get(c, 0.0) for c in win)
        mx = sum(aa_max.get(CODON_TABLE.get(c, ""), 0.0) for c in win)
        mn = sum(aa_min.get(CODON_TABLE.get(c, ""), 0.0) for c in win)
        av = sum(aa_avg.get(CODON_TABLE.get(c, ""), 0.0) for c in win)
        if actual >= av:
            pmm = ((actual - av) / (mx - av) * 100.0) if mx > av else 0.0
        else:
            pmm = (-(av - actual) / (av - mn) * 100.0) if av > mn else 0.0
        positions.append(i + window // 2)
        values.append(pmm)
    return positions, values


@dataclass
class CodonAnalysis:
    organism: str
    cai: Optional[float]
    n_codons: int
    rare_count: int
    rare_fraction: float
    rare_positions: List[int] = field(default_factory=list)
    rare_clusters: List[Tuple[int, int]] = field(default_factory=list)  # (start, end) codon idx
    minmax_positions: List[int] = field(default_factory=list)
    minmax_values: List[float] = field(default_factory=list)
    optimality: List[float] = field(default_factory=list)
    # original-vs-optimized projection
    optimized_cai: Optional[float] = None
    optimized_rare_count: Optional[int] = None
    codons_changed: Optional[int] = None


def _clusters(rare_positions: List[int], min_len: int = RARE_CLUSTER_MIN) -> List[Tuple[int, int]]:
    if not rare_positions:
        return []
    runs = []
    start = prev = rare_positions[0]
    for p in rare_positions[1:]:
        if p == prev + 1:
            prev = p
        else:
            if prev - start + 1 >= min_len:
                runs.append((start, prev))
            start = prev = p
    if prev - start + 1 >= min_len:
        runs.append((start, prev))
    return runs


def analyze_codons(cds: str, organism: str = "human",
                   window: int = DEFAULT_WINDOW,
                   include_optimized: bool = True) -> CodonAnalysis:
    """Full codon analysis for a CDS."""
    org = resolve_organism(organism)
    opt = per_codon_optimality(cds, org)
    n = len(opt)
    rare_positions = [i for i, w in enumerate(opt) if w < RARE_THRESHOLD]
    mm_pos, mm_val = min_max_profile(cds, org, window)

    try:
        cai = calculate_cai(cds, org)
    except Exception:
        cai = None

    result = CodonAnalysis(
        organism=org, cai=cai, n_codons=n,
        rare_count=len(rare_positions),
        rare_fraction=(len(rare_positions) / n) if n else 0.0,
        rare_positions=rare_positions,
        rare_clusters=_clusters(rare_positions),
        minmax_positions=mm_pos, minmax_values=mm_val,
        optimality=opt,
    )

    if include_optimized and n:
        try:
            from core.sequence_tools.codon_optimizer import optimize_codons
            res = optimize_codons(cds, org)
            result.optimized_cai = res.optimized_cai
            result.codons_changed = res.codons_changed
            result.optimized_rare_count = len(
                [w for w in per_codon_optimality(res.optimized_cds, org) if w < RARE_THRESHOLD]
            )
        except Exception:
            pass
    return result
