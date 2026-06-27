"""Tests for sequence-liability motif scanning and the liability aggregator."""
from types import SimpleNamespace

import pytest

from core.analysis.motifs import scan_motifs
from core.analysis.liability import assess_liabilities, CRITICAL, WARNING


# ── Motif scanning ──────────────────────────────────────────────────────────

class TestMotifs:
    def test_uorf_in_5utr(self):
        hits = scan_motifs(five_prime_utr="GGGCATGGGG", cds="ATGAAATAA", three_prime_utr="")
        names = [h.name for h in hits]
        assert "uorf" in names
        uorf = next(h for h in hits if h.name == "uorf")
        assert uorf.region == "5'UTR"
        assert uorf.severity == WARNING

    def test_premature_polya_in_cds_is_critical(self):
        hits = scan_motifs(cds="ATGAATAAACCCTAA")
        prem = [h for h in hits if h.name == "premature_polya"]
        assert prem and prem[0].severity == CRITICAL
        assert prem[0].region == "CDS"

    def test_are_in_3utr(self):
        hits = scan_motifs(three_prime_utr="GGATTTAGG")
        are = [h for h in hits if h.name == "are"]
        assert are and are[0].region == "3'UTR"

    def test_splice_donor_detected_in_full(self):
        hits = scan_motifs(full_seq="CCCGTAAGTCCC")
        assert any(h.name == "splice_donor" for h in hits)

    def test_clean_sequence_has_no_motifs(self):
        # CDS with no AATAAA/ATTAAA, UTRs without ATG/ATTTA, no GT[AG]AGT
        hits = scan_motifs(
            five_prime_utr="CCGCCGCCGCC",
            cds="ATGGGCGGCGGCTAA",
            three_prime_utr="CCGCCGCCG",
        )
        assert hits == []

    def test_uridine_input_is_normalised(self):
        # RNA alphabet (U) should be treated like T
        hits = scan_motifs(three_prime_utr="GGAUUUAGG")
        assert any(h.name == "are" for h in hits)


# ── Liability aggregation ───────────────────────────────────────────────────

def _clean_report():
    return SimpleNamespace(
        gc_percent_global=52.0,
        restriction_enzymes_present=[],
        uridine=SimpleNamespace(u_percent=22.0, high_u_stretches=[]),
        has_start_codon=True, has_stop_codon=True, in_frame=True,
        kozak=SimpleNamespace(strength="strong", score=0.9),
        structure=SimpleNamespace(is_stub=True, mfe=0.0, sequence=""),
        motif_hits=[],
    )


def _clean_seq():
    return SimpleNamespace(
        five_prime_utr="CCGCCACC", kozak=None,
        cds="ATGGGCGGCGGCTAA", three_prime_utr="CCGCCG",
        poly_a="A" * 120,
    )


class TestLiability:
    def test_clean_sequence_passes(self):
        rep = assess_liabilities(_clean_report(), _clean_seq())
        assert rep.verdict == "pass"
        assert rep.score == 100
        assert rep.n_critical == 0 and rep.flag_count == 0

    def test_polya_tail_not_flagged_as_homopolymer(self):
        # body has no long run; the 120-A tail must be ignored
        rep = assess_liabilities(_clean_report(), _clean_seq())
        assert not any(f.category == "Homopolymer" for f in rep.flags)

    def test_body_homopolymer_flagged(self):
        seq = _clean_seq()
        seq.cds = "ATG" + "A" * 16 + "GGCTAA"   # 16-A run in the body
        rep = assess_liabilities(_clean_report(), seq)
        hp = [f for f in rep.flags if f.category == "Homopolymer"]
        assert hp and hp[0].severity == CRITICAL

    def test_extreme_gc_is_critical(self):
        rep_dict = _clean_report()
        rep_dict.gc_percent_global = 25.0
        rep = assess_liabilities(rep_dict, _clean_seq())
        assert any(f.category == "GC" and f.severity == CRITICAL for f in rep.flags)

    def test_restriction_and_uridine_are_warnings(self):
        r = _clean_report()
        r.restriction_enzymes_present = ["EcoRI", "BamHI"]
        r.uridine = SimpleNamespace(u_percent=46.0, high_u_stretches=[(1, 51, 50)])
        rep = assess_liabilities(r, _clean_seq())
        cats = {f.category for f in rep.flags}
        assert "Restriction" in cats and "Uridine" in cats
        assert rep.verdict == "review"

    def test_missing_start_codon_fails(self):
        r = _clean_report()
        r.has_start_codon = False
        rep = assess_liabilities(r, _clean_seq())
        assert rep.verdict == "fail"
        assert any(f.category == "CDS" and f.severity == CRITICAL for f in rep.flags)

    def test_score_decreases_with_severity(self):
        r = _clean_report()
        r.has_start_codon = False            # critical (-25)
        r.restriction_enzymes_present = ["EcoRI"]  # warning (-10)
        rep = assess_liabilities(r, _clean_seq())
        assert rep.score <= 65
        assert rep.verdict == "fail"

    def test_motif_hits_become_flags(self):
        r = _clean_report()
        r.motif_hits = scan_motifs(cds="ATGAATAAACCCTAA")  # premature polyA (critical)
        rep = assess_liabilities(r, _clean_seq())
        assert any(f.category == "Motif" and f.severity == CRITICAL for f in rep.flags)
        assert rep.verdict == "fail"
