"""Tests for codon-optimization analysis."""
import pytest

from core.analysis.codon_analysis import (
    resolve_organism, per_codon_optimality, min_max_profile, analyze_codons,
    RARE_THRESHOLD,
)

# Human top-synonym codons (relative adaptiveness 1.00)
OPTIMAL = "ATG" + "CTG" + "ATC" + "GTG" + "GCC" + "ACC"   # M L I V A T, all = 1.00
# Rare Leu codon TTA = 0.07 in the human table
RARE = "ATG" + "TTA" * 6                                   # M then 6 rare Leu


class TestResolveOrganism:
    def test_human_default(self):
        assert resolve_organism(None) == "human"
        assert resolve_organism("Human") == "human"

    def test_ecoli_variants(self):
        assert resolve_organism("E. coli") == "ecoli"
        assert resolve_organism("ecoli") == "ecoli"

    def test_unknown_falls_back_to_human(self):
        assert resolve_organism("martian") == "human"


class TestOptimality:
    def test_optimal_codons_score_one(self):
        opt = per_codon_optimality(OPTIMAL, "human")
        assert len(opt) == 6
        assert all(w == pytest.approx(1.0) for w in opt)

    def test_rare_codon_below_threshold(self):
        opt = per_codon_optimality(RARE, "human")
        # first is ATG (1.0), rest are rare Leu
        assert opt[0] == pytest.approx(1.0)
        assert all(w < RARE_THRESHOLD for w in opt[1:])

    def test_stop_codons_excluded(self):
        opt = per_codon_optimality("ATG" + "TAA", "human")  # M + stop
        assert len(opt) == 1


class TestMinMax:
    def test_short_sequence_returns_empty(self):
        pos, vals = min_max_profile("ATGCTGATC", "human", window=17)
        assert pos == [] and vals == []

    def test_optimal_run_is_positive(self):
        pos, vals = min_max_profile(OPTIMAL * 5, "human", window=10)
        assert vals and all(v > 0 for v in vals)

    def test_rare_run_is_negative(self):
        pos, vals = min_max_profile(RARE * 4, "human", window=10)
        assert vals and min(vals) < 0


class TestAnalyzeCodons:
    def test_counts_and_cai(self):
        a = analyze_codons(OPTIMAL, "human", include_optimized=False)
        assert a.n_codons == 6
        assert a.rare_count == 0
        assert a.cai is not None and a.cai > 0.9

    def test_rare_clusters_detected(self):
        a = analyze_codons(RARE, "human", include_optimized=False)
        assert a.rare_count == 6
        assert a.rare_clusters and a.rare_clusters[0] == (1, 6)

    def test_optimization_improves_rare_heavy_cds(self):
        a = analyze_codons(RARE, "human", include_optimized=True)
        assert a.optimized_cai is not None
        assert a.optimized_cai >= (a.cai or 0)
        assert a.optimized_rare_count is not None
        assert a.optimized_rare_count <= a.rare_count
