-- 005_agents_prompts.sql
-- Agents and prompts tables in prosauai schema with RLS via prosauai_ops.tenant_id()

CREATE TABLE prosauai.agents (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id        UUID NOT NULL,
    name             VARCHAR(255) NOT NULL,
    config           JSONB NOT NULL DEFAULT '{}',  -- {"model": "openai:gpt-4o-mini", "temperature": 0.7, ...}
    active_prompt_id UUID,  -- FK added after prompts table is created
    enabled          BOOLEAN NOT NULL DEFAULT true,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_agents_tenant ON prosauai.agents(tenant_id);

ALTER TABLE prosauai.agents ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON prosauai.agents
    USING (tenant_id = prosauai_ops.tenant_id());

CREATE TABLE prosauai.prompts (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       UUID NOT NULL,
    agent_id        UUID NOT NULL REFERENCES prosauai.agents(id),
    version         VARCHAR(50) NOT NULL DEFAULT '1.0',
    system_prompt   TEXT NOT NULL,
    safety_prefix   TEXT NOT NULL DEFAULT '',  -- Sandwich pattern — start
    safety_suffix   TEXT NOT NULL DEFAULT '',  -- Sandwich pattern — end
    tools_enabled   JSONB DEFAULT '[]',  -- ["resenhai_rankings", ...]
    parameters      JSONB DEFAULT '{}',  -- {"max_tokens": 1000, "temperature": 0.7}
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_prompt_version UNIQUE (agent_id, version)
);

CREATE INDEX idx_prompts_tenant ON prosauai.prompts(tenant_id);
CREATE INDEX idx_prompts_agent ON prosauai.prompts(agent_id);

ALTER TABLE prosauai.prompts ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON prosauai.prompts
    USING (tenant_id = prosauai_ops.tenant_id());

-- Add FK from agents to prompts (circular dependency resolved via ALTER)
ALTER TABLE prosauai.agents ADD CONSTRAINT fk_agents_active_prompt
    FOREIGN KEY (active_prompt_id) REFERENCES prosauai.prompts(id);
