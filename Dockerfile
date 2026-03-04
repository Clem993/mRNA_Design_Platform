# ─────────────────────────────────────────────────────────────────────────────
#  mRNA Design Studio — production container
#
#  Build:  docker build -t mrna-studio .
#  Run:    docker run -p 5007:5007 -e MRNA_STUDIO_PASSWORD=changeme mrna-studio
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.13-slim AS base

# Prevent Python from buffering stdout/stderr (makes logs visible immediately)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# ── Install system deps (needed by some bioinformatics packages) ─────────────
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc g++ libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# ── Install Python deps (cached layer — only rebuilds when requirements change)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Copy application code ────────────────────────────────────────────────────
COPY . .

# ── Runtime ──────────────────────────────────────────────────────────────────
# Railway, Render, Fly etc. set $PORT automatically
ENV PORT=5007 \
    HOST=0.0.0.0

EXPOSE ${PORT}

CMD ["python", "-m", "ui.app"]
