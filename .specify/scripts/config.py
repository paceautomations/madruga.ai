"""
config.py — Shared path constants and configuration for madruga.ai scripts.

Single source of truth for REPO_ROOT, DB_PATH, pricing, and other common settings.
"""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = REPO_ROOT / ".pipeline" / "madruga.db"
MIGRATIONS_DIR = REPO_ROOT / ".pipeline" / "migrations"
PLATFORMS_DIR = REPO_ROOT / "platforms"
TEMPLATE_DIR = REPO_ROOT / ".specify" / "templates" / "platform"
PORTAL_DIR = REPO_ROOT / "portal"

# Cost estimation — fallback pricing per token (USD) when claude doesn't report cost.
# Override via env vars when pricing changes.
SONNET_INPUT_PRICE = float(os.environ.get("MADRUGA_INPUT_PRICE_PER_TOKEN", "0.000003"))
SONNET_OUTPUT_PRICE = float(os.environ.get("MADRUGA_OUTPUT_PRICE_PER_TOKEN", "0.000015"))
