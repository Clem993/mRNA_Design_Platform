"""
Model plugin system.

Users can contribute two types of models:

1. ScoringModel  — scores an existing mRNASequence, returns a float.
2. GenerativeModel — generates new mRNASequences from constraints / seeds.

Models are loaded via ModelRegistry which supports:
  - Local Python module (path on disk or importable package)
  - Remote REST API endpoint (POST sequences → scores/generations)

The API adapter wraps HTTP calls behind the same interface so the UI
code never needs to know whether a model is local or remote.
"""
from __future__ import annotations

import importlib.util
import inspect
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type, Union

import pandas as pd

from core.models.sequence import mRNASequence


# ── Abstract base classes ────────────────────────────────────────────────────

class ScoringModel(ABC):
    """
    A model that assigns a numeric score to an mRNASequence.

    Implement name and score(). scores_batch() has a default list
    implementation but can be overridden for vectorised inference.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable model name shown in the UI."""
        ...

    @property
    def description(self) -> str:
        """Optional description for the UI."""
        return ""

    @property
    def version(self) -> str:
        return "1.0"

    @abstractmethod
    def score(self, sequence: mRNASequence, metadata: Optional[Dict[str, Any]] = None) -> float:
        """
        Score a single sequence.

        Parameters
        ----------
        sequence : mRNASequence
        metadata : dict, optional
            Raw database metadata attached to the sequence (raw_metadata).

        Returns
        -------
        float
            Score value. Convention: higher is better, but models may
            define their own scale — document it in description.
        """
        ...

    def score_batch(
        self,
        sequences: List[mRNASequence],
        metadata: Optional[List[Optional[Dict[str, Any]]]] = None,
    ) -> List[float]:
        """Score a list of sequences. Override for vectorised models."""
        metas = metadata or [None] * len(sequences)
        return [self.score(seq, meta) for seq, meta in zip(sequences, metas)]


