---
title: "Vision"
updated: 2026-04-02
sidebar:
  order: 1
---
# Madruga AI — Business Vision

## 1. Tese & Aspiracao

Documentacao de arquitetura, especificacao de features e implementacao vivem dispersas em repos, skills e scripts sem contexto compartilhado. O resultado e previsivel: architectural drift, specs sem contexto macro, e documentacao que vira ficcao em semanas.

**Madruga AI** e um repositorio dedicado que funciona como pipeline unico onde arquitetura alimenta especificacoes, implementacao fecha o loop, e um easter executa autonomamente. A plataforma transforma o ciclo `pitch -> spec -> plan -> tasks -> implement -> reconcile` em um processo determinístico, rastreavel e progressivamente autonomo.

**North Star Metric:** Percentual de epics processados autonomamente (pitch-to-PR sem intervencao humana). Hoje: 0%. Meta 6 meses: 80%.

**Diferencial estrutural:** Nenhuma ferramenta existente conecta documentacao arquitetural, especificacao de features e execucao autonoma em um unico pipeline git-versionado. Madruga AI e o unico sistema onde a documentacao arquitetural (Mermaid inline em .md) alimenta diretamente o pipeline de especificacao (SpecKit), que alimenta execucao autonoma (Easter), que retroalimenta a arquitetura (RECONCILE).

---

## 2. Where to Play

### Mercado

Times de engenharia de software (1-20 engenheiros) que precisam manter documentacao arquitetural sincronizada com codigo e especificacoes de features. Foco inicial em plataformas digitais multi-tenant com complexidade moderada a alta.

**TAM:** Todo time de engenharia que sofre com architectural drift.
**SAM:** Times que ja usam Claude Code e documentam arquitetura em git.
**SOM:** Plataformas internas da Pace Automations (ProsaUAI, futuras plataformas).

### Cliente-alvo

- **Primario:** O proprio time Pace Automations — Gabriel Hamu como arquiteto/operator, usando Madruga AI para documentar e construir todas as plataformas da empresa.
- **Secundario:** Desenvolvedores solo ou times pequenos que adotam Claude Code e querem um framework de documentacao arquitetural com pipeline spec-to-code.

### Personas

| Persona | O que faz | O que ganha | Jornada principal |
|---------|-----------|-------------|-------------------|
| **Arquiteto / Tech Lead** | Documenta visao, especifica features, delega execucao ao agente autonomo | Arquitetura sempre atualizada, specs com contexto macro, execucao sem overhead | Documenta → especifica → delega → revisa PR |
| **Revisor** | Valida PRs gerados pelo agente, aprova decisoes irreversiveis | Contexto completo de cada mudanca, rastreabilidade spec→codigo | Recebe PR → ve contexto e diff → aprova ou ajusta |
| **Membro do Time** | Consulta arquitetura, entende decisoes, navega diagramas | Portal unico, diagramas interativos, decisoes pesquisaveis | Abre portal → navega plataforma → entende |

### Segmentos prioritarios

1. **Plataformas internas Pace:** ProsaUAI (WhatsApp agents), proximas plataformas em pipeline.
2. **Projetos greenfield:** Onde a estrutura pode ser adotada desde o inicio.
3. **Projetos brownfield:** Onde a documentacao precisa ser retroativamente construida e mantida sincronizada.

### Onde NAO jogamos

- **NÃO e IDE** — documenta e especifica, nao escreve codigo de producao diretamente.
- **NÃO e CI/CD** — nao faz deploy, nao gerencia infra, nao substitui GitHub Actions.
- **NÃO e project management tool** — nao substitui Linear, Jira ou Notion para tracking operacional.
- **NÃO e developer portal generico** — nao compete com Backstage para service catalog.

---

## 3. How to Win

### Moat estrutural

1. **Mermaid-inline pipeline:** Diagramas Mermaid vivem inline nos proprios `.md` de arquitetura — contexto visual junto com prosa, zero tooling extra (ADR-020). GitHub, Starlight e qualquer viewer Markdown renderiza nativamente.
2. **Skills reutilizaveis:** As mesmas skills (`speckit.*` e `madruga/*`) funcionam tanto interativamente (humano invoca) quanto autonomamente (easter invoca via `SpeckitBridge`). Zero reescrita.
3. **File-based + git-versionado:** Todo estado vive em arquivos git. Sem banco externo para documentacao, sem SaaS para specs. Diff, blame, revert — tudo funciona nativamente.
4. **RECONCILE loop:** Apos implementacao, o sistema compara o diff do PR com a arquitetura e auto-atualiza quando o drift e baixo. Nenhuma ferramenta existente fecha esse loop.
5. **Template system (Copier):** Novas plataformas herdam a mesma estrutura, e `copier update` sincroniza mudancas estruturais. Escala sem overhead.

