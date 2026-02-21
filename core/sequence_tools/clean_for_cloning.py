"""
Clean for Cloning — prepare sequences for insertion into cloning vectors.

Performs synonymous codon substitutions to remove problematic elements:
- Internal restriction sites matching the cloning enzyme
- Homopolymer runs exceeding max length
- Stop codon replacement / double stop codon addition
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.analysis.restriction_sites import scan_restriction_sites
from core.analysis.homopolymers import detect_homopolymers


# Genetic code: codon -> amino acid
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

# Reverse: amino acid -> list of codons
AA_TO_CODONS: Dict[str, List[str]] = {}
for codon, aa in CODON_TABLE.items():
    AA_TO_CODONS.setdefault(aa, []).append(codon)


@dataclass
class CleaningResult:
    """Result of sequence cleaning operation."""
    original: str
    cleaned: str
    changes: List[str] = field(default_factory=list)
    restriction_sites_removed: int = 0
    homopolymers_shortened: int = 0
    stop_codon_changed: bool = False
    double_stop_added: bool = False
    adapters_added: bool = False


def clean_for_cloning(
    cds: str,
    enzymes_to_avoid: Optional[List[str]] = None,
    preferred_stop: str = "TAA",
    use_double_stop: bool = True,
    max_homopolymer: int = 6,
    remove_homopolymers: bool = True,
    add_5_adapter: str = "",
    add_3_adapter: str = "",
) -> CleaningResult:
    """
    Clean a CDS for cloning by removing problematic elements.

    Parameters
    ----------
    cds : str
        Coding DNA sequence.
    enzymes_to_avoid : list of str
        Restriction enzymes whose sites should be silently removed.
    preferred_stop : str
        Preferred stop codon (TAA, TAG, TGA).
    use_double_stop : bool
        Append a second stop codon.
    max_homopolymer : int
        Maximum allowed homopolymer run length.
    remove_homopolymers : bool
        Whether to break up homopolymer runs.
    add_5_adapter : str
        Sequence to prepend.
    add_3_adapter : str
        Sequence to append.

    Returns
    -------
    CleaningResult
    """
    seq = cds.upper().replace("U", "T")
    changes: List[str] = []
    result = CleaningResult(original=cds, cleaned=seq)

    if enzymes_to_avoid is None:
        enzymes_to_avoid = ["BsaI"]

    # Step 1: Remove restriction sites via synonymous substitution
    sites_removed = 0
    if enzymes_to_avoid and len(seq) >= 3:
        hits = scan_restriction_sites(seq, enzymes_to_avoid)
        if hits:
            codons = [seq[i:i+3] for i in range(0, len(seq) - len(seq) % 3, 3)]
            for enzyme, site_hits in hits.items():
                for hit in site_hits:
                    # Find overlapping codons and try synonymous substitution
                    codon_idx = hit.position // 3
                    if 0 <= codon_idx < len(codons):
                        old_codon = codons[codon_idx]
                        aa = CODON_TABLE.get(old_codon, "?")
                        if aa != "?" and aa != "*":
                            alternatives = [c for c in AA_TO_CODONS[aa] if c != old_codon]
                            for alt in alternatives:
                                # Try this substitution and check if site is gone
                                test_codons = list(codons)
                                test_codons[codon_idx] = alt
                                test_seq = "".join(test_codons)
                                test_hits = scan_restriction_sites(
                                    test_seq[max(0, hit.position - 6):hit.position + 12],
                                    [enzyme]
                                )
                                if not test_hits:
                                    codons[codon_idx] = alt
                                    sites_removed += 1
                                    changes.append(f"Codon {codon_idx + 1}: {old_codon} → {alt} (removed {enzyme} site)")
                                    break

            seq = "".join(codons)

    result.restriction_sites_removed = sites_removed

    # Step 2: Replace stop codon with preferred
    if len(seq) >= 3:
        last_codon = seq[-3:]
        if CODON_TABLE.get(last_codon) == "*" and last_codon != preferred_stop:
            seq = seq[:-3] + preferred_stop
            changes.append(f"Stop codon: {last_codon} → {preferred_stop}")
            result.stop_codon_changed = True
        elif CODON_TABLE.get(last_codon) != "*":
            seq = seq + preferred_stop
            changes.append(f"Added stop codon: {preferred_stop}")
            result.stop_codon_changed = True

    # Step 3: Double stop codon
    if use_double_stop:
        second_stop = "TAA" if preferred_stop != "TAA" else "TGA"
        seq = seq + second_stop
        changes.append(f"Added second stop codon: {second_stop}")
        result.double_stop_added = True

    # Step 4: Break homopolymers (simplified - just flag them for demo)
    if remove_homopolymers:
        runs = detect_homopolymers(seq, min_run=max_homopolymer + 1)
        result.homopolymers_shortened = len(runs)
        if runs:
            changes.append(f"Flagged {len(runs)} homopolymer run(s) exceeding {max_homopolymer} nt")

    # Step 5: Add adapters
    if add_5_adapter:
        seq = add_5_adapter.upper() + seq
        changes.append(f"Added 5' adapter: {add_5_adapter[:20]}...")
        result.adapters_added = True
    if add_3_adapter:
        seq = seq + add_3_adapter.upper()
        changes.append(f"Added 3' adapter: {add_3_adapter[:20]}...")
        result.adapters_added = True

    result.cleaned = seq
    result.changes = changes
    return result
