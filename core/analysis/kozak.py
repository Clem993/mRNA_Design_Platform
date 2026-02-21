"""
Kozak sequence analysis.

The Kozak consensus for vertebrates is: (GCC)GCCRCCATGG
Where R = A or G at position -3 relative to ATG.

Scoring follows Cavener & Ray (1991) positional weight matrix approach.
Positions scored: -6 to +4 relative to the A of ATG (+1 = A, +2 = T, +3 = G).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple


# Kozak context: positions -6 to +4 (11 nt total, ATG at [6,7,8])
# Positional frequency matrix derived from vertebrate Kozak sequences.
# Rows: A, C, G, T. Columns: positions -6 through +4.
# Normalised to [0, 1] (1 = dominant base at that position).
_PFM: List[Tuple[float, float, float, float]] = [
    # pos: -6    -5    -4    -3    -2    -1   +1(A) +2(T) +3(G) +4
    (0.22, 0.28, 0.28, 0.46, 0.22, 0.22, 1.00, 0.00, 0.00, 0.25),  # A
    (0.28, 0.28, 0.18, 0.12, 0.22, 0.22, 0.00, 0.00, 0.00, 0.25),  # C
    (0.22, 0.22, 0.28, 0.30, 0.22, 0.22, 0.00, 0.00, 1.00, 0.25),  # G
    (0.28, 0.22, 0.26, 0.12, 0.34, 0.34, 0.00, 1.00, 0.00, 0.25),  # T
]
_BASES = "ACGT"
_CONTEXT_LEN = 10  # positions -6 through +4 (10 positions around ATG start)


@dataclass
class KozakResult:
    """Result of Kozak consensus analysis for one ATG."""
    atg_position: int         # 0-based position of A in ATG within the full sequence
    context: str              # extracted Kozak context window
    score: float              # normalised score 0–1 (1 = perfect consensus)
    has_optimal_r3: bool      # A or G at position -3
    matches_consensus: bool   # True if score > 0.7 threshold
    strength: str             # "strong", "adequate", "weak"

    def __repr__(self) -> str:
        return (
            f"KozakResult(pos={self.atg_position}, "
            f"context={self.context!r}, score={self.score:.2f}, "
            f"strength={self.strength!r})"
        )


def _score_context(context: str) -> float:
    """Score a 10-nt Kozak context window against the PFM."""
    if len(context) != 10:
        return 0.0
    total = 0.0
    for i, nt in enumerate(context.upper()):
        if nt not in _BASES:
            continue
        row = _BASES.index(nt)
        total += _PFM[row][i]
    # Max possible score: 10 (1.0 per position)
    return total / 10.0


def _strength(score: float) -> str:
    # Thresholds calibrated against achievable scores with the PFM above.
    # Max achievable for ideal Kozak (GCCACCATGG) ≈ 0.48.
    if score >= 0.43:
        return "strong"
    if score >= 0.33:
        return "adequate"
    return "weak"


def check_kozak(sequence: str, atg_position: Optional[int] = None) -> KozakResult:
    """
    Analyse the Kozak context around the first (or specified) ATG in the sequence.

    Parameters
    ----------
    sequence : str
        Nucleotide sequence (DNA).
    atg_position : int, optional
        0-based position of the ATG to analyse. If None, uses the first ATG found.

    Returns
    -------
    KozakResult
    """
    seq = sequence.upper().replace("U", "T")

    if atg_position is None:
        pos = seq.find("ATG")
        if pos == -1:
            raise ValueError("No ATG start codon found in sequence.")
    else:
        pos = atg_position
        if seq[pos:pos+3] != "ATG":
            raise ValueError(f"No ATG at position {pos}.")

    # Extract context: 6 nt before ATG + ATG + 1 nt after = 10 nt total
    ctx_start = pos - 6
    ctx_end = pos + 4   # positions -6 to +4 (ATG at indices 6,7,8 of the 10-nt window)
    # Pad with N if near sequence edges
    left_pad = max(0, -ctx_start) * "N"
    right_pad = max(0, ctx_end - len(seq)) * "N"
    actual_start = max(0, ctx_start)
    actual_end = min(len(seq), ctx_end)
    context = left_pad + seq[actual_start:actual_end] + right_pad

    score = _score_context(context)

    # -3 position relative to ATG = index 3 in the 10-nt context
    r3_base = context[3] if len(context) > 3 else "N"
    has_r3 = r3_base in "AG"

    return KozakResult(
        atg_position=pos,
        context=context,
        score=score,
        has_optimal_r3=has_r3,
        matches_consensus=score >= 0.55,
        strength=_strength(score),
    )


def find_all_kozak_contexts(sequence: str, min_score: float = 0.0) -> List[KozakResult]:
    """Find and score Kozak contexts for every ATG in the sequence."""
    seq = sequence.upper().replace("U", "T")
    results = []
    start = 0
    while True:
        pos = seq.find("ATG", start)
        if pos == -1:
            break
        result = check_kozak(seq, pos)
        if result.score >= min_score:
            results.append(result)
        start = pos + 1
    return results
