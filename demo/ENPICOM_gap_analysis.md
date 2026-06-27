# mRNA Design Studio vs. ENPICOM IGX — gap analysis & roadmap

## Positioning (one line)
ENPICOM = **discover & de-risk** candidates from massive sequenced repertoires (antibodies/TCRs).
mRNA Design Studio = **design, build & QC** chosen sequences for expression (mRNA).
Same philosophy (no-code, data + AI for bench scientists); different pipeline stage and scale.

## Shared backbone (already have)
Import data + metadata · pluggable ML scoring · sequence analysis · candidate select/export · code-free UI.

## What would make us a closer antibody-discovery analog

### Quick wins (weeks)
1. **Sequence clustering** — group by similarity (CDS/UTR family for mRNA; CDR3/V-gene for Ab). Mirrors IGX-Cluster; biggest "explore" gap.
2. **Richer liability/QC panel** — extend current QC (restriction sites, homopolymers) into a flagged "liability" view: immunogenic motifs, GC extremes, secondary-structure hotspots. Mirrors IGX-Annotate (shallow version).
3. **Bulk / large-table ingestion** — FASTA/FASTQ import + dedup so we handle thousands, not dozens.

### Medium bets (1–2 quarters)
4. **Tree / cluster visualization** for candidate prioritization (phylogenetic-style for Ab; family/variant tree for mRNA). Mirrors IGX-Branch.
5. **Model lifecycle, not just a registry** — add training, versioning, and experiment tracking (we currently only *call* registered models). Mirrors ENPICOM's AI/MLOps layer.
6. **Projects + collaboration** — multi-user workspaces, metadata lineage, audit trail. We already have Postgres + auth as a foundation.

### Bigger bets (strategic)
7. **NGS repertoire scale** — millions of reads, server-side processing. This is ENPICOM's core moat and the largest gap.
8. **Structure-based developability** — fold/structure models for surface-liability prediction (the antibody-specific heavy lift).
9. **Round/enrichment tracking** — compare selection/panning rounds over time.

## Honest take
Closing items 1–4 makes us a credible "design + light analysis" peer for a *focused* workflow.
Items 7–8 are where ENPICOM's enterprise scale and antibody-structure depth live — matching those is a much larger investment and a different product bet.
