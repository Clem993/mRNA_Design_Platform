"""Tests for the domain models and model plugin system."""
import pytest

from core.models.sequence import mRNASequence, SequenceAnnotation
from core.models.plasmid import PlasmidBackbone, AssembledPlasmid, PlasmidFeature
from core.models.worklist import Worklist, WorklistItem
from models.base import ScoringModel, GenerativeModel, ModelRegistry


# ── mRNASequence ──────────────────────────────────────────────────────────────

class TestMRNASequence:
    def _make_seq(self, **kwargs) -> mRNASequence:
        defaults = {"name": "test_seq", "source": "local"}
        return mRNASequence(**{**defaults, **kwargs})

    def test_assembled_from_components(self):
        seq = self._make_seq(
            five_prime_utr="CCCC",
            cds="ATGCCC",
            three_prime_utr="TTTT",
        )
        assert seq.assembled_sequence == "CCCCATGCCCTTTT"

    def test_assembled_from_full_mrna(self):
        seq = self._make_seq(full_mrna="ATGCCC")
        assert seq.assembled_sequence == "ATGCCC"

    def test_assembled_raises_when_empty(self):
        seq = self._make_seq()
        with pytest.raises(ValueError):
            _ = seq.assembled_sequence

    def test_has_components_true(self):
        seq = self._make_seq(cds="ATGCCC")
        assert seq.has_components is True

    def test_has_components_false(self):
        seq = self._make_seq(full_mrna="ATGCCC")
        assert seq.has_components is False

    def test_component_annotations(self):
        seq = self._make_seq(five_prime_utr="AAAA", cds="ATGCCC")
        anns = seq.component_annotations
        labels = [a.label for a in anns]
        assert "5'UTR" in labels
        assert "CDS" in labels

    def test_length(self):
        seq = self._make_seq(cds="ATGCCC")
        assert seq.length == 6

    def test_to_dict_roundtrip(self):
        seq = self._make_seq(cds="ATGCCC", five_prime_utr="AAAA")
        d = seq.to_dict()
        restored = mRNASequence.from_dict(d)
        assert restored.name == seq.name
        assert restored.cds == seq.cds
        assert restored.five_prime_utr == seq.five_prime_utr

    def test_with_cds(self):
        seq = self._make_seq(cds="ATGCCC", five_prime_utr="AAAA")
        new_seq = seq.with_cds("ATGTTT")
        assert new_seq.cds == "ATGTTT"
        assert new_seq.five_prime_utr == "AAAA"
        assert new_seq.id != seq.id  # new ID


# ── PlasmidBackbone ───────────────────────────────────────────────────────────

class TestPlasmidBackbone:
    def test_basic(self):
        bb = PlasmidBackbone(
            name="pUC19",
            sequence="ATGCATGC" * 100,
            cloning_sites=["EcoRI", "HindIII"],
        )
        assert bb.length == 800
        assert "EcoRI" in bb.cloning_sites

    def test_to_dict_roundtrip(self):
        bb = PlasmidBackbone(
            name="pUC19",
            sequence="ATGCATGC",
            features=[
                PlasmidFeature("lacZ", "other", 0, 8)
            ],
        )
        d = bb.to_dict()
        restored = PlasmidBackbone.from_dict(d)
        assert restored.name == bb.name
        assert len(restored.features) == 1


# ── Worklist ──────────────────────────────────────────────────────────────────

class TestWorklist:
    def _make_seq(self, name: str = "seq") -> mRNASequence:
        return mRNASequence(name=name, source="local", cds="ATGCCC")

    def test_add_and_count(self):
        wl = Worklist()
        wl.add(self._make_seq())
        assert wl.count == 1

    def test_add_many(self):
        wl = Worklist()
        seqs = [self._make_seq(f"seq_{i}") for i in range(5)]
        wl.add_many(seqs, origin="database_import")
        assert wl.count == 5

    def test_remove(self):
        wl = Worklist()
        item = wl.add(self._make_seq())
        assert wl.remove(item.id) is True
        assert wl.count == 0

    def test_remove_nonexistent(self):
        wl = Worklist()
        assert wl.remove("nonexistent") is False

    def test_by_origin(self):
        wl = Worklist()
        wl.add(self._make_seq("s1"), origin="database_import")
        wl.add(self._make_seq("s2"), origin="generated")
        assert len(wl.by_origin("database_import")) == 1
        assert len(wl.by_origin("generated")) == 1

    def test_scored_filter(self):
        wl = Worklist()
        item = wl.add(self._make_seq())
        item.scores["my_model"] = 0.85
        assert len(wl.scored("my_model")) == 1
        assert len(wl.scored("other_model")) == 0

    def test_clear(self):
        wl = Worklist()
        wl.add_many([self._make_seq(f"s{i}") for i in range(3)])
        wl.clear()
        assert wl.count == 0

    def test_sequences_property(self):
        wl = Worklist()
        seq = self._make_seq("my_seq")
        wl.add(seq)
        assert seq in wl.sequences


