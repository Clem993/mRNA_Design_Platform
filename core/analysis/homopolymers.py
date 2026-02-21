"""Homopolymer detection in nucleotide sequences."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class HomopolymerRun:
    nucleotide: str    # the repeated base ("A", "T", "G", "C")
    start: int         # 0-based start position
    end: int           # 0-based end position (exclusive)
    length: int

    def __repr__(self) -> str:
        return f"HomopolymerRun({self.nucleotide!r} ×{self.length} @ [{self.start}:{self.end}])"


def detect_homopolymers(
    sequence: str,
    min_run: int = 5,
    bases: str = "ATGC",
) -> List[HomopolymerRun]:
    """
    Detect homopolymer runs (consecutive identical nucleotides) in a sequence.

    Parameters
    ----------
    sequence : str
        Nucleotide sequence (DNA or RNA).
    min_run : int
        Minimum run length to report (default 5).
    bases : str
        Which bases to check. Default "ATGC" checks all. Use "A" to detect
        only poly-A, for example.

    Returns
    -------
    List[HomopolymerRun]
        Sorted by start position.
    """
    seq = sequence.upper().replace("U", "T")
    if not seq:
        return []

    runs: List[HomopolymerRun] = []
    i = 0
    n = len(seq)

    while i < n:
        base = seq[i]
        if base not in bases:
            i += 1
            continue
        j = i
        while j < n and seq[j] == base:
            j += 1
        run_len = j - i
        if run_len >= min_run:
            runs.append(HomopolymerRun(
                nucleotide=base,
                start=i,
                end=j,
                length=run_len,
            ))
        i = j

    return runs


def homopolymer_summary(runs: List[HomopolymerRun]) -> dict:
    """Summarise a list of HomopolymerRun objects."""
    if not runs:
        return {"count": 0, "max_length": 0, "longest": None}
    longest = max(runs, key=lambda r: r.length)
    by_base = {}
    for r in runs:
        by_base.setdefault(r.nucleotide, []).append(r)
    return {
        "count": len(runs),
        "max_length": longest.length,
        "longest": longest,
        "by_base": {b: len(v) for b, v in by_base.items()},
    }
