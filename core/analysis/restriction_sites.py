"""
Restriction enzyme site scanning.

Uses BioPython's Restriction module for recognition site data.
Falls back to a small curated built-in table for the most common
cloning enzymes if BioPython is unavailable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

# Built-in recognition patterns for common enzymes (IUPAC notation)
# Used as fallback and for quick lookups without full Bio.Restriction import.
COMMON_ENZYMES: Dict[str, str] = {
    # Type IIS / Golden Gate
    "BsaI":   "GGTCTC",
    "BbsI":   "GAAGAC",
    "Esp3I":  "CGTCTC",
    "SapI":   "GCTCTTC",
    "BsmBI":  "CGTCTC",
    # Classic cloning
    "EcoRI":  "GAATTC",
    "HindIII":"AAGCTT",
    "BamHI":  "GGATCC",
    "NcoI":   "CCATGG",
    "NheI":   "GCTAGC",
    "XhoI":   "CTCGAG",
    "XbaI":   "TCTAGA",
    "SpeI":   "ACTAGT",
    "NotI":   "GCGGCCGC",
    "SalI":   "GTCGAC",
    "PstI":   "CTGCAG",
    "KpnI":   "GGTACC",
    "SmaI":   "CCCGGG",
    "SacI":   "GAGCTC",
    "ClaI":   "ATCGAT",
    # Blunt cutters
    "EcoRV":  "GATATC",
    "HpaI":   "GTTAAC",
    "StuI":   "AGGCCT",
    "ScaI":   "AGTACT",
    # Methylation-sensitive
    "DpnI":   "GATC",
    "MboI":   "GATC",
    "Sau3AI": "GATC",
    # Rare cutters (8+ bp)
    "SfiI":   "GGCCNNNNNGGCC",
    "PacI":   "TTAATTAA",
    "AscI":   "GGCGCGCC",
    "FseI":   "GGCCGGCC",
    "SwaI":   "ATTTAAAT",
    "PmeI":   "GTTTAAAC",
}

# IUPAC ambiguity → regex character class
_IUPAC_TO_REGEX: Dict[str, str] = {
    "A": "A", "T": "T", "G": "G", "C": "C",
    "R": "[AG]", "Y": "[CT]", "S": "[GC]", "W": "[AT]",
    "K": "[GT]", "M": "[AC]", "B": "[CGT]", "D": "[AGT]",
    "H": "[ACT]", "V": "[ACG]", "N": "[ACGT]",
}


def _iupac_to_regex(pattern: str) -> str:
    import re
    return "".join(_IUPAC_TO_REGEX.get(c, c) for c in pattern.upper())


@dataclass
class RestrictionSiteHit:
    enzyme: str
    recognition_sequence: str
    position: int     # 0-based start of recognition sequence on forward strand
    strand: str       # "+" forward, "-" reverse complement

    def __repr__(self) -> str:
        return (
            f"RestrictionSiteHit({self.enzyme!r} @ pos {self.position} "
            f"strand={self.strand!r})"
        )


def _reverse_complement(seq: str) -> str:
    comp = str.maketrans("ATGCRYSWKMBDHVN", "TACGYRSWMKVHDBN")
    return seq.upper().translate(comp)[::-1]


def scan_restriction_sites(
    sequence: str,
    enzymes: Optional[List[str]] = None,
) -> Dict[str, List[RestrictionSiteHit]]:
    """
    Scan a DNA sequence for restriction enzyme recognition sites.

    Parameters
    ----------
    sequence : str
        DNA sequence to scan.
    enzymes : list of str, optional
        Enzyme names to check. Defaults to COMMON_ENZYMES.

    Returns
    -------
    dict
        {enzyme_name: [RestrictionSiteHit, ...]}
        Only enzymes with at least one hit are included.
    """
    import re

    seq = sequence.upper().replace("U", "T")
    rc_seq = _reverse_complement(seq)
    n = len(seq)

    enzyme_list = enzymes if enzymes else list(COMMON_ENZYMES.keys())
    results: Dict[str, List[RestrictionSiteHit]] = {}

    for enzyme in enzyme_list:
        recognition = COMMON_ENZYMES.get(enzyme)
        if not recognition:
            # Try BioPython if available
            try:
                from Bio.Restriction import AllEnzymes
                enz_obj = AllEnzymes.get(enzyme)
                if enz_obj:
                    recognition = str(enz_obj.site)
                else:
                    continue
            except ImportError:
                continue

        regex = _iupac_to_regex(recognition)
        hits: List[RestrictionSiteHit] = []

        # Forward strand
        for m in re.finditer(f"(?={regex})", seq):
            hits.append(RestrictionSiteHit(
                enzyme=enzyme,
                recognition_sequence=recognition,
                position=m.start(),
                strand="+",
            ))

        # Reverse complement strand (report position on forward)
        rev_rec = _iupac_to_regex(_reverse_complement(recognition))
        for m in re.finditer(f"(?={rev_rec})", seq):
            hits.append(RestrictionSiteHit(
                enzyme=enzyme,
                recognition_sequence=recognition,
                position=m.start(),
                strand="-",
            ))

        if hits:
            results[enzyme] = sorted(hits, key=lambda h: h.position)

    return results


def sites_present(
    sequence: str,
    enzymes: Optional[List[str]] = None,
) -> List[str]:
    """Return list of enzyme names that have at least one hit in the sequence."""
    return list(scan_restriction_sites(sequence, enzymes).keys())


def sites_absent(
    sequence: str,
    required_absent: List[str],
) -> List[str]:
    """Return list of enzymes from required_absent that ARE present (i.e. violations)."""
    present = set(sites_present(sequence, required_absent))
    return [e for e in required_absent if e in present]
