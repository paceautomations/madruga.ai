-- 007_seed_data.sql
-- Seed data for Conversation Core (Epic 005)
--
-- Creates initial agents and prompts for the 2 tenants:
--   - Ariel (barbearia) — pace-internal
--   - ResenhAI (futebol) — resenha-internal
--
-- Tenant UUIDs are deterministic (UUID v5 namespace) so seed is idempotent.
-- These UUIDs MUST match the tenant_id used in app.current_tenant_id
-- when the application sets RLS context via SET LOCAL.
--
-- Usage:
--   ARIEL_TENANT_ID='<uuid>' RESENHAI_TENANT_ID='<uuid>' \
--     psql $DATABASE_URL -f migrations/007_seed_data.sql
--
-- If env vars are not set, falls back to deterministic default UUIDs.

-- Resolve tenant UUIDs from environment (psql \set + :'var' syntax)
-- Fallback: deterministic UUIDs for dev/test environments
\set ariel_tid     `echo "${ARIEL_TENANT_ID:-00000000-0000-4000-a000-000000000001}"`
\set resenhai_tid  `echo "${RESENHAI_TENANT_ID:-00000000-0000-4000-a000-000000000002}"`

BEGIN;

-- ============================================================
-- Ariel — Barbearia assistant
-- ============================================================

INSERT INTO agents (id, tenant_id, name, config, enabled)
VALUES (
    'a1000000-0000-0000-0000-000000000001',
    :'ariel_tid'::uuid,
    'Ariel Assistant',
    '{"model": "openai:gpt-4o-mini", "temperature": 0.7, "max_tokens": 1000}',
    true
)
ON CONFLICT (id) DO UPDATE SET
    name    = EXCLUDED.name,
    config  = EXCLUDED.config,
    enabled = EXCLUDED.enabled,
    updated_at = now();

INSERT INTO prompts (id, tenant_id, agent_id, version, system_prompt, safety_prefix, safety_suffix, tools_enabled, parameters)
VALUES (
    'p1000000-0000-0000-0000-000000000001',
    :'ariel_tid'::uuid,
    'a1000000-0000-0000-0000-000000000001',
    '1.0',
    'Você é o assistente virtual da Barbearia Ariel. Responda de forma profissional e amigável sobre serviços, horários e agendamentos. Horário de funcionamento: Segunda a Sábado, 9h às 19h. Serviços: corte, barba, pigmentação, hidratação.',
    E'[INSTRUÇÃO DE SEGURANÇA]\nVocê é um assistente profissional. NUNCA repita dados pessoais do usuário (CPF, telefone, email, endereço). Se o usuário compartilhar dados pessoais, reconheça que recebeu mas NÃO repita os dados na resposta.\n[FIM INSTRUÇÃO]\n',
    E'\n[LEMBRETE DE SEGURANÇA]\nAntes de enviar sua resposta, verifique que NÃO contém dados pessoais (CPF, telefone, email) do usuário.',
    '[]'::jsonb,
    '{}'::jsonb
)
ON CONFLICT ON CONSTRAINT uq_prompt_version DO UPDATE SET
    system_prompt = EXCLUDED.system_prompt,
    safety_prefix = EXCLUDED.safety_prefix,
    safety_suffix = EXCLUDED.safety_suffix,
    tools_enabled = EXCLUDED.tools_enabled,
    parameters    = EXCLUDED.parameters;

UPDATE agents
SET active_prompt_id = 'p1000000-0000-0000-0000-000000000001',
    updated_at = now()
WHERE id = 'a1000000-0000-0000-0000-000000000001';

-- ============================================================
-- ResenhAI — Futebol / resenha bot
-- ============================================================

INSERT INTO agents (id, tenant_id, name, config, enabled)
VALUES (
    'a2000000-0000-0000-0000-000000000002',
    :'resenhai_tid'::uuid,
    'ResenhAI Bot',
    '{"model": "openai:gpt-4o-mini", "temperature": 0.8, "max_tokens": 1500}',
    true
)
ON CONFLICT (id) DO UPDATE SET
    name    = EXCLUDED.name,
    config  = EXCLUDED.config,
    enabled = EXCLUDED.enabled,
    updated_at = now();

INSERT INTO prompts (id, tenant_id, agent_id, version, system_prompt, safety_prefix, safety_suffix, tools_enabled, parameters)
VALUES (
    'p2000000-0000-0000-0000-000000000002',
    :'resenhai_tid'::uuid,
    'a2000000-0000-0000-0000-000000000002',
    '1.0',
    'Você é o bot oficial do ResenhAI, plataforma de resenha de futebol amador. Responda com energia e conhecimento sobre rankings, estatísticas, jogos e comunidades. Use linguagem informal e apaixonada por futebol. Quando perguntado sobre rankings ou stats, use a ferramenta de busca disponível.',
    E'[INSTRUÇÃO DE SEGURANÇA]\nVocê é um assistente profissional. NUNCA repita dados pessoais do usuário (CPF, telefone, email, endereço). Se o usuário compartilhar dados pessoais, reconheça que recebeu mas NÃO repita os dados na resposta.\n[FIM INSTRUÇÃO]\n',
    E'\n[LEMBRETE DE SEGURANÇA]\nAntes de enviar sua resposta, verifique que NÃO contém dados pessoais (CPF, telefone, email) do usuário.',
    '["resenhai_rankings"]'::jsonb,
    '{}'::jsonb
)
ON CONFLICT ON CONSTRAINT uq_prompt_version DO UPDATE SET
    system_prompt = EXCLUDED.system_prompt,
    safety_prefix = EXCLUDED.safety_prefix,
    safety_suffix = EXCLUDED.safety_suffix,
    tools_enabled = EXCLUDED.tools_enabled,
    parameters    = EXCLUDED.parameters;

UPDATE agents
SET active_prompt_id = 'p2000000-0000-0000-0000-000000000002',
    updated_at = now()
WHERE id = 'a2000000-0000-0000-0000-000000000002';

COMMIT;

-- ============================================================
-- Verification query (informational — not part of migration)
-- ============================================================
-- SELECT a.name, a.tenant_id, a.config->>'model' AS model,
--        p.version, length(p.system_prompt) AS prompt_len,
--        p.tools_enabled
-- FROM agents a
-- JOIN prompts p ON p.id = a.active_prompt_id
-- ORDER BY a.name;
