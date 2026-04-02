---
id: 008
title: "Epic 008 — Quality & DX"
status: shipped
phase: pitch
appetite: 2w
priority: 3
delivered_at: 2026-03-29
updated: 2026-03-29
---
# Epic 008 — Quality & Developer Experience

## Problema

Skills do pipeline carregam ~15K tokens de boilerplate repetido (contrato de 6 passos, auto-review, personas, structured questions). Cada skill repete o mesmo bloco — manutenção é N×esforço, inconsistência silenciosa cresce com cada nova skill. Auto-review é checkbox theater (mesma lista para gate auto e 1-way-door). Personas são labels decorativos sem impacto no comportamento. E o BD do SQLite (epic 006) tem schema completo mas zero integração real no ciclo das skills — nenhuma skill faz `upsert_pipeline_node()` ou `insert_provenance()` ao salvar artefato.

## Appetite

2 semanas. Escopo cortado para 5 deliverables concretos, todos dentro do sistema de skills existente. Zero infra nova, zero dependências novas.

## Solução

### 1. Knowledge Files em Camadas (A1)

Extrair o contrato uniforme de 6 passos para knowledge files reutilizáveis:

```
.claude/knowledge/
  pipeline-contract-base.md       → Steps 0,1,3,4,5 universais (~80 linhas)
  pipeline-contract-business.md   → Persona Bain/McKinsey + "zero technical content" (~20 linhas)
  pipeline-contract-engineering.md → Persona Staff Engineer + simplicity rules (~20 linhas)
  pipeline-contract-planning.md   → Persona PM + Shape Up rules (~20 linhas)
```

Cada skill: `"Siga contract-base + contract-{layer}. Overrides abaixo."` — 2 file-reads em vez de 40-60 linhas inline.

### 2. Auto-Review Tiered (A8)

Review proporcional ao custo do erro:

| Gate | Review |
|------|--------|
| auto | Checks executáveis (grep/wc — determinísticos) |
| human | Executáveis + scorecard para humano (direciona atenção) |
| 1-way-door | Executáveis + subagent adversarial + scorecard |

Definir cada tier no `pipeline-contract-base.md`. Skills não precisam saber qual tier — o gate type determina automaticamente.

### 3. LikeC4 Knowledge File + Validation (A6)

- `.claude/knowledge/likec4-syntax.md` — specification syntax, views syntax, erros comuns, convenções do repo
- Após salvar `.likec4`, rodar `likec4 build <model-dir>` e reportar erros antes do gate

### 4. Personas Afiadas (M13)

Trocar labels decorativos por diretivas comportamentais:

| Atual | Nova diretiva |
|-------|---------------|
| "Senior Tech Research Analyst" | "Seu default é `[DADOS INSUFICIENTES]`. Só afirme com source verificável." |
| "Product Manager / Architect" | "Seu instinto é REDUZIR escopo. Diga 'isso pode ser cortado?' antes de adicionar." |
| "Pipeline Observer" | Remover — read-only, persona não muda comportamento |
| "Session Recorder" | Remover — data collection, persona sem efeito |

### 5. Integração BD no Step 5 (A3/A4/M14)

Após cada skill salvar artefato:
- `db.upsert_pipeline_node()` — status done + output_hash
- `db.insert_provenance()` — file_path + generated_by
- `db.insert_event()` — action completed
- Para epic cycle: `db.upsert_epic_node()` em vez de pipeline_node

Integrado via instrução no `pipeline-contract-base.md` (step 5), não por mudança individual em cada skill.

## Rabbit Holes

- **NÃO** reescrever skills inteiras — apenas extrair boilerplate para knowledge files e ajustar referências
- **NÃO** implementar daemon/automation — checkpoint automático é trigger, não daemon
- **NÃO** criar novo CLI/tooling — db.py já existe e é suficiente
- **NÃO** mudar gate types das skills — calibração é decisão separada

## Acceptance Criteria

1. Skills referenciam knowledge files em vez de inline contract (medido: grep conta de linhas por skill reduz ≥30%)
2. Auto-review tem 3 tiers distintos, documentados em contract-base
3. `likec4-syntax.md` existe com ≥50 linhas de referência
4. Skills que geram `.likec4` rodam `likec4 build` pós-geração
5. Personas em `pipeline-dag-knowledge.md` são diretivas comportamentais, não labels
6. Step 5 de contract-base inclui instrução de integração BD
7. Zero mudança em gate types, zero mudança na estrutura do DAG

handoff:
  from: epic-breakdown
  to: epic-context
  context: "Epic 008 — Quality & DX. 5 deliverables focados em redução de boilerplate, review proporcional, e integração BD."
  blockers: []


# Epic 008 — Implementation Context

## Captured Decisions

