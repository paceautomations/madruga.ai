---
title: "Solution Overview"
updated: 2026-03-30
---
# Madruga AI — Solution Overview

> O que vamos construir, para quem, e em que ordem.

Madruga AI e um sistema onde o arquiteto documenta a visao de uma plataforma digital, especifica features como epics autocontidos, e progressivamente delega a execucao para um daemon autonomo. O pipeline inteiro — da decisao arquitetural ao PR — vive em git, usa LikeC4 como source of truth para diagramas, e skills Claude Code como interface tanto para humanos quanto para o runtime engine.

O sistema resolve o problema central de times pequenos: manter arquitetura, specs e codigo sincronizados sem overhead de ferramentas enterprise. Tudo e arquivo. Tudo e versionado. Tudo e reproduzivel.

---

## Personas

| Persona | Perfil | Job-to-be-Done | Pain Points |
|---------|--------|----------------|-------------|
| **Arquiteto-Operator** | Engenheiro solo ou tech lead que documenta arquitetura e especifica features. Usa Claude Code diariamente. | Documentar decisoes arquiteturais, especificar features com contexto macro, e eventualmente delegar execucao ao daemon. | Documentacao desatualizada em semanas. Specs sem contexto da arquitetura. Repetir estrutura manualmente para cada plataforma. Context lost entre sessoes. |
| **Daemon (agente autonomo)** | Runtime engine Python que executa o pipeline spec-to-code sem intervencao humana. | Processar epics APPROVED no kanban: specify -> plan -> tasks -> implement -> review -> reconcile. | Context rot em execucoes longas. Decisoes irreversiveis sem gate humano. Drift entre o que foi especificado e o que foi implementado. |
| **Revisor (humano)** | Arquiteto ou engenheiro senior que revisa PRs gerados pelo daemon e aprova decisoes 1-way door. | Validar que implementacao autonoma respeita a arquitetura e aprovar mudancas estruturais. | Falta de contexto sobre o que o daemon decidiu e por que. PRs sem rastreabilidade ate a spec original. |
| **Consumidor do Portal** | Qualquer membro do time que precisa consultar a arquitetura de uma plataforma. | Entender como o sistema funciona: containers, integracoes, bounded contexts, decisoes, roadmap. | Documentacao em multiplos lugares. Diagramas estaticos desatualizados. Sem navegacao unificada. |

---

## Principios de Produto

1. **LikeC4-first, markdown-second** — O modelo `.likec4` e a source of truth. Markdown e view layer gerada via AUTO markers. Justificativa: garante que diagramas e tabelas nunca divergem.

2. **Skills = interface unica** — Mesma skill funciona quando o humano invoca interativamente e quando o daemon invoca via SpeckitBridge. Justificativa: elimina duplicacao de prompts e garante consistencia.

3. **Progressao linear, artefatos MECE** — `pitch -> spec -> plan -> tasks -> implement`. Cada artefato tem 1 dono (skill) e 1 proposito. Spec nao contem design tecnico; plan nao contem task breakdown. Justificativa: evita sobreposicao e facilita validacao por camada.

4. **File-based, git-versionado** — Todo estado vive em arquivos. Sem banco externo para documentacao ou specs. Justificativa: diff, blame, revert nativos. Zero overhead operacional.

5. **Template-driven scaling** — Novas plataformas herdam estrutura via Copier. `copier update` sincroniza evolucoes. Justificativa: escala para N plataformas sem divergencia estrutural.

6. **Autonomia progressiva com safety gates** — Daemon executa autonomamente, mas decisoes 1-way door sempre escalam para humano. Justificativa: confianca incremental sem risco de mudancas irreversiveis.

7. **Reconciliacao automatica** — Implementacao retroalimenta arquitetura via RECONCILE loop. Justificativa: documentacao nunca vira ficcao porque o loop fecha automaticamente.

---

## Feature Map

### Implementado — Funcional hoje

