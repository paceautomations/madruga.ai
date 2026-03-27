---
title: "ADR-016: Agent Runtime Safety — hard limits, guardrails e loop prevention"
status: Accepted
decision: "Hard limits + guardrails"
alternatives: "Sem limites runtime"
rationale: "OWASP Agentic Top 10. Incidente $47K em 11d com agents em loop"
---
# ADR-016: Agent Runtime Safety — hard limits, guardrails e loop prevention
**Status:** Accepted | **Data:** 2026-03-25

## Contexto
Agentes AI operam com autonomia — uma vulnerabilidade que seria contida num LLM stateless vira cadeia de acoes de alto impacto quando o agente pode chamar tools, acessar dados e enviar mensagens. O OWASP Top 10 for Agentic Applications (Dez/2025) documenta riscos especificos:

- **Excessive Agency (#1)**: Agentes com mais permissoes do que precisam amplificam qualquer vulnerabilidade
- **Improper Tool/Function Calling**: Validacao insuficiente de parametros de tools
- **Tool Squatting**: Tools com nomes similares a tools legitimas que capturam chamadas

Incidentes reais:
- $47K em 11 dias com 4 agentes em loop infinito (LangChain, Nov/2025)
- RAG injection que vazou business intelligence de sistema enterprise (Jan/2025)
- Second-order injection no ServiceNow AI Assistant — agente low-privilege engana agente high-privilege (Nov/2025)

Sem protecoes de runtime, um unico tenant comprometido pode gerar custos descontrolados, vazar dados cross-tenant, ou enviar mensagens nao autorizadas via WhatsApp.

## Decisao
We will implementar safety em 4 camadas obrigatorias no agent runtime:

### 1. Hard Limits (safety net basica)

| Limite | Valor | Rationale |
|--------|-------|-----------|
| Max tool calls por conversa | 20 | Previne loops infinitos. Agentes consomem 4-15x mais tokens que chat |
| Timeout por agent execution | 60s | Previne agente preso em tool lenta ou loop |
| Max token context | 8K | Prompts maiores = injection mais eficaz + custo descontrolado |
| Max retries por tool | 3 | Apos 3 falhas, circuit breaker por tool nesta conversa |

Ao atingir qualquer limite: abortar execucao, responder com fallback amigavel ("Desculpe, nao consegui processar sua solicitacao. Vou transferir para um atendente."), e logar evento para diagnostico.

### 2. Guardrails em 3 Camadas

```
Mensagem do usuario
    │
    ▼
┌──────────────────────────────────────┐
│ Layer 1: Regex + Blocklist (<5ms)    │ ← TODA mensagem
│ - PII patterns (CPF, telefone, email)│
│ - Blocklist de topicos (por tenant)  │
│ - Input length limit (2K chars)      │
│ - Known injection patterns           │
└──────────────┬───────────────────────┘
               │ (se suspeito)
               ▼
┌──────────────────────────────────────┐
│ Layer 2: ML Classifier (~50ms)       │ ← mensagens flagged
│ - Injection detection (distilbert)   │
│ - Toxicity classification            │
│ - Sentiment analysis                 │
└──────────────┬───────────────────────┘
               │ (se high-risk action)
               ▼
┌──────────────────────────────────────┐
│ Layer 3: LLM-as-Judge (~200ms)       │ ← antes de tools destrutivos
│ - Avalia se tool call faz sentido    │
│ - Checa se output contem PII/secrets │
│ - Valida antes de enviar via WhatsApp│
└──────────────────────────────────────┘
```

Budget de latencia: max 100ms total para guardrails em mensagem normal de WhatsApp. Layer 2 e 3 so ativam quando necessario.

### 3. Loop Detection

| Mecanismo | Descricao | Acao |
|-----------|-----------|------|
| **Pattern detection** | Ultimas 3 tool calls identicas (mesmo tool + mesmos params) | Abort + notificar |
| **Semantic similarity** | Detecta reformulacao da mesma pergunta | Abort + sugerir handoff |
| **Circuit breaker por tool** | Tool X falha 3x seguidas | Desabilitar tool nesta conversa |
| **Budget tracking** | Custo acumulado > threshold do tenant | Pausar + pedir confirmacao |

### 4. Prompt Injection Mitigation

- **Sandwich pattern**: System prompt antes E depois do user input — instrucoes criticas repetidas apos contexto do usuario
- **Input sanitization**: Remover delimiters XML/markdown do input do usuario que possam confundir o LLM
- **Output scanning**: Antes de enviar via WhatsApp, checar se output contem: system prompt leakage, dados de outros tenants, API keys/tokens (regex para formatos comuns), instrucoes executaveis
- **Contexto isolado por tenant**: NUNCA compartilhar system prompts, historico, ou embeddings entre tenants (reforco ADR-011)

### 5. Tool Safety (complementa ADR-014)

- **Server-side tenant_id injection**: TODA tool que acessa dados recebe tenant_id injetado pelo runtime. NUNCA confiar no que o LLM passa como parametro
- **Schema Pydantic estrito**: Nenhum parametro `Any` ou `dict` generico. Cada tool tem modelo Pydantic com validators
- **Whitelist enforcement**: Runtime checa tools_enabled do agent config (ADR-006) antes de cada chamada
- **Evolution API safety**: Validar que tool calls de mensagem target apenas numeros associados ao tenant corrente

## Alternativas consideradas

### NeMo Guardrails (NVIDIA)
- Pros: 5 tipos de rails (input, dialog, retrieval, execution, output), metadata estruturado para compliance
- Cons: Adiciona 1 inference extra por prompt (custo + latencia), depende de LLM calls adicionais, infra pesada. Para WhatsApp bot v1, overhead nao justifica
- Decisao: Nao usar em v1. Reavaliar em v2 se volume justificar

### Sem guardrails (confiar no LLM)
- Pros: Zero overhead, menor complexidade
- Cons: Inaceitavel. Um prompt injection = mensagens nao autorizadas via WhatsApp, vazamento de dados cross-tenant, custo descontrolado. OWASP classifica como risco #1

### Guardrails apenas no output
- Pros: Mais simples, protege o canal de saida
- Cons: Nao previne tool calls maliciosos (injection pode chamar tool antes do output). Precisa proteger input E output

## Consequencias
- [+] Hard limits previnem cenarios catastroficos (loops, custo descontrolado)
- [+] Guardrails em camadas: overhead minimo para 95% das mensagens (<5ms), profundo apenas quando necessario
- [+] Loop detection previne o caso real de $47K em 11 dias
- [+] Server-side tenant_id injection elimina classe inteira de confused deputy attacks
- [+] Output scanning previne vazamento de PII e secrets via WhatsApp
- [-] Hard limits podem cortar conversas legitimas complexas (mitiga: limites generosos + handoff humano)
- [-] Regex Layer 1 tem falsos positivos e nao pega ataques sofisticados (mitiga: Layer 2 e 3 como fallback)
- [-] LLM-as-judge adiciona custo em acoes de alto risco (mitiga: so ativa para tools destrutivos, ~5% das mensagens)
- [-] Prompt injection nao tem solucao definitiva — apenas mitigacao. Planejar para breach: audit trail completo, blast radius limitado por tenant

## Referencias
- [OWASP Top 10 for Agentic Applications 2026](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/)
- [OWASP LLM01:2025 Prompt Injection](https://genai.owasp.org/llmrisk/llm01-prompt-injection/)
- [$47K Agent Loop Incident](https://rocketedge.com/2026/03/15/your-ai-agent-bill-is-30x-higher-than-it-needs-to-be-the-6-tier-fix/)
- [Vercel AI SDK — Agent Loop Control](https://ai-sdk.dev/docs/agents/loop-control)
