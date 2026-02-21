# mRNA Design Studio

A browser-based workbench for designing, analyzing, and assembling mRNA sequences. Import sequence data from CSV files or PostgreSQL databases, run codon-usage and structural analyses, score sequences with pluggable models, assemble inserts into plasmid backbones with QC checks, and export results — all from a single reactive UI powered by Panel.

- **Import Data** — load sequences from CSV/Excel files or PostgreSQL, map columns to the mRNA model, and organize into worklists
- **Model Repository** — register local Python scoring/generative models or remote API endpoints
- **Worklist** — inspect, analyze (GC%, CAI, homopolymers, restriction sites), score with loaded models, and export sequences as CSV
- **Parts Workshop** — browse and compose reusable sequence parts (UTRs, Kozak, CDS, PolyA)
- **Assemble Plasmid** — pick a backbone and cloning strategy, run QC, and export assembled constructs
- **Generate Sequences** — create optimized mRNA variants with configurable generation settings

## Getting Started

The only prerequisite is a terminal with `make` and `curl` (both come pre-installed on macOS; on Windows use Git Bash or WSL). No Python install is required — the setup command handles everything.

```bash
git clone <repo-url> && cd mrna_design_studio

make setup   # installs uv, Python 3.13, and all dependencies (~1 min)
make run     # starts the app at http://localhost:5007
```

Run `make` by itself to see every available command:

```
make help

  setup          One-time setup: install Python, create venv, install deps
  run            Start the app
  run-debug      Start with DEBUG-level logging
  kill           Stop the app if it's running
  restart        Kill + restart the app
  test           Run the test suite
  lint           Lint with ruff
  clean          Remove the virtual environment
  db-up          Start the demo PostgreSQL database (requires Docker)
  db-down        Stop the demo database
  db-status      Check database container status
```

### Demo database (optional)

A Docker Compose file is included to spin up a PostgreSQL instance pre-loaded with sample mRNA sequences:

```bash
make db-up      # start the container
make run        # connect using the pre-filled credentials on the Import Data tab
make db-down    # stop when done
```
