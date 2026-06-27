"""
Global application state using param.Parameterized.

All UI components depend on AppState parameters reactively. Because
Panel uses server-side state, each user session gets its own AppState
instance, cleanly separating in-progress local sequences from imported
database records.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import param

logger = logging.getLogger(__name__)

from core.models.sequence import mRNASequence
from core.models.plasmid import PlasmidBackbone
from core.models.worklist import Worklist
from core.models.parts import SequencePart
from core.database.base import DatabaseConnector, SchemaMapper
from models.base import ModelRegistry
from models.runs import RunHistory


class AppState(param.Parameterized):
    """
    Central reactive state container.

    UI components observe these parameters via @param.depends decorators
    or Panel's reactive binding (pn.bind).
    """

    # ── Registry ─────────────────────────────────────────────────────────────
    # Local sequences created or modified in this session
    registry_local: List[mRNASequence] = param.List(default=[], doc="In-session sequences")

    # Sequences imported from databases: {db_name: [mRNASequence, ...]}
    registry_db: Dict[str, List[mRNASequence]] = param.Dict(
        default={}, doc="DB-imported sequences keyed by connection name"
    )

    # Currently selected sequence (drives all detail panels)
    active_sequence: Optional[mRNASequence] = param.Parameter(
        default=None, doc="Currently selected sequence"
    )

    # ── Worklist ─────────────────────────────────────────────────────────────
    worklist: Worklist = param.ClassSelector(
        class_=Worklist, default=None, allow_None=False,
        instantiate=True,
    )

    # ── Database connections ──────────────────────────────────────────────────
    # Active connectors: {display_name: DatabaseConnector}
    db_connections: Dict[str, DatabaseConnector] = param.Dict(
        default={}, doc="Active database connections"
    )

    # Schema mappers: {display_name: SchemaMapper}
    db_mappers: Dict[str, SchemaMapper] = param.Dict(
        default={}, doc="Schema mappers per connection"
    )

    # ── Model registry ────────────────────────────────────────────────────────
    model_registry: ModelRegistry = param.ClassSelector(
        class_=ModelRegistry, default=None, allow_None=False,
        instantiate=True,
    )

    # ── Experiment / run history (model lifecycle) ─────────────────────────────
    run_history: RunHistory = param.ClassSelector(
        class_=RunHistory, default=None, allow_None=False,
        instantiate=True,
    )

    # ── Plasmid backbones ─────────────────────────────────────────────────────
    backbone_library: List[PlasmidBackbone] = param.List(
        default=[], doc="Available plasmid backbones"
    )

    # ── Parts library ─────────────────────────────────────────────────────────
    parts_library: List[SequencePart] = param.List(
        default=[], doc="Reusable sequence parts (UTRs, CDS, Kozak, PolyA)"
    )

    # ── Multi-worklist management ────────────────────────────────────────────
    worklists: List[Worklist] = param.List(default=[], doc="All worklists")
    active_worklist_index: int = param.Integer(default=0, doc="Index of active worklist")

    # ── Analysis settings ─────────────────────────────────────────────────────
    analysis_settings: Dict[str, Any] = param.Dict(default={}, doc="Configurable analysis settings")

    # ── Generation settings ───────────────────────────────────────────────────
    generation_settings: Dict[str, Any] = param.Dict(default={}, doc="Sequence generation settings")

    # ── UI state ─────────────────────────────────────────────────────────────
    active_tab: str = param.String(default="import_db", doc="Active main panel tab")
    is_loading: bool = param.Boolean(default=False, doc="Global loading indicator")

    def __init__(self, **params: Any) -> None:
        if "worklist" not in params:
            params["worklist"] = Worklist()
        if "model_registry" not in params:
            params["model_registry"] = ModelRegistry()
        if "run_history" not in params:
            params["run_history"] = RunHistory()
        super().__init__(**params)

        # Load seed parts library if parts_library is empty
        if not self.parts_library:
            self._load_seed_parts()

    def _load_seed_parts(self) -> None:
        """Load predefined seed parts into the library."""
        from core.data.seed_parts import get_seed_parts
        seed_parts = get_seed_parts()
        self.parts_library = seed_parts

    # ── Registry helpers ──────────────────────────────────────────────────────

    def add_local_sequence(self, seq: mRNASequence) -> None:
        """Add or replace a sequence in the local registry."""
        existing = [s for s in self.registry_local if s.id != seq.id]
        self.registry_local = existing + [seq]

    def remove_local_sequence(self, seq_id: str) -> None:
        self.registry_local = [s for s in self.registry_local if s.id != seq_id]

    def add_db_sequences(self, db_name: str, sequences: List[mRNASequence]) -> None:
        """Add (or replace) the sequence list for a database connection."""
        updated = dict(self.registry_db)
        updated[db_name] = sequences
        self.registry_db = updated

    def all_sequences(self) -> List[mRNASequence]:
        """Flat list of all sequences: local + all DB imports."""
        result = list(self.registry_local)
        for seqs in self.registry_db.values():
            result.extend(seqs)
        return result

    def get_sequence(self, seq_id: str) -> Optional[mRNASequence]:
        return next((s for s in self.all_sequences() if s.id == seq_id), None)

    # ── Database connection helpers ───────────────────────────────────────────

    def register_db_connection(
        self,
        connector: DatabaseConnector,
        mapper: SchemaMapper,
    ) -> None:
        conns = dict(self.db_connections)
        conns[connector.name] = connector
        self.db_connections = conns

        mappers = dict(self.db_mappers)
        mappers[connector.name] = mapper
        self.db_mappers = mappers

    def remove_db_connection(self, name: str) -> None:
        if name in self.db_connections:
            self.db_connections[name].disconnect()
        conns = {k: v for k, v in self.db_connections.items() if k != name}
        mappers = {k: v for k, v in self.db_mappers.items() if k != name}
        db_reg = {k: v for k, v in self.registry_db.items() if k != name}
        self.db_connections = conns
        self.db_mappers = mappers
        self.registry_db = db_reg

    # ── Parts library helpers ─────────────────────────────────────────────────

    def add_part(self, part: SequencePart, allow_duplicates: bool = False) -> bool:
        """
        Add a part to the library. Returns True if added, False if duplicate.

        By default, deduplicates by sequence hash to avoid storing identical parts.
        """
        if not allow_duplicates:
            existing_hashes = {p.sequence_hash for p in self.parts_library}
            if part.sequence_hash in existing_hashes:
                return False

        updated = list(self.parts_library)
        updated.append(part)
        self.parts_library = updated
        return True

    def add_parts_batch(self, parts: List[SequencePart]) -> int:
        """
        Add multiple parts in a single operation (one param trigger).
        Deduplicates against existing library and within the batch.
        Returns the number of parts actually added.
        """
        existing_hashes = {p.sequence_hash for p in self.parts_library}
        new_parts = []
        for part in parts:
            if part.sequence_hash not in existing_hashes:
                existing_hashes.add(part.sequence_hash)
                new_parts.append(part)
        if new_parts:
            self.parts_library = list(self.parts_library) + new_parts
        return len(new_parts)

    def extract_parts_from_sequence(self, seq: mRNASequence, source: str = "extracted") -> int:
        """
        Extract all available components from an mRNASequence and add to parts library.
        Returns the number of parts extracted.
        """
        from core.models.parts import create_part_from_component

        candidates = []
        component_map = [
            (seq.five_prime_utr, "5_utr", "5UTR"),
            (seq.kozak, "kozak", "Kozak"),
            (seq.cds, "cds", "CDS"),
            (seq.three_prime_utr, "3_utr", "3UTR"),
            (seq.poly_a, "polya", "PolyA"),
        ]
        for value, part_type, suffix in component_map:
            if value:
                candidates.append(create_part_from_component(
                    sequence=value,
                    part_type=part_type,
                    name=f"{seq.name}_{suffix}",
                    source=source,
                    origin_sequence_id=seq.id,
                ))

        return self.add_parts_batch(candidates)

    def parts_by_type(self, part_type: str) -> List[SequencePart]:
        """Return all parts of a given type."""
        return [p for p in self.parts_library if p.part_type == part_type]

    # ── Status helpers ────────────────────────────────────────────────────────

    def set_status(self, message: str, level: str = "success") -> None:
        """Show a toast notification. level: 'success', 'info', 'warning', 'error'."""
        import panel as pn
        try:
            notif = pn.state.notifications
            getattr(notif, level, notif.info)(message, duration=4000)
        except Exception:
            # Fallback if notifications not available (e.g., in tests)
            logger.info("Status: %s", message)
