"""
SequenceAnalyzer — main analysis entry point.

Runs all analysis modules against an mRNASequence and returns a
structured AnalysisReport. Results are cached on the sequence object
so repeated calls are cheap.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

from core.models.sequence import mRNASequence
from core.analysis.gc_content import (
    gc_percent,
    gc_sliding_window,
    gc_by_codon_position,
)
from core.analysis.cai import calculate_cai, codon_usage_report, CODON_TABLES
from core.analysis.homopolymers import detect_homopolymers, HomopolymerRun
from core.analysis.restriction_sites import (
    scan_restriction_sites,
    RestrictionSiteHit,
    COMMON_ENZYMES,
)
from core.analysis.kozak import check_kozak, KozakResult
from core.analysis.structure import predict_structure, StructureResult
from core.analysis.uridine import analyze_uridine, UridineReport
from core.analysis.motifs import scan_motifs, MotifHit
from core.analysis.liability import assess_liabilities, LiabilityReport


@dataclass
class AnalysisReport:
    """All analysis results for a single mRNASequence."""
    sequence_id: str
    sequence_name: str
    sequence_length: int

    # GC content
    gc_percent_global: float = 0.0
    gc_sliding_positions: Optional[np.ndarray] = None  # centre positions
    gc_sliding_values: Optional[np.ndarray] = None     # GC% per window
    gc_by_codon_position: Optional[Dict[str, float]] = None

    # Codon Adaptation Index
    cai: Optional[float] = None
    cai_organism: Optional[str] = None
    codon_usage: Optional[Dict[str, int]] = None

    # Homopolymers
    homopolymer_runs: List[HomopolymerRun] = field(default_factory=list)
    homopolymer_count: int = 0
    longest_homopolymer: int = 0

    # Restriction sites
    restriction_hits: Dict[str, List[RestrictionSiteHit]] = field(default_factory=dict)
    restriction_enzymes_present: List[str] = field(default_factory=list)

    # Start / stop codon validation
    has_start_codon: Optional[bool] = None
    has_stop_codon: Optional[bool] = None
    stop_codon: Optional[str] = None
    in_frame: Optional[bool] = None

    # Kozak context
    kozak: Optional[KozakResult] = None

    # Secondary structure (ViennaRNA)
    structure: Optional[StructureResult] = None

    # Uridine content (immunogenicity proxy)
    uridine: Optional[UridineReport] = None

    # Sequence-liability motifs (uORF, premature polyA, ARE, splice donor)
    motif_hits: List[MotifHit] = field(default_factory=list)

    # Aggregated liability / QC assessment
    liability: Optional[LiabilityReport] = None

    # Errors / warnings generated during analysis
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sequence_id": self.sequence_id,
            "sequence_name": self.sequence_name,
            "sequence_length": self.sequence_length,
            "gc_content": self.gc_percent_global,
            "gc_percent_global": self.gc_percent_global,
            "gc_by_codon_position": self.gc_by_codon_position,
            "cai": self.cai,
            "cai_organism": self.cai_organism,
            "homopolymer_count": self.homopolymer_count,
            "longest_homopolymer": self.longest_homopolymer,
            "restriction_site_count": len(self.restriction_enzymes_present),
            "restriction_enzymes_present": self.restriction_enzymes_present,
            "has_start_codon": self.has_start_codon,
            "has_stop_codon": self.has_stop_codon,
            "stop_codon": self.stop_codon,
            "in_frame": self.in_frame,
            "kozak_score": self.kozak.score if self.kozak else None,
            "kozak_strength": self.kozak.strength if self.kozak else None,
            "mfe": self.structure.mfe if self.structure else None,
            "uridine_percent": self.uridine.u_percent if self.uridine else None,
            "liability_score": self.liability.score if self.liability else None,
            "liability_verdict": self.liability.verdict if self.liability else None,
            "liability_critical": self.liability.n_critical if self.liability else None,
            "liability_warning": self.liability.n_warning if self.liability else None,
            "liability_flag_count": self.liability.flag_count if self.liability else None,
            "warnings": self.warnings,
        }


class SequenceAnalyzer:
    """
    Runs analysis modules against mRNASequence objects.

    Results are cached inside the sequence's _analysis_cache dict
    (keyed by analysis type) so re-running is a cache lookup.
    """

    def __init__(
        self,
        gc_window: int = 100,
        gc_step: int = 1,
        homopolymer_min_run: int = 5,
        restriction_enzymes: Optional[List[str]] = None,
        cai_organism: str = "human",
        cai_custom_table: Optional[Dict[str, float]] = None,
    ) -> None:
        self.gc_window = gc_window
        self.gc_step = gc_step
        self.homopolymer_min_run = homopolymer_min_run
        self.restriction_enzymes = restriction_enzymes or list(COMMON_ENZYMES.keys())
        self.cai_organism = cai_organism
        self.cai_custom_table = cai_custom_table

    # ── Individual analysis methods ─────────────────────────────────────────

    def analyze_gc(self, sequence: str) -> Dict[str, Any]:
        positions, values = gc_sliding_window(sequence, self.gc_window, self.gc_step)
        return {
            "gc_percent_global": gc_percent(sequence),
            "gc_sliding_positions": positions,
            "gc_sliding_values": values,
        }

    def analyze_cai(self, cds: str) -> Dict[str, Any]:
        try:
            cai_value = calculate_cai(cds, self.cai_organism, self.cai_custom_table)
            usage = codon_usage_report(cds)
            return {
                "cai": cai_value,
                "cai_organism": self.cai_custom_table and "custom" or self.cai_organism,
                "codon_usage": usage,
            }
        except Exception as e:
            return {"cai": None, "cai_organism": None, "codon_usage": None, "error": str(e)}

    def analyze_homopolymers(self, sequence: str) -> Dict[str, Any]:
        runs = detect_homopolymers(sequence, self.homopolymer_min_run)
        return {
            "homopolymer_runs": runs,
            "homopolymer_count": len(runs),
            "longest_homopolymer": max((r.length for r in runs), default=0),
        }

    def analyze_restriction_sites(self, sequence: str) -> Dict[str, Any]:
        hits = scan_restriction_sites(sequence, self.restriction_enzymes)
        return {
            "restriction_hits": hits,
            "restriction_enzymes_present": list(hits.keys()),
        }

    def validate_cds(self, cds: str) -> Dict[str, Any]:
        seq = cds.upper().replace("U", "T")
        start_codons = {"ATG"}
        stop_codons = {"TAA", "TAG", "TGA"}
        has_start = seq[:3] in start_codons if len(seq) >= 3 else False
        stop = seq[-3:] if len(seq) >= 3 else ""
        has_stop = stop in stop_codons
        in_frame = len(seq) % 3 == 0
        return {
            "has_start_codon": has_start,
            "has_stop_codon": has_stop,
            "stop_codon": stop if has_stop else None,
            "in_frame": in_frame,
        }

    def analyze_kozak(self, sequence: str) -> Dict[str, Any]:
        try:
            result = check_kozak(sequence)
            return {"kozak": result}
        except ValueError as e:
            return {"kozak": None, "kozak_warning": str(e)}

    def analyze_structure(self, sequence: str) -> Dict[str, Any]:
        result = predict_structure(sequence)
        return {"structure": result}

    # ── Full report ─────────────────────────────────────────────────────────

    def run_full_analysis(
        self,
        seq: mRNASequence,
        include_structure: bool = True,
        force_rerun: bool = False,
    ) -> AnalysisReport:
        """
        Run all analysis modules against seq and return an AnalysisReport.

        Results are cached in seq._analysis_cache. Set force_rerun=True
        to bypass the cache.
        """
        cache_key = "full_analysis"
        if not force_rerun and cache_key in seq._analysis_cache:
            return seq._analysis_cache[cache_key]  # type: ignore[return-value]

        full_seq = seq.assembled_sequence
        warnings: List[str] = []

        report = AnalysisReport(
            sequence_id=seq.id,
            sequence_name=seq.name,
            sequence_length=len(full_seq),
        )

        # GC content — run on full sequence
        gc_data = self.analyze_gc(full_seq)
        report.gc_percent_global = gc_data["gc_percent_global"]
        report.gc_sliding_positions = gc_data["gc_sliding_positions"]
        report.gc_sliding_values = gc_data["gc_sliding_values"]

        # GC by codon position — only if CDS available
        if seq.cds and len(seq.cds) % 3 == 0:
            try:
                report.gc_by_codon_position = gc_by_codon_position(seq.cds)
            except Exception as e:
                warnings.append(f"GC by codon position failed: {e}")

        # CAI — only on CDS
        if seq.cds:
            cai_data = self.analyze_cai(seq.cds)
            report.cai = cai_data.get("cai")
            report.cai_organism = cai_data.get("cai_organism")
            report.codon_usage = cai_data.get("codon_usage")
            if "error" in cai_data:
                warnings.append(f"CAI error: {cai_data['error']}")

            # CDS validation
            cds_data = self.validate_cds(seq.cds)
            report.has_start_codon = cds_data["has_start_codon"]
            report.has_stop_codon = cds_data["has_stop_codon"]
            report.stop_codon = cds_data["stop_codon"]
            report.in_frame = cds_data["in_frame"]

            if not report.has_start_codon:
                warnings.append("CDS does not begin with ATG.")
            if not report.has_stop_codon:
                warnings.append("CDS does not end with a stop codon.")
            if not report.in_frame:
                warnings.append("CDS length is not divisible by 3.")

        # Homopolymers — full assembled sequence
        hp_data = self.analyze_homopolymers(full_seq)
        report.homopolymer_runs = hp_data["homopolymer_runs"]
        report.homopolymer_count = hp_data["homopolymer_count"]
        report.longest_homopolymer = hp_data["longest_homopolymer"]

        # Restriction sites
        rs_data = self.analyze_restriction_sites(full_seq)
        report.restriction_hits = rs_data["restriction_hits"]
        report.restriction_enzymes_present = rs_data["restriction_enzymes_present"]

        # Kozak — try on kozak component, then fall back to full sequence
        kozak_seq = seq.kozak or full_seq
        kozak_data = self.analyze_kozak(kozak_seq)
        report.kozak = kozak_data.get("kozak")
        if "kozak_warning" in kozak_data:
            warnings.append(kozak_data["kozak_warning"])

        # Secondary structure
        if include_structure:
            struct_data = self.analyze_structure(full_seq)
            report.structure = struct_data["structure"]

        # Uridine content (immunogenicity proxy)
        report.uridine = analyze_uridine(full_seq)

        # Sequence-liability motifs (region-aware when components are available)
        report.motif_hits = scan_motifs(
            five_prime_utr=seq.five_prime_utr,
            cds=seq.cds,
            three_prime_utr=seq.three_prime_utr,
            full_seq=full_seq,
        )

        report.warnings = warnings

        # Aggregate everything into the liability / QC assessment
        report.liability = assess_liabilities(report, seq)

        # Cache result
        seq._analysis_cache[cache_key] = report
        return report
