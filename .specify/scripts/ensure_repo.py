"""Clone/fetch repositories for platform code via SSH/HTTPS with locking."""

from __future__ import annotations

import fcntl
import logging
import shutil
import subprocess
from pathlib import Path

import yaml

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]


# ── Helpers ──────────────────────────────────────────────────────────


def _load_repo_binding(name: str) -> dict:
    """Read repo binding from platforms/<name>/platform.yaml."""
    manifest_path = REPO_ROOT / "platforms" / name / "platform.yaml"
    if not manifest_path.exists():
        raise SystemExit(f"ERROR: platforms/{name}/platform.yaml not found")

    with open(manifest_path) as f:
        manifest = yaml.safe_load(f)

    repo = manifest.get("repo")
    if not repo:
        raise SystemExit(f"ERROR: platform '{name}' has no repo: block in platform.yaml")

    org = repo.get("org")
    repo_name = repo.get("name")
    if not org or not repo_name:
        raise SystemExit(f"ERROR: platform '{name}' repo: block missing org or name")

    return {
        "org": org,
        "name": repo_name,
        "base_branch": repo.get("base_branch", "main"),
        "epic_branch_prefix": repo.get("epic_branch_prefix", f"epic/{name}/"),
    }


def _is_self_ref(repo_name: str) -> bool:
    """Return True if the repo is the madruga.ai repo itself."""
    return repo_name == "madruga.ai"


def _resolve_repos_base() -> Path:
    """Resolve the base directory for repositories."""
    try:
        import sys

        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from db import get_conn, get_local_config

        with get_conn() as conn:
            val = get_local_config(conn, "repos_base_dir")
        if val:
            return Path(val).expanduser()
    except Exception:
        log.debug("DB unavailable, using default repos_base_dir")
    return Path.home() / "repos"


# ── Main ─────────────────────────────────────────────────────────────


def ensure_repo(platform_name: str) -> Path:
    """Clone or fetch a platform's code repository. Returns local path."""
    binding = _load_repo_binding(platform_name)
    org = binding["org"]
    repo_name = binding["name"]

    # Self-referencing platform
    if _is_self_ref(repo_name):
        log.info("Self-ref platform '%s' → %s", platform_name, REPO_ROOT)
        return REPO_ROOT

    base = _resolve_repos_base()
    repo_path = base / org / repo_name
    log.info("Repo path: %s", repo_path)

    # Existing valid repo → fetch
    if repo_path.exists() and (repo_path / ".git").is_dir():
        log.info("Repo exists, fetching...")
        subprocess.run(
            ["git", "fetch", "--all", "--prune"],
            cwd=str(repo_path),
            check=True,
        )
        return repo_path

    # Partial clone (dir without .git) → remove and re-clone
    if repo_path.exists():
        log.warning("Partial clone detected at %s — removing", repo_path)
        shutil.rmtree(repo_path)

    # Ensure parent dir exists
    repo_path.parent.mkdir(parents=True, exist_ok=True)

    # Acquire per-repo lock
    lock_path = repo_path.parent / f"{repo_name}.lock"
    lock_file = open(lock_path, "w")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        log.info("Lock acquired: %s", lock_path)

        # Double-check after acquiring lock (another process may have cloned)
        if repo_path.exists() and (repo_path / ".git").is_dir():
            log.info("Repo appeared after lock — already cloned")
            return repo_path

        # Try SSH first
        ssh_url = f"git@github.com:{org}/{repo_name}.git"
        log.info("Cloning via SSH: %s", ssh_url)
        result = subprocess.run(
            ["git", "clone", ssh_url, str(repo_path)],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            # Fallback to HTTPS
            https_url = f"https://github.com/{org}/{repo_name}.git"
            log.warning("SSH failed, trying HTTPS: %s", https_url)
            subprocess.run(
                ["git", "clone", https_url, str(repo_path)],
                check=True,
            )

        log.info("Clone complete: %s", repo_path)
        return repo_path
    finally:
        fcntl.flock(lock_file, fcntl.LOCK_UN)
        lock_file.close()
        # Clean up lock file
        try:
            lock_path.unlink()
        except OSError:
            pass


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Ensure platform repo exists locally")
    parser.add_argument("platform", help="Platform name")
    parser.add_argument("-v", "--verbose", action="store_true", help="Debug logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )
    path = ensure_repo(args.platform)
    print(path)
