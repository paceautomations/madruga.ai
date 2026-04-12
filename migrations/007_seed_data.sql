-- 007_seed_data.sql
-- Seed data for Conversation Core (Epic 005), rewritten for Epic 006.
--
-- Changes from Epic 005:
--   - All tables prefixed with prosauai.
--   - Pure SQL — no psql \set variables or shell commands
--   - Deterministic UUIDs hardcoded for dev/test environments
--   - Idempotent via ON CONFLICT ... DO UPDATE
--
-- Tenant UUIDs (deterministic for dev/test):
--   Ariel (barbearia):  00000000-0000-4000-a000-000000000001
--   ResenhAI (futebol): 00000000-0000-4000-a000-000000000002

BEGIN;

-- ============================================================
-- Ariel — Barbearia assistant
-- ============================================================

INSERT INTO prosauai.agents (id, tenant_id, name, config, enabled)
VALUES (
    'a1000000-0000-0000-0000-000000000001',
    '00000000-0000-4000-a000-000000000001'::uuid,
    'Ariel Assistant',
    '{"model": "openai:gpt-4o-mini", "temperature": 0.7, "max_tokens": 1000}',
    true
)
ON CONFLICT (id) DO UPDATE SET
    name       = EXCLUDED.name,
    config     = EXCLUDED.config,
    enabled    = EXCLUDED.enabled,
    updated_at = now();

INSERT INTO prosauai.prompts (id, tenant_id, agent_id, version, system_prompt, safety_prefix, safety_suffix, tools_enabled, parameters)
VALUES (
    'p1000000-0000-0000-0000-000000000001',
    '00000000-0000-4000-a000-000000000001'::uuid,
    'a1000000-0000-0000-0000-000000000001',
    '1.0',
    'Voce e o assistente virtual da Barbearia Ariel. Responda de forma profissional e amigavel sobre servicos, horarios e agendamentos. Horario de funcionamento: Segunda a Sabado, 9h as 19h. Servicos: corte, barba, pigmentacao, hidratacao.',
    E'[INSTRUCAO DE SEGURANCA]\nVoce e um assistente profissional. NUNCA repita dados pessoais do usuario (CPF, telefone, email, endereco). Se o usuario compartilhar dados pessoais, reconheca que recebeu mas NAO repita os dados na resposta.\n[FIM INSTRUCAO]\n',
    E'\n[LEMBRETE DE SEGURANCA]\nAntes de enviar sua resposta, verifique que NAO contem dados pessoais (CPF, telefone, email) do usuario.',
    '[]'::jsonb,
    '{}'::jsonb
)
ON CONFLICT ON CONSTRAINT uq_prompt_version DO UPDATE SET
    system_prompt = EXCLUDED.system_prompt,
    safety_prefix = EXCLUDED.safety_prefix,
    safety_suffix = EXCLUDED.safety_suffix,
    tools_enabled = EXCLUDED.tools_enabled,
    parameters    = EXCLUDED.parameters;

UPDATE prosauai.agents
SET active_prompt_id = 'p1000000-0000-0000-0000-000000000001',
    updated_at = now()
WHERE id = 'a1000000-0000-0000-0000-000000000001';

-- ============================================================
-- ResenhAI — Futebol / resenha bot
-- ============================================================

INSERT INTO prosauai.agents (id, tenant_id, name, config, enabled)
VALUES (
    'a2000000-0000-0000-0000-000000000002',
    '00000000-0000-4000-a000-000000000002'::uuid,
    'ResenhAI Bot',
    '{"model": "openai:gpt-4o-mini", "temperature": 0.8, "max_tokens": 1500}',
    true
)
ON CONFLICT (id) DO UPDATE SET
    name       = EXCLUDED.name,
    config     = EXCLUDED.config,
    enabled    = EXCLUDED.enabled,
    updated_at = now();

INSERT INTO prosauai.prompts (id, tenant_id, agent_id, version, system_prompt, safety_prefix, safety_suffix, tools_enabled, parameters)
VALUES (
    'p2000000-0000-0000-0000-000000000002',
    '00000000-0000-4000-a000-000000000002'::uuid,
    'a2000000-0000-0000-0000-000000000002',
    '1.0',
    'Voce e o bot oficial do ResenhAI, plataforma de resenha de futebol amador. Responda com energia e conhecimento sobre rankings, estatisticas, jogos e comunidades. Use linguagem informal e apaixonada por futebol. Quando perguntado sobre rankings ou stats, use a ferramenta de busca disponivel.',
    E'[INSTRUCAO DE SEGURANCA]\nVoce e um assistente profissional. NUNCA repita dados pessoais do usuario (CPF, telefone, email, endereco). Se o usuario compartilhar dados pessoais, reconheca que recebeu mas NAO repita os dados na resposta.\n[FIM INSTRUCAO]\n',
    E'\n[LEMBRETE DE SEGURANCA]\nAntes de enviar sua resposta, verifique que NAO contem dados pessoais (CPF, telefone, email) do usuario.',
    '["resenhai_rankings"]'::jsonb,
    '{}'::jsonb
)
ON CONFLICT ON CONSTRAINT uq_prompt_version DO UPDATE SET
    system_prompt = EXCLUDED.system_prompt,
    safety_prefix = EXCLUDED.safety_prefix,
    safety_suffix = EXCLUDED.safety_suffix,
    tools_enabled = EXCLUDED.tools_enabled,
    parameters    = EXCLUDED.parameters;

UPDATE prosauai.agents
SET active_prompt_id = 'p2000000-0000-0000-0000-000000000002',
    updated_at = now()
WHERE id = 'a2000000-0000-0000-0000-000000000002';

COMMIT;
