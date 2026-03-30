"""
config.py — Shared path constants for madruga.ai scripts.

Single source of truth for REPO_ROOT, DB_PATH, and other common paths.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = REPO_ROOT / ".pipeline" / "madruga.db"
MIGRATIONS_DIR = REPO_ROOT / ".pipeline" / "migrations"
PLATFORMS_DIR = REPO_ROOT / "platforms"
TEMPLATE_DIR = REPO_ROOT / ".specify" / "templates" / "platform"
PORTAL_DIR = REPO_ROOT / "portal"
