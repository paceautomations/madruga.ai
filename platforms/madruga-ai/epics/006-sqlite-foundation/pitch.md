---
id: 006
title: "SQLite Foundation — BD para Estado do Pipeline"
status: shipped
phase: pitch
appetite: 2w
priority: 1
---
# SQLite Foundation — BD para Estado do Pipeline

## Problema

O madruga.ai armazena todo estado como arquivos no filesystem: pipeline status derivado de file existence, decision log inexistente, provenance de artefatos não rastreada, tracking de custo/tokens inexistente. Isso causa:

1. **Prerequisites falhos** — `check-platform-prerequisites.sh` só checa se arquivo existe (0 bytes conta como "done")
2. **Zero observabilidade** — sem dashboard, sem tracking de progresso per-epic, sem custo por skill
3. **Idempotência quebrada** — `adr-gen` e `epic-breakdown` criam duplicatas em re-runs (sem registry)
4. **Staleness invisível** — quando upstream muda, downstream não é invalidado
5. **Decision log inexistente** — decisões tomadas durante skills se perdem entre sessões
6. **Hallucination sem guardrails** — research skills fabricam sources sem escape hatch

## Appetite

1 semana (small batch). Schema SQL + `db.py` + integração no step 5 + guardrails.

## Solução

Implementar SQLite como BD para todo estado do pipeline:
- `.pipeline/madruga.db` com 8 tabelas (platforms, pipeline_nodes, epics, epic_nodes, decisions, artifact_provenance, pipeline_runs, events)
- `db.py` como thin wrapper Python (~200 linhas, zero dependências externas)
- Migration runner com SQL files numerados
- Integração no step 5 (Save+Report) do contrato de skills
- Seed data dos artefatos existentes
- Guardrails de hallucination em research skills

## Rabbit Holes

- NÃO implementar portal dashboard (fase futura)
- NÃO migrar prerequisites checker para BD (epic 007)
- NÃO adicionar architecture graph/elements (fase futura)
- NÃO implementar cross-references/tags (fase futura)

## Acceptance Criteria

1. `python3 -c "import sys; sys.path.insert(0,'.specify/scripts'); from db import get_conn; get_conn()"` funciona
2. Migration cria 8 tabelas no SQLite
3. CRUD round-trip funciona (insert + select)
4. `platform.py lint --all` passa (pipeline: section presente)
5. GitHub Actions workflow `lint.yml` existe e é válido
6. Grep encontra `[DADOS INSUFICIENTES]` em tech-research.md e adr-gen.md
