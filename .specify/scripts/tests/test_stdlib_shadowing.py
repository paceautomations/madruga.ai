"""Test that no script file shadows a Python stdlib module.

When scripts_dir is inserted into sys.path (as easter.py and conftest.py do),
a file named e.g. 'platform.py' would shadow stdlib 'platform', breaking
transitive imports like structlog -> uuid -> platform.

pytest masks this because it caches stdlib modules in sys.modules before
conftest injects the path. Only real process startup exposes the conflict.
"""

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent


def test_no_stdlib_shadowing():
    """No .py file in scripts/ shares a name with a stdlib module."""
    stdlib_names = sys.stdlib_module_names
    script_names = {p.stem for p in SCRIPTS_DIR.glob("*.py") if not p.name.startswith("_")}
    conflicts = script_names & stdlib_names
    assert not conflicts, (
        f"Script(s) shadow stdlib: {conflicts}. Rename to avoid import conflicts when scripts_dir is on sys.path."
    )


def test_no_stdlib_shadowing_in_subdirs():
    """No package dir in scripts/ shares a name with a stdlib module."""
    stdlib_names = sys.stdlib_module_names
    package_names = {p.name for p in SCRIPTS_DIR.iterdir() if p.is_dir() and (p / "__init__.py").exists()}
    conflicts = package_names & stdlib_names
    assert not conflicts, f"Package dir(s) shadow stdlib: {conflicts}. Rename to avoid import conflicts."
