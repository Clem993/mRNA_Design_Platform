"""
Dinucleotide frequency analysis.

CpG dinucleotides are immunostimulatory in mammals (recognized by TLR9).
UpA dinucleotides are associated with mRNA instability (targeted by
cellular RNases). Quantifying these helps optimize mRNA therapeutics.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple


@dataclass
class DinucleotideReport:
    """Dinucleotide frequency analysis results."""
    frequencies: Dict[str, int]          # all dinucleotide counts
    normalized: Dict[str, float]         # frequencies / total dinucleotides
    cpg_count: int = 0
    upa_count: int = 0
    cpg_positions: List[int] = field(default_factory=list)
    upa_positions: List[int] = field(default_factory=list)
    total_dinucleotides: int = 0


def analyze_dinucleotides(
    sequence: str,
    flag_cpg: bool = True,
    flag_upa: bool = True,
) -> DinucleotideReport:
    """
    Analyze dinucleotide frequencies in a nucleotide sequence.

    Parameters
    ----------
    sequence : str
        DNA or RNA sequence.
    flag_cpg : bool
        Track CpG positions.
    flag_upa : bool
        Track UpA (TpA in DNA) positions.

    Returns
    -------
    DinucleotideReport
    """
    seq = sequence.upper()
    n = len(seq)

    frequencies: Dict[str, int] = {}
    cpg_positions: List[int] = []
    upa_positions: List[int] = []

    for i in range(n - 1):
        di = seq[i:i + 2]
        frequencies[di] = frequencies.get(di, 0) + 1

        if flag_cpg and di == "CG":
            cpg_positions.append(i)
        if flag_upa and di in ("TA", "UA"):
            upa_positions.append(i)

    total = sum(frequencies.values())
    normalized = {k: v / total if total > 0 else 0.0 for k, v in frequencies.items()}

    return DinucleotideReport(
        frequencies=frequencies,
        normalized=normalized,
        cpg_count=len(cpg_positions),
        upa_count=len(upa_positions),
        cpg_positions=cpg_positions,
        upa_positions=upa_positions,
        total_dinucleotides=total,
    )
