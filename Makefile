# Makefile — madruga.ai task runner
# Usage: make <target>

PLATFORM := .specify/scripts/platform_cli.py

.PHONY: help test coverage lint ruff ruff-fix format ci status status-json seed recover \
       portal-dev portal-build portal-install install-hooks \
       install-services up down restart logs logs-easter logs-portal

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-18s %s\n", $$1, $$2}'

test: ## Run Python tests (excludes slow git-subprocess tests)
	MADRUGA_DISPATCH=0 python3 -m pytest .specify/scripts/tests/ -v -m "not slow"

test-full: ## Run all tests including slow git-subprocess tests
	MADRUGA_DISPATCH=0 python3 -m pytest .specify/scripts/tests/ -v

coverage: ## Run tests with coverage report
	MADRUGA_DISPATCH=0 python3 -m pytest .specify/scripts/tests/ -v --cov --cov-report=term-missing --cov-report=html
	@echo "HTML report at htmlcov/index.html"

lint: ## Lint all platforms + validate YAML frontmatter in platform docs
	python3 $(PLATFORM) lint --all
	python3 .specify/scripts/validate_frontmatter.py

ruff: ## Run ruff check on Python scripts
	python3 -m ruff check .specify/scripts/

ruff-fix: ## Run ruff fix on Python scripts
	python3 -m ruff check --fix .specify/scripts/

format: ## Run ruff format on Python scripts
	python3 -m ruff format .specify/scripts/

ci: ## Run local CI checks (lint + tests)
	bash .specify/scripts/bash/ci-checks.sh

status: ## Show pipeline status for all platforms
	python3 $(PLATFORM) status --all

status-json: ## Export pipeline status as JSON
	python3 $(PLATFORM) status --all --json --output portal/src/data/pipeline-status.json

seed: ## Re-seed all platforms from filesystem (recreates madruga.db from canonical sources)
	python3 .specify/scripts/seed.py

seed-force: ## Drop madruga.db (+wal/-shm) and re-seed from scratch
	python3 .specify/scripts/seed.py --force

recover: ## Recover historical data from git-archived DB snapshot
	python3 .specify/scripts/recover_db.py

portal-dev: ## Start portal dev server
	cd portal && npm run dev

portal-build: ## Build portal for production
	cd portal && npm run build

portal-install: ## Install portal dependencies
	cd portal && npm install

install-hooks: ## Install git hooks (post-commit traceability)
	@mkdir -p .git/hooks
	@cp .specify/scripts/git-hooks/post-commit .git/hooks/post-commit
	@chmod +x .git/hooks/post-commit
	@echo "Installed post-commit hook."

# --- Service management (systemd) ---

SERVICES := madruga-easter madruga-portal
PORTS := 4321 18789
SERVICE_DIR := etc/systemd
USER_SYSTEMD := $(HOME)/.config/systemd/user

install-services: ## Install systemd user services (symlink + reload)
	@mkdir -p $(USER_SYSTEMD)
	@ln -sf $(CURDIR)/$(SERVICE_DIR)/madruga-easter.service $(USER_SYSTEMD)/
	@ln -sf $(CURDIR)/$(SERVICE_DIR)/madruga-portal.service $(USER_SYSTEMD)/
	@systemctl --user daemon-reload
	@echo "Services installed. Run 'make up' to start."

_pre-up-clean:
	@for svc in $(SERVICES); do \
	  if systemctl --user is-active --quiet $$svc; then \
	    echo "Detected running service $$svc — cleaning up first..."; \
	    exec $(MAKE) --no-print-directory down; \
	  fi; \
	done; \
	for port in $(PORTS); do \
	  if [ -n "$$(lsof -ti :$$port 2>/dev/null)" ]; then \
	    echo "Detected stale process on port $$port — cleaning up first..."; \
	    exec $(MAKE) --no-print-directory down; \
	  fi; \
	done; \
	echo "Nothing running — proceeding to start."

up: _pre-up-clean install-services ## Start all services (easter + portal). Auto-cleans if anything is already running.
	@systemctl --user start $(SERVICES)
	@echo "Started: $(SERVICES)"
	@systemctl --user --no-pager status $(SERVICES) | head -20

down: ## Stop all services and free their ports (idempotent, fails loud if a port stays held)
	@systemctl --user stop $(SERVICES) 2>/dev/null
	@waited=0; \
	while [ $$waited -lt 8 ]; do \
	  any_active=0; \
	  for svc in $(SERVICES); do \
	    systemctl --user is-active --quiet $$svc && any_active=1; \
	  done; \
	  [ "$$any_active" = "0" ] && break; \
	  sleep 1; waited=$$((waited+1)); \
	done
	@for port in $(PORTS); do \
	  pids="$$(lsof -ti :$$port 2>/dev/null)"; \
	  if [ -n "$$pids" ]; then \
	    echo "Port $$port held by PIDs: $$pids — sending SIGTERM"; \
	    kill $$pids 2>/dev/null || true; \
	    sleep 2; \
	    survivors="$$(lsof -ti :$$port 2>/dev/null)"; \
	    if [ -n "$$survivors" ]; then \
	      echo "Port $$port still held by $$survivors — sending SIGKILL"; \
	      kill -9 $$survivors 2>/dev/null || true; \
	      sleep 1; \
	    fi; \
	    final="$$(lsof -ti :$$port 2>/dev/null)"; \
	    if [ -n "$$final" ]; then \
	      echo "ERROR: port $$port still held by PIDs $$final after SIGKILL" >&2; \
	      exit 1; \
	    fi; \
	    echo "Port $$port freed."; \
	  fi; \
	done
	@echo "Stopped: $(SERVICES)"

restart: ## Restart all services
	@systemctl --user restart $(SERVICES)
	@echo "Restarted: $(SERVICES)"
	@systemctl --user --no-pager status $(SERVICES) | head -20

logs: ## Tail logs from all services
	@journalctl --user -u madruga-easter -u madruga-portal -f --no-hostname

logs-easter: ## Tail easter logs only
	@journalctl --user -u madruga-easter -f --no-hostname

logs-portal: ## Tail portal logs only
	@journalctl --user -u madruga-portal -f --no-hostname
