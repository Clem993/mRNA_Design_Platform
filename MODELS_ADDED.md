# mRNA Scoring Models - Implementation Summary

I've successfully added two mRNA scoring models to the core package as requested.

## Models Added

### 1. **RNAstructure MFE Scorer** (`models/rna_structure_scorer.py`)

**What it does**: Predicts the minimum free energy (MFE) of mRNA secondary structure to assess translation efficiency.

**Key features**:
- Uses ViennaRNA when available for accurate MFE calculation
- Falls back to GC-content based proxy scoring when ViennaRNA is not installed
- Score range: 0-100 (optimal: 40-70)
- Higher scores indicate stronger secondary structures

**Scientific basis**: Based on ViennaRNA thermodynamic calculations (Lorenz et al., 2011)

---

### 2. **mRNA Stability Scorer** (`models/mrna_stability_scorer.py`)

**What it does**: Composite stability prediction combining five established mRNA design principles.

**Scoring components**:
1. **GC Content** (30% weight) - Optimal range: 50-60%
2. **Codon Adaptation Index** (25% weight) - Codon optimization
3. **Homopolymer Detection** (20% weight) - Penalizes long identical runs
4. **5' UTR Structure** (15% weight) - Moderate stability preferred
5. **Kozak Consensus** (10% weight) - Translation initiation strength

**Key features**:
- Score range: 0-100 (70+ = excellent, 40-70 = acceptable, <40 = poor)
- Configurable for different organisms (default: human)
- Individual component scores accessible for detailed analysis

**Scientific basis**:
- Kozak sequence analysis (Mauro & Edelman, 2002)
- CAI methodology (Sharp & Li, 1987)
- mRNA stability research (Presnyak et al., 2015)

---

## Files Created

```
models/
├── rna_structure_scorer.py    # RNAstructure MFE model
├── mrna_stability_scorer.py   # mRNA Stability composite model
├── __init__.py                # Updated to export new models
└── README.md                  # Full documentation

tests/
└── test_models.py             # Added comprehensive tests for both models

demo/
└── demo_models.py             # Demo script showing usage
```

---

## Testing Results

All tests pass successfully:

```bash
$ pytest tests/test_models.py::TestRNAStructureMFEScorer -v
$ pytest tests/test_models.py::TestmRNAStabilityScorer -v

8 passed in 0.13s ✓
```

---

## Usage Example

```python
from core.models.sequence import mRNASequence
from models import RNAStructureMFEScorer, mRNAStabilityScorer

# Create a sequence
seq = mRNASequence(
    name="my_mrna",
    source="local",
    five_prime_utr="GTTGCTCCTTCGGGCCTGTGGCGGCT",
    kozak="GCCACCATGG",
    cds="ATGGTGAGCAAGGGCGAGGAG...",
)

# Score with MFE model
mfe_scorer = RNAStructureMFEScorer()
mfe_score = mfe_scorer.score(seq)
print(f"MFE Score: {mfe_score:.1f}/100")

# Score with Stability model
stability_scorer = mRNAStabilityScorer(organism="human")
stability_score = stability_scorer.score(seq)
print(f"Stability Score: {stability_score:.1f}/100")
```

---

## Demo Output

Run the demo to see both models in action:

```bash
$ PYTHONPATH=. .venv/bin/python demo/demo_models.py
```

Sample output:
```
RNAstructure MFE Scorer
Score: 64.2/100
Interpretation: Optimal structure for translation ✓

mRNA Stability Scorer
Overall Score: 76.2/100
Interpretation: Excellent design ✓

  Component Breakdown:
    GC Content (30%):   100.0/100
    CAI (25%):          63.9/100
    Homopolymers (20%): 65.0/100
    5' UTR (15%):       61.5/100
    Kozak (10%):        80.0/100
```

---

## ModelRegistry Integration

Both models are compatible with the existing ModelRegistry system:

```python
from models import ModelRegistry

registry = ModelRegistry()
registry._register(RNAStructureMFEScorer(), "scoring", "builtin", "")
registry._register(mRNAStabilityScorer(), "scoring", "builtin", "")

# Batch score sequences
results = registry.run_scoring("mRNA Stability", sequences)
```

---

## Dependencies

**Required**:
- Core Python libraries (no additional dependencies for basic functionality)

**Optional** (for enhanced features):
- `ViennaRNA` - For accurate RNA secondary structure prediction
- `BioPython` - For advanced codon usage analysis

Both models degrade gracefully when optional dependencies are missing.

---

## Next Steps

To integrate these models into the UI sidebar:

1. Update `ui/components/sidebar.py` to show loaded models
2. Implement model loading UI in the "⊕ Load Model" button handler
3. Auto-register built-in models on app startup
4. Add model scoring to the Worklist view

---

## References

- **ViennaRNA**: Lorenz et al. (2011). Algorithms for Molecular Biology, 6:26
- **Kozak**: Mauro & Edelman (2002). PNAS, 99(19):12031-12036
- **CAI**: Sharp & Li (1987). Nucleic Acids Research, 15(3):1281-1295
- **mRNA Stability**: Presnyak et al. (2015). Cell, 160(6):1111-1124
