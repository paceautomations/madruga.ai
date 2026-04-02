"""Tests for platform_cli.py status command."""

import json
import subprocess
import sys
from pathlib import Path


SCRIPTS_DIR = Path(__file__).parent.parent
REPO_ROOT = SCRIPTS_DIR.parent.parent


def run_status(*args: str) -> subprocess.CompletedProcess:
    """Run platform_cli.py status with given args."""
    return subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "platform_cli.py"), "status", *args],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )


class TestStatusTable:
    def test_single_platform(self):
        result = run_status("fulano")
        assert result.returncode == 0
        assert "Fulano" in result.stdout
        assert "L1 Progress:" in result.stdout
        assert "platform-new" in result.stdout

    def test_all_platforms(self):
        result = run_status("--all")
        assert result.returncode == 0
        assert "fulano" in result.stdout.lower() or "Fulano" in result.stdout
        assert "madruga" in result.stdout.lower()

    def test_unknown_platform(self):
        result = run_status("nonexistent-xyz")
        assert result.returncode == 1
        assert "not found" in result.stdout.lower() or "error" in result.stdout.lower()

    def test_no_args_defaults_to_all(self):
        result = run_status()
        assert result.returncode == 0
        # Should show all platforms when no args


class TestStatusJSON:
    def test_json_output_is_valid(self):
        result = run_status("--all", "--json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "generated_at" in data
        assert "platforms" in data
        assert isinstance(data["platforms"], list)
        assert len(data["platforms"]) > 0

    def test_json_schema_l1(self):
        result = run_status("--all", "--json")
        data = json.loads(result.stdout)
        for p in data["platforms"]:
            assert "id" in p
            assert "title" in p
            assert "lifecycle" in p
            assert "l1" in p
            l1 = p["l1"]
            assert "total" in l1
            assert "done" in l1
            assert "progress_pct" in l1
            assert "nodes" in l1
            for n in l1["nodes"]:
                assert "id" in n
                assert "status" in n
                assert "layer" in n
                assert "gate" in n
                assert "depends" in n
                assert isinstance(n["depends"], list)

    def test_json_schema_l2(self):
        result = run_status("--all", "--json")
        data = json.loads(result.stdout)
        for p in data["platforms"]:
            assert "l2" in p
            assert "epics" in p["l2"]
            for e in p["l2"]["epics"]:
                assert "id" in e
                assert "title" in e
                assert "nodes" in e

    def test_single_platform_json(self):
        result = run_status("fulano", "--json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert len(data["platforms"]) == 1
        assert data["platforms"][0]["id"] == "fulano"
