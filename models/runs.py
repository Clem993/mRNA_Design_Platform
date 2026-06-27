"""
Model run / experiment tracking.

A lightweight MLOps layer: every time a scoring model is run against a worklist
we record a ``ModelRun`` (model name + version, timestamp, score statistics, and
per-sequence scores). ``RunHistory`` stores them and can compare two runs — e.g.
two versions of the same model — to show how scores shifted.

Pure-Python (uses only the stdlib ``statistics`` module).
"""
from __future__ import annotations

import math
import statistics
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ModelRun:
    """A single scoring run over a set of sequences."""
    model_name: str
    model_version: str
    model_source: str
    worklist_name: str
    n_sequences: int
    score_min: float
    score_max: float
    score_mean: float
    score_std: float
    timestamp: str                         # ISO-8601
    run_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    notes: str = ""
    scores: Dict[str, float] = field(default_factory=dict)  # seq_id -> score

    @property
    def label(self) -> str:
        return f"{self.model_name} v{self.model_version} · {self.timestamp}"


def summarize_run(
    model_name: str,
    model_version: str,
    model_source: str,
    worklist_name: str,
    scores: Dict[str, float],
    timestamp: str,
    notes: str = "",
) -> ModelRun:
    """Build a ModelRun from a {seq_id: score} mapping (ignoring NaNs in stats)."""
    valid = [v for v in scores.values() if v is not None and not math.isnan(v)]
    n = len(valid)
    smin = min(valid) if valid else float("nan")
    smax = max(valid) if valid else float("nan")
    smean = statistics.fmean(valid) if valid else float("nan")
    sstd = statistics.pstdev(valid) if len(valid) > 1 else 0.0
    return ModelRun(
        model_name=model_name, model_version=model_version,
        model_source=model_source, worklist_name=worklist_name,
        n_sequences=n, score_min=smin, score_max=smax,
        score_mean=smean, score_std=sstd, timestamp=timestamp,
        notes=notes, scores=dict(scores),
    )


@dataclass
class RunComparison:
    """Per-sequence delta between two runs over their shared sequences."""
    run_a: ModelRun
    run_b: ModelRun
    shared_ids: List[str]
    deltas: Dict[str, float]               # seq_id -> (b - a)
    mean_delta: float
    n_improved: int                        # b > a
    n_worsened: int                        # b < a
    n_unchanged: int


class RunHistory:
    """Append-only store of ModelRun records."""

    def __init__(self) -> None:
        self.runs: List[ModelRun] = []

    def add(self, run: ModelRun) -> None:
        self.runs.append(run)

    def for_model(self, model_name: str) -> List[ModelRun]:
        return [r for r in self.runs if r.model_name == model_name]

    def model_names(self) -> List[str]:
        # preserve first-seen order
        seen: List[str] = []
        for r in self.runs:
            if r.model_name not in seen:
                seen.append(r.model_name)
        return seen

    @staticmethod
    def compare(run_a: ModelRun, run_b: ModelRun) -> RunComparison:
        shared = [sid for sid in run_a.scores if sid in run_b.scores]
        deltas: Dict[str, float] = {}
        improved = worsened = unchanged = 0
        for sid in shared:
            a, b = run_a.scores[sid], run_b.scores[sid]
            if a is None or b is None or math.isnan(a) or math.isnan(b):
                continue
            d = b - a
            deltas[sid] = d
            if d > 1e-9:
                improved += 1
            elif d < -1e-9:
                worsened += 1
            else:
                unchanged += 1
        mean_delta = statistics.fmean(deltas.values()) if deltas else 0.0
        return RunComparison(
            run_a=run_a, run_b=run_b, shared_ids=list(deltas.keys()),
            deltas=deltas, mean_delta=mean_delta,
            n_improved=improved, n_worsened=worsened, n_unchanged=unchanged,
        )
