# Makefile — madruga.ai task runner
# Usage: make <target>

PLATFORM := .specify/scripts/platform.py

.PHONY: help test lint ruff status seed portal-dev portal-build

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-18s %s\n", $$1, $$2}'

test: ## Run Python tests
	python3 -m pytest .specify/scripts/tests/ -v

lint: ## Lint all platforms
	python3 $(PLATFORM) lint --all

ruff: ## Run ruff check on Python scripts
	python3 -m ruff check .specify/scripts/

ruff-fix: ## Run ruff fix on Python scripts
	python3 -m ruff check --fix .specify/scripts/

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
