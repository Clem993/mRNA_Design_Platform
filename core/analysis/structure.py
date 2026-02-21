"""
RNA secondary structure prediction via ViennaRNA.

ViennaRNA (RNA package) must be installed:
  conda install -c bioconda viennarna
  or: pip install ViennaRNA (if wheel available for the platform)

Falls back to a stub when ViennaRNA is not available so the rest of the
app can run without it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

_VIENNARNA_AVAILABLE = False
try:
    import RNA  # type: ignore[import-untyped]
    _VIENNARNA_AVAILABLE = True
except ImportError:
    pass


@dataclass
class StructureResult:
    sequence: str
    structure: str          # dot-bracket notation
    mfe: float              # minimum free energy (kcal/mol)
    ensemble_free_energy: Optional[float] = None
    centroid_structure: Optional[str] = None
    centroid_distance: Optional[float] = None

    @property
    def is_stub(self) -> bool:
        return self.structure == "" and self.mfe == 0.0

    def __repr__(self) -> str:
        return (
            f"StructureResult(mfe={self.mfe:.2f} kcal/mol, "
            f"len={len(self.sequence)})"
        )


def predict_structure(sequence: str) -> StructureResult:
    """
    Predict the MFE secondary structure of an RNA/DNA sequence.

    The sequence is automatically converted from DNA to RNA (T→U) before
    passing to ViennaRNA, which expects RNA input.

    Returns a StructureResult. If ViennaRNA is not installed, returns a
    stub result with empty structure and mfe=0.0.
    """
    rna_seq = sequence.upper().replace("T", "U")

    if not _VIENNARNA_AVAILABLE:
        return StructureResult(
            sequence=rna_seq,
            structure="",
            mfe=0.0,
        )

    # MFE structure
    structure, mfe = RNA.fold(rna_seq)  # type: ignore[attr-defined]

    # Ensemble / centroid (for longer seqs this is informative)
    md = RNA.md()  # type: ignore[attr-defined]
    fc = RNA.fold_compound(rna_seq, md)  # type: ignore[attr-defined]
    _, ensemble_free_energy = fc.pf()
    centroid_structure, centroid_distance = fc.centroid()

    return StructureResult(
        sequence=rna_seq,
        structure=structure,
        mfe=mfe,
        ensemble_free_energy=ensemble_free_energy,
        centroid_structure=centroid_structure,
        centroid_distance=centroid_distance,
    )


def is_viennarna_available() -> bool:
    return _VIENNARNA_AVAILABLE
