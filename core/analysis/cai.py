"""
Codon Adaptation Index (CAI) calculation.

Uses BioPython's CodonAdaptationIndex and codon usage tables.
Supports human and a set of common lab organisms. Additional organisms
can be added by providing a codon usage table as a dict.
"""
from __future__ import annotations

import math
from typing import Dict, Optional

# Codon usage tables: {codon: relative_adaptiveness}
# Tables below are RSCU (relative synonymous codon usage) normalized per
# synonymous family to relative adaptiveness (0–1). Human table derived
# from Homo sapiens Kazusa database (high-expression genes).

_HUMAN_RSCU: Dict[str, float] = {
    # Phe
    "TTT": 0.55, "TTC": 1.00,
    # Leu
    "TTA": 0.07, "TTG": 0.19, "CTT": 0.42, "CTC": 0.68, "CTA": 0.16, "CTG": 1.00,
    # Ile
    "ATT": 0.71, "ATC": 1.00, "ATA": 0.31,
    # Met
    "ATG": 1.00,
    # Val
    "GTT": 0.46, "GTC": 0.62, "GTA": 0.27, "GTG": 1.00,
    # Ser
    "TCT": 0.85, "TCC": 1.00, "TCA": 0.69, "TCG": 0.27, "AGT": 0.72, "AGC": 0.97,
    # Pro
    "CCT": 0.85, "CCC": 1.00, "CCA": 0.83, "CCG": 0.22,
    # Thr
    "ACT": 0.74, "ACC": 1.00, "ACA": 0.77, "ACG": 0.27,
    # Ala
    "GCT": 0.91, "GCC": 1.00, "GCA": 0.67, "GCG": 0.19,
    # Tyr
    "TAT": 0.57, "TAC": 1.00,
    # Stop
    "TAA": 1.00, "TAG": 0.22, "TGA": 0.61,
    # His
    "CAT": 0.56, "CAC": 1.00,
    # Gln
    "CAA": 0.36, "CAG": 1.00,
    # Asn
    "AAT": 0.53, "AAC": 1.00,
    # Lys
    "AAA": 0.74, "AAG": 1.00,
    # Asp
    "GAT": 0.63, "GAC": 1.00,
    # Glu
    "GAA": 0.68, "GAG": 1.00,
    # Cys
    "TGT": 0.56, "TGC": 1.00,
    # Trp
    "TGG": 1.00,
    # Arg
    "CGT": 0.17, "CGC": 0.40, "CGA": 0.19, "CGG": 0.48, "AGA": 0.74, "AGG": 1.00,
    # Gly
    "GGT": 0.52, "GGC": 1.00, "GGA": 0.67, "GGG": 0.54,
}

_ECOLI_RSCU: Dict[str, float] = {
    # Phe
    "TTT": 1.00, "TTC": 0.59,
    # Leu
    "TTA": 0.49, "TTG": 0.74, "CTT": 0.68, "CTC": 0.39, "CTA": 0.24, "CTG": 1.00,
    # Ile
    "ATT": 1.00, "ATC": 0.82, "ATA": 0.19,
    # Met
    "ATG": 1.00,
    # Val
    "GTT": 1.00, "GTC": 0.60, "GTA": 0.73, "GTG": 0.72,
    # Ser
    "TCT": 0.92, "TCC": 0.52, "TCA": 0.46, "TCG": 0.46, "AGT": 0.72, "AGC": 1.00,
    # Pro
    "CCT": 0.63, "CCC": 0.27, "CCA": 0.67, "CCG": 1.00,
    # Thr
    "ACT": 0.95, "ACC": 1.00, "ACA": 0.47, "ACG": 0.81,
    # Ala
    "GCT": 0.92, "GCC": 0.70, "GCA": 0.91, "GCG": 1.00,
    # Tyr
    "TAT": 1.00, "TAC": 0.67,
    # Stop
    "TAA": 1.00, "TAG": 0.10, "TGA": 0.07,
    # His
    "CAT": 1.00, "CAC": 0.53,
    # Gln
    "CAA": 0.69, "CAG": 1.00,
    # Asn
    "AAT": 0.89, "AAC": 1.00,
    # Lys
    "AAA": 1.00, "AAG": 0.41,
    # Asp
    "GAT": 1.00, "GAC": 0.52,
    # Glu
    "GAA": 1.00, "GAG": 0.41,
    # Cys
    "TGT": 1.00, "TGC": 0.54,
    # Trp
    "TGG": 1.00,
    # Arg
    "CGT": 1.00, "CGC": 0.68, "CGA": 0.19, "CGG": 0.18, "AGA": 0.07, "AGG": 0.05,
    # Gly
    "GGT": 1.00, "GGC": 0.69, "GGA": 0.35, "GGG": 0.26,
}

CODON_TABLES: Dict[str, Dict[str, float]] = {
    "human": _HUMAN_RSCU,
    "ecoli": _ECOLI_RSCU,
}


def calculate_cai(
    cds: str,
    organism: str = "human",
    custom_table: Optional[Dict[str, float]] = None,
) -> float:
    """
    Calculate the Codon Adaptation Index for a CDS.

    Parameters
    ----------
    cds : str
        Coding sequence (DNA, T not U). Must start with ATG and be
        divisible by 3. Stop codon is excluded from the CAI calculation.
    organism : str
        Key into CODON_TABLES. Ignored if custom_table is provided.
    custom_table : dict, optional
        Custom {codon: relative_adaptiveness} table (values 0–1).

    Returns
    -------
    float
        CAI value in [0, 1]. Higher is better adapted.
    """
    seq = cds.upper().replace("U", "T")
    if len(seq) % 3 != 0:
        raise ValueError("CDS length is not divisible by 3.")

    table = custom_table if custom_table else CODON_TABLES.get(organism)
    if table is None:
        raise ValueError(
            f"Unknown organism '{organism}'. "
            f"Available: {list(CODON_TABLES.keys())}. "
            "Provide a custom_table to use another organism."
        )

    codons = [seq[i:i+3] for i in range(0, len(seq), 3)]
    # Exclude stop codons from CAI
    stop_codons = {"TAA", "TAG", "TGA"}
    codons = [c for c in codons if c not in stop_codons]

    if not codons:
        return 0.0

    log_sum = 0.0
    unknown = []
    for codon in codons:
        w = table.get(codon)
        if w is None or w <= 0:
            unknown.append(codon)
            continue
        log_sum += math.log(w)

    if unknown:
        # Non-standard codons (ambiguity codes, etc.) — skip gracefully
        n = len(codons) - len(unknown)
    else:
        n = len(codons)

    if n == 0:
        return 0.0

    return math.exp(log_sum / n)


def codon_usage_report(cds: str) -> Dict[str, int]:
    """Return a frequency count of each codon in the CDS."""
    seq = cds.upper().replace("U", "T")
    if len(seq) % 3 != 0:
        raise ValueError("CDS length is not divisible by 3.")
    freq: Dict[str, int] = {}
    for i in range(0, len(seq), 3):
        codon = seq[i:i+3]
        freq[codon] = freq.get(codon, 0) + 1
    return freq
