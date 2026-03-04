# ─────────────────────────────────────────────────────────────────────────────
#  mRNA Design Studio — Makefile
#
#  Quick start (from scratch, no Python required):
#    make setup        # one-time: installs uv, Python 3.13, and all deps
#    make run          # start the app → http://localhost:5007
# ─────────────────────────────────────────────────────────────────────────────
.PHONY: help setup run run-debug run-secure kill restart clean test lint \
        db-up db-down db-status docker-build docker-run

# ── OS detection ──────────────────────────────────────────────────────────────
# $(OS) is set to "Windows_NT" on Windows by the shell; empty on macOS/Linux.
ifeq ($(OS),Windows_NT)
    VENV_BIN := .venv/Scripts
else
    VENV_BIN := .venv/bin
endif

PYTHON  := $(VENV_BIN)/python
PORT    := 5007
URL     := http://localhost:$(PORT)
COMPOSE := docker compose -f demo/docker-compose.yml

# Where uv installs itself by default (used right after first install,
# before the user's shell has reloaded PATH).
UV_HOME := $(or $(XDG_BIN_HOME),$(HOME)/.local/bin)
UV      := $(shell command -v uv 2>/dev/null || echo "$(UV_HOME)/uv")

# ── Default target ────────────────────────────────────────────────────────────
help: ## Show available commands
	@echo ""
	@echo "  mRNA Design Studio"
	@echo "  ===================="
	@echo ""
	@echo "  First time?  Run:  make setup"
	@echo "  Then:              make run     →  $(URL)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'
	@echo ""

# ── Setup ─────────────────────────────────────────────────────────────────────
setup: _ensure-uv _ensure-venv _install-deps ## One-time setup: install Python, create venv, install deps
	@echo ""
	@echo "  Setup complete!"
	@echo "  Run 'make run' to start the app."
	@echo ""

_ensure-uv:
	@command -v uv >/dev/null 2>&1 && exit 0; \
	if [ -x "$(UV_HOME)/uv" ]; then exit 0; fi; \
	echo "Installing uv (fast Python package manager)..."; \
	curl -LsSf https://astral.sh/uv/install.sh | sh 2>/dev/null \
		|| { echo "curl failed — trying wget..."; \
		     wget -qO- https://astral.sh/uv/install.sh | sh; }; \
	if ! command -v uv >/dev/null 2>&1 && [ ! -x "$(UV_HOME)/uv" ]; then \
		echo ""; \
		echo "  ERROR: uv installed but not found in PATH."; \
		echo "  Restart your terminal, then re-run:  make setup"; \
		echo ""; \
		exit 1; \
	fi

_ensure-venv:
	@if [ ! -d ".venv" ]; then \
		echo "Creating virtual environment..."; \
		if command -v $(UV) >/dev/null 2>&1; then \
			$(UV) venv .venv --python 3.13; \
		else \
			python3 -m venv .venv; \
		fi; \
	fi

_install-deps:
	@echo "Installing dependencies..."
	@if command -v $(UV) >/dev/null 2>&1; then \
		$(UV) pip install -r requirements-dev.txt --python $(PYTHON) --quiet; \
	else \
		$(PYTHON) -m pip install -r requirements-dev.txt --quiet; \
	fi

# ── App ───────────────────────────────────────────────────────────────────────
run: _check-venv ## Start the app → http://localhost:5007
	$(PYTHON) -m ui.app

run-secure: _check-venv ## Start with password protection (.env must exist)
	@if [ ! -f .env ]; then \
		echo ""; \
		echo "  No .env file found. Copy the template first:"; \
		echo "    cp .env.example .env"; \
		echo "  Then set MRNA_STUDIO_PASSWORD in .env"; \
		echo ""; \
		exit 1; \
	fi
	MRNA_STUDIO_RELOAD=1 $(PYTHON) -m ui.app

run-debug: _check-venv ## Start with DEBUG-level logging
	LOG_LEVEL=DEBUG $(PYTHON) -c "\
		import logging, sys, os; \
		logging.basicConfig(level=getattr(logging, os.environ.get('LOG_LEVEL','INFO')), \
			format='%(asctime)s [%(levelname)s] %(name)s: %(message)s', datefmt='%H:%M:%S', stream=sys.stderr); \
		from ui.app import main; main()"

kill: ## Stop the app if it's running
ifeq ($(OS),Windows_NT)
	@powershell -Command \
		"Get-NetTCPConnection -LocalPort $(PORT) -ErrorAction SilentlyContinue \
		 | ForEach-Object { Stop-Process -Id $$_.OwningProcess -Force }" 2>/dev/null \
		|| echo "Nothing running on port $(PORT)"
else
	@lsof -ti:$(PORT) | xargs kill -9 2>/dev/null || echo "Nothing running on port $(PORT)"
endif

restart: kill run ## Kill + restart the app

# ── Dev tools ─────────────────────────────────────────────────────────────────
test: _check-venv ## Run the test suite
	$(PYTHON) -m pytest tests/ -v

lint: _check-venv ## Lint with ruff
	$(PYTHON) -m ruff check .

clean: ## Remove the virtual environment
	rm -rf .venv
	@echo "Removed .venv — run 'make setup' to recreate."

# ── Database ──────────────────────────────────────────────────────────────────
db-up: ## Start the demo PostgreSQL database
	$(COMPOSE) up -d
	@echo "Waiting for PostgreSQL to be ready..."
	@until docker exec mrna_studio_demo_db pg_isready -U demo_user -d mrna_studio >/dev/null 2>&1; do sleep 1; done
	@echo "PostgreSQL is ready on localhost:5432"

db-down: ## Stop the demo database
	$(COMPOSE) down

db-status: ## Check database container status
	@docker ps --filter name=mrna_studio_demo_db --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || echo "Container not running"

# ── Docker (production) ──────────────────────────────────────────────────────
docker-build: ## Build production Docker image
	docker build -t mrna-studio .

docker-run: ## Run container with .env file (password-protected)
	docker run --rm -p 5007:5007 --env-file .env mrna-studio

# ── Internal helpers ──────────────────────────────────────────────────────────
_check-venv:
	@if [ ! -d ".venv" ]; then \
		echo ""; \
		echo "  No virtual environment found."; \
		echo "  Run 'make setup' first."; \
		echo ""; \
		exit 1; \
	fi
