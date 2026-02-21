"""
Curated catalog of public mRNA models for the Model Repository browser.

Each entry represents a real publicly available model/tool. The catalog
is hardcoded for demo purposes — in production this would be fetched
from a model registry API.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class ModelCatalogEntry:
    """A model available for import from the catalog."""
    name: str
    model_type: str          # "analytical" | "generative"
    category: str            # "Structure", "Stability", "Codon Optimization", etc.
    description: str
    repository: str          # e.g. "github.com/ViennaRNA/ViennaRNA"
    repository_url: str
    deployment: str          # "embedded" | "api" | "both"
    version: str
    paper: str               # citation
    paper_url: str
    icon: str                # emoji
    tags: List[str] = field(default_factory=list)
    inputs: str = ""         # "Full mRNA sequence", "CDS only", etc.
    status: str = "available"  # "available" | "imported" | "connected"


def get_model_catalog() -> List[ModelCatalogEntry]:
    """Return the curated model catalog."""
    catalog: List[ModelCatalogEntry] = []

    # ── Analytical Models ────────────────────────────────────────────────────

    catalog.append(ModelCatalogEntry(
        name="ViennaRNA (RNAfold)",
        model_type="analytical",
        category="Structure Prediction",
        description="Gold-standard thermodynamic RNA secondary structure prediction. Computes MFE structures, partition functions, and base-pair probabilities.",
        repository="github.com/ViennaRNA/ViennaRNA",
        repository_url="https://github.com/ViennaRNA/ViennaRNA",
        deployment="embedded",
        version="2.6.4",
        paper="Lorenz et al., ViennaRNA Package 2.0, Algorithms Mol Biol (2011)",
        paper_url="https://doi.org/10.1186/1748-7188-6-26",
        icon="🧬",
        tags=["scoring", "MFE", "secondary structure", "thermodynamics"],
        inputs="Full mRNA sequence",
    ))

    catalog.append(ModelCatalogEntry(
        name="LinearFold",
        model_type="analytical",
        category="Structure Prediction",
        description="Linear-time RNA secondary structure prediction using beam search. Orders of magnitude faster than cubic-time algorithms on long sequences.",
        repository="github.com/LinearFold/LinearFold",
        repository_url="https://github.com/LinearFold/LinearFold",
        deployment="embedded",
        version="1.0",
        paper="Huang et al., LinearFold: linear-time approximate RNA folding, Bioinformatics (2019)",
        paper_url="https://doi.org/10.1093/bioinformatics/btz375",
        icon="⚡",
        tags=["scoring", "MFE", "secondary structure", "fast"],
        inputs="Full mRNA sequence",
    ))

    catalog.append(ModelCatalogEntry(
        name="EternaFold",
        model_type="analytical",
        category="Structure Prediction",
        description="RNA secondary structure prediction trained on Eterna player data. Improved accuracy on structured RNA elements.",
        repository="github.com/eternagame/EternaFold",
        repository_url="https://github.com/eternagame/EternaFold",
        deployment="embedded",
        version="1.3",
        paper="Wayment-Steele et al., RNA secondary structure packages evaluated, Nat Methods (2022)",
        paper_url="https://doi.org/10.1038/s41592-022-01605-0",
        icon="🎯",
        tags=["scoring", "secondary structure", "deep learning"],
        inputs="Full mRNA sequence",
    ))

    catalog.append(ModelCatalogEntry(
        name="Optimus 5-Prime",
        model_type="analytical",
        category="UTR Scoring",
        description="Predicts mean ribosome load from 5' UTR sequence. Convolutional model trained on massively parallel reporter assays.",
        repository="github.com/pjsample/human_5utr_modeling",
        repository_url="https://github.com/pjsample/human_5utr_modeling",
        deployment="embedded",
        version="1.0",
        paper="Sample et al., Human 5' UTR design and variant effect prediction, Nat Biotechnol (2019)",
        paper_url="https://doi.org/10.1038/s41587-019-0164-5",
        icon="📊",
        tags=["scoring", "UTR", "translation", "ribosome load"],
        inputs="5' UTR only",
    ))

    catalog.append(ModelCatalogEntry(
        name="RNAdegformer",
        model_type="analytical",
        category="Stability / Degradation",
        description="Transformer model predicting per-nucleotide RNA degradation rates. Trained on OpenVaccine challenge data.",
        repository="github.com/Shujun-He/RNAdegformer",
        repository_url="https://github.com/Shujun-He/RNAdegformer",
        deployment="embedded",
        version="1.0",
        paper="He et al., RNAdegformer, competition solution (2020)",
        paper_url="https://arxiv.org/abs/2110.07531",
        icon="📉",
        tags=["scoring", "stability", "degradation", "transformer"],
        inputs="Full mRNA sequence",
    ))

    catalog.append(ModelCatalogEntry(
        name="Saluki",
        model_type="analytical",
        category="Stability / Half-life",
        description="Deep learning model predicting mRNA half-life from sequence and structure. Integrates codon usage, UTR features, and secondary structure.",
        repository="github.com/vagarwal87/saluki_paper",
        repository_url="https://github.com/vagarwal87/saluki_paper",
        deployment="embedded",
        version="1.0",
        paper="Agarwal & Kelley, The genetic and biochemical determinants of mRNA degradation rates, Genome Biol (2022)",
        paper_url="https://doi.org/10.1186/s13059-022-02811-x",
        icon="⏱️",
        tags=["scoring", "half-life", "stability", "deep learning"],
        inputs="Full mRNA sequence",
    ))

    catalog.append(ModelCatalogEntry(
        name="CodonFM (NVIDIA)",
        model_type="analytical",
        category="Foundation Model",
        description="Foundation model for codon-level mRNA representations. Pre-trained on millions of coding sequences for downstream tasks.",
        repository="github.com/NVIDIA-Digital-Bio/CodonFM",
        repository_url="https://github.com/NVIDIA-Digital-Bio/CodonFM",
        deployment="both",
        version="1.0",
        paper="NVIDIA Digital Biology, CodonFM (2024)",
        paper_url="https://github.com/NVIDIA-Digital-Bio/CodonFM",
        icon="🏗️",
        tags=["foundation model", "embeddings", "codon", "NVIDIA"],
        inputs="CDS only",
    ))

    catalog.append(ModelCatalogEntry(
        name="mRNABERT",
        model_type="analytical",
        category="Foundation Model",
        description="BERT-based foundation model for mRNA sequences. Generates contextual embeddings useful for property prediction and design.",
        repository="huggingface.co/YYLY66/mRNABERT",
        repository_url="https://huggingface.co/YYLY66/mRNABERT",
        deployment="embedded",
        version="1.0",
        paper="Yang et al., mRNABERT (2023)",
        paper_url="https://huggingface.co/YYLY66/mRNABERT",
        icon="🤖",
        tags=["foundation model", "BERT", "embeddings", "HuggingFace"],
        inputs="Full mRNA sequence",
    ))

    catalog.append(ModelCatalogEntry(
        name="Riboformer",
        model_type="analytical",
        category="Translation Efficiency",
        description="Transformer model predicting translation efficiency from mRNA sequence. Models ribosome dynamics and codon-level features.",
        repository="Paper",
        repository_url="https://doi.org/10.1101/2023.09.09.556981",
        deployment="embedded",
        version="1.0",
        paper="Gu et al., Riboformer: a deep learning framework for predicting context-dependent translation dynamics (2023)",
        paper_url="https://doi.org/10.1101/2023.09.09.556981",
        icon="🔬",
        tags=["scoring", "translation", "ribosome", "transformer"],
        inputs="Full mRNA sequence",
    ))

    # ── Generative Models ────────────────────────────────────────────────────

    catalog.append(ModelCatalogEntry(
        name="GEMORNA",
        model_type="generative",
        category="Full mRNA Design",
        description="Generative model for complete mRNA sequence design. Jointly optimizes codon usage, UTR selection, and structural stability.",
        repository="github.com/RainaBio/GEMORNA",
        repository_url="https://github.com/RainaBio/GEMORNA",
        deployment="embedded",
        version="1.0",
        paper="Raina Bio, GEMORNA (2024)",
        paper_url="https://github.com/RainaBio/GEMORNA",
        icon="🧪",
        tags=["generative", "full mRNA", "end-to-end", "design"],
        inputs="Target protein / constraints",
    ))

    catalog.append(ModelCatalogEntry(
        name="LinearDesign",
        model_type="generative",
        category="CDS Optimization",
        description="Simultaneously optimizes mRNA sequence for codon usage and minimum free energy structure. Uses dynamic programming for global optimality.",
        repository="github.com/LinearDesignSoftware/LinearDesign",
        repository_url="https://github.com/LinearDesignSoftware/LinearDesign",
        deployment="embedded",
        version="1.0",
        paper="Zhang et al., Algorithm for optimized mRNA design improves stability and immunogenicity, Nature (2023)",
        paper_url="https://doi.org/10.1038/s41586-023-06127-z",
        icon="📐",
        tags=["generative", "CDS", "codon optimization", "structure"],
        inputs="CDS only",
    ))

    catalog.append(ModelCatalogEntry(
        name="mRNAid (Merck)",
        model_type="generative",
        category="mRNA Optimization",
        description="Multi-objective mRNA optimization tool. Simultaneously optimizes GC content, codon usage, MFE, and uridine depletion.",
        repository="github.com/Merck/mRNAid",
        repository_url="https://github.com/Merck/mRNAid",
        deployment="both",
        version="1.0",
        paper="Medina-Inojosa et al., mRNAid (2024)",
        paper_url="https://github.com/Merck/mRNAid",
        icon="💊",
        tags=["generative", "optimization", "multi-objective", "Merck"],
        inputs="CDS only",
    ))

    catalog.append(ModelCatalogEntry(
        name="CodonTransformer",
        model_type="generative",
        category="Codon Optimization",
        description="Transformer-based codon optimizer supporting 164 organisms. Generates optimized CDS from protein sequences using organism-specific codon preferences.",
        repository="huggingface.co/Adibvafa/CodonTransformer",
        repository_url="https://huggingface.co/Adibvafa/CodonTransformer",
        deployment="embedded",
        version="1.5",
        paper="Farhadi et al., CodonTransformer (2024)",
        paper_url="https://huggingface.co/Adibvafa/CodonTransformer",
        icon="🔄",
        tags=["generative", "codon optimization", "transformer", "multi-species"],
        inputs="Protein sequence",
    ))

    catalog.append(ModelCatalogEntry(
        name="UTRGAN",
        model_type="generative",
        category="UTR Generation",
        description="Generative adversarial network for designing functional 5' UTR sequences. Generates UTRs with target expression levels.",
        repository="github.com/ciceklab/UTRGAN",
        repository_url="https://github.com/ciceklab/UTRGAN",
        deployment="embedded",
        version="1.0",
        paper="Daskalakis et al., UTRGAN, NeurIPS Workshop (2022)",
        paper_url="https://github.com/ciceklab/UTRGAN",
        icon="🎲",
        tags=["generative", "UTR", "GAN", "expression"],
        inputs="Target expression level",
    ))

    catalog.append(ModelCatalogEntry(
        name="iCodon",
        model_type="generative",
        category="Codon Stability Optimization",
        description="Codon optimization tool focusing on mRNA stability. Uses codon influence on mRNA stability to guide synonymous substitutions.",
        repository="github.com/santiago1234/iCodon",
        repository_url="https://github.com/santiago1234/iCodon",
        deployment="embedded",
        version="1.0",
        paper="Diez et al., iCodon customizes gene expression based on codon influence on mRNA stability, Genome Biol (2022)",
        paper_url="https://doi.org/10.1186/s13059-021-02571-y",
        icon="🧊",
        tags=["generative", "codon optimization", "stability", "half-life"],
        inputs="CDS only",
    ))

    return catalog


# Category constants for filtering
ANALYTICAL_CATEGORIES = [
    "Structure Prediction",
    "UTR Scoring",
    "Stability / Degradation",
    "Stability / Half-life",
    "Foundation Model",
    "Translation Efficiency",
]

GENERATIVE_CATEGORIES = [
    "Full mRNA Design",
    "CDS Optimization",
    "mRNA Optimization",
    "Codon Optimization",
    "UTR Generation",
    "Codon Stability Optimization",
]

ALL_CATEGORIES = sorted(set(ANALYTICAL_CATEGORIES + GENERATIVE_CATEGORIES))

FILTER_OPTIONS = [
    "All",
    "Analytical",
    "Generative",
    "Structure",
    "Stability",
    "Codon",
    "UTR",
    "Foundation",
]
