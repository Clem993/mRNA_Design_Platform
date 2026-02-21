"""
Core mRNA sequence domain model.

Designed to be flexible: different databases store sequence data differently.
Some customers have a single 'mrna_sequence' field; others split into UTR/CDS/PolyA.
The SchemaMapper normalizes those into this model.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional


@dataclass
class SequenceAnnotation:
    """A named region within a sequence (0-based, half-open [start, end))."""
    label: str
    start: int
    end: int
    strand: Literal["+", "-", "."] = "+"
    color: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def length(self) -> int:
        return self.end - self.start


@dataclass
class mRNASequence:
    """
    Core mRNA sequence model.

    Components are all optional because different databases represent
    sequence data at different granularities. assembled_sequence will
    concatenate whichever components are present, or return full_mrna
    if the database provides the complete sequence as a single field.
    """
    name: str
    source: Literal["local", "database"]

    # Auto-generated unique identifier
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Which database connection this came from (None for local sequences)
    db_source: Optional[str] = None

    # ── Sequence components (all optional) ──────────────────────────────────
    # Stored as DNA (T not U) for computational convenience; displayed as RNA
    five_prime_utr: Optional[str] = None
    kozak: Optional[str] = None
    cds: Optional[str] = None
    three_prime_utr: Optional[str] = None
    poly_a: Optional[str] = None

    # Full pre-assembled sequence from DB (when component breakdown is unavailable)
    full_mrna: Optional[str] = None

    # Annotations populated by analysis or DB import
    annotations: List[SequenceAnnotation] = field(default_factory=list)

    # Raw database record — all original fields preserved for model use
    raw_metadata: Dict[str, Any] = field(default_factory=dict)

    # Analysis cache — populated lazily by SequenceAnalyzer
    _analysis_cache: Dict[str, Any] = field(default_factory=dict, repr=False)

    # ── Derived properties ──────────────────────────────────────────────────

    @property
    def assembled_sequence(self) -> str:
        """
        Return the full sequence by concatenating present components.
        Falls back to full_mrna if no components are set.
        Raises ValueError if neither is available.
        """
        parts = [
            self.five_prime_utr or "",
            self.kozak or "",
            self.cds or "",
            self.three_prime_utr or "",
            self.poly_a or "",
        ]
        assembled = "".join(parts)
        if assembled:
            return assembled.upper()
        if self.full_mrna:
            return self.full_mrna.upper()
        raise ValueError(
            f"Sequence '{self.name}' has no components and no full_mrna set."
        )

    @property
    def has_components(self) -> bool:
        """True if at least one sub-component is explicitly set."""
        return any([
            self.five_prime_utr,
            self.kozak,
            self.cds,
            self.three_prime_utr,
            self.poly_a,
        ])

    @property
    def component_annotations(self) -> List[SequenceAnnotation]:
        """
        Auto-derive position annotations from the component breakdown.
        Only available when has_components is True.
        """
        annotations = []
        pos = 0
        component_colors = {
            "5'UTR": "#4A90D9",
            "Kozak": "#F5A623",
            "CDS": "#7ED321",
            "3'UTR": "#9B59B6",
            "PolyA": "#E74C3C",
        }
        components = [
            ("5'UTR", self.five_prime_utr),
            ("Kozak", self.kozak),
            ("CDS", self.cds),
            ("3'UTR", self.three_prime_utr),
            ("PolyA", self.poly_a),
        ]
        for label, seq in components:
            if seq:
                annotations.append(SequenceAnnotation(
                    label=label,
                    start=pos,
                    end=pos + len(seq),
                    color=component_colors.get(label),
                ))
                pos += len(seq)
        return annotations

    @property
    def length(self) -> int:
        try:
            return len(self.assembled_sequence)
        except ValueError:
            return 0

    @property
    def cds_length(self) -> Optional[int]:
        return len(self.cds) if self.cds else None

    # ── Mutation helpers ────────────────────────────────────────────────────

    def with_cds(self, cds: str) -> "mRNASequence":
        """Return a new mRNASequence with the CDS replaced."""
        from dataclasses import replace
        return replace(
            self,
            id=str(uuid.uuid4()),
            cds=cds.upper(),
            source="local",
            db_source=None,
            _analysis_cache={},
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "source": self.source,
            "db_source": self.db_source,
            "five_prime_utr": self.five_prime_utr,
            "kozak": self.kozak,
            "cds": self.cds,
            "three_prime_utr": self.three_prime_utr,
            "poly_a": self.poly_a,
            "full_mrna": self.full_mrna,
            "raw_metadata": self.raw_metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "mRNASequence":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data["name"],
            source=data.get("source", "local"),
            db_source=data.get("db_source"),
            five_prime_utr=data.get("five_prime_utr"),
            kozak=data.get("kozak"),
            cds=data.get("cds"),
            three_prime_utr=data.get("three_prime_utr"),
            poly_a=data.get("poly_a"),
            full_mrna=data.get("full_mrna"),
            raw_metadata=data.get("raw_metadata", {}),
        )

    def __repr__(self) -> str:
        length = self.length
        return f"mRNASequence(name={self.name!r}, source={self.source!r}, length={length})"
