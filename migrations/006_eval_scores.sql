-- 006_eval_scores.sql
-- Eval scores table in prosauai schema with RLS via prosauai_ops.tenant_id()
--
-- NOTE: FK to messages(id) is intentionally REMOVED.
-- PG does not support UNIQUE(id) alone on a partitioned table (partition key
-- must be part of all unique constraints). Since messages uses composite PK
-- (id, created_at), we cannot create a FK referencing only id.
-- Integrity is guaranteed by UUID v4 collision probability (~1e-37) and
-- application-level validation before INSERT.

CREATE TABLE prosauai.eval_scores (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       UUID NOT NULL,
    conversation_id UUID NOT NULL REFERENCES prosauai.conversations(id),
    message_id      UUID,  -- App-level reference to messages(id), no FK constraint
    evaluator_type  VARCHAR(50) NOT NULL DEFAULT 'heuristic',  -- 'heuristic' | 'llm_judge'
    quality_score   FLOAT NOT NULL,  -- 0.0 - 1.0
    details         JSONB DEFAULT '{}',  -- {"checks": {"empty": false, "too_short": false, ...}}
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_eval_scores_tenant ON prosauai.eval_scores(tenant_id);
CREATE INDEX idx_eval_scores_conversation ON prosauai.eval_scores(conversation_id);

ALTER TABLE prosauai.eval_scores ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON prosauai.eval_scores
    USING (tenant_id = prosauai_ops.tenant_id());
