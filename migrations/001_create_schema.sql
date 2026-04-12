-- 001_create_schema.sql
-- Production Readiness (Epic 006): Schema isolation for Supabase compatibility.
--
-- Creates 4 schemas:
--   prosauai      — Business data (customers, conversations, messages, etc.)
--   prosauai_ops  — Operational helpers (RLS functions, migration tracking)
--   observability — Phoenix traces (managed by Phoenix, created empty)
--   admin         — Reserved for epic 013 (TenantStore Postgres)
--
-- Objects in auth/public schemas are NOT touched (Supabase-managed).

-- Extension in public schema (required by Supabase for uuid_generate_v4)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Business data schema
CREATE SCHEMA IF NOT EXISTS prosauai;

-- Operational helpers (RLS functions, migration tracking)
CREATE SCHEMA IF NOT EXISTS prosauai_ops;

-- Phoenix observability (managed by Phoenix — created empty here)
CREATE SCHEMA IF NOT EXISTS observability;

-- Admin (reserved for epic 013 — TenantStore Postgres)
CREATE SCHEMA IF NOT EXISTS admin;

-- RLS helper function (ADR-011 hardening)
-- Reads app.current_tenant_id set via SET LOCAL in the application layer.
CREATE OR REPLACE FUNCTION prosauai_ops.tenant_id()
RETURNS uuid
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
  SELECT current_setting('app.current_tenant_id', true)::uuid
$$;

-- Migration tracking table
CREATE TABLE IF NOT EXISTS prosauai_ops.schema_migrations (
    version    TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    checksum   TEXT
);
