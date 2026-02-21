"""
Plasmid domain models.

Covers plasmid backbones and fully assembled plasmids (backbone + mRNA insert).
Assembly strategies and junction logic live in core/optimization/assembly.py;
these are pure data structures.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, Tuple

from core.models.sequence import SequenceAnnotation, mRNASequence


@dataclass
class PlasmidFeature:
    """A named functional element within a plasmid sequence."""
    label: str
    feature_type: Literal[
        "promoter", "terminator", "ori", "resistance", "tag",
        "cloning_site", "insert", "utr", "cds", "other"
    ]
    start: int       # 0-based, within linear representation
    end: int
    strand: Literal["+", "-", "."] = "+"
    color: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def length(self) -> int:
        return self.end - self.start


@dataclass
class PlasmidBackbone:
    """
    A cloning vector / expression backbone.

    The backbone sequence is stored as linearised DNA. For circular
    representation in the UI, the sequence wraps end-to-start.
    cloning_sites lists the restriction enzyme names or recombination
    sites present (for QC/assembly checks).
    """
    name: str
    sequence: str                             # full circular backbone, linearised

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: Optional[str] = None

    # Functional elements (promoters, resistance, ori, MCS, etc.)
    features: List[PlasmidFeature] = field(default_factory=list)

    # Restriction/recombination sites available for cloning
    cloning_sites: List[str] = field(default_factory=list)

    # Source: "local", "library", or a db_source name
    source: str = "local"
    raw_metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def length(self) -> int:
        return len(self.sequence)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "sequence": self.sequence,
            "features": [
                {
                    "label": f.label,
                    "feature_type": f.feature_type,
                    "start": f.start,
                    "end": f.end,
                    "strand": f.strand,
                    "color": f.color,
                }
                for f in self.features
            ],
            "cloning_sites": self.cloning_sites,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlasmidBackbone":
        features = [
            PlasmidFeature(
                label=f["label"],
                feature_type=f.get("feature_type", "other"),
                start=f["start"],
                end=f["end"],
                strand=f.get("strand", "+"),
                color=f.get("color"),
            )
            for f in data.get("features", [])
        ]
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data["name"],
            description=data.get("description"),
            sequence=data["sequence"],
            features=features,
            cloning_sites=data.get("cloning_sites", []),
            source=data.get("source", "local"),
        )


@dataclass
class AssemblyJunction:
    """
    Records how two parts are joined in an assembly.
    Stores the junction sequence added/used, and the strategy that created it.
    """
    part_a_name: str
    part_b_name: str
    strategy: Literal["restriction", "golden_gate", "gibson", "direct"]
    junction_sequence: str         # the overhang / overlap / linker added
    enzyme: Optional[str] = None   # for restriction/GG assemblies


@dataclass
class AssembledPlasmid:
    """
    A fully assembled plasmid: backbone + mRNA insert, with provenance.

    full_sequence is the assembled circular sequence as a flat string.
    junctions records every join point for audit / re-assembly.
    In QC mode this is populated from the unmodified parts; in Make mode
    the parts are modified and junctions record what was added.
    """
    name: str
    backbone: PlasmidBackbone
    insert: mRNASequence
    assembly_strategy: Literal["restriction", "golden_gate", "gibson"]
    assembly_mode: Literal["qc", "make"]

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    full_sequence: Optional[str] = None      # None until assembly is run
    features: List[PlasmidFeature] = field(default_factory=list)
    junctions: List[AssemblyJunction] = field(default_factory=list)
    qc_issues: List[str] = field(default_factory=list)   # validation warnings
    notes: Optional[str] = None

    @property
    def is_assembled(self) -> bool:
        return self.full_sequence is not None

    @property
    def length(self) -> Optional[int]:
        return len(self.full_sequence) if self.full_sequence else None

    def to_genbank_annotations(self) -> List[Tuple[str, str, int, int, str]]:
        """
        Return (label, feature_type, start, end, strand) tuples suitable
        for writing a GenBank file via BioPython.
        """
        return [
            (f.label, f.feature_type, f.start, f.end, f.strand)
            for f in self.features
        ]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "backbone_id": self.backbone.id,
            "backbone_name": self.backbone.name,
            "insert_id": self.insert.id,
            "insert_name": self.insert.name,
            "assembly_strategy": self.assembly_strategy,
            "assembly_mode": self.assembly_mode,
            "full_sequence": self.full_sequence,
            "qc_issues": self.qc_issues,
            "notes": self.notes,
        }
