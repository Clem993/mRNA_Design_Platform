"""
Codon Optimization — optimize CDS codon usage for target organism.

Demo-level implementation that replaces rare codons with frequent ones
based on the organism's codon usage table.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.analysis.cai import CODON_TABLES, calculate_cai


# Genetic code
CODON_TABLE = {
    "TTT": "F", "TTC": "F", "TTA": "L", "TTG": "L",
    "CTT": "L", "CTC": "L", "CTA": "L", "CTG": "L",
    "ATT": "I", "ATC": "I", "ATA": "I", "ATG": "M",
    "GTT": "V", "GTC": "V", "GTA": "V", "GTG": "V",
    "TCT": "S", "TCC": "S", "TCA": "S", "TCG": "S",
    "CCT": "P", "CCC": "P", "CCA": "P", "CCG": "P",
    "ACT": "T", "ACC": "T", "ACA": "T", "ACG": "T",
    "GCT": "A", "GCC": "A", "GCA": "A", "GCG": "A",
    "TAT": "Y", "TAC": "Y", "TAA": "*", "TAG": "*",
    "CAT": "H", "CAC": "H", "CAA": "Q", "CAG": "Q",
    "AAT": "N", "AAC": "N", "AAA": "K", "AAG": "K",
    "GAT": "D", "GAC": "D", "GAA": "E", "GAG": "E",
    "TGT": "C", "TGC": "C", "TGA": "*", "TGG": "W",
    "CGT": "R", "CGC": "R", "CGA": "R", "CGG": "R",
    "AGT": "S", "AGC": "S", "AGA": "R", "AGG": "R",
    "GGT": "G", "GGC": "G", "GGA": "G", "GGG": "G",
}

AA_TO_CODONS: Dict[str, List[str]] = {}
for codon, aa in CODON_TABLE.items():
    AA_TO_CODONS.setdefault(aa, []).append(codon)


@dataclass
class OptimizationResult:
    """Result of codon optimization."""
    original_cds: str
    optimized_cds: str
    original_cai: float
    optimized_cai: float
    organism: str
    codons_changed: int
    total_codons: int
    changes: List[str] = field(default_factory=list)


def optimize_codons(
    cds: str,
    organism: str = "human",
    min_cai_target: float = 0.8,
    strategy: str = "match_host",
) -> OptimizationResult:
    """
    Optimize codon usage of a CDS for the target organism.

    Parameters
    ----------
    cds : str
        Coding DNA sequence.
    organism : str
        Target organism key.
    min_cai_target : float
        Target minimum CAI.
    strategy : str
        "match_host" — replace rare with frequent.
        "harmonize" — preserve relative usage.
        "balance" — avoid most common to prevent tRNA depletion.

    Returns
    -------
    OptimizationResult
    """
    seq = cds.upper().replace("U", "T")
    organism_key = organism.lower().replace(" ", "").replace(".", "")

    # Map organism names to table keys
    org_map = {
        "human": "human",
        "mouse": "human",  # similar codon bias
        "ecoli": "ecoli",
        "cho": "human",    # similar to human
        "yeast": "human",  # fallback
        "zebrafish": "human",
    }
    table_key = org_map.get(organism_key, "human")
    table = CODON_TABLES.get(table_key, CODON_TABLES["human"])

    # Calculate original CAI
    try:
        original_cai = calculate_cai(seq, table_key)
    except Exception:
        original_cai = 0.0

    # Split into codons
    codons = [seq[i:i+3] for i in range(0, len(seq) - len(seq) % 3, 3)]
    optimized = list(codons)
    changes = []
    codons_changed = 0

    stop_codons = {"TAA", "TAG", "TGA"}

    for i, codon in enumerate(codons):
        aa = CODON_TABLE.get(codon, "?")
        if aa == "?" or aa == "*":
            continue  # skip unknown and stop codons

        w = table.get(codon, 0.5)
        if w >= 0.8:
            continue  # already a good codon

        # Find best alternative codon for this amino acid
        alternatives = [(c, table.get(c, 0.0)) for c in AA_TO_CODONS.get(aa, []) if c not in stop_codons]
        if not alternatives:
            continue

        if strategy == "match_host":
            # Pick the most frequent codon
            best = max(alternatives, key=lambda x: x[1])
        elif strategy == "balance":
            # Pick a moderately frequent codon (avoid the very top)
            sorted_alts = sorted(alternatives, key=lambda x: x[1], reverse=True)
            best = sorted_alts[min(1, len(sorted_alts) - 1)]
        else:  # harmonize
            # Keep codons with similar relative frequency
            best = max(alternatives, key=lambda x: x[1])

        if best[0] != codon and best[1] > w:
            optimized[i] = best[0]
            changes.append(f"Pos {i + 1}: {codon} → {best[0]} ({aa}, {w:.2f} → {best[1]:.2f})")
            codons_changed += 1

    optimized_seq = "".join(optimized)

    # Calculate optimized CAI
    try:
        optimized_cai = calculate_cai(optimized_seq, table_key)
    except Exception:
        optimized_cai = 0.0

    return OptimizationResult(
        original_cds=cds,
        optimized_cds=optimized_seq,
        original_cai=original_cai,
        optimized_cai=optimized_cai,
        organism=organism,
        codons_changed=codons_changed,
        total_codons=len(codons),
        changes=changes,
    )