### Capabilities necessarias

| Capability | Status | Criticidade |
|------------|--------|-------------|
| Platform CLI (scaffold, lint, sync) | Funcional | Alta |
| Mermaid inline diagrams + astro-mermaid | Funcional | Alta |
| Portal Starlight com auto-discovery | Funcional | Alta |
| SpecKit pipeline (specify, plan, tasks) | Funcional (interativo + autonomo) | Alta |
| DAG Executor + compose_skill_prompt | Funcional — execucao autonoma do pipeline via dag_executor.py | Alta |
| Easter 24/7 (FastAPI + asyncio) | Funcional — processo persistente, health checks, systemd | Alta |
| Subagent Judge (4 personas + 1 juiz) | Funcional — review multi-perspectiva (ADR-019) | Media |
| RECONCILE loop | Funcional — 9 categorias de drift, diffs concretos | Media |
| Codebase Mapping (`speckit.map`) | Planejado | Media |

### Pricing (se aplicavel)

Uso interno — sem pricing externo. Custo operacional: consumo de API Claude (circuit breaker com throttle configuravel).

---

## 4. O que e sucesso

| Metrica | Hoje | 6 meses | 12 meses |
|---------|------|---------|----------|
| Plataformas documentadas | 2 (ProsaUAI + Madruga AI) | 5+ | 10+ |
| Epics processados autonomamente | 0% (tooling pronto, falta end-to-end com ProsaUAI) | 80% | 95% |
| Architectural drift detection | Auto-detect (reconcile 9 categorias) | Auto-fix (drift < 0.3) | Auto-fix continuo |
| Time-to-spec (pitch → spec.md) | ~1h (semi-autonomo com skills) | ~30min autonomo | ~15min autonomo |
| Skills disponiveis | 24 (13 L1 + 11 L2) | 26+ (+ observability, codebase map) | 30+ |
| Cobertura Vision (artefatos preenchidos) | 100% Madruga AI, ~60% ProsaUAI | 95%+ por plataforma | 100% com auto-sync |

---

## 5. Principios inegociaveis

1. **Mermaid-inline** — Diagramas Mermaid inline nos `.md` sao a source of truth visual (ADR-020). Prosa e diagrama vivem juntos, sem tooling externo.
2. **Skills reutilizaveis** — Mesma skill funciona interativa e autonomamente. Se a skill nao funciona nos dois modos, esta errada.
3. **Copier template** — Toda plataforma herda a mesma estrutura. Desvios sao bugs, nao features.
4. **File-based storage** — Git-versionado, zero overhead operacional. Sem banco externo para documentacao.
5. **Progressao linear** — `pitch -> spec -> plan -> tasks -> implement`. Cada artefato tem 1 dono e 1 proposito (MECE).
6. **Pragmatismo sobre elegancia** — "Funciona e entrega valor" > "elegante mas lento". Codigo descartavel e aceitavel.
7. **Brutal honesty** — Sem elogios vazios. Problemas identificados cedo. "Isso nao faz sentido" quando nao faz sentido.

---

## 6. Riscos existenciais

| # | Risco | Impacto | Mitigacao |
|---|-------|---------|-----------|
| 1 | Context rot em execucao autonoma — context window cheia degrada qualidade | Alto — specs geradas ficam incompletas ou inconsistentes | Execucao em waves com subagents frescos (`speckit.execute-wave`). Cada wave recebe contexto limpo. |
| 2 | Drift entre arquitetura e codigo — implementacao diverge do modelo | Alto — documentacao vira ficcao, perde confianca | RECONCILE loop: compara diff vs arquitetura, auto-update se drift < 0.3, escala humano se drift >= 0.3 |
| 3 | Over-engineering do easter — complexidade desnecessaria no runtime | Medio — atrasa entrega, aumenta manutencao | Principio de pragmatismo. Ship imperfect. Testes cobrindo fluxo critico (51 testes existentes). |
| 4 | Dependencia de Claude API — rate limits, mudancas de pricing, downtime | Alto — pipeline autonomo para completamente | Circuit breaker + retry com backoff exponencial. Fallback para modo interativo. Throttle configuravel. |
| 5 | Complexidade do template Copier — sync quebra ao evoluir estrutura | Medio — plataformas existentes divergem da nova estrutura | `_skip_if_exists` para arquivos editaveis. Testes de template (`pytest`). `copier update` nao sobrescreve conteudo. |
| 6 | Single-operator risk — dependencia de 1 pessoa (Gabriel) | Alto — todo conhecimento esta em 1 cabeca | Madruga AI e, por definicao, a mitigacao: documentacao versionada, skills reproduziveis, pipeline determinístico. |

