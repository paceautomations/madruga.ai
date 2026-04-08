---
id: 009
title: "Decision Log BD"
status: shipped
phase: pitch
priority: 4
delivered_at: 2026-03-29
updated: 2026-03-29
---
# Decision Log BD

BD como source of truth para decisions e memory. FTS5 full-text search. CLI import/export. 5 novas migrations. 20+ funcoes em db.py.



## Resumo

Inverter o fluxo de decisoes: **BD e a fonte, markdown e a view**. Hoje ADRs sao escritos em markdown e o BD (`decisions` table) esta vazio. A mudanca faz toda decisao nascer no SQLite via `insert_decision()` e exportar para `ADR-*.md` no formato Nygard identico ao atual.

Adicionalmente, criar tabela `memory_entries` no BD para complementar/substituir o sistema de memory em `.claude/memory/*.md`.

## Motivacao

Pesquisa em 4 frameworks (Gas Town, PaperClip, OpenClaw, BMAD) revelou:
- **Gas Town** e **PaperClip** (os mais maduros) usam BD como source of truth
- Markdown e view/export, nao fonte
- Zero drift por definicao — uma fonte so
- Query rica por status, skill, epic, data, full-text
- Suporte a micro-decisions (trade-offs que nao viram ADR formal)

## Captured Decisions

| # | Area | Decisao | Referencia Arquitetural |
|---|------|---------|------------------------|
| 1 | Storage | SQLite (`.pipeline/madruga.db`) como source of truth — tabela `decisions` existente | 001_initial.sql (epic 006-sqlite-foundation) |
| 2 | Export | Markdown exportado no formato Nygard identico ao atual (zero breaking change no portal) | Formato existente em ADR-001 a ADR-019 (prosauai) |
| 3 | Import | Retroativo — parsear frontmatter + conteudo dos 19 ADRs existentes e popular BD | — |
| 4 | Memory | Tabela `memory_entries` no BD (tipos: user, feedback, project, reference) | .claude/memory/ pattern atual |
| 5 | Escopo | Decisions + Memory juntos neste epic | Decisao do usuario |
| 6 | Fluxo | `skill → insert_decision() → BD → export → ADR-*.md` (Alternativa B) | Pesquisa Gas Town/PaperClip |
| 7 | Micro-decisions | BD captura trade-offs de qualquer skill, nao so ADRs formais | Lacuna atual — decisions perdidas |
| 8 | Plataforma | Epic pertence a plataforma madruga-ai (infra do sistema) | platforms/madruga-ai/ |

## Resolved Gray Areas

### 1. Como manter backward compatibility com o portal?
**Pergunta**: O portal le ADRs em markdown. Se BD e a fonte, o export precisa ser identico?
**Resposta**: Sim. Export gera exatamente o mesmo formato Nygard com YAML frontmatter. Portal, links e referencias continuam funcionando zero-change.
**Rationale**: Menor blast radius. Portal nao precisa mudar.

### 2. E se alguem editar o markdown diretamente?
**Pergunta**: Na Alternativa B pura, markdown nao e editavel. Mas e se alguem editar?
**Resposta**: Aceitar como edge case. Se detectado (hash mismatch), o markdown vence e atualiza o BD (import). Pragmatico — nao impedir edits manuais, so preferir o fluxo via BD.
**Rationale**: Constitution Principio I — Pragmatism Above All.

### 3. Como lidar com ADRs que referenciam outros ADRs?
**Pergunta**: ADR-011 referencia ADR-016. Isso precisa ser rastreado no BD?
**Resposta**: Sim, via tabela `decision_links` com tipos: supersedes, depends_on, related, contradicts.
**Rationale**: Gas Town e PaperClip fazem isso. Permite queries como "quais decisoes dependem de ADR-011?".

### 4. Memory entries substituem ou complementam `.claude/memory/`?
**Pergunta**: O sistema de auto-memory do Claude Code usa arquivos em `.claude/memory/`. O BD substitui?
**Resposta**: Complementa inicialmente, substitui gradualmente. BD e queryavel; markdown nao. Mas `.claude/memory/` continuara existindo porque o Claude Code le automaticamente. Sync bidirecional necessario.
**Rationale**: Nao quebrar o auto-memory do Claude Code que depende de MEMORY.md.

