# mRNA Design Studio — Demo Script (one page)

**Live app:** https://offtargeteffect-mrna-design-studio.hf.space
**Login:** username `admin` · password `vOAMljsXrzCemLZK4A38` *(or remove the password for a smoother live demo — see Prep)*
**Open in its own browser tab** — not the Hugging Face embedded preview (that loops on login).

---

## Prep (do 5 min before)
- [ ] Visit the URL to **wake the Space** (free tier sleeps; first load is slow).
- [ ] Have the sample file ready to drag in: `demo/demo_sequences_extended.csv` (14 constructs).
- [ ] *(Optional)* For the live database demo, have the Postgres connection details on a sticky note.
- [ ] *(Optional)* Remove the login: Space → Settings → secrets → delete `MRNA_STUDIO_PASSWORD` → app opens with no login.

---

## The story — follow the sidebar top to bottom (~8–10 min)

**1. Import Data  (90s)** — "It ingests real-world sequence tables and structures them automatically."
- Drag `demo/demo_sequences_extended.csv` onto the CSV uploader.
- Show the **auto-suggested column mapping** (gene_name, cds, UTRs, …).
- Click **Import Records** → 14 sequences land in the Worklist.
- *Or* demo the **PostgreSQL** path: pick PostgreSQL, paste the connection details, Connect → select `mrna_sequences` → Preview → Import.

**2. Worklist → Analyze  (2 min)** — "Instant QC across the whole panel."
- Select all → **Analyze**.
- Point out **GC%**, **CAI** (codon adaptation), **homopolymer** runs (the poly-A tails!), **restriction sites**.
- Note the contrast: component-based vs monolithic records both analyze cleanly.

**3. Model Repository  (1 min)** — "Pluggable scoring — local models or remote APIs."
- Show the two built-in scorers: **mRNA Stability Scorer** and **RNA Structure Scorer**.
- Mention you can register a remote API endpoint too.

**4. Worklist → Score & Export  (2 min)** — "Rank candidates, hand off to the lab."
- Back on the Worklist, **Score** with a loaded model → **sort by score**.
- **Export CSV** of the ranked panel.

**5. Parts Workshop  (1 min)** — "A reusable parts library."
- Browse 5'UTR / Kozak / CDS / 3'UTR / poly-A parts; compose a construct.

**6. Assemble Plasmid → Generate Sequences  (2 min)** — "Close the loop."
- Pick the **pUC19-MCS** backbone, run **QC**, export the assembled construct.
- In **Generate Sequences**, produce a codon-optimized variant.

---

## If you have only 3 minutes
Import `demo/demo_sequences_extended.csv` → **Analyze** → **Score** → **Export.**
That's the whole value: ingest → analyze → score → export.

## Likely questions
- *"Where does the data live?"* → CSV/Excel upload or a PostgreSQL connection you provide.
- *"Can I use my own models?"* → Yes — register a local Python model or a remote API endpoint.
- *"Is it hosted?"* → Runs on Hugging Face Spaces (Docker); also runs locally with `make run`.
