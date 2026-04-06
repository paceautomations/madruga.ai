# Makefile — madruga.ai task runner
# Usage: make <target>

PLATFORM := .specify/scripts/platform_cli.py

.PHONY: help test coverage lint ruff format status seed portal-dev portal-build \
       install-services up down restart logs logs-easter logs-portal

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-18s %s\n", $$1, $$2}'

test: ## Run Python tests
	python3 -m pytest .specify/scripts/tests/ -v

coverage: ## Run tests with coverage report
	python3 -m pytest .specify/scripts/tests/ -v --cov --cov-report=term-missing --cov-report=html
	@echo "Report HTML em htmlcov/index.html"

lint: ## Lint all platforms
	python3 $(PLATFORM) lint --all

ruff: ## Run ruff check on Python scripts
	python3 -m ruff check .specify/scripts/

ruff-fix: ## Run ruff fix on Python scripts
	python3 -m ruff check --fix .specify/scripts/

format: ## Run ruff format on Python scripts
	python3 -m ruff format .specify/scripts/

status: ## Show pipeline status for all platforms
	python3 $(PLATFORM) status --all

status-json: ## Export pipeline status as JSON
	python3 $(PLATFORM) status --all --json --output portal/src/data/pipeline-status.json

seed: ## Re-seed all platforms from filesystem
	python3 .specify/scripts/post_save.py --reseed-all

portal-dev: ## Start portal dev server
	cd portal && npm run dev

portal-build: ## Build portal for production
	cd portal && npm run build

portal-install: ## Install portal dependencies
	cd portal && npm install

# --- Service management (systemd) ---

SERVICES := madruga-easter madruga-portal
SERVICE_DIR := etc/systemd
USER_SYSTEMD := $(HOME)/.config/systemd/user

install-services: ## Install systemd user services (symlink + reload)
	@mkdir -p $(USER_SYSTEMD)
	@ln -sf $(CURDIR)/$(SERVICE_DIR)/madruga-easter.service $(USER_SYSTEMD)/
	@ln -sf $(CURDIR)/$(SERVICE_DIR)/madruga-portal.service $(USER_SYSTEMD)/
	@systemctl --user daemon-reload
	@echo "Services installed. Run 'make up' to start."

up: install-services ## Start all services (easter + portal)
	@systemctl --user start $(SERVICES)
	@echo "Started: $(SERVICES)"
	@systemctl --user --no-pager status $(SERVICES) | head -20

down: ## Stop all services
	@systemctl --user stop $(SERVICES) 2>/dev/null || true
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