### 5. FTS5 full-text search neste epic ou futuro?
**Pergunta**: FTS5 permite busca textual sem grep. Incluir agora?
**Resposta**: Incluir. O custo e minimo (2 CREATE VIRTUAL TABLE) e o valor e alto para queries cross-decision.
**Rationale**: Constitution Principio II — Automate Repetitive Tasks.

### 6. BD e central para todas as plataformas?
**Pergunta**: O BD em `.pipeline/madruga.db` serve ProsaUAI e madruga-ai e futuras plataformas?
**Resposta**: Sim. Toda tabela tem `platform_id` como FK. IDs unicos com referencias corretas cross-platform.
**Rationale**: Design existente no 001_initial.sql ja suporta N plataformas.

## Applicable Constraints

| Constraint | Fonte | Impacto |
|------------|-------|---------|
| Python stdlib only (sqlite3, hashlib, json, pathlib, uuid) | Epic 006-sqlite-foundation | Nenhuma dependencia externa no db.py |
| SQLite WAL mode, foreign_keys=ON, busy_timeout=5000 | Epic 006-sqlite-foundation | Ja configurado em get_conn() |
| Migrations sequenciais em `.pipeline/migrations/` | Pattern existente (001, 002) | Nova migration sera 003 |
| Formato Nygard para ADRs | Convention existente | Export deve gerar identico |
| Ruff para formatacao Python | CLAUDE.md | Todo codigo Python novo |
| Auto-simplify apos implementacao | CLAUDE.md | Rodar /simplify nos arquivos alterados |

## Suggested Approach

### Fase 1 — Schema (migration 003)
- ALTER TABLE `decisions`: adicionar `content_hash`, `decision_type`, `context`, `consequences`, `tags_json`
- CREATE TABLE `decision_links` (from, to, link_type)
- CREATE TABLE `memory_entries` (memory_id, platform_id, type, name, description, content, source, file_path, content_hash, timestamps)
- CREATE VIRTUAL TABLE `decisions_fts` USING fts5
- CREATE VIRTUAL TABLE `memory_fts` USING fts5

### Fase 2 — API (db.py)
- Refatorar `insert_decision()` para suportar novos campos
- Adicionar `export_decision_to_markdown()` — gera ADR-*.md no formato Nygard
- Adicionar `import_adr_from_markdown()` — parseia markdown existente
- CRUD para `memory_entries` e `decision_links`
- `sync_decisions_to_markdown()` — batch export
- `search_decisions()` e `search_memory()` via FTS5

### Fase 3 — Import retroativo
- Comando `--import-adrs` em post_save.py
- Parsear frontmatter YAML + conteudo dos 19 ADRs de ProsaUAI
- Popular tabela `decisions` com hash de conteudo
- Detectar links entre ADRs (superseded_by ja existe no schema)

### Fase 4 — Integrar skills
- Skill `madruga:adr` insere no BD primeiro, depois exporta markdown
- Outros skills chamam `insert_decision()` para micro-decisions
- `post_save.py` registra provenance + event no audit log

### Fase 5 — Memory sync
- Import `.claude/memory/*.md` para tabela `memory_entries`
- Sync bidirecional BD ↔ `.claude/memory/`

## Alternativas Consideradas

### A. BD como Index (markdown = source of truth)
- **Pro**: Zero breaking change, ADRs existentes continuam inalterados
- **Con**: Dual-write problem, parser de frontmatter fragil, nao suporta micro-decisions
- **Rejeitado**: Consistencia inferior — duas fontes sempre divergem

### B. BD como Source of Truth (escolhida)
- **Pro**: Query rica, zero drift, micro-decisions, supersede chain nativa
- **Con**: Skills precisam mudar, markdown vira read-only (export)
- **Escolhida**: Validada por Gas Town e PaperClip. Consistencia maxima.

### C. Dual-Source Hibrido
- **Pro**: Menor breaking change, markdown editavel
- **Con**: Reconcile bidirecional complexo, edge cases de divergencia
- **Rejeitado**: Complexidade de reconcile nao justifica vs B puro

## Riscos

| Risco | Mitigacao |
|-------|----------|
| BD corrompido = perda de dados | Git-tracked markdown como backup. `--import-adrs` reconstroi BD de markdown |
| Skill esquece de chamar insert_decision() | Lint/check no pipeline contract |
| FTS5 nao disponivel em SQLite antigo | Python 3.11+ garante FTS5 (stdlib sqlite3) |
| Edit manual no markdown diverge do BD | Hash check detecta, import vence |
