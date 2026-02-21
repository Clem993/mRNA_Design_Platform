"""
Worklist domain model.

A Worklist is the user's active work queue — a curated collection of
sequences they want to analyze, score, assemble, or export.

Items can originate from three sources:
  - database_import  : selected rows from a DB connector
  - generated        : output of a generative model or genetic algorithm
  - cds_optimized    : protein sequence → optimized CDS + UTR selection
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, List, Literal, Optional

from core.models.sequence import mRNASequence


ItemOrigin = Literal["database_import", "generated", "cds_optimized", "manual"]
ItemStatus = Literal["pending", "analyzing", "analyzed", "error"]


@dataclass
class WorklistItem:
    """
    A single entry in the worklist.

    scores: populated by model runners — {model_name: score}
    analysis: populated by SequenceAnalyzer — {metric_name: value}
    """
    sequence: mRNASequence
    origin: ItemOrigin

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: ItemStatus = "pending"
    added_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Scoring results — keyed by model name
    scores: Dict[str, float] = field(default_factory=dict)

    # Analysis results — support multiple analyses
    # Structure: {analysis_name: {metric: value, ...}}
    # - "base_analysis": core sequence metrics (GC%, CAI, etc.)
    # - model/analysis names: custom analysis results
    analyses: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # Notes / tags
    notes: Optional[str] = None
    tags: List[str] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.sequence.name

    @property
    def has_scores(self) -> bool:
        return bool(self.scores)

    @property
    def has_analyses(self) -> bool:
        return bool(self.analyses)

    @property
    def base_analysis(self) -> Optional[Dict[str, Any]]:
        """Quick accessor for base sequence analysis results."""
        return self.analyses.get("base_analysis")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "sequence_id": self.sequence.id,
            "sequence_name": self.sequence.name,
            "origin": self.origin,
            "status": self.status,
            "added_at": self.added_at.isoformat(),
            "scores": self.scores,
            "notes": self.notes,
            "tags": self.tags,
        }


@dataclass
class Worklist:
    """
    The user's active sequence work queue.

    Provides list-like access to WorklistItems with helpers for
    filtering by origin, status, and tags.
    """
    name: str = "Untitled Worklist"
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    items: List[WorklistItem] = field(default_factory=list)

    # ── Mutation ────────────────────────────────────────────────────────────

    def add(self, sequence: mRNASequence, origin: ItemOrigin = "manual") -> WorklistItem:
        """Add a sequence and return the new WorklistItem."""
        item = WorklistItem(sequence=sequence, origin=origin)
        self.items.append(item)
        return item

    def add_many(
        self,
        sequences: List[mRNASequence],
        origin: ItemOrigin = "manual",
    ) -> List[WorklistItem]:
        return [self.add(seq, origin) for seq in sequences]

    def remove(self, item_id: str) -> bool:
        """Remove item by id. Returns True if found and removed."""
        before = len(self.items)
        self.items = [i for i in self.items if i.id != item_id]
        return len(self.items) < before

    def clear(self) -> None:
        self.items.clear()

    # ── Query ────────────────────────────────────────────────────────────────

    def get(self, item_id: str) -> Optional[WorklistItem]:
        return next((i for i in self.items if i.id == item_id), None)

    def by_origin(self, origin: ItemOrigin) -> List[WorklistItem]:
        return [i for i in self.items if i.origin == origin]

    def by_status(self, status: ItemStatus) -> List[WorklistItem]:
        return [i for i in self.items if i.status == status]

    def with_tag(self, tag: str) -> List[WorklistItem]:
        return [i for i in self.items if tag in i.tags]

    def scored(self, model_name: Optional[str] = None) -> List[WorklistItem]:
        """Items that have scores. Filter by model_name if given."""
        if model_name:
            return [i for i in self.items if model_name in i.scores]
        return [i for i in self.items if i.scores]

    # ── Properties ──────────────────────────────────────────────────────────

    @property
    def count(self) -> int:
        return len(self.items)

    @property
    def sequences(self) -> List[mRNASequence]:
        return [i.sequence for i in self.items]

    def __iter__(self) -> Iterator[WorklistItem]:
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def __repr__(self) -> str:
        return f"Worklist(name={self.name!r}, count={self.count})"
