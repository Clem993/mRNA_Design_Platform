"""
Model plugin system for mRNA Design Studio.

Included models:
- RNAStructureMFEScorer: Secondary structure MFE prediction
- mRNAStabilityScorer: Composite stability prediction based on multiple factors
"""

from models.base import (
    ScoringModel,
    GenerativeModel,
    ModelRegistry,
    APIScoringModel,
    APIGenerativeModel,
    RegisteredModel,
)

from models.rna_structure_scorer import RNAStructureMFEScorer
from models.mrna_stability_scorer import mRNAStabilityScorer

__all__ = [
    # Base classes
    "ScoringModel",
    "GenerativeModel",
    "ModelRegistry",
    "APIScoringModel",
    "APIGenerativeModel",
    "RegisteredModel",
    # Concrete models
    "RNAStructureMFEScorer",
    "mRNAStabilityScorer",
]
