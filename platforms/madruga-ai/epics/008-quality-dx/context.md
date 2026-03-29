---
title: "Implementation Context — Epic 008"
updated: 2026-03-29
---
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

---
handoff:
  from: epic-context
  to: specify
  context: "Spec deve cobrir os 5 deliverables. Decisões D1-D5 são vinculantes. 4 knowledge files + tiered review + personas + BD integration + LikeC4."
  blockers: []
