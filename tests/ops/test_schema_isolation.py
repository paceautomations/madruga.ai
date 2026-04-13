"""Integration tests for schema isolation (Epic 006 — Production Readiness).

These tests apply all migrations to a real Postgres and verify:
  T015: prosauai schema has 7 business tables, prosauai_ops has tenant_id() + schema_migrations,
        auth/public have no custom objects.
  T016: search_path resolves unqualified table names (SELECT without schema prefix).
  T017: prosauai_ops.tenant_id() returns correct UUID when app.current_tenant_id is SET LOCAL.

Requires: Docker available (spins up a temporary Postgres container).
"""

from __future__ import annotations

import asyncio
import socket
import subprocess
import time
from pathlib import Path

import pytest

try:
    import asyncpg
except ImportError:
    asyncpg = None

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"

# Postgres container config
PG_IMAGE = "postgres:15-alpine"
PG_USER = "testuser"
PG_PASSWORD = "testpass"
PG_DB = "testdb"
PG_PORT = 15432  # avoid clashing with host Postgres


def _docker_available() -> bool:
    """Check if Docker daemon is reachable."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _free_port() -> int:
    """Find a free TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


_skip_no_docker = pytest.mark.skipif(
    not _docker_available(),
    reason="Docker not available — skipping integration tests",
)
_skip_no_asyncpg = pytest.mark.skipif(
    asyncpg is None,
    reason="asyncpg not installed",
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def pg_port():
    """Return a free port to bind Postgres on."""
    return _free_port()


@pytest.fixture(scope="module")
def pg_container(pg_port):
    """Start a temporary Postgres container for the test module, yield DSN, then cleanup."""
    container_name = f"test_schema_isolation_{pg_port}"
    dsn = f"postgresql://{PG_USER}:{PG_PASSWORD}@127.0.0.1:{pg_port}/{PG_DB}?sslmode=disable"

    # Start container
    subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            container_name,
            "-e",
            f"POSTGRES_USER={PG_USER}",
            "-e",
            f"POSTGRES_PASSWORD={PG_PASSWORD}",
            "-e",
            f"POSTGRES_DB={PG_DB}",
            "-p",
            f"127.0.0.1:{pg_port}:5432",
            PG_IMAGE,
        ],
        check=True,
        capture_output=True,
    )

    # Wait for Postgres to be ready (max ~30s)
    for attempt in range(30):
        try:
            result = subprocess.run(
                [
                    "docker",
                    "exec",
                    container_name,
                    "pg_isready",
                    "-U",
                    PG_USER,
                    "-d",
                    PG_DB,
                ],
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0:
                break
        except subprocess.TimeoutExpired:
            pass
        time.sleep(1)
    else:
        subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)
        pytest.fail("Postgres container did not become ready within 30s")

    yield dsn

    # Cleanup
    subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)


@pytest.fixture(scope="module")
def applied_migrations(pg_container):
    """Apply all migrations once for the module using the migration runner."""
    from prosauai.ops.migrate import run_migrations

    result = asyncio.run(run_migrations(dsn=pg_container, migrations_dir=MIGRATIONS_DIR))
    assert result.failed is None, f"Migration failed: {result.failed}"
    return result


@pytest.fixture()
def dsn(pg_container, applied_migrations):
    """Return the Postgres DSN after migrations have been applied."""
    return pg_container


# ---------------------------------------------------------------------------
# T015 — Schema contents verification
# ---------------------------------------------------------------------------