---

## 7. Landscape

| Player | Foco | Forca | Fraqueza vs nos |
|--------|------|-------|-----------------|
| **arc42 / Structurizr** | Documentacao arquitetural + diagramas C4 | Standard industry, DSL maduro (Structurizr), comunidade ativa | Sem pipeline spec-to-code. Sem execucao autonoma. Diagramas sao output final, nao input de pipeline. |
| **Backstage (Spotify)** | Developer portal + service catalog | Ecossistema de plugins, adocao enterprise, TechDocs | Sem IA. Sem pipeline de especificacao. Focado em catalog, nao em documentacao arquitetural ativa. |
| **adr-tools / log4brains** | ADR management | Simples, leve, focado | So ADRs. Sem visao integrada de arquitetura. Sem pipeline. |
| **BMAD / GSD** | Frameworks spec-to-code com IA | Pipeline similar (spec -> plan -> tasks), multi-agent | Sem documentacao arquitetural integrada. Sem RECONCILE loop. Skills nao reutilizaveis interativo/autonomo. |
| **Cursor / Windsurf / Claude Code** | AI-assisted coding | Excelente para implementacao pontual, context-aware | Sem framework de documentacao. Sem pipeline determinístico. Sem persistencia de decisoes arquiteturais entre sessoes. |

**Tese competitiva:** Nenhum player existente conecta as 3 camadas (documentacao arquitetural + especificacao de features + execucao autonoma) em um unico pipeline git-versionado. Madruga AI nao compete com IDEs ou CI/CD — ocupa o espaco entre "decisao arquitetural" e "codigo em PR", que hoje e um vazio de tooling.

---

## 8. Linguagem Ubiqua

| Termo | Definicao | Dominio |
|-------|-----------|---------|
| **Platform** | Unidade central de documentacao. Cada plataforma (`platforms/<name>/`) contem Vision, epics e diagramas Mermaid inline. | Core |
| **Vision** | Conjunto de artefatos de arquitetura de uma plataforma: business/, engineering/, decisions/, model/. | Core |
| **Epic** | Folder autocontido (`epics/NNN-slug/`) que progride por pitch -> spec -> plan -> tasks -> implement. | Planning |
| **Pitch** | Documento Shape Up que define problema, appetite, solucao e rabbit holes. Ponto de entrada de um epic. | Planning |
| **Skill** | Comando Claude Code (`.claude/commands/`) que gera ou valida um artefato especifico. | Tooling |
| **SpeckitBridge** | Compositor que transforma skills interativas em prompts autonomos, lendo de `.claude/commands/` + `.specify/templates/`. | Runtime |
| **RECONCILE** | Loop que compara diff de implementacao vs arquitetura e auto-atualiza Vision se drift < threshold. | Runtime |
| **AUTO marker** | Marcador `<!-- AUTO:name -->` em markdown que delimita conteudo auto-gerado por `vision-build.py`. | Pipeline |
| **Drift score** | Metrica (0.0–1.0) que mede divergencia entre implementacao e arquitetura. < 0.3 = auto-fix, >= 0.3 = escala humano. | Runtime |
| **Wave** | Unidade de execucao do easter. Cada wave processa N tasks com subagent fresco para evitar context rot. | Runtime |
| **1-way door** | Decisao irreversivel que requer aprovacao humana (ex: mudanca de schema, API publica). | Decisions |
| **2-way door** | Decisao reversivel que o easter pode tomar autonomamente (ex: escolha de lib interna). | Decisions |
| **Constitution** | Documento (`.specify/memory/constitution.md`) com regras que governam todos os artefatos gerados. | Governance |
| **Platform manifest** | Arquivo `platform.yaml` que declara nome, lifecycle, views e comandos de build de uma plataforma. | Core |
| **Copier template** | Template Jinja2 (`.specify/templates/platform/`) para scaffolding padronizado de novas plataformas. | Tooling |
