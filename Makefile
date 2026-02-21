.PHONY: run run-debug kill restart db-up db-down db-status

VENV := .venv/bin
PORT := 5007
COMPOSE := docker compose -f demo/docker-compose.yml

# ── App ───────────────────────────────────────────────────────────────────────

# Start the app (INFO-level logging to terminal)
run:
	$(VENV)/python -m ui.app

# Start with DEBUG-level logging
run-debug:
	LOG_LEVEL=DEBUG $(VENV)/python -c "\
		import logging, sys, os; \
		logging.basicConfig(level=getattr(logging, os.environ.get('LOG_LEVEL','INFO')), \
			format='%(asctime)s [%(levelname)s] %(name)s: %(message)s', datefmt='%H:%M:%S', stream=sys.stderr); \
		from ui.app import main; main()"

# Kill anything running on the app port
kill:
	@lsof -ti:$(PORT) | xargs kill -9 2>/dev/null || echo "Nothing running on port $(PORT)"

# Kill + start fresh
restart: kill run

# ── Database ──────────────────────────────────────────────────────────────────

# Start the demo PostgreSQL database
db-up:
	$(COMPOSE) up -d
	@echo "Waiting for PostgreSQL to be ready..."
	@until docker exec mrna_studio_demo_db pg_isready -U demo_user -d mrna_studio >/dev/null 2>&1; do sleep 1; done
	@echo "PostgreSQL is ready on localhost:5432"

# Stop the demo database
db-down:
	$(COMPOSE) down

# Check database status
db-status:
	@docker ps --filter name=mrna_studio_demo_db --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || echo "Container not running"