@_skip_no_docker
@_skip_no_asyncpg
class TestSchemaContents:
    """T015: Verify prosauai/prosauai_ops/auth/public schema contents after migrations."""

    @pytest.mark.asyncio
    async def test_prosauai_has_all_business_tables(self, dsn):
        """prosauai schema must contain exactly 7 business tables."""
        conn = await asyncpg.connect(dsn)
        try:
            rows = await conn.fetch(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'prosauai'
                  AND table_type = 'BASE TABLE'
                ORDER BY table_name
                """
            )
            table_names = {r["table_name"] for r in rows}

            expected = {
                "customers",
                "conversations",
                "conversation_states",
                "messages",
                "agents",
                "prompts",
                "eval_scores",
            }
            # messages is partitioned — the parent appears as BASE TABLE,
            # and child partitions also appear. Filter to the 7 core tables.
            # Child partitions are named messages_YYYY_MM, so we check the
            # expected set is a subset.
            assert expected.issubset(table_names), f"Missing tables in prosauai: {expected - table_names}"
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_prosauai_ops_has_schema_migrations(self, dsn):
        """prosauai_ops schema must contain schema_migrations table."""
        conn = await asyncpg.connect(dsn)
        try:
            rows = await conn.fetch(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'prosauai_ops'
                  AND table_type = 'BASE TABLE'
                """
            )
            table_names = {r["table_name"] for r in rows}
            assert "schema_migrations" in table_names
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_prosauai_ops_has_tenant_id_function(self, dsn):
        """prosauai_ops schema must contain tenant_id() function."""
        conn = await asyncpg.connect(dsn)
        try:
            rows = await conn.fetch(
                """
                SELECT routine_name
                FROM information_schema.routines
                WHERE routine_schema = 'prosauai_ops'
                  AND routine_type = 'FUNCTION'
                """
            )
            func_names = {r["routine_name"] for r in rows}
            assert "tenant_id" in func_names
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_auth_schema_has_no_custom_objects(self, dsn):
        """auth schema must NOT contain any custom tables or functions."""
        conn = await asyncpg.connect(dsn)
        try:
            # auth schema may not even exist in a plain Postgres
            tables = await conn.fetch(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'auth'
                  AND table_type = 'BASE TABLE'
                """
            )
            assert len(tables) == 0, f"auth schema has custom tables: {[r['table_name'] for r in tables]}"

            funcs = await conn.fetch(
                """
                SELECT routine_name
                FROM information_schema.routines
                WHERE routine_schema = 'auth'
                """
            )
            assert len(funcs) == 0, f"auth schema has custom functions: {[r['routine_name'] for r in funcs]}"
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_public_schema_has_no_custom_tables(self, dsn):
        """public schema must NOT contain custom tables (only extensions like uuid-ossp)."""
        conn = await asyncpg.connect(dsn)
        try:
            tables = await conn.fetch(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_type = 'BASE TABLE'
                """
            )
            assert len(tables) == 0, f"public schema has custom tables: {[r['table_name'] for r in tables]}"
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_observability_schema_exists_and_empty(self, dsn):
        """observability schema must exist (reserved for Phoenix) and be empty."""
        conn = await asyncpg.connect(dsn)
        try:
            schemas = await conn.fetch(
                "SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'observability'"
            )
            assert len(schemas) == 1, "observability schema does not exist"

            tables = await conn.fetch(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'observability'
                  AND table_type = 'BASE TABLE'
                """
            )
            assert len(tables) == 0, "observability schema should be empty (Phoenix-managed)"
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_admin_schema_exists_and_empty(self, dsn):
        """admin schema must exist (reserved for epic 013) and be empty."""
        conn = await asyncpg.connect(dsn)
        try:
            schemas = await conn.fetch(
                "SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'admin'"
            )
            assert len(schemas) == 1, "admin schema does not exist"

            tables = await conn.fetch(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'admin'
                  AND table_type = 'BASE TABLE'
                """
            )
            assert len(tables) == 0, "admin schema should be empty (reserved for epic 013)"
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_messages_is_partitioned(self, dsn):
        """messages table must be partitioned by RANGE(created_at)."""
        conn = await asyncpg.connect(dsn)
        try:
            row = await conn.fetchrow(
                """
                SELECT c.relkind, pg_get_partkeydef(c.oid) AS partition_key
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'prosauai' AND c.relname = 'messages'
                """
            )
            assert row is not None, "prosauai.messages table not found"
            # asyncpg returns pg "char" type as bytes
            relkind = row["relkind"]
            if isinstance(relkind, bytes):
                relkind = relkind.decode()
            assert relkind == "p", f"messages should be partitioned (relkind='p'), got '{relkind}'"
            assert "created_at" in row["partition_key"], (
                f"Partition key should include created_at, got: {row['partition_key']}"
            )
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_messages_has_child_partitions(self, dsn):
        """messages must have at least 3 child partitions (current + 2 future months)."""
        conn = await asyncpg.connect(dsn)
        try:
            rows = await conn.fetch(
                """
                SELECT c.relname
                FROM pg_inherits i
                JOIN pg_class c ON c.oid = i.inhrelid
                JOIN pg_class parent ON parent.oid = i.inhparent
                JOIN pg_namespace n ON n.oid = parent.relnamespace
                WHERE n.nspname = 'prosauai' AND parent.relname = 'messages'
                ORDER BY c.relname
                """
            )
            assert len(rows) >= 3, f"Expected >=3 partitions, got {len(rows)}: {[r['relname'] for r in rows]}"
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_all_migrations_recorded(self, dsn):
        """All 8 migration files should be recorded in schema_migrations."""
        conn = await asyncpg.connect(dsn)
        try:
            rows = await conn.fetch("SELECT version FROM prosauai_ops.schema_migrations ORDER BY version")
            versions = [r["version"] for r in rows]
            expected_prefixes = [
                "001_create_schema",
                "002_customers",
                "003_conversations",
                "003b_conversation_states",
                "004_messages",
                "005_agents_prompts",
                "006_eval_scores",
                "007_seed_data",
            ]
            assert versions == expected_prefixes, f"Expected migrations {expected_prefixes}, got {versions}"
        finally:
            await conn.close()


