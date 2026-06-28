"""
Sequence-liability motif scanning for mRNA constructs.

Scans the functional regions of an mRNA for short sequence motifs that are
known to compromise expression, stability, or processing:

  - **uORF start (upstream AUG)** in the 5'UTR — can initiate an upstream
    open reading frame and reduce translation of the main CDS.
  - **Premature polyadenylation signal** (AAUAAA / AUUAAA) inside the CDS —
    can cause truncated transcripts.
  - **AU-rich element (ARE, AUUUA)** in the 3'UTR — recruits decay machinery
    and shortens mRNA half-life.
  - **Cryptic 5' splice-donor consensus** (GT[AG]AGT) anywhere — risk of
    aberrant splicing when transcribed from a DNA template.

All scanning is done on DNA alphabet (T, not U); inputs are normalised.
Severities are plain strings ("critical" / "warning" / "info") so this module
stays free of any dependency on the liability aggregator.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

# Severity labels (kept as bare strings to avoid import cycles)
CRITICAL = "critical"
WARNING = "warning"
INFO = "info"

# Cap per-motif hits so a pathological sequence can't produce thousands of rows
_MAX_HITS_PER_MOTIF = 50


@dataclass
class MotifHit:
    """A single sequence-liability motif occurrence."""
    name: str            # machine name, e.g. "uorf"
    label: str           # human label, e.g. "Upstream AUG (uORF)"
    region: str          # "5'UTR" | "CDS" | "3'UTR" | "full"
    start: int           # 0-based start within the scanned region
    end: int             # exclusive end within the region
    match: str           # the matched subsequence (DNA alphabet)
    severity: str        # CRITICAL | WARNING | INFO
    description: str     # why it matters
    recommendation: str  # what to do about it

    def __repr__(self) -> str:
        return f"MotifHit({self.name} {self.region}@{self.start} {self.match!r})"


def _norm(seq: Optional[str]) -> str:
    return (seq or "").upper().replace("U", "T")


def _find_all(pattern: str, seq: str) -> List[re.Match]:
    """Find non-overlapping regex matches, capped."""
    return list(re.finditer(pattern, seq))[:_MAX_HITS_PER_MOTIF]


def scan_motifs(
    five_prime_utr: Optional[str] = None,
    cds: Optional[str] = None,
    three_prime_utr: Optional[str] = None,
    full_seq: Optional[str] = None,
) -> List[MotifHit]:
    """
    Scan an mRNA's regions for liability motifs.

    Pass the individual components when available. ``full_seq`` is used for
    region-agnostic scans (splice donor) and as a fallback when components
    are not provided (e.g. a monolithic ``full_mrna`` record).
    """
    hits: List[MotifHit] = []

    utr5 = _norm(five_prime_utr)
    cds_s = _norm(cds)
    utr3 = _norm(three_prime_utr)
    full = _norm(full_seq) or (utr5 + cds_s + utr3)

    # ── uORF: any ATG in the 5'UTR ────────────────────────────────────────────
    for m in _find_all("ATG", utr5):
        hits.append(MotifHit(
            name="uorf",
            label="Upstream AUG (uORF)",
            region="5'UTR",
            start=m.start(), end=m.end(), match=m.group(),
            severity=WARNING,
            description="An AUG in the 5'UTR can start an upstream ORF and "
                        "reduce ribosome loading on the main CDS.",
            recommendation="Remove or silently mutate upstream AUGs in the 5'UTR.",
        ))

    # ── Premature polyadenylation signal inside the CDS ───────────────────────
    for m in _find_all("AATAAA|ATTAAA", cds_s):
        hits.append(MotifHit(
            name="premature_polya",
            label="Premature polyA signal",
            region="CDS",
            start=m.start(), end=m.end(), match=m.group(),
            severity=CRITICAL,
            description="A canonical polyadenylation signal inside the CDS can "
                        "cause premature cleavage and a truncated protein.",
            recommendation="Codon-optimise to remove the internal AAUAAA/AUUAAA signal.",
        ))

    # ── AU-rich element (ARE) in the 3'UTR ────────────────────────────────────
    for m in _find_all("ATTTA", utr3):
        hits.append(MotifHit(
            name="are",
            label="AU-rich element (ARE)",
            region="3'UTR",
            start=m.start(), end=m.end(), match=m.group(),
            severity=WARNING,
            description="AUUUA pentamers recruit mRNA-decay machinery and shorten "
                        "transcript half-life.",
            recommendation="Remove ARE motifs from the 3'UTR to improve stability.",
        ))

    # ── Cryptic 5' splice-donor consensus (region-agnostic) ───────────────────
    for m in _find_all("GT[AG]AGT", full):
        hits.append(MotifHit(
            name="splice_donor",
            label="Cryptic splice donor",
            region="full",
            start=m.start(), end=m.end(), match=m.group(),
            severity=INFO,
            description="Matches the 5' splice-donor consensus; may cause aberrant "
                        "splicing if transcribed from a DNA template in cells.",
            recommendation="Consider disrupting the GU[A/G]AGU consensus if splicing is a concern.",
        ))

    return hits
