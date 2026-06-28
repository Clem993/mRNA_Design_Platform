"""Tests for candidate objective scoring."""
from types import SimpleNamespace

import pytest

from core.analysis.candidate_score import score_objectives, OBJECTIVE_WEIGHTS


def _report(cai=0.8, kozak="strong", gc=55.0, u_pct=20.0, stretches=0,
            enzymes=None, flags=None, structure_stub=True):
    return SimpleNamespace(
        cai=cai,
        kozak=SimpleNamespace(strength=kozak) if kozak else None,
        gc_percent_global=gc,
        uridine=SimpleNamespace(u_percent=u_pct, high_u_stretches=[(0, 1, 1)] * stretches),
        restriction_enzymes_present=enzymes or [],
        structure=SimpleNamespace(is_stub=structure_stub, mfe=0.0, sequence=""),
        liability=SimpleNamespace(flags=flags or []),
    )


def _flag(category, severity):
    return SimpleNamespace(category=category, severity=severity)


class TestObjectiveScores:
    def test_ideal_candidate_scores_high(self):
        s = score_objectives(_report())
        assert s.expression > 80
        assert s.immunogenicity > 90      # low uridine
        assert s.manufacturability == 100  # no liabilities
        assert s.overall > 80

    def test_weights_sum_to_one(self):
        assert abs(sum(OBJECTIVE_WEIGHTS.values()) - 1.0) < 1e-9

    def test_overall_is_weighted_mean(self):
        s = score_objectives(_report())
        expected = (
            OBJECTIVE_WEIGHTS["expression"] * s.expression
            + OBJECTIVE_WEIGHTS["stability"] * s.stability
            + OBJECTIVE_WEIGHTS["immunogenicity"] * s.immunogenicity
            + OBJECTIVE_WEIGHTS["manufacturability"] * s.manufacturability
        )
        assert s.overall == pytest.approx(expected, abs=0.5)

    def test_low_cai_and_weak_kozak_drop_expression(self):
        hi = score_objectives(_report(cai=0.9, kozak="strong"))
        lo = score_objectives(_report(cai=0.3, kozak="weak"))
        assert lo.expression < hi.expression

    def test_high_uridine_lowers_immunogenicity_score(self):
        clean = score_objectives(_report(u_pct=18.0))
        hot = score_objectives(_report(u_pct=45.0, stretches=2))
        assert hot.immunogenicity < clean.immunogenicity

    def test_restriction_sites_lower_manufacturability(self):
        s = score_objectives(_report(enzymes=["EcoRI", "BamHI"]))
        assert s.manufacturability < 100

    def test_homopolymer_flag_hits_stability_and_manufacturability(self):
        s = score_objectives(_report(flags=[_flag("Homopolymer", "critical")]))
        clean = score_objectives(_report())
        assert s.stability < clean.stability
        assert s.manufacturability < clean.manufacturability

    def test_missing_metrics_are_neutral_not_zero(self):
        s = score_objectives(SimpleNamespace())  # empty report
        for v in (s.expression, s.stability, s.immunogenicity, s.manufacturability):
            assert 0 < v <= 100

    def test_scores_bounded_0_100(self):
        s = score_objectives(_report(cai=0.0, kozak="weak", gc=10.0, u_pct=90.0,
                                     stretches=10, enzymes=["A", "B", "C", "D"],
                                     flags=[_flag("Homopolymer", "critical"),
                                            _flag("GC", "critical"), _flag("Motif", "warning")]))
        for v in (s.expression, s.stability, s.immunogenicity, s.manufacturability, s.overall):
            assert 0 <= v <= 100
