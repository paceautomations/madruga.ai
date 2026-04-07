"""
db.py — Re-export facade. Preserves `from db import X` compatibility.

Implementation has been split into focused modules:
  - db_core.py        — connection lifecycle, migration, FTS5 utilities
  - db_pipeline.py    — platform/pipeline CRUD, run tracking, gate management
  - db_decisions.py   — decisions/ADRs and memory entries
  - db_observability.py — traces, eval scores, stats, cleanup

New code should import directly from the appropriate submodule.

Usage (unchanged):
    from db import get_conn, migrate, upsert_platform, insert_decision, create_trace
    with get_conn() as conn:
        migrate(conn)
        upsert_platform(conn, 'prosauai', name='ProsaUAI', repo_path='platforms/prosauai')
"""

from db_core import *  # noqa: F401, F403
from db_pipeline import *  # noqa: F401, F403
from db_decisions import *  # noqa: F401, F403
from db_observability import *  # noqa: F401, F403
from db_pipeline import _is_valid_output, _EPIC_STATUS_MAP  # noqa: F401 — private re-exports for test access
from db_decisions import _parse_adr_markdown, _parse_memory_markdown  # noqa: F401 — private re-exports for test access
from db_core import _check_fts5  # noqa: F401 — private re-export for test access
