---
title: "Spec — Epic 008: Quality & DX"
updated: 2026-03-29
---
# Spec — Quality & Developer Experience

**Input**: Epic 008 — Quality & DX. Redução de boilerplate via knowledge files em camadas, auto-review tiered, LikeC4 validation, personas afiadas, integração BD.

## Visão Geral

O pipeline de 19 skills funciona mas acumula ~15K tokens de boilerplate duplicado. Auto-review é checkbox theater. Personas são decorativas. O BD (epic 006) tem schema completo mas zero integração real no ciclo das skills. Este epic resolve os 5 pontos sem reescrever skills — apenas extraindo, afiando, e conectando.

## User Scenarios

### US1. Knowledge Files em Camadas

**Given** 16+ skills com contrato de 6 passos inline (~40-60 linhas repetidas),
**When** o operador abre uma skill para manutenção,
**Then** a skill contém apenas: Cardinal Rule, Usage, Output Dir, Instructions (artifact-specific), Error Handling, HANDOFF. Steps genéricos (0,3,4,5) vêm de `pipeline-contract-base.md`.

**Independent Test**: `wc -l` médio por skill reduz ≥30%. Grep por "Auto-Review" em skills retorna referência ao knowledge file, não checklist inline.

### US2. Auto-Review Tiered

**Given** contract-base com 3 tiers definidos,
**When** uma skill com gate `auto` roda auto-review,
**Then** executa apenas checks determinísticos (grep/wc).
**When** uma skill com gate `human` roda auto-review,
**Then** executa checks determinísticos + apresenta scorecard ao operador.
**When** uma skill com gate `1-way-door` roda auto-review,
**Then** executa checks determinísticos + lança subagent adversarial + apresenta scorecard.

**Independent Test**: Contract-base tem 3 seções distintas de auto-review. Cada tier é claramente diferenciado.

### US3. Personas Afiadas

**Given** pipeline-dag-knowledge.md §4 com labels decorativos,
**When** o operador consulta a persona de uma layer,
**Then** encontra diretiva comportamental específica (não label).

**Independent Test**: Seção §4 do DAG knowledge não contém "Senior", "Specialist", ou "15+ years" como qualificadores. Cada persona tem frase imperativa.

### US4. Integração BD no Step 5

**Given** `.pipeline/madruga.db` existe com schema de epic 006,
**When** uma skill salva artefato (step 5),
**Then** contract-base instrui: chamar `db.upsert_pipeline_node()`, `db.insert_provenance()`, `db.insert_event()`.
**When** `.pipeline/madruga.db` não existe,
**Then** skill prossegue normalmente (opt-in).

**Independent Test**: Contract-base §Step 5 contém bloco de código Python com chamadas db.py. Guard clause para DB inexistente.

### US5. LikeC4 Knowledge File + Validation

**Given** skills `domain-model` e `containers` geram `.likec4` files,
**When** skill salva um `.likec4`,
**Then** roda `likec4 build <model-dir>` e reporta erros antes do gate.
**Given** `.claude/knowledge/likec4-syntax.md` existe,
**When** skill precisa gerar `.likec4`,
**Then** referencia o knowledge file para syntax correta.

**Independent Test**: `likec4-syntax.md` existe com ≥50 linhas. Skills domain-model e containers mencionam `likec4 build` na seção de Instructions.

## Functional Requirements

| ID | Requisito | Critério de Aceitação |
|----|-----------|----------------------|
| FR-001 | `pipeline-contract-base.md` existe com steps 0,1,3,4,5 genéricos | Arquivo existe, ≥60 linhas, contém seções para cada step |
| FR-002 | `pipeline-contract-business.md` existe com persona e regras | Arquivo existe, contém diretiva comportamental |
| FR-003 | `pipeline-contract-engineering.md` existe com persona e regras | Arquivo existe, contém diretiva comportamental |
| FR-004 | `pipeline-contract-planning.md` existe com persona e regras | Arquivo existe, contém diretiva comportamental |
| FR-005 | 13 skills DAG referenciam contract files em vez de inline | Grep "pipeline-contract" em ≥13 skills. Inline boilerplate removido |
| FR-006 | Contract-base tem 3 tiers de auto-review | Seções "Tier 1 (auto)", "Tier 2 (human)", "Tier 3 (1-way-door)" |
| FR-007 | `pipeline-dag-knowledge.md` §4 tem diretivas comportamentais | Zero labels decorativos. Frases imperativas |
| FR-008 | Contract-base step 5 tem instrução BD | Bloco com `upsert_pipeline_node`, `insert_provenance`, `insert_event` |
| FR-009 | Guard clause para BD inexistente | "Se `.pipeline/madruga.db` existe" condicional |
| FR-010 | `likec4-syntax.md` existe com ≥50 linhas | Arquivo existe, syntax de specification + views + erros comuns |
| FR-011 | `domain-model` e `containers` mencionam `likec4 build` | Grep confirma em ambas skills |
| FR-012 | Média de linhas por skill reduz ≥30% | Antes: ~219 linhas/skill → Depois: ≤153 linhas/skill |

## Success Criteria

1. Operador mantém uma skill em 50% do tempo (menos boilerplate para ler/modificar)
2. Auto-review para skills 1-way-door inclui step de subagent adversarial
3. Skills que geram .likec4 detectam erros de syntax antes do gate humano
4. BD recebe atualizações de estado automaticamente durante o ciclo normal de skills

## Assumptions

- Skills têm boilerplate suficientemente uniforme para extrair para knowledge files sem perda de funcionalidade
- LLM consegue mergear contract-base + contract-{layer} + skill-specific sem confusão
- `likec4` CLI está instalado no ambiente de execução

## Edge Cases

- Skill com auto-review totalmente custom (qa) — mantém inline, não referencia contract-base para auto-review
- Skills utilitárias (pipeline, checkpoint) — referenciam contract-base parcialmente (sem persona, sem structured questions)

---
handoff:
  from: specify
  to: plan
  context: "Spec com 12 FRs, 5 user scenarios. Escopo: 4 knowledge files + refactor 13+ skills + LikeC4 syntax + personas + BD integration."
  blockers: []
