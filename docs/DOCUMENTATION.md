# mRNA Data Management Platform — Documentation

A browser-based workbench for designing, analyzing, QC-ing, scoring and assembling
mRNA sequences — end to end, with no code. It gives RNA-therapeutics teams a single
structured record for every construct, an explainable QC layer, pluggable AI models,
and experiment tracking that lays the groundwork for a closed Design-Build-Test-Learn
loop.

- **Live app:** https://offtargeteffect-mrna-design-studio.hf.space
- **Stack:** Python 3.13 · Panel/Bokeh · Plotly · pandas/NumPy · SQLAlchemy · BioPython · DNAChisel · ViennaRNA (optional)

---

## Table of contents
1. [What it is](#1-what-it-is)
2. [Architecture](#2-architecture)
3. [The application (tab by tab)](#3-the-application-tab-by-tab)
4. [The analysis engine](#4-the-analysis-engine)
5. [Liability / QC scoring](#5-liability--qc-scoring)
6. [Candidate objective scoring](#6-candidate-objective-scoring)
7. [Codon-optimization analysis](#7-codon-optimization-analysis)
8. [The model system (pluggable AI)](#8-the-model-system-pluggable-ai)
9. [Experiment / run tracking](#9-experiment--run-tracking)
10. [The data layer](#10-the-data-layer)
11. [Configuration](#11-configuration)
12. [Running it](#12-running-it)
13. [Deployment](#13-deployment)
14. [Testing](#14-testing)
15. [Project structure](#15-project-structure)
16. [Extending the platform](#16-extending-the-platform)
17. [Scope & roadmap](#17-scope--roadmap)

---

## 1. What it is

The platform takes an mRNA construct from **import → analyse & QC → compare & score →
assemble**, in one reactive UI. Its design goals:

- **One structured record** per construct (no sequences scattered across spreadsheets).
- **Explainable QC** — every quality flag and score traces back to a specific metric.
- **Pluggable intelligence** — scoring/generative models register as plugins (local code
  or remote API); the platform itself is the deterministic data + orchestration layer.
- **Traceability** — every model run is logged with its version and comparable over time.

It is a **prototype**: a focused workbench over curated sets, not production NGS-scale
infrastructure. See [Scope & roadmap](#17-scope--roadmap).

---

## 2. Architecture

Layered, with a strict separation between a pure domain core and the UI:

```
┌─────────────────────────────────────────────────────────────┐
│  UI layer            ui/                                      │
│  Panel/Bokeh reactive components; one AppState per session    │
├─────────────────────────────────────────────────────────────┤
│  Domain core         core/                                    │
│  Pure-Python analysis & models — no UI deps, fully unit-tested │
├─────────────────────────────────────────────────────────────┤
│  Model layer         models/                                  │
│  Pluggable scoring/generative model registry + run tracking   │
├─────────────────────────────────────────────────────────────┤
│  Data layer          core/database/                           │
│  SQLAlchemy + CSV importers, schema-mapped to a canonical model│
└─────────────────────────────────────────────────────────────┘
```

- **`core/`** has no Panel/Plotly imports — it can be tested and reused headlessly.
- **`ui/state.py`** holds `AppState`, a `param.Parameterized` object instantiated **once per
  browser session**; every component reacts to its parameters.
- Data flows one way: **importers → `mRNASequence` model → `SequenceAnalyzer` →
  `AnalysisReport` → scoring/UI**.

---

## 3. The application (tab by tab)

| Tab | Purpose |
|-----|---------|
| **Import Data** | Load sequences from CSV/Excel or PostgreSQL; columns auto-map to the mRNA model; import into a worklist. |
| **Model Repository** | Browse/register scoring & generative models (local Python or remote API), each versioned. |
| **Worklist** | Inspect sequences; run base analysis (GC, CAI, homopolymers, restriction sites) + **QC score**; per-row liability breakdown; score with models; export CSV. |
| **Candidate Analysis** | Multi-objective comparison scorecard (Expression / Stability / Immunogenicity / Manufacturability + Overall) with shortlist; per-candidate structure map + codon analysis. |
| **Experiments** | Registered model versions, run history, and version-to-version score comparison. |
| **Parts Workshop** | Browse/compose reusable parts (5′UTR, Kozak, CDS, 3′UTR, poly-A). |
| **Assemble Plasmid** | Pick a backbone & cloning strategy, run QC, export the assembled construct. |
| **Generate Sequences** | Produce codon-optimized variants from configurable settings. |

---

## 4. The analysis engine

`core/analysis/analyzer.py` → `SequenceAnalyzer.run_full_analysis(seq)` is the **single
entry point** that runs the entire QC panel on one sequence and returns one
`AnalysisReport`. It is a **deterministic pipeline — not an ML model**: same input → same
output, every result explainable.

Pipeline steps:
1. **Assemble** the full sequence (5′UTR + Kozak + CDS + 3′UTR + poly-A, or the supplied `full_mrna`).
2. Run each analysis module:
   - **GC content** (`gc_content.py`) — global % + sliding window + GC-by-codon-position
   - **CAI** (`cai.py`) — Codon Adaptation Index + codon usage, per host organism
   - **CDS validation** — start (ATG), stop codon, in-frame (÷3)
   - **Homopolymers** (`homopolymers.py`) — runs of repeated bases
   - **Restriction sites** (`restriction_sites.py`) — common cloning enzymes
   - **Kozak context** (`kozak.py`) — translation-initiation strength
   - **Secondary structure** (`structure.py`) — ViennaRNA MFE (optional; stub if not installed)
   - **Uridine content** (`uridine.py`) — total % + high-U stretches
   - **Motifs** (`motifs.py`) — uORFs, premature polyA, AU-rich elements, splice donors
3. **Aggregate** a liability/QC assessment (`liability.py`).

Two behaviours worth knowing:
- **Caching** — results are stored on the sequence (`_analysis_cache`); re-analysis is a
  cache hit unless `force_rerun=True`.
- **Configurable** — the analyzer is constructed with `gc_window`, `gc_step`,
  `homopolymer_min_run`, `restriction_enzymes`, and `cai_organism`, so QC rules are tunable
  per programme/modality.

Output: an `AnalysisReport` dataclass holding every result + a `to_dict()` for the worklist/table.

---

## 5. Liability / QC scoring

`core/analysis/liability.py` → `assess_liabilities(report, seq)` rolls the analysis into a
**severity-ranked list of flags + a 0–100 QC score + a verdict** (pass / review / fail).

- **Flags** (each with severity, detail, location, recommendation) cover: GC out of range,
  homopolymer runs (excluding the legitimate poly-A tail), restriction sites, elevated
  uridine, CDS integrity, weak Kozak, strong structure, and sequence motifs.
- **Severity → penalty:** critical −25, warning −10, info −3. **Score** = `max(0, 100 − Σ penalties)`.
- **Verdict:** any critical → *fail*; else any warning → *review*; else *pass*.

Surfaced as a scorecard (analysis dashboard / candidate inspect) and as **QC** + **Liabilities**
columns in the worklist.

---

## 6. Candidate objective scoring

`core/analysis/candidate_score.py` → `score_objectives(report)` condenses the report into the
four objectives mRNA designers trade off, each **0–100, higher is better**. These are
**transparent weighted heuristics, not trained models**.

| Objective | Formula (summary) |
|-----------|-------------------|
| **Expression** | `0.6 × CAI(0–100) + 0.4 × Kozak` (strong 100 / adequate 70 / weak 35) |
| **Stability** | GC distance from 50–60% optimal band, − homopolymer penalty, + folding-MFE bonus if available |
| **Immunogenicity** | `100 − (uridine% − 20)×3 − 8 × high-U stretches` (low U = high score) |
| **Manufacturability** | 100 − penalties for restriction sites / homopolymers / GC extremes / splice motifs |
| **Overall** | weighted mean: Expression 30% · Stability 25% · Immunogenicity 20% · Manufacturability 25% |

All scores clamp to 0–100; missing metrics fall back to neutral defaults. The Candidate
Analysis tab ranks by Overall, colour-codes by band, and shortlists the top N.

---

## 7. Codon-optimization analysis

`core/analysis/codon_analysis.py` → `analyze_codons(cds, organism)` provides per-codon detail:

- **Per-codon optimality** — each codon's relative adaptiveness (0–1) vs the best synonym.
- **%MinMax profile** — classic sliding-window measure (positive = common/fast codons,
  negative = rare/slow clusters that stall ribosomes).
- **Rare-codon clusters** — runs of low-optimality codons worth recoding.
- **Original-vs-optimized projection** — projected CAI gain and rare-codon reduction if the
  CDS were optimized for the host (reuses `core/sequence_tools/codon_optimizer.py`).

---

## 8. The model system (pluggable AI)

This is where ML lives — **separate from the deterministic analysis pipeline**. Defined in
`models/base.py`:

- **`ScoringModel`** (ABC) — `name`, `description`, `version`, `score(sequence) → float`,
  `score_batch(...)`.
- **`GenerativeModel`** (ABC) — `generate(constraints, n, seed) → [sequences]`.
- **`APIScoringModel` / `APIGenerativeModel`** — wrap a remote REST endpoint (POST sequences → scores/sequences).
- **`ModelRegistry`** — registers models from a local Python file (`load_local`) or an API
  endpoint; exposes `scoring_models`, `generative_models`, `run_scoring`, `run_generation`.

Built-in example scorers: `models/mrna_stability_scorer.py`, `models/rna_structure_scorer.py`.
A `models/catalog.py` lists public models that can be imported.

**Framing:** the platform is AI-*enabling* infrastructure — structured data in, models run
against it, every run tracked. The intelligence plugs in; the platform is not itself a model.

---

## 9. Experiment / run tracking

`models/runs.py` records every scoring run:

- **`ModelRun`** — model name + version + source, worklist, N, score min/max/mean/std,
  timestamp, and the per-sequence scores.
- **`RunHistory`** — append-only store; `for_model()`, `model_names()`, and
  `compare(run_a, run_b)` → a `RunComparison` with per-sequence deltas and
  improved/worsened/unchanged counts.

The **Experiments** tab shows registered model versions, the run history, and a
version-to-version comparison. This is the "Learn" scaffolding of the DBTL loop.

---

## 10. The data layer

`core/database/` provides a uniform import interface:

- **`base.py`** — `DatabaseConnector` interface + `SchemaMapper` (maps arbitrary
  source columns to the canonical `mRNASequence` model).
- **`postgres.py`** (SQLAlchemy + psycopg2), **`sqlite.py`**, **`csv_importer.py`** (CSV/Excel).

Core models (`core/models/`):
- **`mRNASequence`** — the canonical record: optional components (5′UTR, Kozak, CDS, 3′UTR,
  poly-A) or a `full_mrna`, plus metadata; `assembled_sequence` concatenates components.
- **`Worklist`** / **`WorklistItem`**, **`PlasmidBackbone`**, **`SequencePart`**.

---

## 11. Configuration

Environment variables (see `.env.example`; loaded via python-dotenv):

| Variable | Purpose |
|----------|---------|
| `MRNA_STUDIO_PASSWORD` | Single shared password (any username) — enables the login screen |
| `MRNA_STUDIO_USERS` | JSON `{"user": "pass"}` for multiple users (overrides the above) |
| `MRNA_STUDIO_COOKIE_SECRET` | Session-cookie signing secret (set in production) |
| `PORT` / `HOST` | Server bind (default 5007 / 0.0.0.0; platforms set `PORT` automatically) |
| `MRNA_STUDIO_RELOAD` | `1` enables hot-reload in development |

If neither password variable is set, the app runs open (no login).

---

## 12. Running it

Prerequisites: a terminal with `make` and `curl` (no system Python needed — setup installs
`uv` + Python 3.13).

```bash
make setup     # install uv, Python 3.13, venv, dependencies (~1 min)
make run       # start at http://localhost:5007
make run-secure  # password-protected (requires .env)
make test      # run the test suite
make lint      # ruff
make kill      # stop the app
```

Optional demo database (Docker):

```bash
make db-up     # start demo PostgreSQL
make db-down   # stop it
```

Sample data lives in `demo/` (`demo_sequences_extended.csv` is the richest).

---

## 13. Deployment

The app is containerised (`Dockerfile`) and reads `PORT`/`HOST` from the environment, so it
runs on any container host.

- **Hosted demo:** Hugging Face Spaces (Docker SDK, `app_port: 5007`). Secrets
  (`MRNA_STUDIO_PASSWORD`, `MRNA_STUDIO_COOKIE_SECRET`) are set in Space settings.
- **Also supported:** Railway, Render, local Docker (`make docker-build` / `make docker-run`).

Note: ViennaRNA is optional and not in the hosted image — secondary-structure results show as
a stub there; all other analyses run.

---

## 14. Testing

`pytest` suite under `tests/` (run with `make test`): `test_analysis.py`,
`test_liability.py`, `test_candidate_score.py`, `test_codon_analysis.py`, `test_runs.py`,
`test_models.py`, `test_database.py`. The pure-core design means the analysis, scoring, and
model logic are all unit-tested without the UI. **118 tests** at time of writing.

---

## 15. Project structure

```
core/
  analysis/        analyzer.py + GC, CAI, homopolymers, restriction_sites, kozak,
                   structure, uridine, motifs, liability, candidate_score, codon_analysis
  database/        base (SchemaMapper) + postgres / sqlite / csv importers
  models/          mRNASequence, Worklist, PlasmidBackbone, SequencePart
  sequence_tools/  codon_optimizer, clean_for_cloning
  data/            seed parts & backbones
models/            ScoringModel/GenerativeModel ABCs, ModelRegistry, runs (tracking),
                   built-in scorers, catalog
ui/
  app.py           Panel entry point (template, tabs, auth, serve)
  state.py         AppState (per-session reactive state)
  components/      one module per tab + shared panels
tests/             pytest suite
demo/              sample data, demo DB, deck, demo script
Dockerfile, Makefile, Procfile, pyproject.toml, requirements.txt
```

---

## 16. Extending the platform

**Add a scoring model** — drop a Python file exposing a `ScoringModel` subclass and load it
via the Model Repository (or `ModelRegistry.load_local(path)`), or register a REST endpoint
with `register_api_scorer(...)`. Every run is then tracked automatically.

**Add an analysis** — write a pure function/module under `core/analysis/`, add its result to
`AnalysisReport`, compute it in `run_full_analysis`, and (optionally) feed it into
`assess_liabilities` / `score_objectives`. Add a test under `tests/`.

**Add a tab** — create a component under `ui/components/`, then register it in
`ui/app.py` (`_TAB_NAMES` / `_TAB_KEYS` + the `pn.Tabs` construction).

---

## 17. Scope & roadmap

**Today (prototype):** import & structured model · explainable QC/liability · multi-objective
candidate comparison · codon analysis · pluggable model scoring · run/version tracking ·
parts/assembly/generation. Demonstrates DBTL steps 1 (design), 2 (automated QC), and 4
(feedback/versioning).

**Not yet built:** wet-lab experimental testing (step 3, external by nature), automated
outcome ingestion and model retraining, NGS-scale ingestion, and structure-based
developability. These are the closed-loop and scale roadmap items.
