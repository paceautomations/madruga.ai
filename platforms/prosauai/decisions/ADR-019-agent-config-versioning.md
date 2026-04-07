---
title: 'ADR-019: Versionamento de Agent Config com Canary Rollout'
status: Accepted
decision: Config versioning + canary traffic split
alternatives: All-or-nothing (status quo), Feature flags externo (LaunchDarkly, Unleash),
  Shadow mode (executa ambas, retorna so active)
rationale: Mudancas de prompt com rede de seguranca — canary detecta regressao antes
  de afetar 100%
---
# ADR-019: Versionamento de Agent Config com Canary Rollout
**Status:** Accepted | **Data:** 2026-03-27

## Contexto

ADR-006 (Agent-as-Data) define agentes como configuracao JSONB e menciona "A/B testing com golden dataset antes de mudar prompts". ADR-009 (Human-Gated Flywheel) define revisao semanal de prompts com gate humano. Porem, **nenhum define o mecanismo** de como versionar configs, fazer rollout progressivo, ou comparar performance entre versoes.

Sem isso, mudanca de prompt e all-or-nothing: ou aplica pra 100% do trafego ou nao aplica. Se a mudanca causar regressao, 100% dos usuarios sao afetados ate o rollback manual.

Inspirado pelo pattern de Agent Graphs da LaunchDarkly — onde configs de agentes sao alteradas sem deploy e com metricas por node — este ADR define o mecanismo interno de canary para agent configs.

## Decisao

We will implementar versionamento de agent configs com canary rollout progressivo e comparacao automatica de eval scores.

### Modelo

```sql
CREATE TABLE agent_config_versions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    agent_id        UUID NOT NULL REFERENCES agents(id),
    version         INT NOT NULL,
    config_snapshot JSONB NOT NULL,
    system_prompt   TEXT NOT NULL,
    change_summary  TEXT,
    status          TEXT NOT NULL DEFAULT 'draft'
                    CHECK (status IN ('draft', 'canary', 'active', 'rolled_back')),
    traffic_pct     INT NOT NULL DEFAULT 0
                    CHECK (traffic_pct >= 0 AND traffic_pct <= 100),
    eval_baseline   JSONB,
    eval_current    JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    promoted_at     TIMESTAMPTZ,
    rolled_back_at  TIMESTAMPTZ,
    UNIQUE (agent_id, version)
);

ALTER TABLE agent_config_versions ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON agent_config_versions USING (tenant_id = auth.tenant_id());
CREATE INDEX idx_acv_agent ON agent_config_versions (agent_id, status);
CREATE INDEX idx_acv_tenant ON agent_config_versions (tenant_id);

-- Referencia na tabela agents
ALTER TABLE agents ADD COLUMN active_version_id UUID REFERENCES agent_config_versions(id);
```

### Ciclo de vida de uma versao

```
draft → canary → active
  │        │
  │        └→ rolled_back (se eval_current < eval_baseline)
  └→ (descartada, nunca ativada)
```

1. **draft**: Operador cria nova versao no admin com mudancas de prompt/config. Nao recebe trafego.
2. **canary**: Operador ativa canary com `traffic_pct` (default 10%). Parte do trafego usa esta versao.
3. **active**: Apos eval scores confirmarem melhoria (margem configurable, default +0.05), operador promove. Versao anterior vira historico.
4. **rolled_back**: Se eval scores piorarem ou operador decidir reverter, canary volta a draft/rolled_back. Trafego retorna 100% para versao active.

### Fluxo no pipeline (M8 Agent)

```
M8 recebe request
  → Busca agent_id do tenant
  → SELECT active + canary versions WHERE agent_id = X AND status IN ('active', 'canary')
  → Se existe canary:
      random(0-100) <= canary.traffic_pct → usa canary config
      senao → usa active config
  → Se nao existe canary:
      usa active config
  → Executa agente com config selecionado
  → Tag no LangFuse trace: config_version_id = versao usada
  → eval_scores vinculados ao config_version_id
```

### Comparacao de eval scores

```json
// eval_baseline (snapshot da versao active no momento do canary)
{
  "relevance": 0.82,
  "faithfulness": 0.88,
  "toxicity": 0.02,
  "sample_size": 1500
}

// eval_current (acumulado durante canary)
{
  "relevance": 0.85,
  "faithfulness": 0.87,
  "toxicity": 0.01,
  "sample_size": 120
}
```

Regra de promocao: `eval_current[metric] >= eval_baseline[metric] - margem` para TODAS as metricas. `sample_size` minimo configurable (default 50 conversas).

### Invariantes

1. **Apenas 1 versao `active` por agent** — constraint logica enforced no app layer
2. **No maximo 1 versao `canary` por agent** — nao permite multiplos canaries simultaneos
3. **`traffic_pct` da canary + active sempre soma 100** — enforced no app layer ao ativar canary
4. **Rollback e imediato** — canary → rolled_back, active mantem 100%
5. **`config_snapshot` e imutavel** — editar cria nova versao, nunca modifica existente
6. **Minimum sample size** antes de promover — evita decisoes com dados insuficientes
7. **Historico completo** — versoes rolled_back e antigas nunca deletadas, auditoria total

## Alternativas consideradas

### All-or-nothing (status quo)
- Pros: Simples, sem complexidade de routing, sem tabela extra
- Cons: 100% do trafego afetado por mudanca ruim, rollback manual, sem comparacao de performance, contradiz a promessa do ADR-006 de A/B testing

### Feature flags externo (LaunchDarkly, Unleash)
- Pros: Tooling maduro, UI pronta, integracao com metricas
- Cons: Dependencia externa, custo adicional, overkill para config de agentes (que ja sao data-driven no banco), duplica source of truth (config no Supabase + flags no LaunchDarkly)

### Shadow mode (executa ambas, retorna so active)
- Pros: Zero risco para usuario, comparacao perfeita
- Cons: Dobra custo de LLM (executa 2x por request), complexidade de implementacao alta, latencia adicional

## Consequencias

- [+] Mudancas de prompt com rede de seguranca — canary detecta regressao antes de afetar 100%
- [+] Comparacao objetiva via eval scores — decisao baseada em dados, nao gut feeling
- [+] Historico completo de versoes — auditoria e rollback a qualquer momento
- [+] Complementa ADR-009 (flywheel): revisao semanal agora tem mecanismo de deploy gradual
- [+] Sem dependencia externa — tudo no Supabase, consistente com stack existente
- [-] Complexidade no M8 — precisa de lookup de 2 versoes e random routing
- [-] Eval scores precisam de volume minimo — canary lento em tenants com pouco trafego
- [-] Admin panel precisa de UI para gerenciar versoes (cabe no epic 007)

## Referencias

- ADR-006: Agent-as-Data (define JSONB config, menciona A/B)
- ADR-008: Eval Stack (DeepEval + Promptfoo — fonte dos eval scores)
- ADR-009: Human-Gated Flywheel (cadencia semanal de revisao)
- LaunchDarkly Agent Graphs: inspiracao para config changes sem deploy + metricas por node
