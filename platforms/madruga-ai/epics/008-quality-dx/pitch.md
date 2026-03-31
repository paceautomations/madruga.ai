---
id: 008
title: "Epic 008 — Quality & DX"
status: shipped
phase: pitch
appetite: 2w
priority: 3
delivered_at: 2026-03-29
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

---
handoff:
  from: epic-breakdown
  to: epic-context
  context: "Epic 008 — Quality & DX. 5 deliverables focados em redução de boilerplate, review proporcional, e integração BD."
  blockers: []
