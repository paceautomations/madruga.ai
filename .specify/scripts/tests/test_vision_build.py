"""Tests for vision-build.py — LikeC4 model export and markdown table generation."""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the module using importlib since the filename contains a hyphen
import importlib

_vb = importlib.import_module("vision-build")

_containers_table = _vb._containers_table
_domains_table = _vb._domains_table
update_markdown = _vb.update_markdown
export_json = _vb.export_json
export_png = _vb.export_png
validate_model = _vb.validate_model


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _minimal_container_data(name="myapi", kind="api"):
    """Return a minimal LikeC4 JSON dict with one container element."""
    return {
        "elements": {
            f"platform.{name}": {
                "kind": kind,
                "title": name.capitalize(),
                "technology": "Python",
                "description": "A test container",
                "metadata": {"port": "8080"},
            }
        },
        "relations": {},
        "views": {},
    }


def _minimal_domain_data(bc_id="platform.orders", bc_title="Orders"):
    """Return a minimal LikeC4 JSON dict with one bounded context."""
    return {
        "elements": {
            bc_id: {
                "kind": "boundedContext",
                "title": bc_title,
                "description": "Manages orders",
                "tags": ["core"],
            }
        },
        "relations": {},
        "views": {},
    }


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


class TestContainersTable:
    """Test _containers_table() output."""

    def test_containers_table_minimal(self):
        data = _minimal_container_data(name="myapi", kind="api")
        result = _containers_table(data)

        assert isinstance(result, str)
        assert len(result) > 0
        assert "Myapi" in result
        assert "Python" in result
        assert "8080" in result
        # Must contain a markdown table header
        assert "| Container |" in result

    def test_containers_table_skips_bc_children(self):
        """Containers nested under a bounded context should be excluded."""
        data = {
            "elements": {
                "platform.orders": {"kind": "boundedContext", "title": "Orders"},
                "platform.orders.db": {
                    "kind": "database",
                    "title": "OrdersDB",
                    "technology": "PostgreSQL",
                    "description": "Order storage",
                    "metadata": {},
                },
                "platform.gateway": {
                    "kind": "proxy",
                    "title": "Gateway",
                    "technology": "Nginx",
                    "description": "Reverse proxy",
                    "metadata": {},
                },
            },
            "relations": {},
            "views": {},
        }
        result = _containers_table(data)
        # OrdersDB is under a BC — must be excluded
        assert "OrdersDB" not in result
        # Gateway is top-level — must be included
        assert "Gateway" in result


class TestDomainsTable:
    """Test _domains_table() output."""

    def test_domains_table_minimal(self):
        data = _minimal_domain_data(bc_id="platform.orders", bc_title="Orders")
        result = _domains_table(data)

        assert isinstance(result, str)
        assert len(result) > 0
        assert "Orders" in result
        assert "Core" in result
        # Must contain a markdown table header
        assert "| # | Domain |" in result

    def test_domains_table_pattern_in_title_no_duplication(self):
        """If the title already contains the pattern, don't duplicate it."""
        data = {
            "elements": {
                "platform.auth": {
                    "kind": "boundedContext",
                    "title": "Auth (Core)",
                    "description": "Authentication",
                    "tags": ["core"],
                },
            },
            "relations": {},
            "views": {},
        }
        result = _domains_table(data)
        # Should NOT produce "Auth (Core) (Core)"
        assert "(Core) (Core)" not in result
        assert "Auth (Core)" in result


class TestUpdateMarkdown:
    """Test update_markdown() round-trip."""

    def test_update_markdown_round_trip(self, tmp_path):
        md_file = tmp_path / "test.md"
        original = (
            "# Title\n\n"
            "Some intro text.\n\n"
            "<!-- AUTO:containers -->\n"
            "old content here\n"
            "<!-- /AUTO:containers -->\n\n"
            "Footer text.\n"
        )
        md_file.write_text(original)

        new_content = "| Container | Tech |\n|-----------|------|\n| MyAPI | Python |"
        result = update_markdown(md_file, "containers", new_content)

        assert result is True
        updated = md_file.read_text()
        assert "old content here" not in updated
        assert "MyAPI" in updated
        assert "Footer text." in updated
        assert "<!-- AUTO:containers -->" in updated
        assert "<!-- /AUTO:containers -->" in updated

    def test_update_markdown_missing_markers(self, tmp_path):
        md_file = tmp_path / "no_markers.md"
        md_file.write_text("# Title\n\nNo markers here.\n")

        result = update_markdown(md_file, "containers", "new content")
        assert result is False

    def test_update_markdown_nonexistent_file(self, tmp_path):
        missing = tmp_path / "does_not_exist.md"
        result = update_markdown(missing, "containers", "content")
        assert result is False


class TestExportJson:
    """Test export_json() with mocked subprocess."""

    def test_export_json_success(self, tmp_path):
        model_dir = tmp_path / "model"
        model_dir.mkdir()

        expected_data = {
            "elements": {"a": {"kind": "api"}},
            "relations": {},
            "views": {},
        }

        def side_effect(*args, **kwargs):
            # Simulate likec4 writing the output file
            out_file = model_dir / "output" / "likec4.json"
            out_file.parent.mkdir(exist_ok=True)
            out_file.write_text(json.dumps(expected_data))
            return subprocess.CompletedProcess(args=args[0], returncode=0)

        with patch.object(_vb.subprocess, "run", side_effect=side_effect) as mock_run:
            result = export_json(model_dir)

        assert result == expected_data
        mock_run.assert_called_once()


class TestExportPng:
    """Test export_png() with mocked subprocess."""

    def test_export_png_missing_cli(self, tmp_path):
        model_dir = tmp_path / "model"
        model_dir.mkdir()

        with patch.object(_vb.subprocess, "run", side_effect=FileNotFoundError("likec4 not found")):
            with pytest.raises(FileNotFoundError, match="likec4"):
                export_png(model_dir)


class TestValidateModel:
    """Test validate_model() with mocked subprocess."""

    def test_validate_model_nonzero_returncode(self, tmp_path):
        model_dir = tmp_path / "model"

        with patch.object(
            _vb.subprocess,
            "run",
            side_effect=subprocess.CalledProcessError(returncode=1, cmd=["likec4", "build", str(tmp_path)]),
        ):
            with pytest.raises(subprocess.CalledProcessError) as exc_info:
                validate_model(model_dir)

        assert exc_info.value.returncode == 1

    def test_validate_model_success(self, tmp_path):
        model_dir = tmp_path / "model"

        with patch.object(
            _vb.subprocess,
            "run",
            return_value=subprocess.CompletedProcess(args=["likec4", "build"], returncode=0),
        ) as mock_run:
            validate_model(model_dir)
            mock_run.assert_called_once()
