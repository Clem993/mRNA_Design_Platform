"""Tests for model run / experiment tracking."""
import math

from models.runs import summarize_run, RunHistory


def _run(name, version, scores, ts="2026-01-01 00:00:00"):
    return summarize_run(
        model_name=name, model_version=version, model_source="local",
        worklist_name="wl", scores=scores, timestamp=ts,
    )


class TestSummarize:
    def test_basic_stats(self):
        r = _run("m", "1.0", {"a": 1.0, "b": 3.0, "c": 5.0})
        assert r.n_sequences == 3
        assert r.score_min == 1.0 and r.score_max == 5.0
        assert r.score_mean == 3.0
        assert r.score_std > 0

    def test_nan_scores_excluded(self):
        r = _run("m", "1.0", {"a": 2.0, "b": float("nan")})
        assert r.n_sequences == 1
        assert r.score_mean == 2.0

    def test_empty_scores_safe(self):
        r = _run("m", "1.0", {})
        assert r.n_sequences == 0
        assert math.isnan(r.score_mean)

    def test_label(self):
        r = _run("MyModel", "2.1", {"a": 1.0})
        assert "MyModel" in r.label and "2.1" in r.label


class TestRunHistory:
    def test_add_and_for_model(self):
        h = RunHistory()
        h.add(_run("A", "1.0", {"x": 1.0}))
        h.add(_run("B", "1.0", {"x": 2.0}))
        h.add(_run("A", "2.0", {"x": 3.0}))
        assert len(h.runs) == 3
        assert len(h.for_model("A")) == 2
        assert h.model_names() == ["A", "B"]

    def test_compare_deltas(self):
        a = _run("A", "1.0", {"s1": 1.0, "s2": 2.0, "s3": 5.0})
        b = _run("A", "2.0", {"s1": 2.0, "s2": 2.0, "s3": 4.0})  # +1, 0, -1
        cmp = RunHistory.compare(a, b)
        assert cmp.n_improved == 1
        assert cmp.n_worsened == 1
        assert cmp.n_unchanged == 1
        assert cmp.mean_delta == 0.0
        assert set(cmp.shared_ids) == {"s1", "s2", "s3"}

    def test_compare_only_shared_sequences(self):
        a = _run("A", "1.0", {"s1": 1.0, "only_a": 9.0})
        b = _run("A", "2.0", {"s1": 2.0, "only_b": 8.0})
        cmp = RunHistory.compare(a, b)
        assert cmp.shared_ids == ["s1"]
        assert cmp.deltas["s1"] == 1.0