# ── ModelRegistry ─────────────────────────────────────────────────────────────

class DummyScorer(ScoringModel):
    @property
    def name(self) -> str:
        return "dummy_scorer"

    def score(self, sequence, metadata=None) -> float:
        return len(sequence.assembled_sequence) / 1000.0


class DummyGenerator(GenerativeModel):
    @property
    def name(self) -> str:
        return "dummy_gen"

    def generate(self, constraints, n=10, seed=None):
        return [
            mRNASequence(name=f"gen_{i}", source="local", cds="ATGCCC")
            for i in range(n)
        ]


class TestModelRegistry:
    def _registry(self) -> ModelRegistry:
        r = ModelRegistry()
        r._register(DummyScorer(), "scoring", "local", "")
        r._register(DummyGenerator(), "generative", "local", "")
        return r

    def test_scoring_models_list(self):
        r = self._registry()
        assert len(r.scoring_models) == 1
        assert r.scoring_models[0].model.name == "dummy_scorer"

    def test_generative_models_list(self):
        r = self._registry()
        assert len(r.generative_models) == 1

    def test_run_scoring_returns_dataframe(self):
        import pandas as pd
        r = self._registry()
        seqs = [mRNASequence(name="s1", source="local", cds="ATGCCC")]
        df = r.run_scoring("dummy_scorer", seqs)
        assert isinstance(df, pd.DataFrame)
        assert "score" in df.columns
        assert df.loc[0, "score"] == pytest.approx(6 / 1000.0)

    def test_run_generation(self):
        r = self._registry()
        results = r.run_generation("dummy_gen", constraints={}, n=5)
        assert len(results) == 5
        assert all(isinstance(s, mRNASequence) for s in results)

    def test_wrong_type_raises(self):
        r = self._registry()
        with pytest.raises(TypeError):
            r.run_scoring("dummy_gen", [])

    def test_unregister(self):
        r = self._registry()
        assert r.unregister("dummy_scorer") is True
        assert len(r.scoring_models) == 0

    def test_unregister_nonexistent(self):
        r = self._registry()
        assert r.unregister("nonexistent") is False


# ── Concrete Scoring Models ───────────────────────────────────────────────────

