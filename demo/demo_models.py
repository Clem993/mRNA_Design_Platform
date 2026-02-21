"""
Demo script for mRNA scoring models.

Shows how to use the RNAstructure MFE and mRNA Stability scorers.
"""
from core.models.sequence import mRNASequence
from models import RNAStructureMFEScorer, mRNAStabilityScorer, ModelRegistry


def demo_individual_scorers():
    """Demo individual model scoring."""
    print("=" * 60)
    print("Demo: Individual Model Scoring")
    print("=" * 60)

    # Create a test mRNA sequence
    seq = mRNASequence(
        name="EGFP_construct",
        source="local",
        five_prime_utr="GTTGCTCCTTCGGGCCTGTGGCGGCT",
        kozak="GCCACCATGG",
        cds="ATGGTGAGCAAGGGCGAGGAGCTGTTCACCGGGGTGGTGCCCATCCTGGTCGAGCTGGACGGCGACGTAAACGGCCACAAGTTCAGCGTGTCCGGCGAGGGCGAGGGCGATGCCACCTACGGCAAGCTGACCCTGAAG",
        three_prime_utr="TGCCTGCTGCCGAGCGCCTGCGCGCGCGCGAG",
        poly_a="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
    )

    print(f"\nSequence: {seq.name}")
    print(f"Length: {seq.length} nt")
    print(f"Components: 5'UTR, Kozak, CDS, 3'UTR, PolyA\n")

    # Score with RNAstructure MFE
    print("-" * 60)
    print("RNAstructure MFE Scorer")
    print("-" * 60)
    mfe_scorer = RNAStructureMFEScorer()
    mfe_score = mfe_scorer.score(seq)
    print(f"Score: {mfe_score:.1f}/100")
    print(f"Interpretation: ", end="")
    if mfe_score < 40:
        print("Weak secondary structure")
    elif mfe_score < 70:
        print("Optimal structure for translation ✓")
    else:
        print("Strong structure (may inhibit translation)")

    # Score with mRNA Stability
    print("\n" + "-" * 60)
    print("mRNA Stability Scorer")
    print("-" * 60)
    stability_scorer = mRNAStabilityScorer(organism="human")
    stability_score = stability_scorer.score(seq)
    print(f"Overall Score: {stability_score:.1f}/100")
    print(f"Interpretation: ", end="")
    if stability_score >= 70:
        print("Excellent design ✓")
    elif stability_score >= 40:
        print("Acceptable design")
    else:
        print("Poor design, optimization recommended")

    # Show component scores
    print("\n  Component Breakdown:")
    gc_score = stability_scorer._score_gc_content(seq)
    cai_score = stability_scorer._score_cai(seq)
    homopoly_score = stability_scorer._score_homopolymers(seq)
    utr_score = stability_scorer._score_utr_structure(seq)
    kozak_score = stability_scorer._score_kozak(seq)

    if gc_score is not None:
        print(f"    GC Content (30%):   {gc_score:.1f}/100")
    if cai_score is not None:
        print(f"    CAI (25%):          {cai_score:.1f}/100")
    if homopoly_score is not None:
        print(f"    Homopolymers (20%): {homopoly_score:.1f}/100")
    if utr_score is not None:
        print(f"    5' UTR (15%):       {utr_score:.1f}/100")
    if kozak_score is not None:
        print(f"    Kozak (10%):        {kozak_score:.1f}/100")


def demo_model_registry():
    """Demo ModelRegistry integration."""
    print("\n\n" + "=" * 60)
    print("Demo: ModelRegistry Integration")
    print("=" * 60)

    # Create sequences
    sequences = [
        mRNASequence(
            name="seq_good",
            source="local",
            five_prime_utr="GTTGCTCCTTCGGGCCTGTGGCGGCT",
            kozak="GCCACCATGG",
            cds="ATGGTGAGCAAGGGCGAGGAGCTGTTCACCGGG" * 2,
        ),
        mRNASequence(
            name="seq_poor",
            source="local",
            cds="ATGAAAAAAAAAAAAAAAAAAAAAAATGA",  # Poor: homopolymers, low GC
        ),
        mRNASequence(
            name="seq_medium",
            source="local",
            five_prime_utr="ACGTACGT",
            cds="ATGCGACGATCGATCGATCGACGATGA",
        ),
    ]

    # Create registry
    registry = ModelRegistry()

    # Register models
    registry._register(RNAStructureMFEScorer(), "scoring", "builtin", "")
    registry._register(mRNAStabilityScorer(), "scoring", "builtin", "")

    print(f"\nRegistered models: {len(registry.scoring_models)}")
    for model in registry.scoring_models:
        print(f"  - {model.model.name}")

    # Score all sequences with both models
    print("\n" + "-" * 60)
    print("Scoring Results")
    print("-" * 60)

    for model_reg in registry.scoring_models:
        model_name = model_reg.model.name
        print(f"\n{model_name}:")
        results = registry.run_scoring(model_name, sequences)
        for _, row in results.iterrows():
            print(f"  {row['name']:15} → {row['score']:5.1f}")


def demo_batch_scoring():
    """Demo batch scoring efficiency."""
    print("\n\n" + "=" * 60)
    print("Demo: Batch Scoring")
    print("=" * 60)

    # Create 10 test sequences
    sequences = [
        mRNASequence(
            name=f"seq_{i:02d}",
            source="local",
            cds="ATGCGATCGATCGATCG" * (i + 1),
        )
        for i in range(10)
    ]

    scorer = mRNAStabilityScorer()

    # Batch score
    scores = scorer.score_batch(sequences)

    print(f"\nScored {len(sequences)} sequences:")
    for seq, score in zip(sequences, scores):
        print(f"  {seq.name}: {score:.1f}/100 ({seq.length} nt)")


if __name__ == "__main__":
    demo_individual_scorers()
    demo_model_registry()
    demo_batch_scoring()

    print("\n" + "=" * 60)
    print("Demo Complete!")
    print("=" * 60)