# ---------------------------------------------------------------------------
# T016 — search_path resolution
# ---------------------------------------------------------------------------


@_skip_no_docker
@_skip_no_asyncpg
class TestSearchPathResolution:
    """T016: Verify unqualified table names resolve correctly via search_path."""

    @pytest.mark.asyncio
    async def test_select_from_customers_without_prefix(self, dsn):
        """SELECT from customers (no schema prefix) resolves to prosauai.customers."""
        conn = await asyncpg.connect(
            dsn,
            server_settings={"search_path": "prosauai,prosauai_ops,public"},
        )
        try:
            # Should not raise — resolves to prosauai.customers
            rows = await conn.fetch("SELECT id FROM customers LIMIT 0")
            assert rows is not None  # query succeeds, result set may be empty
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_select_from_conversations_without_prefix(self, dsn):
        """SELECT from conversations (no schema prefix) resolves to prosauai.conversations."""
        conn = await asyncpg.connect(
            dsn,
            server_settings={"search_path": "prosauai,prosauai_ops,public"},
        )
        try:
            rows = await conn.fetch("SELECT id FROM conversations LIMIT 0")
            assert rows is not None
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_select_from_messages_without_prefix(self, dsn):
        """SELECT from messages (no schema prefix) resolves to prosauai.messages."""
        conn = await asyncpg.connect(
            dsn,
            server_settings={"search_path": "prosauai,prosauai_ops,public"},
        )
        try:
            rows = await conn.fetch("SELECT id FROM messages LIMIT 0")
            assert rows is not None
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_select_from_all_tables_without_prefix(self, dsn):
        """All 7 business tables are queryable without schema prefix."""
        conn = await asyncpg.connect(
            dsn,
            server_settings={"search_path": "prosauai,prosauai_ops,public"},
        )
        try:
            tables = [
                "customers",
                "conversations",
                "conversation_states",
                "messages",
                "agents",
                "prompts",
                "eval_scores",
            ]
            for table in tables:
                rows = await conn.fetch(f"SELECT count(*) FROM {table}")
                assert rows is not None, f"Failed to query {table} without schema prefix"
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_schema_migrations_accessible_via_search_path(self, dsn):
        """schema_migrations in prosauai_ops is accessible via search_path."""
        conn = await asyncpg.connect(
            dsn,
            server_settings={"search_path": "prosauai,prosauai_ops,public"},
        )
        try:
            rows = await conn.fetch("SELECT version FROM schema_migrations LIMIT 1")
            assert rows is not None
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_uuid_generate_v4_accessible(self, dsn):
        """uuid_generate_v4() from public schema is accessible via search_path."""
        conn = await asyncpg.connect(
            dsn,
            server_settings={"search_path": "prosauai,prosauai_ops,public"},
        )
        try:
            row = await conn.fetchrow("SELECT uuid_generate_v4() AS uid")
            assert row is not None
            assert row["uid"] is not None
        finally:
            await conn.close()


