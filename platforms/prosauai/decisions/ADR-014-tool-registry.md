---
title: 'ADR-014: Tool Registry declarativo para extensibilidade multi-tenant'
status: Accepted
decision: Tool Registry declarativo
alternatives: Tools avulsas sem registro (status quo), Tool marketplace (modelo Botpress/n8n),
  Tools como microservices (modelo Salesforce)
rationale: Admin panel tem fonte de verdade para tools disponiveis — sem hardcode
  no frontend
---
# ADR-014: Tool Registry declarativo para extensibilidade multi-tenant
**Status:** Accepted | **Data:** 2026-03-25

## Contexto
ProsaUAI usa Agent-as-Data (ADR-006) onde tenants habilitam/desabilitam tools via config JSONB. Porem, sem um catalogo central de tools, o sistema nao sabe quais tools existem, quais parametros aceitam, quais integracoes externas requerem, ou quais categorias pertencem. O admin panel precisa de uma fonte de verdade para popular dropdowns e validar configs.

O research (multi-tenant-agents-mar2026.md, Secao 4.4) identificou o Tool Registry como gap #1 na arquitetura.

## Decisao
We will implementar um Tool Registry declarativo onde cada tool e registrada com metadata estruturada. O registry serve como catalogo central que alimenta:

1. **Admin panel** — dropdown de tools disponiveis por categoria
2. **Validacao** — ao salvar agent config, sistema checa se tools existem e se dependencias estao configuradas
3. **LLM context** — so tools habilitadas no agent config sao injetadas no prompt (anti-pattern #5: nunca tools globais)
4. **Documentacao** — cada tool auto-documenta seus params e descricao

### Estrutura do Registry

```python
@tool_registry.register(
    name="search_knowledge_base",
    description="Busca na knowledge base do tenant",
    category="knowledge",          # knowledge | communication | integration | internal
    required_params=["query"],
    optional_params=["top_k", "namespace"],
    requires_integration=None,     # None = built-in, disponivel pra todos
    agent_templates=["support_1v1", "group_responder", "sales"],  # templates compativeis
)
async def search_knowledge_base(ctx: ToolContext, query: str, top_k: int = 5):
    ...

@tool_registry.register(
    name="make_reservation",
    description="Faz reserva no restaurante",
    category="integration",
    required_params=["date", "time", "party_size"],
    requires_integration="restaurant_api",  # tenant precisa ter esta integracao configurada
    agent_templates=["scheduling"],
)
async def make_reservation(ctx: ToolContext, date: str, time: str, party_size: int):
    ...
```

### Fluxo de validacao

```
Tenant salva agent config com tools_enabled: ["search_kb", "make_reservation"]
    │
    ├─ Registry checa: "search_kb" existe? ✓
    ├─ Registry checa: "make_reservation" existe? ✓
    ├─ Registry checa: tenant tem integracao "restaurant_api"?
    │   └─ Se nao: erro com mensagem clara ("Tool 'make_reservation' requer integracao 'restaurant_api'")
    └─ Salva config ✓
```

### Faseamento
- **Fase 1-4:** ~5-10 tools built-in (search_kb, handoff, query_api, create_ticket, send_template). Registry existe no codigo mas com poucas entries. Admin hardcoda lista.
- **Fase 5+:** Registry formal com auto-discovery. Admin panel puxa lista dinamicamente. Validacao completa de dependencias. Possibilidade de tools custom por tenant (v3).

## Alternativas consideradas

### Tools avulsas sem registro (status quo)
- Pros: Zero overhead, funciona com poucas tools, rapido de implementar
- Cons: Admin panel nao sabe quais tools existem (hardcoda no frontend), sem validacao (tenant habilita tool que nao existe e descobre em runtime), sem metadata para categorizar/filtrar, nao escala alem de ~10 tools

### Tool marketplace (modelo Botpress/n8n)
- Pros: Extensibilidade maxima, terceiros contribuem tools, ecossistema
- Cons: Overengineering massivo para o momento, requer review/approval de tools de terceiros, seguranca complexa (sandboxing), time de 5 nao consegue manter marketplace

### Tools como microservices (modelo Salesforce)
- Pros: Isolamento total, deploy independente, escala horizontal por tool
- Cons: Complexidade operacional enorme (N servicos), latencia adicional (network hop por tool call), overkill para o volume esperado, custo de infra

## Consequencias
- [+] Admin panel tem fonte de verdade para tools disponiveis — sem hardcode no frontend
- [+] Validacao em tempo de config — erros pegos antes de chegar em runtime
- [+] Metadata permite filtrar tools por categoria, template, integracao — UX melhor no admin
- [+] Auto-documentacao — cada tool declara seus params e descricao
- [+] Base para extensibilidade futura (tools custom, marketplace) sem rewrite
- [-] Overhead de registrar cada tool com metadata (mitiga: ~5 tools na Fase 1, esforco minimo)
- [-] Decorator pattern pode ficar verboso com muitas tools (mitiga: YAML config como alternativa em v2)
- [-] Metadata desatualizada se dev muda tool sem atualizar registro (mitiga: testes que validam registry vs implementacao)

## Regras de seguranca (OWASP Agentic Top 10)

1. **Server-side tenant_id injection**: TODA tool que acessa dados recebe `tenant_id` injetado pelo runtime via `RunContext[TenantDeps]`. NUNCA confiar no que o LLM passa como parametro — previne confused deputy attacks
2. **Schema Pydantic estrito**: Nenhum parametro `Any` ou `dict` generico em tools. Cada tool tem modelo Pydantic com validators explicitos
3. **Tool call rate limiting**: Max N chamadas por tool por conversa (configuravel no registry metadata). Previne loops de tool call (ADR-016)
4. **Whitelist enforcement**: Runtime checa `tools_enabled` do agent config (ADR-006) antes de cada chamada — tool nao habilitada = exception, nunca fallback silencioso
