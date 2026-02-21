"""GC content calculation — global and sliding window."""
from __future__ import annotations

from typing import Optional
import numpy as np


def gc_fraction(sequence: str) -> float:
    """Return global GC fraction (0.0 – 1.0) for a nucleotide sequence."""
    seq = sequence.upper()
    if not seq:
        return 0.0
    gc = sum(1 for nt in seq if nt in "GC")
    return gc / len(seq)


def gc_percent(sequence: str) -> float:
    """Return global GC% (0 – 100)."""
    return gc_fraction(sequence) * 100.0


def gc_sliding_window(
    sequence: str,
    window: int = 100,
    step: int = 1,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Compute GC% in a sliding window across the sequence.

    Returns
    -------
    positions : np.ndarray of int
        Centre position of each window (0-based nucleotide index).
    gc_values : np.ndarray of float
        GC% (0–100) for each window.
    """
    seq = sequence.upper()
    n = len(seq)
    if n == 0 or window > n:
        return np.array([], dtype=int), np.array([], dtype=float)

    # Pre-compute cumulative GC counts for O(n) sliding window
    gc_flags = np.array([1 if nt in "GC" else 0 for nt in seq], dtype=np.int32)
    cumsum = np.zeros(n + 1, dtype=np.int32)
    cumsum[1:] = np.cumsum(gc_flags)

    starts = np.arange(0, n - window + 1, step)
    ends = starts + window
    gc_counts = cumsum[ends] - cumsum[starts]
    gc_values = gc_counts / window * 100.0
    positions = starts + window // 2

    return positions, gc_values


def gc_by_codon_position(cds: str) -> dict[str, float]:
    """
    Return GC% at each codon position (GC1, GC2, GC3).
    cds must be in-frame and length divisible by 3.
    """
    seq = cds.upper()
    if len(seq) % 3 != 0:
        raise ValueError("CDS length is not divisible by 3.")
    codons = [seq[i:i+3] for i in range(0, len(seq), 3)]
    gc1 = sum(1 for c in codons if c[0] in "GC") / len(codons) * 100
    gc2 = sum(1 for c in codons if c[1] in "GC") / len(codons) * 100
    gc3 = sum(1 for c in codons if c[2] in "GC") / len(codons) * 100
    return {"GC1": gc1, "GC2": gc2, "GC3": gc3, "GC_overall": gc_percent(seq)}