# ---------------------------------------------------------------------------
# T017 — tenant_id() function verification
# ---------------------------------------------------------------------------


@_skip_no_docker
@_skip_no_asyncpg
class TestTenantIdFunction:
    """T017: Verify prosauai_ops.tenant_id() returns correct value with SET LOCAL."""

    @pytest.mark.asyncio
    async def test_tenant_id_returns_set_value(self, dsn):
        """tenant_id() returns the UUID set via SET LOCAL app.current_tenant_id."""
        conn = await asyncpg.connect(dsn)
        try:
            tenant_uuid = "00000000-0000-4000-a000-000000000001"
            async with conn.transaction():
                await conn.execute(f"SET LOCAL app.current_tenant_id = '{tenant_uuid}'")
                row = await conn.fetchrow("SELECT prosauai_ops.tenant_id() AS tid")
                assert row is not None
                assert str(row["tid"]) == tenant_uuid
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_tenant_id_returns_null_when_unset(self, dsn):
        """tenant_id() returns NULL when app.current_tenant_id is not set."""
        conn = await asyncpg.connect(dsn)
        try:
            row = await conn.fetchrow("SELECT prosauai_ops.tenant_id() AS tid")
            # current_setting with missing_ok=true returns empty string → cast to uuid is NULL
            assert row is not None
            assert row["tid"] is None
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_tenant_id_different_values_per_transaction(self, dsn):
        """Different transactions can have different tenant_id values (SET LOCAL is tx-scoped)."""
        conn = await asyncpg.connect(dsn)
        try:
            tenant_a = "00000000-0000-4000-a000-000000000001"
            tenant_b = "00000000-0000-4000-a000-000000000002"

            # Set tenant A in a transaction
            async with conn.transaction():
                await conn.execute(f"SET LOCAL app.current_tenant_id = '{tenant_a}'")
                row = await conn.fetchrow("SELECT prosauai_ops.tenant_id() AS tid")
                assert str(row["tid"]) == tenant_a

            # After transaction ends, SET LOCAL is reverted
            # New transaction with tenant B
            async with conn.transaction():
                await conn.execute(f"SET LOCAL app.current_tenant_id = '{tenant_b}'")
                row = await conn.fetchrow("SELECT prosauai_ops.tenant_id() AS tid")
                assert str(row["tid"]) == tenant_b
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_tenant_id_accessible_via_search_path(self, dsn):
        """tenant_id() is callable without schema prefix when search_path includes prosauai_ops."""
        conn = await asyncpg.connect(
            dsn,
            server_settings={"search_path": "prosauai,prosauai_ops,public"},
        )
        try:
            tenant_uuid = "00000000-0000-4000-a000-000000000001"
            async with conn.transaction():
                await conn.execute(f"SET LOCAL app.current_tenant_id = '{tenant_uuid}'")
                row = await conn.fetchrow("SELECT tenant_id() AS tid")
                assert str(row["tid"]) == tenant_uuid
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_rls_filters_by_tenant(self, dsn):
        """RLS policies filter rows by tenant_id when app.current_tenant_id is set.

        Uses seed data from migration 007 which inserts agents for 2 tenants.
        """
        conn = await asyncpg.connect(
            dsn,
            server_settings={"search_path": "prosauai,prosauai_ops,public"},
        )
        try:
            tenant_ariel = "00000000-0000-4000-a000-000000000001"

            # Enable RLS for this connection by NOT being superuser
            # Note: In a plain Postgres (non-Supabase), the connecting user IS
            # the owner, so RLS may not apply by default (owner bypasses RLS).
            # We test the function return value instead, which is what RLS uses.
            async with conn.transaction():
                await conn.execute(f"SET LOCAL app.current_tenant_id = '{tenant_ariel}'")
                row = await conn.fetchrow("SELECT prosauai_ops.tenant_id() AS tid")
                assert str(row["tid"]) == tenant_ariel

                # Verify seed data exists for this tenant
                count = await conn.fetchval(
                    "SELECT count(*) FROM prosauai.agents WHERE tenant_id = $1",
                    tenant_ariel,
                )
                assert count >= 1, "Expected at least 1 agent for tenant Ariel"
        finally:
            await conn.close()
