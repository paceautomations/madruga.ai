-- 003_conversations.sql
-- Conversations table in prosauai schema with RLS via prosauai_ops.tenant_id()

CREATE TYPE conversation_status AS ENUM ('active', 'closed');
CREATE TYPE close_reason AS ENUM ('inactivity_timeout', 'user_closed', 'escalated', 'agent_closed');

CREATE TABLE prosauai.conversations (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id        UUID NOT NULL,
    customer_id      UUID NOT NULL REFERENCES prosauai.customers(id),
    agent_id         UUID NOT NULL,
    channel          VARCHAR(50) NOT NULL DEFAULT 'whatsapp',
    status           conversation_status NOT NULL DEFAULT 'active',
    close_reason     close_reason,
    started_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at        TIMESTAMPTZ,
    last_activity_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Invariante: Uma conversa ativa por customer/channel
CREATE UNIQUE INDEX idx_one_active_per_customer
    ON prosauai.conversations(tenant_id, customer_id, channel)
    WHERE status = 'active';

CREATE INDEX idx_conversations_tenant ON prosauai.conversations(tenant_id);
CREATE INDEX idx_conversations_customer ON prosauai.conversations(customer_id);
CREATE INDEX idx_conversations_last_activity ON prosauai.conversations(last_activity_at)
    WHERE status = 'active';

ALTER TABLE prosauai.conversations ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON prosauai.conversations
    USING (tenant_id = prosauai_ops.tenant_id());