class TestRNAStructureMFEScorer:
    """Test RNAstructure MFE scorer."""

    def test_scorer_basic(self):
        from models.rna_structure_scorer import RNAStructureMFEScorer
        scorer = RNAStructureMFEScorer()

        seq = mRNASequence(
            name="test_seq",
            source="local",
            five_prime_utr="GTTGCTCCTTCGGGCCTGTGGCGGCT",
            kozak="GCCACCATG",
            cds="ATGGTGAGCAAGGGCGAGGAGCTGTTCACCGGG",
            three_prime_utr="TGCCTGCTGCCGAGCGCCTGCGCGCGCGCGAG",
            poly_a="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        )

        score = scorer.score(seq)
        assert 0 <= score <= 100
        assert isinstance(score, float)

    def test_scorer_metadata(self):
        from models.rna_structure_scorer import RNAStructureMFEScorer
        scorer = RNAStructureMFEScorer()

        assert scorer.name == "RNAstructure MFE"
        assert len(scorer.description) > 0
        assert scorer.version == "1.0"

    def test_batch_scoring(self):
        from models.rna_structure_scorer import RNAStructureMFEScorer
        scorer = RNAStructureMFEScorer()

        sequences = [
            mRNASequence(name=f"seq_{i}", source="local", cds="ATGGTGAGCAAGGGCGAGGAG" * 3)
            for i in range(3)
        ]

        scores = scorer.score_batch(sequences)
        assert len(scores) == 3
        assert all(0 <= s <= 100 for s in scores)


class TestmRNAStabilityScorer:
    """Test mRNA stability scorer."""

    def test_scorer_basic(self):
        from models.mrna_stability_scorer import mRNAStabilityScorer
        scorer = mRNAStabilityScorer(organism="human")

        seq = mRNASequence(
            name="test_seq",
            source="local",
            five_prime_utr="GTTGCTCCTTCGGGCCTGTGGCGGCT",
            kozak="GCCACCATGG",
            cds="ATGGTGAGCAAGGGCGAGGAGCTGTTCACCGGGGTGGTGCCCATCCTGGTCGAGCTGGACGGCGACGTAAACGGCCACAAGTTCAGCGTGTCCGGCGAGGGCGAGGGCGATGCCACCTACGGCAAGCTGACCCTGAAG",
            three_prime_utr="TGCCTGCTGCCGAGCGCCTGCGCGCGCGCGAG",
            poly_a="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        )

        score = scorer.score(seq)
        assert 0 <= score <= 100
        assert isinstance(score, float)
        assert 20 <= score <= 90  # Should get a reasonable score

    def test_scorer_metadata(self):
        from models.mrna_stability_scorer import mRNAStabilityScorer
        scorer = mRNAStabilityScorer()

        assert scorer.name == "mRNA Stability"
        assert "human" in scorer.description
        assert scorer.version == "1.0"

    def test_gc_content_component(self):
        from models.mrna_stability_scorer import mRNAStabilityScorer
        scorer = mRNAStabilityScorer()

        # Good GC content (~55% - 11G+C out of 20 nt)
        seq_good = mRNASequence(name="good", source="local", cds="GCGGCGGCGGCGGCGGCGGC")  # 100% GC
        gc_score = scorer._score_gc_content(seq_good)
        assert gc_score is not None
        # 100% GC should get a lower score (too high)

        # Optimal GC content (55%)
        seq_optimal = mRNASequence(name="optimal", source="local", cds="ATGCGCATGCGCATGCGCAT")  # 50% GC
        gc_score_optimal = scorer._score_gc_content(seq_optimal)
        assert gc_score_optimal is not None
        assert 90 <= gc_score_optimal <= 100  # Should be very good

        # Poor GC content (very low)
        seq_poor = mRNASequence(name="poor", source="local", cds="ATGAAAAAAAAAAAAAAAAATGA")
        gc_score_poor = scorer._score_gc_content(seq_poor)
        assert gc_score_poor is not None
        assert gc_score_poor < gc_score_optimal

    def test_homopolymer_component(self):
        from models.mrna_stability_scorer import mRNAStabilityScorer
        scorer = mRNAStabilityScorer()

        # No homopolymers
        seq_good = mRNASequence(name="good", source="local", cds="ATGGCGAGCAGCTGA")
        homopoly_score = scorer._score_homopolymers(seq_good)
        assert homopoly_score == 100.0

        # With long homopolymer run
        seq_bad = mRNASequence(name="bad", source="local", cds="ATGAAAAAAAAAGCGTGA")
        homopoly_score_bad = scorer._score_homopolymers(seq_bad)
        assert homopoly_score_bad < homopoly_score

    def test_kozak_component(self):
        from models.mrna_stability_scorer import mRNAStabilityScorer
        scorer = mRNAStabilityScorer()

        # Optimal Kozak (GCCACCATGG has G at -3 and G at +4)
        seq_good = mRNASequence(name="good", source="local", kozak="GCCACCATGG")
        kozak_score = scorer._score_kozak(seq_good)
        assert kozak_score is not None
        assert kozak_score >= 70  # Should get 80 (40+40+0 for no ATG match bonus)

        # Poor Kozak
        seq_poor = mRNASequence(name="poor", source="local", kozak="ATTATG")
        kozak_score_poor = scorer._score_kozak(seq_poor)
        assert kozak_score_poor is not None
        assert kozak_score_poor < kozak_score