| # | Área | Decisão | Referência Arquitetural | Alternativa Rejeitada |
|---|------|---------|------------------------|----------------------|
| 1 | Boilerplate | Extrair contrato para 4 knowledge files (base + 3 layers). Cada skill referencia com "Siga contract-base + contract-{layer}" | ADR-008 (MECE), Constitution §I (Pragmatism) | Copier/Jinja2 code-gen — cria duas fontes de verdade |
| 2 | Auto-review | 3 tiers por gate type. Definido em contract-base, skills não escolhem tier | ADR-013 (Decision Gates), process_improvement A8 | Tier único para tudo — review inadequado |
| 3 | LikeC4 | Knowledge file de referência + `likec4 build` pós-geração em skills que geram .likec4 | Blueprint §3, process_improvement A6 | Só Context7 per-run — não offline, não repo-specific |
| 4 | Personas | Diretivas comportamentais em pipeline-dag-knowledge.md, não labels | process_improvement M13 | Manter labels decorativos — zero impacto no output |
| 5 | Integração BD | Instrução de integração no step 5 de contract-base. Skills leem do knowledge file | ADR-012 (SQLite WAL), epic 006 db.py | Integrar individualmente em cada skill — N×esforço |

## Resolved Gray Areas

### GA1. Quantos knowledge files criar?

**Pergunta:** 1 monolítico, 4 em camadas, ou 1 per-skill?
**Resposta:** 4 em camadas (base + business + engineering + planning). Base tem steps 0,1,3,4,5 universais. Cada layer tem persona e regras específicas.
**Rationale:** Com 19 skills e 4 camadas, monolítico vira 500+ linhas. Per-skill derrota o propósito. Camadas refletem arquitetura real (4 layers no DAG).

### GA2. Skills perdem o contrato inline — ficam incompletas?

**Pergunta:** Se o contrato sai da skill, ela fica ilegível sozinha?
**Resposta:** Cada skill mantém: Cardinal Rule, Usage, Output Directory, Instructions (steps 1+2 artifact-specific), Error Handling, HANDOFF. O que sai: steps 0,3,4,5 genéricos + persona.
**Rationale:** Steps genéricos são idênticos em 16/19 skills. Removê-los não perde legibilidade — ganha foco no que é único da skill.

### GA3. Como funciona o tier automático no auto-review?

**Pergunta:** Skill sabe seu gate type ou infere?
**Resposta:** Skill já declara gate no frontmatter. Contract-base instrui: "Se seu gate é auto, use tier 1. Se human, tier 2. Se 1-way-door, tier 3." Zero lógica nova.
**Rationale:** Gate type já existe e é imutável por skill. Mapeamento direto.

### GA4. LikeC4 validation — quais skills afetadas?

**Pergunta:** Quais skills geram .likec4?
**Resposta:** Apenas 2: `domain-model` (model/ddd-contexts.likec4) e `containers` (model/platform.likec4). Só essas precisam de `likec4 build` validation.
**Rationale:** Validation post-save em 2 skills é cirúrgico. Não infla o contrato base.

### GA5. DB integration — funciona se DB não existe?

**Pergunta:** E se `.pipeline/madruga.db` não existe (repo novo, sem epic 006)?
**Resposta:** Contract-base já tem guard: "Se `.pipeline/madruga.db` existe, faça upsert. Caso contrário, prossiga normalmente." Opt-in, não obrigatório.
**Rationale:** Já implementado no knowledge file atual (pipeline-dag-knowledge.md §2, step 5). Só precisa expandir com instruções mais específicas.

## Applicable Constraints

| # | Constraint | Fonte | Impacto neste epic |
|---|-----------|-------|-------------------|
| 1 | Zero external dependencies | Blueprint §3, ADR-012 | Knowledge files são markdown puro |
| 2 | MECE artifact model — 1 owner por artefato | ADR-008 | Cada knowledge file tem 1 propósito |
| 3 | PT-BR para artefatos, EN para código | Constitution §VI | Knowledge files em EN (são instruções para LLM, não artefatos de documentação) |
| 4 | TDD para todo código | Constitution §VII | Não há código novo — apenas markdown |
| 5 | Skills não reescritas | pitch §Rabbit Holes | Apenas extrair boilerplate, não mudar lógica |

## Suggested Approach

### Ordem de execução (por dependência)

1. **Knowledge files em camadas** — Criar 4 arquivos em `.claude/knowledge/`. Base (~80 linhas) + 3 layers (~20 linhas cada). Depois atualizar cada skill para referenciar em vez de inline.
2. **Auto-review tiered** — Definir 3 tiers na seção de auto-review do contract-base. Incluir exemplos de checks executáveis por tier.
3. **Personas afiadas** — Atualizar tabela de personas no `pipeline-dag-knowledge.md`. Trocar labels por diretivas comportamentais.
4. **Integração BD no step 5** — Expandir seção "SQLite Integration" no contract-base com instruções mais específicas e exemplos.
5. **LikeC4 knowledge file** — Criar `likec4-syntax.md` com referência de syntax. Adicionar instrução de `likec4 build` nas 2 skills que geram .likec4.

### Princípio de priorização

**Resultado >> esforço.** Knowledge files em camadas é o item de maior impacto (toca 16+ skills, corta ~40 linhas/skill). Fazer primeiro, validar, depois os demais.

handoff:
  from: epic-context
  to: specify
  context: "Spec deve cobrir os 5 deliverables. Decisões D1-D5 são vinculantes. 4 knowledge files + tiered review + personas + BD integration + LikeC4."
  blockers: []