class GenerativeModel(ABC):
    """
    A model that generates new mRNASequences from constraints or seed sequences.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    def description(self) -> str:
        return ""

    @property
    def version(self) -> str:
        return "1.0"

    @abstractmethod
    def generate(
        self,
        constraints: Dict[str, Any],
        n: int = 10,
        seed: Optional[mRNASequence] = None,
    ) -> List[mRNASequence]:
        """
        Generate n sequences from the given constraints.

        Parameters
        ----------
        constraints : dict
            Model-specific constraint dict (e.g. target GC, CAI, organism, etc.)
        n : int
            Number of sequences to generate.
        seed : mRNASequence, optional
            Seed sequence for mutation-based generators.

        Returns
        -------
        List[mRNASequence]
        """
        ...


ModelType = Union[ScoringModel, GenerativeModel]


# ── API Adapter ──────────────────────────────────────────────────────────────

class APIScoringModel(ScoringModel):
    """
    Wraps a remote REST API behind the ScoringModel interface.

    Expected API contract:
      POST {endpoint}/score
      Body: {"sequences": [{"id": ..., "sequence": ...}, ...]}
      Response: {"scores": [{"id": ..., "score": float}, ...]}
    """

    def __init__(
        self,
        endpoint: str,
        model_name: str,
        api_key: Optional[str] = None,
        description: str = "",
        version: str = "1.0",
        timeout: float = 30.0,
    ) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._name = model_name
        self._api_key = api_key
        self._description = description
        self._version = version
        self._timeout = timeout

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def version(self) -> str:
        return self._version

    def _headers(self) -> Dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self._api_key:
            h["Authorization"] = f"Bearer {self._api_key}"
        return h

    def score(self, sequence: mRNASequence, metadata: Optional[Dict[str, Any]] = None) -> float:
        results = self.score_batch([sequence], [metadata])
        return results[0]

    def score_batch(
        self,
        sequences: List[mRNASequence],
        metadata: Optional[List[Optional[Dict[str, Any]]]] = None,
    ) -> List[float]:
        import httpx

        payload = {
            "sequences": [
                {
                    "id": seq.id,
                    "name": seq.name,
                    "sequence": seq.assembled_sequence,
                    "metadata": (metadata[i] if metadata else None),
                }
                for i, seq in enumerate(sequences)
            ]
        }
        response = httpx.post(
            f"{self._endpoint}/score",
            json=payload,
            headers=self._headers(),
            timeout=self._timeout,
        )
        response.raise_for_status()
        data = response.json()
        score_map = {item["id"]: item["score"] for item in data["scores"]}
        return [score_map.get(seq.id, float("nan")) for seq in sequences]


class APIGenerativeModel(GenerativeModel):
    """
    Wraps a remote REST API behind the GenerativeModel interface.

    Expected API contract:
      POST {endpoint}/generate
      Body: {"constraints": {...}, "n": int, "seed_sequence": str | null}
      Response: {"sequences": [{"name": ..., "cds": ..., ...}, ...]}
    """

    def __init__(
        self,
        endpoint: str,
        model_name: str,
        api_key: Optional[str] = None,
        description: str = "",
        version: str = "1.0",
        timeout: float = 60.0,
    ) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._name = model_name
        self._api_key = api_key
        self._description = description
        self._version = version
        self._timeout = timeout

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def version(self) -> str:
        return self._version

    def _headers(self) -> Dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self._api_key:
            h["Authorization"] = f"Bearer {self._api_key}"
        return h

    def generate(
        self,
        constraints: Dict[str, Any],
        n: int = 10,
        seed: Optional[mRNASequence] = None,
    ) -> List[mRNASequence]:
        import httpx

        payload = {
            "constraints": constraints,
            "n": n,
            "seed_sequence": seed.assembled_sequence if seed else None,
        }
        response = httpx.post(
            f"{self._endpoint}/generate",
            json=payload,
            headers=self._headers(),
            timeout=self._timeout,
        )
        response.raise_for_status()
        data = response.json()
        return [mRNASequence.from_dict({**item, "source": "local"}) for item in data["sequences"]]


# ── Model Registry ───────────────────────────────────────────────────────────

@dataclass
class RegisteredModel:
    model: ModelType
    model_type: str       # "scoring" | "generative"
    source: str           # "local" | "api" | "builtin" | "catalog"
    source_path: str = "" # file path or endpoint URL
    repository: str = ""  # display provenance (e.g. "github.com/ViennaRNA")
    category: str = ""    # model category for display


class ModelRegistry:
    """
    Manages loaded scoring and generative models.

    Models are registered either by loading a local Python file/module
    or by configuring an API endpoint.
    """

    def __init__(self) -> None:
        self._models: Dict[str, RegisteredModel] = {}

    # ── Loading ──────────────────────────────────────────────────────────────

    def load_local(self, path: str) -> List[ModelType]:
        """
        Dynamically import a Python file and register all ScoringModel /
        GenerativeModel subclasses found in it.

        Returns the list of loaded model instances.
        """
        spec = importlib.util.spec_from_file_location("_user_model", path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load module from: {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore[union-attr]

        loaded: List[ModelType] = []
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if obj.__module__ != module.__name__:
                continue
            if issubclass(obj, ScoringModel) and obj is not ScoringModel:
                instance = obj()
                self._register(instance, "scoring", "local", path)
                loaded.append(instance)
            elif issubclass(obj, GenerativeModel) and obj is not GenerativeModel:
                instance = obj()
                self._register(instance, "generative", "local", path)
                loaded.append(instance)

        if not loaded:
            raise ValueError(
                f"No ScoringModel or GenerativeModel subclasses found in {path}."
            )
        return loaded

    def register_api_scorer(
        self,
        endpoint: str,
        model_name: str,
        api_key: Optional[str] = None,
        description: str = "",
    ) -> APIScoringModel:
        """Register a remote scoring API."""
        model = APIScoringModel(
            endpoint=endpoint,
            model_name=model_name,
            api_key=api_key,
            description=description,
        )
        self._register(model, "scoring", "api", endpoint)
        return model

    def register_api_generator(
        self,
        endpoint: str,
        model_name: str,
        api_key: Optional[str] = None,
        description: str = "",
    ) -> APIGenerativeModel:
        """Register a remote generative API."""
        model = APIGenerativeModel(
            endpoint=endpoint,
            model_name=model_name,
            api_key=api_key,
            description=description,
        )
        self._register(model, "generative", "api", endpoint)
        return model

    # ── Running ──────────────────────────────────────────────────────────────

    def run_scoring(
        self,
        model_name: str,
        sequences: List[mRNASequence],
    ) -> pd.DataFrame:
        """
        Run a scoring model against sequences and return a DataFrame.

        Columns: id, name, score
        """
        reg = self._get(model_name, "scoring")
        scorer: ScoringModel = reg.model  # type: ignore[assignment]
        scores = scorer.score_batch(sequences)
        return pd.DataFrame({
            "id": [s.id for s in sequences],
            "name": [s.name for s in sequences],
            "score": scores,
        })

    def run_generation(
        self,
        model_name: str,
        constraints: Dict[str, Any],
        n: int = 10,
        seed: Optional[mRNASequence] = None,
    ) -> List[mRNASequence]:
        """Run a generative model and return new sequences."""
        reg = self._get(model_name, "generative")
        generator: GenerativeModel = reg.model  # type: ignore[assignment]
        return generator.generate(constraints, n=n, seed=seed)

    # ── Query ────────────────────────────────────────────────────────────────

    @property
    def scoring_models(self) -> List[RegisteredModel]:
        return [r for r in self._models.values() if r.model_type == "scoring"]

    @property
    def generative_models(self) -> List[RegisteredModel]:
        return [r for r in self._models.values() if r.model_type == "generative"]

    @property
    def all_models(self) -> List[RegisteredModel]:
        return list(self._models.values())

    def unregister(self, model_name: str) -> bool:
        if model_name in self._models:
            del self._models[model_name]
            return True
        return False

    # ── Internal ─────────────────────────────────────────────────────────────

    def _register(
        self,
        model: ModelType,
        model_type: str,
        source: str,
        source_path: str,
    ) -> None:
        self._models[model.name] = RegisteredModel(
            model=model,
            model_type=model_type,
            source=source,
            source_path=source_path,
        )

    def _get(self, name: str, expected_type: str) -> RegisteredModel:
        if name not in self._models:
            raise KeyError(f"Model '{name}' not found in registry.")
        reg = self._models[name]
        if reg.model_type != expected_type:
            raise TypeError(
                f"Model '{name}' is a {reg.model_type} model, not {expected_type}."
            )
        return reg
