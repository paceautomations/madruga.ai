---
title: "Solution Overview"
updated: 2026-03-27
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

### Now (MVP) — Funcional hoje

| Feature | Descricao | Persona | Metrica |
|---------|-----------|---------|---------|
| **Platform CLI** | `platform.py` com comandos `new`, `lint`, `sync`, `register`, `list`. Scaffold de plataformas via Copier, validacao de estrutura, registro no portal. | Arquiteto-Operator | Tempo para criar nova plataforma: < 2min |
| **LikeC4 Model Pipeline** | Arquivos `.likec4` como source of truth. `vision-build.py` exporta JSON e popula tabelas markdown via AUTO markers (containers, domains, relations, integrations). | Arquiteto-Operator | Tabelas sempre sincronizadas com modelo |
| **Copier Template System** | Template em `.specify/templates/platform/` com Jinja2. `copier copy` scaffolda, `copier update` sincroniza. `_skip_if_exists` protege conteudo editavel. | Arquiteto-Operator | Plataformas com estrutura identica |
| **Portal Starlight** | Astro + Starlight com auto-discovery de plataformas (`platforms.mjs`), sidebar dinamica, dynamic routes, e diagramas LikeC4 interativos (pan, zoom, drill-down). | Consumidor do Portal | Portal acessivel em localhost:4321 com todas as plataformas |
| **SpecKit Pipeline (interativo)** | 9 skills (`speckit.*`): specify, clarify, plan, tasks, implement, analyze, checklist, constitution, taskstoissues. Progressao linear pitch -> spec -> plan -> tasks. | Arquiteto-Operator | Pipeline completo funcional interativamente |
| **Architecture Skills** | 20 skills (`madruga/*`): pipeline DAG incremental com 14 nós (platform-new → roadmap) + utilities (pipeline-status, pipeline-next, checkpoint, verify, reconcile, discuss). Geracao de artefatos de arquitetura. | Arquiteto-Operator | Artefatos gerados seguem template padrao |
| **ADRs (Nygard)** | Decisoes arquiteturais em `decisions/ADR-NNN-*.md`. Formato: Context, Decision, Alternatives, Consequences. | Arquiteto-Operator, Revisor | Decisoes rastreadas e versionadas |
| **Epics (Shape Up)** | Folders autocontidos `epics/NNN-slug/` com pitch.md. Formato: Problem, Appetite, Solution, Rabbit Holes, Acceptance Criteria. | Arquiteto-Operator | Epics com contexto completo e autocontido |

### Next (3-6 meses)

| Feature | Descricao | Persona | Metrica |
|---------|-----------|---------|---------|
| **Runtime Engine Migration** | Migrar 10K LOC Python de `general/services/madruga-ai/` para `madruga.ai/src/`. SpeckitBridge ja consome skills e templates dos mesmos paths. | Arquiteto-Operator, Daemon | 51 testes passando no novo repo |
| **Daemon 24/7** | `MadrugaDaemon` asyncio: poll Obsidian kanban (60s), orchestrator com slots, pipeline autonomo completo. systemd service com PID file e graceful shutdown. | Daemon | Epics APPROVED processados automaticamente |
| **Debate Engine** | Multi-persona convergence: personas (QA, Business, Security) validam specs em 2 rounds. Convergencia automatica quando consenso >= threshold. | Daemon | Specs validadas por 3+ perspectivas antes de plan |
| **Decision System** | Classificador 1-way/2-way door. Gates automaticos: 1-way door parka epic e notifica humano. 2-way door auto-decide. | Daemon, Revisor | Zero decisoes irreversiveis tomadas autonomamente |
| **Codebase Mapping (`speckit.map`)** | Agents paralelos mapeiam codebase existente: stack, patterns, convencoes. Plan recebe contexto do codigo real (brownfield). | Daemon | Plan alinhado com codebase existente |
| **Verify post-impl (`speckit.verify`)** | Compara spec vs codigo implementado. Detecta phantom completions (task marcada done sem implementacao real). | Daemon, Revisor | 0 phantom completions em producao |
| **Execute Waves (`speckit.execute-wave`)** | Execucao em waves com subagents frescos. Cada wave recebe contexto limpo para evitar context rot. | Daemon | Qualidade estavel independente do tamanho do epic |
| **Namespace Unification** | Merge `speckit.*` em `madruga.*`. Skills passam a ser `madruga.specify`, `madruga.plan`, etc. | Arquiteto-Operator | Namespace unico e consistente |

### Later (6-12 meses)

| Feature | Descricao | Persona | Metrica |
|---------|-----------|---------|---------|
| **RECONCILE Loop** | Apos implementacao: le diff do PR, compara vs arquitetura, calcula drift_score. Auto-update se < 0.3, escala humano se >= 0.3. | Daemon, Revisor | Architectural drift detectado e corrigido automaticamente |
| **State Checkpoint (`speckit.checkpoint`)** | `STATE.md` persistido entre sessoes com decisoes tomadas, blockers, proximos passos. Contexto nunca perdido. | Daemon | Zero context loss entre sessoes |
| **Discuss Phase (`speckit.discuss`)** | Captura preferencias de implementacao em gray areas antes do plan. Reduz retrabalho. | Arquiteto-Operator | Preferencias capturadas antes de gastar tokens em plan |
| **Research Paralelo** | Subagents paralelos pesquisam stack, patterns, pitfalls e libs simultaneamente durante plan. | Daemon | Tempo de research reduzido em 60% |
| **Roadmap Auto-Sync** | Roadmap.md gerado automaticamente do frontmatter dos epics (status, phase, priority). Epic frontmatter e source of truth. | Consumidor do Portal | Roadmap sempre reflete estado real dos epics |
| **Architecture Fitness Functions** | Validacao continua: `stress/arch_fitness.py` verifica spec compliance, cobertura de testes, conformidade com ADRs. | Daemon, Revisor | Score de fitness por plataforma visivel no portal |
| **WhatsApp Notifications** | Notificacoes em gates criticos: 1-way door detected, epic blocked, drift alto. Via WhatsApp bridge. | Revisor | Tempo de resposta para gates criticos < 30min |
| **Dashboard Web** | FastAPI dashboard com status em tempo real: epics em pipeline, slots do orchestrator, metricas do daemon. | Arquiteto-Operator | Visibilidade completa do pipeline autonomo |
| **CI/CD Pipeline** | Lint Python (ruff), portal build, template tests (pytest), platform lint all. GitHub Actions. | Arquiteto-Operator | Zero regressoes em merges |
| **Multi-repo Implement** | `speckit.implement` opera em target repos (ex: `fulano-api`) via git worktree, nao dentro do madruga.ai. | Daemon | Implementacao no repo correto, PR no repo correto |
