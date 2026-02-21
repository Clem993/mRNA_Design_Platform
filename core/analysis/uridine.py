"""
Uridine content analysis for mRNA sequences.

High uridine content can trigger innate immune responses. Modified
nucleotides (N1-methylpseudouridine) mitigate this, but it's still
useful to quantify uridine distribution.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class UridineReport:
    """Uridine content analysis results."""
    total_u: int
    total_length: int
    u_fraction: float          # 0.0 – 1.0
    u_percent: float           # 0 – 100
    ua_ratio: float            # U/A ratio
    high_u_stretches: List[Tuple[int, int, int]]  # (start, end, length) of high-U regions


def analyze_uridine(
    sequence: str,
    window: int = 50,
    threshold: float = 0.40,
) -> UridineReport:
    """
    Analyze uridine content in an RNA/DNA sequence.

    Parameters
    ----------
    sequence : str
        Nucleotide sequence (DNA or RNA).
    window : int
        Sliding window size for high-U stretch detection.
    threshold : float
        U fraction threshold for flagging high-U windows.

    Returns
    -------
    UridineReport
    """
    seq = sequence.upper().replace("T", "U")
    n = len(seq)

    total_u = seq.count("U")
    total_a = seq.count("A")

    u_fraction = total_u / n if n > 0 else 0.0
    ua_ratio = total_u / total_a if total_a > 0 else float("inf")

    # Find high-U stretches using sliding window
    stretches: List[Tuple[int, int, int]] = []
    if n >= window:
        in_stretch = False
        stretch_start = 0
        for i in range(n - window + 1):
            win = seq[i:i + window]
            u_frac = win.count("U") / window
            if u_frac >= threshold:
                if not in_stretch:
                    stretch_start = i
                    in_stretch = True
            else:
                if in_stretch:
                    stretches.append((stretch_start, i + window - 1, i + window - 1 - stretch_start))
                    in_stretch = False
        if in_stretch:
            stretches.append((stretch_start, n, n - stretch_start))

    return UridineReport(
        total_u=total_u,
        total_length=n,
        u_fraction=u_fraction,
        u_percent=u_fraction * 100,
        ua_ratio=ua_ratio,
        high_u_stretches=stretches,
    )
