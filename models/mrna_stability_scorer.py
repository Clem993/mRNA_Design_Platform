"""
mRNA Stability Scorer — Composite stability prediction model.

This model predicts mRNA stability based on multiple sequence features known
to affect mRNA half-life and translation efficiency:

1. GC Content (optimal: 50-60%)
2. Codon Adaptation Index (CAI) - codon optimization for host organism
3. Homopolymer runs (penalized - prone to errors)
4. 5' UTR secondary structure (moderate stability preferred)
5. Kozak consensus (strong Kozak = better translation initiation)

Score convention: 0-100 scale where higher scores indicate better predicted
stability and translation efficiency.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from models.base import ScoringModel
from core.models.sequence import mRNASequence


class mRNAStabilityScorer(ScoringModel):
    """
    Composite mRNA stability scorer based on established design principles.

    Combines multiple sequence features into a unified stability score:
    - GC content balance (30%)
    - Codon optimization via CAI (25%)
    - Absence of homopolymers (20%)
    - 5' UTR structure (15%)
    - Kozak strength (10%)

    Score scale:
    - 0-40: Poor stability/translation
    - 40-70: Acceptable
    - 70-100: Excellent design
    """

    def __init__(self, organism: str = "human"):
        """
        Initialize the stability scorer.

        Parameters:
            organism: Target organism for codon optimization (default: human)
        """
        self.organism = organism

    @property
    def name(self) -> str:
        return "mRNA Stability"

    @property
    def description(self) -> str:
        return (
            f"Composite stability score for {self.organism} mRNA expression. "
            "Evaluates GC content, codon optimization, homopolymers, UTR structure, "
            "and Kozak strength. Scores 70+ indicate optimal design."
        )

    @property
    def version(self) -> str:
        return "1.0"

    def score(self, sequence: mRNASequence, metadata: Optional[Dict[str, Any]] = None) -> float:
        """
        Calculate composite stability score.

        Returns:
            float: Score from 0-100
        """
        scores = []
        weights = []

        # 1. GC Content Score (30% weight)
        gc_score = self._score_gc_content(sequence)
        if gc_score is not None:
            scores.append(gc_score)
            weights.append(0.30)

        # 2. CAI Score (25% weight)
        cai_score = self._score_cai(sequence)
        if cai_score is not None:
            scores.append(cai_score)
            weights.append(0.25)

        # 3. Homopolymer Score (20% weight)
        homopoly_score = self._score_homopolymers(sequence)
        if homopoly_score is not None:
            scores.append(homopoly_score)
            weights.append(0.20)

        # 4. 5' UTR Structure Score (15% weight)
        utr_score = self._score_utr_structure(sequence)
        if utr_score is not None:
            scores.append(utr_score)
            weights.append(0.15)

        # 5. Kozak Score (10% weight)
        kozak_score = self._score_kozak(sequence)
        if kozak_score is not None:
            scores.append(kozak_score)
            weights.append(0.10)

        if not scores:
            return 0.0

        # Weighted average
        total_weight = sum(weights)
        weighted_sum = sum(s * w for s, w in zip(scores, weights))
        return weighted_sum / total_weight

    def _score_gc_content(self, sequence: mRNASequence) -> Optional[float]:
        """Score GC content. Optimal: 50-60%."""
        seq = sequence.assembled_sequence
        if not seq:
            return None

        gc_count = seq.count('G') + seq.count('C')
        gc_percent = (gc_count / len(seq)) * 100

        # Optimal range: 50-60%
        if 50 <= gc_percent <= 60:
            return 100.0
        elif 45 <= gc_percent < 50:
            return 100 - ((50 - gc_percent) * 10)  # 50-100
        elif 60 < gc_percent <= 65:
            return 100 - ((gc_percent - 60) * 10)  # 50-100
        elif 40 <= gc_percent < 45:
            return 50 - ((45 - gc_percent) * 10)  # 0-50
        elif 65 < gc_percent <= 70:
            return 50 - ((gc_percent - 65) * 10)  # 0-50
        else:
            return 0.0

    def _score_cai(self, sequence: mRNASequence) -> Optional[float]:
        """Score codon adaptation index. Uses simplified CAI estimation."""
        if not sequence.cds:
            return None

        try:
            from Bio.SeqUtils import CodonUsage
            from Bio.Seq import Seq
        except ImportError:
            # If BioPython not available, use simple codon diversity metric
            return self._simple_codon_score(sequence.cds)

        # Calculate CAI using BioPython
        # For now, use a simple diversity metric as proxy
        return self._simple_codon_score(sequence.cds)

    def _simple_codon_score(self, cds: str) -> float:
        """Simple codon diversity score as CAI proxy."""
        if len(cds) < 3:
            return 0.0

        codons = [cds[i:i+3] for i in range(0, len(cds) - 2, 3)]
        if not codons:
            return 0.0

        # Calculate codon diversity
        unique_codons = len(set(codons))
        diversity_ratio = unique_codons / len(codons)

        # Penalize extreme repetition, reward moderate diversity
        if diversity_ratio > 0.7:
            return 100.0
        elif diversity_ratio > 0.5:
            return 70 + (diversity_ratio - 0.5) * 150
        else:
            return diversity_ratio * 140

    def _score_homopolymers(self, sequence: mRNASequence) -> Optional[float]:
        """Score homopolymer runs. Penalize long runs."""
        seq = sequence.assembled_sequence
        if not seq:
            return None

        # Find all homopolymer runs >= 4 nucleotides
        homopolymers = self._find_homopolymers(seq, min_length=4)

        if not homopolymers:
            return 100.0

        # Penalize based on number and length of runs
        total_penalty = 0
        for start, end, base in homopolymers:
            length = end - start
            if length >= 8:
                total_penalty += 30  # Severe penalty
            elif length >= 6:
                total_penalty += 15
            else:
                total_penalty += 5

        return max(0.0, 100.0 - total_penalty)

    def _find_homopolymers(self, seq: str, min_length: int = 4) -> List[Tuple[int, int, str]]:
        """Find homopolymer runs in sequence."""
        homopolymers = []
        for base in ['A', 'T', 'C', 'G', 'U']:
            pattern = f"{base}{{{min_length},}}"
            for match in re.finditer(pattern, seq):
                homopolymers.append((match.start(), match.end(), base))
        return homopolymers

    def _score_utr_structure(self, sequence: mRNASequence) -> Optional[float]:
        """Score 5' UTR secondary structure stability."""
        if not sequence.five_prime_utr:
            return None

        try:
            import RNA
        except ImportError:
            # If ViennaRNA not available, use simple GC% as proxy
            utr = sequence.five_prime_utr
            gc_count = utr.count('G') + utr.count('C')
            gc_percent = (gc_count / len(utr)) * 100 if len(utr) > 0 else 50

            # Moderate GC (40-60%) is good for 5' UTR
            if 40 <= gc_percent <= 60:
                return 100.0
            else:
                return max(0.0, 100 - abs(50 - gc_percent) * 2)

        # Calculate MFE for 5' UTR
        utr = sequence.five_prime_utr
        structure, mfe = RNA.fold(utr)

        # Moderate stability preferred for 5' UTR
        # Too stable = translation initiation inhibited
        # Too unstable = degradation prone
        mfe_per_nt = mfe / len(utr) if len(utr) > 0 else 0

        # Optimal: -0.2 to -0.1 kcal/mol per nt
        if -0.25 <= mfe_per_nt <= -0.08:
            return 100.0
        elif -0.35 <= mfe_per_nt < -0.25:
            return 100 - abs(mfe_per_nt + 0.25) * 200
        elif -0.08 < mfe_per_nt <= 0:
            return 100 - abs(mfe_per_nt + 0.08) * 400
        else:
            return 0.0

    def _score_kozak(self, sequence: mRNASequence) -> Optional[float]:
        """Score Kozak consensus strength."""
        if not sequence.kozak:
            return None

        # Kozak consensus: GCCRCCATGG (R = A or G)
        # Most critical positions: -3 (G), +4 (G)
        kozak = sequence.kozak.upper()

        if len(kozak) < 9:
            return 50.0  # Incomplete Kozak

        score = 0.0
        max_score = 100.0

        # Position -3 (index 6 if ATGG is at end): prefer G (40 points)
        if len(kozak) >= 7:
            if kozak[-7] == 'G':
                score += 40
            elif kozak[-7] in ['A', 'C']:
                score += 20

        # Position +4 (index 3 after ATG): prefer G (40 points)
        if kozak.endswith('ATGG'):
            score += 40
        elif kozak[-3:] == 'ATG':
            score += 20

        # ATG start codon must be present (20 points)
        if 'ATG' in kozak:
            score += 20

        return min(score, max_score)
