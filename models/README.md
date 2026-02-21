# mRNA Scoring Models

This directory contains built-in mRNA scoring models for the mRNA Design Studio.

## Available Models

### 1. RNAstructure MFE Scorer (`rna_structure_scorer.py`)

**Purpose**: Predicts the minimum free energy (MFE) of mRNA secondary structure.

**Method**: Uses ViennaRNA RNAfold algorithm to compute the thermodynamic stability of RNA secondary structures. More negative MFE values indicate stronger secondary structure formation.

**Score Range**: 0-100
- **0-40**: Weak/unstable secondary structure (may be too unstructured)
- **40-70**: Moderate secondary structure (**optimal range** for translation)
- **70-100**: Strong secondary structure (may inhibit translation)

**Dependencies**:
- ViennaRNA Python package (optional)
- If ViennaRNA is not available, falls back to GC-content based proxy scoring

**Usage**:
```python
from models import RNAStructureMFEScorer

scorer = RNAStructureMFEScorer()
score = scorer.score(sequence)
```

**Interpretation**:
- Target moderate scores (40-70) for optimal translation efficiency
- Very low scores suggest the mRNA may be prone to degradation
- Very high scores suggest strong secondary structures that may block ribosome access

---

### 2. mRNA Stability Scorer (`mrna_stability_scorer.py`)

**Purpose**: Composite stability prediction based on multiple sequence features.

**Method**: Combines five established mRNA design principles:
1. **GC Content** (30% weight) - Optimal: 50-60%
2. **Codon Adaptation Index (CAI)** (25% weight) - Codon optimization for host organism
3. **Homopolymer Detection** (20% weight) - Penalizes long runs of identical nucleotides
4. **5' UTR Structure** (15% weight) - Moderate stability preferred
5. **Kozak Consensus** (10% weight) - Translation initiation efficiency

**Score Range**: 0-100
- **0-40**: Poor stability/translation efficiency
- **40-70**: Acceptable design
- **70-100**: Excellent design

**Dependencies**:
- BioPython (optional, for advanced CAI calculation)
- ViennaRNA (optional, for UTR structure analysis)

**Parameters**:
- `organism` (default: "human") - Target organism for codon optimization

**Usage**:
```python
from models import mRNAStabilityScorer

scorer = mRNAStabilityScorer(organism="human")
score = scorer.score(sequence)
```

**Individual Component Scores**:

You can access individual component scores for detailed analysis:
```python
scorer = mRNAStabilityScorer()

# Individual component scores
gc_score = scorer._score_gc_content(sequence)      # 0-100
cai_score = scorer._score_cai(sequence)           # 0-100
homopoly_score = scorer._score_homopolymers(sequence)  # 0-100
utr_score = scorer._score_utr_structure(sequence) # 0-100
kozak_score = scorer._score_kozak(sequence)       # 0-100
```

**Interpretation**:
- **70+**: Well-designed mRNA suitable for production
- **40-70**: Moderate quality, may benefit from optimization
- **<40**: Significant design issues, optimization strongly recommended

---

## Model Registry Integration

Both models implement the `ScoringModel` interface and can be loaded into the ModelRegistry:

```python
from models import ModelRegistry, RNAStructureMFEScorer, mRNAStabilityScorer

registry = ModelRegistry()

# Register built-in models
registry._register(RNAStructureMFEScorer(), "scoring", "builtin", "models/rna_structure_scorer.py")
registry._register(mRNAStabilityScorer(), "scoring", "builtin", "models/mrna_stability_scorer.py")

# Run scoring on sequences
import pandas as pd
results = registry.run_scoring("RNAstructure MFE", sequences)
```

---

## Testing

Run tests for both models:
```bash
pytest tests/test_models.py::TestRNAStructureMFEScorer -v
pytest tests/test_models.py::TestmRNAStabilityScorer -v
```

---

## Adding Custom Models

To add your own scoring model:

1. Create a new Python file in this directory
2. Import and subclass `ScoringModel`:

```python
from models.base import ScoringModel
from core.models.sequence import mRNASequence

class MyCustomScorer(ScoringModel):
    @property
    def name(self) -> str:
        return "My Custom Scorer"

    @property
    def description(self) -> str:
        return "Description of what this model does"

    def score(self, sequence: mRNASequence, metadata=None) -> float:
        # Your scoring logic here
        return 0.0  # Return score 0-100
```

3. Load it via the ModelRegistry:

```python
models = registry.load_local("path/to/your_model.py")
```

---

## References

### RNAstructure MFE Scorer
- Lorenz et al. (2011). "ViennaRNA Package 2.0." *Algorithms for Molecular Biology*, 6:26.
- Turner & Mathews (2010). "NNDB: the nearest neighbor parameter database for predicting stability of nucleic acid secondary structure." *Nucleic Acids Research*, 38:D280-282.

### mRNA Stability Scorer
- Mauro & Edelman (2002). "The ribosome filter hypothesis." *PNAS*, 99(19):12031-12036. (Kozak sequence)
- Sharp & Li (1987). "The codon adaptation index—a measure of directional synonymous codon usage bias." *Nucleic Acids Research*, 15(3):1281-1295.
- Kudla et al. (2009). "Coding-sequence determinants of gene expression in Escherichia coli." *Science*, 324(5924):255-258.
- Presnyak et al. (2015). "Codon optimality is a major determinant of mRNA stability." *Cell*, 160(6):1111-1124.
