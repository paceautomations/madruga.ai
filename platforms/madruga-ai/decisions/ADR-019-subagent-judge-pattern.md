---
title: "ADR-019: Subagent Paralelo + Judge Pattern para Review de Specs"
status: accepted
date: 2026-03-31
supersedes: ADR-007
decision: Usar Claude Code Agent tool (subagents paralelos) com 3 personas especializadas
  + 1 Judge pass para review multi-perspectiva de specs, plans, code e ADRs.
alternatives: Multi-persona debate engine custom (ADR-007), Claude Code Agent Teams
  (experimental), Single-pass review
rationale: Nativo do Claude Code (zero runtime custom), Judge filtra false positives
  (maior signal-to-noise), composable com pipeline gates existentes
---
# ADR-019: Subagent Paralelo + Judge Pattern para Review de Specs

## Status

Accepted — 2026-03-31. Supersedes [ADR-007](ADR-007-debate-engine.md).

## Contexto

Specs geradas por LLM em single-pass tendem a ter blind spots: edge cases ignorados, over-engineering, assuncoes nao validadas. ADR-007 propunha uma debate engine custom em Python com 3-5 reviewers sinteticos em rounds estruturados. Na pratica, Claude Code ja oferece o Agent tool nativo para subagents paralelos — capacidade provada no pipeline existente (Tier 3 adversarial auto-review em `pipeline-contract-base.md`, 4 subagents paralelos em `pm-discovery.md`). Construir um runtime Python custom para orquestrar debate duplica capacidade que ja existe nativamente.

Pesquisa de mercado (2026-03) identificou o **Judge Pattern** (validado pelo HubSpot em producao): apos coletar findings de multiplos reviewers, um "juiz" avalia cada finding por Accuracy, Actionability e Severity, filtrando noise. HubSpot reportou 90% reducao no tempo de review e 80% aprovacao dos engenheiros.

A decisao de nao migrar codigo de `general/` para `madruga.ai` elimina a premissa de "debate engine ja existe e esta testado". O approach correto e usar a capacidade nativa do Claude Code e construir apenas a camada de orquestracao minima.

## Decisao

Usar **Claude Code Agent tool** (subagents paralelos) com 3 personas especializadas + 1 Judge pass para review multi-perspectiva de specs, plans, code e ADRs.

**3 Personas (paralelas):**

| Persona | Foco | Exemplos de findings |
|---------|------|---------------------|
| **Architecture Reviewer** | Drift de ADRs, violacoes de blueprint, acoplamento, MECE | "Este servico viola ADR-004 (file-based storage)" |
| **Bug Hunter** | Edge cases, error handling, seguranca, null safety, OWASP | "SQL injection possivel na query sem sanitizacao" |
| **Simplifier** | Over-engineering, dead code, alternativas mais simples | "Este wrapper adiciona indirection sem valor" |

**1 Judge pass (sequencial, apos personas):**
- Recebe findings agregados de todas as personas
- Avalia cada finding em 3 criterios: **Accuracy** (o finding e factualmente correto?), **Actionability** (ha uma acao clara para resolver?), **Severity** (o impacto justifica atencao?)
- Filtra findings que falham em qualquer criterio
- Output final: JSON estruturado com severity levels (BLOCKER/WARNING/NIT)

**Integracao com pipeline gates:**
- `auto` gates: review executa automaticamente, findings integrados no report
- `human` gates: review apresentado para confirmacao humana
- `1-way-door` gates: todas as personas devem concordar (sem BLOCKERs divergentes)

## Alternativas Consideradas

### Alternativa A: Subagent Paralelo + Judge Pattern (escolhida)
- **Pros:** nativo do Claude Code (zero runtime custom), paralelo (3 subagents simultaneos), Judge filtra false positives (maior signal-to-noise que debate rounds), composable com pipeline gates existentes, custo previsivel (~4-5x single review), ja provado no pipeline (Tier 3, pm-discovery)
- **Cons:** depende do Agent tool do Claude Code (vendor lock-in), sem persistencia de rounds entre sessoes, custo de tokens (~$1-3 por review cycle completo)
- **Fit:** Alto — extensao direta do pattern existente, zero dependencias novas

### Alternativa B: Multi-persona debate engine custom — ADR-007 (rejeitada)
- **Pros:** controle total sobre personas, pesos, output, rounds estruturados com convergencia
- **Cons:** runtime Python custom desnecessario (duplica Agent tool), manutencao de prompts e agregacao, sem inter-agent debate real (cada persona revisa independente de qualquer forma), decisao de nao migrar de general/ elimina codigo existente
- **Rejeitada porque:** construir runtime custom quando a capacidade ja existe nativamente viola o principio de pragmatismo

### Alternativa C: Claude Code Agent Teams (rejeitada)
- **Pros:** inter-agent communication real (teammates debatem entre si), orquestracao nativa da Anthropic
- **Cons:** feature experimental (flag `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`, API pode mudar), todos rodam Opus (sem mix de modelos), orquestracao e black box (perde controle deterministico), nao scriptable (feature interativa, nao API headless), spawn lento (~20-30s por teammate)
- **Rejeitada porque:** nao scriptable em CI/pipeline automatizado, experimental, overkill para review task que e "embarrassingly parallel"

### Alternativa D: Single-pass review (rejeitada)
- **Pros:** rapido, barato (1 LLM call), simples
- **Cons:** uma perspectiva so — perde edge cases que outra persona encontraria, pesquisa Anthropic mostra multi-agent supera single-agent em ~90% em tasks complexas
- **Rejeitada porque:** qualidade insuficiente para specs que alimentam implementacao autonoma

## Consequencias

### Positivas
- Nativo do Claude Code — zero runtime Python custom para manter
- 3 subagents rodam em paralelo (Agent tool ja suporta)
- Judge pass filtra false positives — maior signal-to-noise que debate rounds (ADR-007)
- Composable com pipeline gates existentes (auto, human, 1-way-door, auto-escalate)
- Mesma mecanica funciona para specs, plans, code review, ADRs
- Custo previsivel: ~4-5x tokens de single review (~$1-3 por cycle)

### Negativas
- Vendor lock-in no Agent tool do Claude Code — se Anthropic mudar a API, precisa adaptar
- Sem persistencia de debate entre sessoes — cada review e stateless
- Judge pass adiciona 1 call extra (~2x tokens a mais vs sem judge)
- Calibracao do Judge requer 5-10 reviews manuais para tuning inicial

### Riscos
- Agent tool muda API entre versoes do Claude Code → mitigacao: adapter layer fino, monitorar changelogs
- False negatives (Judge filtra finding real) → mitigacao: threshold conservador no inicio, relaxar com calibracao
- Agent Teams amadurece e se torna GA → oportunidade: migrar camada de dispatch sem mudar arquitetura de personas + judge

## Referencias

- [Anthropic: Multi-Agent Research System](https://www.anthropic.com/engineering/multi-agent-research-system)
- [HubSpot: Automated Code Review — Judge Agent Pattern](https://product.hubspot.com/blog/automated-code-review-the-6-month-evolution)
- Supersedes: [ADR-007 — Multi-Persona Debate Engine](ADR-007-debate-engine.md)
- Pattern existente: `pipeline-contract-base.md` Tier 3 adversarial auto-review
- Pattern existente: `pm-discovery.md` 4 subagents paralelos
