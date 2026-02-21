"""
Sequence part models for the parts library.

SequencePart is the base class; specialized part types inherit to add
bespoke fields (e.g., CDS has protein_sequence, codon_usage; UTRs have
stability metrics).

Parts are auto-extracted when sequences are analyzed or imported.
"""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Literal, Optional


@dataclass
class SequencePart:
    """
    Base class for reusable sequence parts.

    Each part can be mixed and matched in the Parts Workshop to
    assemble new mRNA sequences.
    """
    name: str
    sequence: str
    part_type: Literal["5_utr", "kozak", "cds", "3_utr", "polya"]
    source: str  # "database_import", "generated", "manual", "extracted"

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    origin_sequence_id: Optional[str] = None  # ID of parent mRNASequence
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def length(self) -> int:
        return len(self.sequence)

    @property
    def sequence_hash(self) -> str:
        """SHA256 hash for deduplication."""
        return hashlib.sha256(self.sequence.encode()).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "sequence": self.sequence,
            "part_type": self.part_type,
            "source": self.source,
            "origin_sequence_id": self.origin_sequence_id,
            "metadata": self.metadata,
        }


@dataclass
class UTR5Part(SequencePart):
    """5' UTR part with stability and structure metrics."""
    part_type: Literal["5_utr"] = field(default="5_utr", init=False)

    # Predicted secondary structure stability
    stability_score: Optional[float] = None
    mfe: Optional[float] = None  # Minimum free energy from ViennaRNA
    secondary_structure_dot: Optional[str] = None  # Dot-bracket notation


@dataclass
class KozakPart(SequencePart):
    """Kozak consensus sequence part."""
    part_type: Literal["kozak"] = field(default="kozak", init=False)

    # Consensus score (0-1) based on optimal Kozak pattern
    consensus_score: Optional[float] = None
    # Canonical Kozak is: gcc(A/G)ccATGG
    matches_canonical: Optional[bool] = None


@dataclass
class CDSPart(SequencePart):
    """Coding sequence part with translation and codon metrics."""
    part_type: Literal["cds"] = field(default="cds", init=False)

    # Translated protein sequence
    protein_sequence: Optional[str] = None

    # Codon usage metrics
    codon_usage: Optional[Dict[str, float]] = None  # {codon: frequency}
    cai: Optional[float] = None  # Codon Adaptation Index

    # Quality checks
    has_start_codon: Optional[bool] = None
    has_stop_codon: Optional[bool] = None
    in_frame: Optional[bool] = None


@dataclass
class UTR3Part(SequencePart):
    """3' UTR part with stability and regulatory element annotations."""
    part_type: Literal["3_utr"] = field(default="3_utr", init=False)

    # Predicted stability
    stability_score: Optional[float] = None
    mfe: Optional[float] = None

    # Regulatory elements (AU-rich elements, miRNA binding sites, etc.)
    regulatory_elements: Optional[Dict[str, Any]] = None


@dataclass
class PolyAPart(SequencePart):
    """Poly(A) tail part."""
    part_type: Literal["polya"] = field(default="polya", init=False)

    # Length of the poly(A) stretch
    tail_length: Optional[int] = None

    # Purity (percentage of A nucleotides)
    purity: Optional[float] = None


# Type alias for all part types
AnyPart = UTR5Part | KozakPart | CDSPart | UTR3Part | PolyAPart


def create_part_from_component(
    sequence: str,
    part_type: Literal["5_utr", "kozak", "cds", "3_utr", "polya"],
    name: str,
    source: str,
    origin_sequence_id: Optional[str] = None,
) -> AnyPart:
    """
    Factory function to create the appropriate Part subclass.

    Used during auto-extraction from mRNASequence objects.
    """
    if part_type == "5_utr":
        return UTR5Part(
            name=name,
            sequence=sequence,
            source=source,
            origin_sequence_id=origin_sequence_id,
        )
    elif part_type == "kozak":
        return KozakPart(
            name=name,
            sequence=sequence,
            source=source,
            origin_sequence_id=origin_sequence_id,
        )
    elif part_type == "cds":
        return CDSPart(
            name=name,
            sequence=sequence,
            source=source,
            origin_sequence_id=origin_sequence_id,
        )
    elif part_type == "3_utr":
        return UTR3Part(
            name=name,
            sequence=sequence,
            source=source,
            origin_sequence_id=origin_sequence_id,
        )
    elif part_type == "polya":
        return PolyAPart(
            name=name,
            sequence=sequence,
            source=source,
            origin_sequence_id=origin_sequence_id,
        )
    else:
        raise ValueError(f"Unknown part type: {part_type}")
