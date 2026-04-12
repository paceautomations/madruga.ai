-- 003b_conversation_states.sql
-- Conversation states table in prosauai schema with RLS via prosauai_ops.tenant_id()

CREATE TABLE prosauai.conversation_states (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id         UUID NOT NULL,
    conversation_id   UUID NOT NULL REFERENCES prosauai.conversations(id) ON DELETE CASCADE,
    context_window    JSONB NOT NULL DEFAULT '[]',  -- Array of last N message summaries
    current_intent    VARCHAR(100) DEFAULT 'general',
    intent_confidence FLOAT DEFAULT 0.0,
    message_count     INT NOT NULL DEFAULT 0,
    token_count       INT NOT NULL DEFAULT 0,
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_conversation_state UNIQUE (conversation_id)
);

CREATE INDEX idx_conv_states_tenant ON prosauai.conversation_states(tenant_id);

ALTER TABLE prosauai.conversation_states ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON prosauai.conversation_states
    USING (tenant_id = prosauai_ops.tenant_id());
