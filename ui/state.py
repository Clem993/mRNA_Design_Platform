"""
Global application state using param.Parameterized.

All UI components depend on AppState parameters reactively. Because
Panel uses server-side state, each user session gets its own AppState
instance, cleanly separating in-progress local sequences from imported
database records.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import param

from core.models.sequence import mRNASequence
from core.models.plasmid import PlasmidBackbone
from core.models.worklist import Worklist
from core.models.parts import SequencePart
from core.database.base import DatabaseConnector, SchemaMapper
from models.base import ModelRegistry


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
    active_tab: str = param.String(default="worklist", doc="Active main panel tab")
    status_message: str = param.String(default="", doc="Status bar message")
    is_loading: bool = param.Boolean(default=False, doc="Global loading indicator")
    show_sequence_modal: bool = param.Boolean(default=False, doc="Show sequence inspection modal")
    show_db_import_modal: bool = param.Boolean(default=False, doc="Show database import modal")
    show_model_repo_modal: bool = param.Boolean(default=False, doc="Show model repository modal")
    show_analysis_settings_modal: bool = param.Boolean(default=False, doc="Show analysis settings modal")
    show_backbone_import_modal: bool = param.Boolean(default=False, doc="Show backbone import modal")

    def __init__(self, **params: Any) -> None:
        if "worklist" not in params:
            params["worklist"] = Worklist()
        if "model_registry" not in params:
            params["model_registry"] = ModelRegistry()
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
            # Check if this exact sequence already exists
            existing_hashes = {p.sequence_hash for p in self.parts_library}
            if part.sequence_hash in existing_hashes:
                return False

        updated = list(self.parts_library)
        updated.append(part)
        self.parts_library = updated
        return True

    def extract_parts_from_sequence(self, seq: mRNASequence, source: str = "extracted") -> int:
        """
        Extract all available components from an mRNASequence and add to parts library.
        Returns the number of parts extracted.
        """
        from core.models.parts import create_part_from_component

        extracted_count = 0

        if seq.five_prime_utr:
            part = create_part_from_component(
                sequence=seq.five_prime_utr,
                part_type="5_utr",
                name=f"{seq.name}_5UTR",
                source=source,
                origin_sequence_id=seq.id,
            )
            if self.add_part(part):
                extracted_count += 1

        if seq.kozak:
            part = create_part_from_component(
                sequence=seq.kozak,
                part_type="kozak",
                name=f"{seq.name}_Kozak",
                source=source,
                origin_sequence_id=seq.id,
            )
            if self.add_part(part):
                extracted_count += 1

        if seq.cds:
            part = create_part_from_component(
                sequence=seq.cds,
                part_type="cds",
                name=f"{seq.name}_CDS",
                source=source,
                origin_sequence_id=seq.id,
            )
            if self.add_part(part):
                extracted_count += 1

        if seq.three_prime_utr:
            part = create_part_from_component(
                sequence=seq.three_prime_utr,
                part_type="3_utr",
                name=f"{seq.name}_3UTR",
                source=source,
                origin_sequence_id=seq.id,
            )
            if self.add_part(part):
                extracted_count += 1

        if seq.poly_a:
            part = create_part_from_component(
                sequence=seq.poly_a,
                part_type="polya",
                name=f"{seq.name}_PolyA",
                source=source,
                origin_sequence_id=seq.id,
            )
            if self.add_part(part):
                extracted_count += 1

        return extracted_count

    def parts_by_type(self, part_type: str) -> List[SequencePart]:
        """Return all parts of a given type."""
        return [p for p in self.parts_library if p.part_type == part_type]

    # ── Status helpers ────────────────────────────────────────────────────────

    def set_status(self, message: str) -> None:
        self.status_message = message

    def clear_status(self) -> None:
        self.status_message = ""
