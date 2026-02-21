"""Tests for the sequence analysis core."""
import math
import pytest

from core.analysis.gc_content import gc_percent, gc_sliding_window, gc_by_codon_position
from core.analysis.cai import calculate_cai, codon_usage_report
from core.analysis.homopolymers import detect_homopolymers
from core.analysis.restriction_sites import scan_restriction_sites, sites_present
from core.analysis.kozak import check_kozak, find_all_kozak_contexts


# ── GC content ────────────────────────────────────────────────────────────────

class TestGCContent:
    def test_pure_gc(self):
        assert gc_percent("GCGCGC") == pytest.approx(100.0)

    def test_pure_at(self):
        assert gc_percent("ATATAT") == pytest.approx(0.0)

    def test_fifty_percent(self):
        assert gc_percent("ATGC") == pytest.approx(50.0)

    def test_empty_sequence(self):
        assert gc_percent("") == 0.0

    def test_sliding_window_shape(self):
        seq = "ATGC" * 50  # 200 nt
        positions, values = gc_sliding_window(seq, window=100, step=1)
        assert len(positions) == len(values)
        assert len(positions) == 200 - 100 + 1  # 101 windows

    def test_sliding_window_all_gc(self):
        seq = "GC" * 100
        _, values = gc_sliding_window(seq, window=50, step=10)
        assert all(v == pytest.approx(100.0) for v in values)

    def test_gc_by_codon_position(self):
        # ATG CCC TAA — G at pos 1,3 of ATG; C at pos 1,2,3 of CCC; A at all in TAA
        cds = "ATGCCCTAA"
        result = gc_by_codon_position(cds)
        assert "GC1" in result
        assert "GC2" in result
        assert "GC3" in result

    def test_gc_by_codon_not_divisible(self):
        with pytest.raises(ValueError):
            gc_by_codon_position("ATGC")


# ── CAI ───────────────────────────────────────────────────────────────────────

class TestCAI:
    # Perfect human-optimized sequence uses the best codon at every position
    # ATG (Met=1.0) + TTC (Phe=1.0) + CTG (Leu=1.0) + TAA (stop, skipped)
    _GOOD_CDS = "ATGTTCCTGTAA"

    def test_cai_range(self):
        cai = calculate_cai(self._GOOD_CDS, organism="human")
        assert 0.0 <= cai <= 1.0

    def test_cai_ecoli(self):
        cai = calculate_cai(self._GOOD_CDS, organism="ecoli")
        assert 0.0 <= cai <= 1.0

    def test_cai_unknown_organism(self):
        with pytest.raises(ValueError):
            calculate_cai(self._GOOD_CDS, organism="martian")

    def test_cai_non_divisible(self):
        with pytest.raises(ValueError):
            calculate_cai("ATGTTCA", organism="human")  # 7 nt — not divisible by 3

    def test_codon_usage_report(self):
        usage = codon_usage_report("ATGTTCCTG")
        assert usage["ATG"] == 1
        assert usage["TTC"] == 1
        assert usage["CTG"] == 1


# ── Homopolymers ──────────────────────────────────────────────────────────────

class TestHomopolymers:
    def test_detect_poly_a(self):
        seq = "ATGCAAAAAATGC"  # AAAAAA = 6 As at positions 4-9
        runs = detect_homopolymers(seq, min_run=5)
        assert len(runs) == 1
        assert runs[0].nucleotide == "A"
        assert runs[0].length == 6

    def test_below_threshold(self):
        seq = "ATGCAAAATGC"  # only 4 As
        runs = detect_homopolymers(seq, min_run=5)
        assert len(runs) == 0

    def test_multiple_runs(self):
        seq = "AAAAAGGGGG"
        runs = detect_homopolymers(seq, min_run=5)
        assert len(runs) == 2
        nucls = {r.nucleotide for r in runs}
        assert nucls == {"A", "G"}

    def test_empty_sequence(self):
        assert detect_homopolymers("", min_run=5) == []


# ── Restriction sites ─────────────────────────────────────────────────────────

class TestRestrictionSites:
    def test_ecori_present(self):
        seq = "NNNNGAATTCNNNN"  # EcoRI site
        hits = scan_restriction_sites(seq, ["EcoRI"])
        assert "EcoRI" in hits
        assert any(h.strand == "+" for h in hits["EcoRI"])

    def test_site_absent(self):
        seq = "ATGCATGCATGC"
        hits = scan_restriction_sites(seq, ["EcoRI"])
        assert "EcoRI" not in hits

    def test_reverse_complement(self):
        # EcoRI on RC strand: GAATTC RC = GAATTC (palindrome)
        seq = "NNNNGAATTCNNNN"
        hits = scan_restriction_sites(seq, ["EcoRI"])
        assert "EcoRI" in hits

    def test_sites_present_list(self):
        seq = "GAATTCGGATCC"  # EcoRI + BamHI
        present = sites_present(seq, ["EcoRI", "BamHI", "NotI"])
        assert "EcoRI" in present
        assert "BamHI" in present
        assert "NotI" not in present


# ── Kozak ─────────────────────────────────────────────────────────────────────

class TestKozak:
    def test_strong_kozak(self):
        # Ideal context: GCC ACC ATG G
        seq = "NNNNGCCACCATGGCCC"
        result = check_kozak(seq)
        assert result.strength in ("strong", "adequate")
        assert result.has_optimal_r3  # A at -3

    def test_no_atg(self):
        with pytest.raises(ValueError):
            check_kozak("GCGCGCGCGC")

    def test_score_range(self):
        seq = "ATGCCCATG"
        result = check_kozak(seq)
        assert 0.0 <= result.score <= 1.0

    def test_find_all_kozak(self):
        seq = "ATGNNATGATGN"
        results = find_all_kozak_contexts(seq)
        assert len(results) == 3  # three ATGs