| Feature | Descricao | Persona | Epic |
|---------|-----------|---------|------|
| **Platform CLI** | `platform.py` com comandos `new`, `lint`, `sync`, `register`, `list`, `use`, `current`, `status`, `import-adrs`, `export-adrs`, `import-memory`, `export-memory`. Scaffold via Copier, validacao, pipeline status (tabela + JSON). | Arquiteto-Operator | 007 |
| **LikeC4 Model Pipeline** | Arquivos `.likec4` como source of truth. `vision-build.py` exporta JSON e popula tabelas markdown via AUTO markers. | Arquiteto-Operator | — |
| **Copier Template System** | Template em `.specify/templates/platform/` com Jinja2. `copier copy` scaffolda, `copier update` sincroniza. `_skip_if_exists` protege conteudo editavel. Inclui `CLAUDE.md.jinja` por plataforma. | Arquiteto-Operator | 007 |
| **Portal Starlight + Dashboard** | Astro + Starlight com auto-discovery de plataformas, sidebar dinamica, dynamic routes, diagramas LikeC4 interativos, e **dashboard visual de pipeline** (L1 + L2, Mermaid DAG, filtros, detalhes por epic). | Consumidor do Portal | 010 |
| **Pipeline Unificado (L1 + L2)** | Fluxo continuo de 24 skills: L1 (13 nodes) + L2 (11 nodes por epic). Cada skill segue contrato de 6 passos com knowledge files extraidos (pipeline-contract-base.md, pipeline-contract-planning.md). | Arquiteto-Operator | 008 |
| **SQLite Pipeline State** | BD SQLite (WAL mode) como state store. Tabelas: platforms, pipeline_nodes, epics, epic_nodes, pipeline_runs, events, artifact_provenance. Migrations incrementais. Seed automatico do filesystem. | Arquiteto-Operator | 006 |
| **Decision Log BD** | BD como source of truth para decisions e memory. Tabelas decisions, decision_links, memory_entries com FTS5 full-text search. CLI: import-adrs, export-adrs, import-memory, export-memory. Markdown e view layer exportada do BD. | Arquiteto-Operator | 009 |
| **ADRs (Nygard)** | 14 ADRs em `decisions/ADR-NNN-*.md`. Formato: Context, Decision, Alternatives, Consequences. Sincronizados com BD via import/export. | Arquiteto-Operator, Revisor | 009 |
| **Epics (Shape Up)** | Folders autocontidos `epics/NNN-slug/` com pitch.md e artefatos L2. 5 epics shipped (006-010). | Arquiteto-Operator | — |
| **Skill Contracts (Knowledge Files)** | Boilerplate extraido de skills para knowledge files reutilizaveis: `pipeline-contract-base.md` (contrato de 6 passos), `pipeline-contract-planning.md` (revisao de planejamento). Skills ficaram enxutas. | Arquiteto-Operator | 008 |
| **Verify + QA + Reconcile** | Skills de validacao pos-implementacao: verify (spec vs codigo), QA (static analysis + tests + browser), reconcile (drift detection 9 categorias, drift score, concrete diffs). | Arquiteto-Operator, Revisor | 008 |

### Next — Candidatos para proximos epics

| Feature | Descricao | Persona | Complexidade |
|---------|-----------|---------|-------------|
| **Runtime Engine Migration** | Migrar daemon Python de `general/services/madruga-ai/` para `madruga.ai/src/`. SpeckitBridge ja consome skills e templates dos mesmos paths. | Daemon | Grande |
| **Daemon 24/7** | `MadrugaDaemon` asyncio: poll kanban, orchestrator com slots, pipeline autonomo completo. systemd service. | Daemon | Grande |
| **Multi-repo Implement** | `speckit.implement` opera em target repos (ex: `fulano-api`) via git worktree. | Daemon | Media |
| **CI/CD Pipeline** | GitHub Actions: lint Python (ruff), portal build, template tests (pytest), platform lint all. | Arquiteto-Operator | Pequena |
| **Namespace Unification** | Merge `speckit.*` em `madruga.*`. Skills passam a ser `madruga.specify`, `madruga.plan`, etc. | Arquiteto-Operator | Pequena |

### Later — Visao de longo prazo

| Feature | Descricao | Persona |
|---------|-----------|---------|
| **Debate Engine** | Multi-persona convergence para validacao de specs. | Daemon |
| **Decision System** | Classificador 1-way/2-way door com gates automaticos. | Daemon, Revisor |
| **Architecture Fitness Functions** | Validacao continua de spec compliance e conformidade com ADRs. | Daemon, Revisor |
| **WhatsApp Notifications** | Notificacoes em gates criticos via WhatsApp bridge. | Revisor |
| **Roadmap Auto-Sync** | Roadmap gerado automaticamente do estado dos epics no BD. | Consumidor do Portal |
