# mRNA Design Studio — Demo Script (full run-through)

**Live app:** https://offtargeteffect-mrna-design-studio.hf.space
**Login:** username `admin` · password `vOAMljsXrzCemLZK4A38`
**Open in its own browser tab** — NOT the Hugging Face embedded preview (that loops on login).

---

## 0. Prep (5 min before)
- [ ] Visit the URL to **wake the Space** (free tier sleeps; first load is slow). Log in once.
- [ ] Have the CSV ready to drag in: `demo/demo_sequences_extended.csv` (14 constructs).
- [ ] (Optional) Postgres path — keep these handy for the Import Data → PostgreSQL form:
      host `ep-blue-flower-abs3fw0x.eu-west-2.aws.neon.tech` · port `5432` · db `neondb`
      · user `neondb_owner` · pass `npg_oJzU6SfIK7yg` · table `mrna_sequences`
- [ ] (Optional) For a no-login live demo: delete the `MRNA_STUDIO_PASSWORD` secret in Space settings.

## The pitch (say this first, ~30s)
"This is a workbench that takes mRNA sequence data from import all the way to a
QC'd, scored, assembled construct — in one no-code UI. I'll walk the funnel:
**import → analyze & flag liabilities → compare candidates → score → track runs → assemble.**"

---

## 1. Import Data  (~90s)
- **[Click]** the **Import Data** tab.
- **CSV path:** drag `demo_sequences_extended.csv` onto the uploader → it **auto-suggests column mappings** (gene_name, cds, UTRs…) → **Import Records**.
- **OR Postgres path:** choose **PostgreSQL**, paste the connection details above, **Connect** → pick table `mrna_sequences` → **Preview** → **Import Records**.
- **[Say]** "It ingests messy real-world tables — component-based *or* monolithic — and maps them to a structured mRNA model automatically."

## 2. Worklist — analysis + liability/QC  (~3 min)  ★ NEW
- **[Click]** the **Worklist** tab → your 14 sequences are listed.
- **[Click]** the **Analysis** dropdown → **Base Analysis** → **Run**.
- **[Show]** the new columns populate: **GC%, CAI, Homopolymers, Restriction Sites**, and the new **QC** (`Pass/Review · score`) and **Liabilities** count.
- **[Click] a row** (e.g. `eGFP-hBG-HEK`) → a **Liability / QC breakdown** appears below the table:
  - a **QC scorecard** (0–100 score, Pass/Review/Fail verdict, severity counts),
  - a ranked list of **flags** with severity, detail, location, and a recommendation
    (e.g. internal restriction site, uORF in the 5′UTR, elevated uridine).
- **[Say]** "This is the developability/liability overlay — every candidate gets a QC
  score and specific, actionable flags, right on the candidate list."

## 3. Candidate Analysis  (~3 min)  ★ NEW
- **[Click]** the **Candidate Analysis** tab.
- **[Show]** the **Comparison scorecard** — every candidate scored 0–100 on the four mRNA
  objectives (**Expression, Stability, Immunogenicity, Manufacturability**) + an **Overall**,
  ranked, with a ★ **top-N shortlist** (drag the slider).
- **[Say]** "This is the design trade-off view — a candidate can win on expression but lose
  on immunogenicity. You rank and shortlist on the criteria that actually matter for mRNA."
- **[Use]** the **Inspect candidate** dropdown → the **Sequence / structure map** shows that
  molecule's region bands (5′UTR/CDS/3′UTR/polyA), GC profile, and markers for restriction
  sites / homopolymers / liability motifs — i.e. *where* the problems are — plus its full
  liability scorecard.
- **[Say]** "And drill into any candidate to see exactly where its features and liabilities sit."

## 4. Model Repository  (~1 min)
- **[Click]** the **Model Repository** tab → browse models; note each has a **version**.
- **[Show]** the two built-in scorers: **mRNA Stability Scorer** and **RNA Structure Scorer**
  (and that you can register a local Python model or a remote API endpoint).

## 5. Score the worklist  (~1 min)
- **[Click]** back to **Worklist** → **Analysis** dropdown → pick a model
  (e.g. **mRNA Stability Scorer**) → **Run**.
- **[Show]** a score column appears; sort by it to rank candidates. **Export CSV** for the lab.
- (Run a *second* model too — e.g. RNA Structure Scorer — so you have two runs to compare next.)

## 6. Experiments — run history + comparison  (~2 min)  ★ NEW
- **[Click]** the **Experiments** tab.
- **[Show]** **Registered models** (with versions) and a **Run history** table — every scoring
  run is logged with version, N, mean/range of scores, and timestamp.
- **[Use]** the **Compare runs** dropdowns (Run A baseline → Run B) → a summary shows
  **mean Δ, ▲ improved / ▼ worsened** counts and a per-sequence delta table.
- **[Say]** "This is the lifecycle layer: track every scoring run and compare versions or
  scorers to see exactly which candidates moved and by how much."

## 7. Parts Workshop → Assemble → Generate  (~2 min)
- **Parts Workshop:** browse reusable parts (5′UTR / Kozak / CDS / 3′UTR / poly-A) and compose.
- **Assemble Plasmid:** pick the **pUC19-MCS** backbone, run **QC**, export the assembled construct.
- **Generate Sequences:** produce a codon-optimized variant.
- **[Say]** "Close the loop — assemble into a plasmid with QC, or generate optimized variants."

---

## If you only have 3 minutes
Import `demo_sequences_extended.csv` → **Worklist** Run base analysis → click a row for the
**liability breakdown** → **Candidate Analysis** scorecard + map → score a model → **Experiments** compare.
That hits the four differentiators (QC liability, candidate comparison, scoring, experiment tracking).

## Likely questions
- *"Where does data live?"* → CSV/Excel upload or a PostgreSQL connection you provide.
- *"Custom models?"* → register a local Python model or a remote API endpoint; runs are tracked.
- *"How is this like/unlike ENPICOM?"* → same no-code, data+AI philosophy; this is the
  design/build + light-liability side (mRNA), not NGS-scale repertoire discovery. See
  `demo/ENPICOM_gap_analysis.md`.
- *"Is it hosted?"* → runs on Hugging Face Spaces (Docker); also runs locally with `make run`.
