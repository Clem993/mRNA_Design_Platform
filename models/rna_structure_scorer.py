"""
RNAstructure MFE Scorer — Secondary structure prediction model.

This model uses ViennaRNA to predict the minimum free energy (MFE) of the
mRNA secondary structure. Lower MFE indicates more stable secondary structures.

Score convention: Negative MFE values are normalized to a 0-100 scale where
higher scores indicate more favorable (more stable) structures.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from models.base import ScoringModel
from core.models.sequence import mRNASequence


class RNAStructureMFEScorer(ScoringModel):
    """
    Scores mRNA sequences based on predicted secondary structure MFE.

    Uses ViennaRNA RNAfold to compute minimum free energy. More negative
    MFE values indicate stronger secondary structure formation, which can
    affect translation efficiency and mRNA stability.

    Score scale:
    - 0-40: Weak/unstable secondary structure (may be too unstructured)
    - 40-70: Moderate secondary structure (good balance)
    - 70-100: Strong secondary structure (may inhibit translation)
    """

    @property
    def name(self) -> str:
        return "RNAstructure MFE"

    @property
    def description(self) -> str:
        return (
            "Predicts minimum free energy (MFE) of mRNA secondary structure "
            "using ViennaRNA. Scores from 0-100 where moderate values (40-70) "
            "indicate optimal structure balance for translation efficiency."
        )

    @property
    def version(self) -> str:
        return "1.0"

    def score(self, sequence: mRNASequence, metadata: Optional[Dict[str, Any]] = None) -> float:
        """
        Calculate MFE-based structure score.

        Returns:
            float: Score from 0-100, where 40-70 is optimal range
                   If ViennaRNA is not available, returns GC-based proxy score
        """
        # Get assembled sequence
        seq = sequence.assembled_sequence
        if not seq:
            return 0.0

        try:
            import RNA  # ViennaRNA Python bindings
        except ImportError:
            # Fallback: Use GC content as a proxy for structure stability
            return self._gc_based_fallback(seq)

        # Calculate MFE using ViennaRNA
        structure, mfe = RNA.fold(seq)

        # Normalize MFE to 0-100 scale
        # Typical MFE range for mRNA: -200 to 0 kcal/mol
        # More negative = stronger structure
        # Target range: -100 to -50 kcal/mol for optimal balance

        seq_length = len(seq)
        mfe_per_nt = mfe / seq_length if seq_length > 0 else 0

        # Normalize based on MFE per nucleotide
        # Optimal range: -0.3 to -0.15 kcal/mol per nt
        if mfe_per_nt >= -0.05:
            # Too unstable
            score = max(0, 40 + mfe_per_nt * 800)  # 0-40 range
        elif mfe_per_nt >= -0.15:
            # Optimal lower bound
            score = 40 + ((-0.15 - mfe_per_nt) / 0.10) * 30  # 40-70 range
        elif mfe_per_nt >= -0.30:
            # Optimal upper bound
            score = 70 - ((-0.30 - mfe_per_nt) / 0.15) * 30  # 70-40 range
        else:
            # Too stable (may inhibit translation)
            score = max(0, 40 + (mfe_per_nt + 0.30) * 100)  # 40-0 range

        return max(0.0, min(100.0, score))

    def _gc_based_fallback(self, seq: str) -> float:
        """
        GC-content based proxy score when ViennaRNA is unavailable.

        GC content correlates with secondary structure stability:
        - Higher GC = more stable structures (stronger base stacking)
        - Optimal GC for mRNA: 40-60%
        """
        gc_count = seq.count('G') + seq.count('C')
        gc_percent = (gc_count / len(seq)) * 100 if len(seq) > 0 else 50

        # Map GC% to structure stability score
        # 30-40% GC = weak structure (score ~40)
        # 50-60% GC = moderate structure (score ~55)
        # 70%+ GC = strong structure (score ~70)

        if gc_percent < 35:
            score = 30 + (gc_percent / 35) * 10  # 30-40
        elif gc_percent < 50:
            score = 40 + ((gc_percent - 35) / 15) * 15  # 40-55
        elif gc_percent < 65:
            score = 55 + ((gc_percent - 50) / 15) * 15  # 55-70
        else:
            score = 70 - ((gc_percent - 65) / 35) * 30  # 70-40

        return max(30.0, min(70.0, score))
