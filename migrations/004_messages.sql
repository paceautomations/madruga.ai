-- 004_messages.sql
-- Messages table in prosauai schema — partitioned by RANGE(created_at) monthly.
--
-- PK is composite (id, created_at) because PG requires the partition key
-- in all unique constraints. UUID v4 guarantees practical global uniqueness.
-- FK from eval_scores.message_id is REMOVED — PG does not support FK
-- referencing a non-unique column in a partitioned table.

CREATE TYPE prosauai.message_direction AS ENUM ('inbound', 'outbound');

-- Set search_path so unqualified enum references resolve to prosauai schema
SET search_path TO prosauai, prosauai_ops, public;

CREATE TABLE prosauai.messages (
    id              UUID NOT NULL DEFAULT uuid_generate_v4(),
    tenant_id       UUID NOT NULL,
    conversation_id UUID NOT NULL REFERENCES prosauai.conversations(id),
    direction       message_direction NOT NULL,
    content         TEXT NOT NULL,
    content_type    VARCHAR(50) NOT NULL DEFAULT 'text',
    metadata        JSONB DEFAULT '{}',  -- trace_id, latency_ms, model, etc.
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

-- Index for RLS filter pushdown
CREATE INDEX idx_messages_tenant ON prosauai.messages(tenant_id);

-- Index for context window queries
CREATE INDEX idx_messages_conversation ON prosauai.messages(conversation_id, created_at);

ALTER TABLE prosauai.messages ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON prosauai.messages
    USING (tenant_id = prosauai_ops.tenant_id());

-- Append-only enforcement: DENY UPDATE/DELETE via policy
CREATE POLICY messages_append_only ON prosauai.messages
    FOR UPDATE USING (false);
CREATE POLICY messages_no_delete ON prosauai.messages
    FOR DELETE USING (false);

-- Initial partitions: current month + 2 future months
-- Using date_trunc to compute boundaries dynamically.
-- NOTE: These use DO blocks for dynamic SQL since partition bounds
-- must be literal values in DDL.
DO $$
DECLARE
    m INTEGER;
    start_date DATE;
    end_date DATE;
    part_name TEXT;
BEGIN
    FOR m IN 0..2 LOOP
        start_date := date_trunc('month', CURRENT_DATE)::date + (m || ' months')::interval;
        end_date := start_date + '1 month'::interval;
        part_name := 'prosauai.messages_' || to_char(start_date, 'YYYY_MM');

        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS %s PARTITION OF prosauai.messages FOR VALUES FROM (%L) TO (%L)',
            part_name, start_date, end_date
        );
    END LOOP;
END
$$;
