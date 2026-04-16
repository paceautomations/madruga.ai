# Relatório de Análise Pós-Implementação: Runtime QA & Testing Pyramid

**Epic**: 026-runtime-qa-testing-pyramid  
**Gerado por**: `speckit.analyze` (post-implementation pass — pós-Phase 1)  
**Data**: 2026-04-16  
**Status de Implementação**: Phase 1 completa (12/39 tasks); Phases 2–7 pendentes

---

## Contexto

Este relatório analisa a consistência cross-artifact entre `spec.md`, `plan.md` e `tasks.md` após a conclusão da **Phase 1** (infraestrutura Python: `qa_startup.py` + `test_qa_startup.py`). A análise valida:

- Cobertura de requisitos funcionais (FR-001 a FR-023) pelas tasks
- Qualidade e integridade do que foi implementado vs. o que foi especificado
- Riscos e inconsistências que podem bloquear Phases 2–7
- Alinhamento com a Constituição do projeto

**Artefatos analisados**:
- `spec.md` — 23 FRs + 7 SCs, 7 USs, 5 edge cases
- `plan.md` — 7 fases, FR-to-Phase mapping, contratos, guardrails
- `tasks.md` — 39 tasks, 7 phases, 12 [x] completas, 27 [ ] pendentes
- `qa_startup.py` — 883 LOC implementado (Phase 1 completa)
- `test_qa_startup.py` — 83 testes, 100% passando

---

## Relatório de Análise

| ID | Categoria | Severidade | Localização | Resumo | Recomendação |
|----|-----------|------------|-------------|--------|--------------|
| D1 | Coverage Gap | HIGH | spec.md SC-001 / tasks.md Phase 7 | SC-001 afirma "7/7 bugs do Epic 007 detectados (100%)" mas Phase 7 (T035–T039) não testa nenhum dos 7 bugs individualmente. T035–T039 validam infraestrutura genérica mas não provam que cada classe de bug específica seria bloqueada. | Adicionar subtasks em Phase 7 ou documentar explicitamente que SC-001 requer ambiente prosauai completo com Docker + `.env` real. Alternativa: criar `tests/test_bug_regression.py` com mocks dos 7 cenários (sem serviços reais). |
| D2 | Coverage Gap | HIGH | spec.md SC-005 / tasks.md T039 | `make test` falha com `INTERNALERROR` em `test_sync_memory_module.py` (erro pré-existente, não causado por este epic). T039 afirma "confirmar 0 failures" — condição impossível de atender sem corrigir issue pré-existente. SC-005 não pode ser verificado como especificado. | Amender SC-005 para: "test_qa_startup.py e todos os testes não-broken pelo epic passam; `make test` retorna 0 failures excluindo pre-existing failures documentadas." Registrar INTERNALERROR em `test_sync_memory_module.py` como blocker pré-existente. |
| B1 | Ambiguidade | MEDIUM | spec.md SC-003 | "Tempo médio para diagnosticar falha de deployment reduzido" — sem baseline nem target numérico. Critério não verificável. | Substituir por critério qualitativo verificável: "Mensagem de BLOCKER inclui: (1) qual health check falhou, (2) output de diagnóstico do serviço, (3) sugestão de resolução — sem necessidade de abrir logs manualmente." Já implementado em `qa_startup.py`; spec deve refletir isso. |
| B2 | Ambiguidade | MEDIUM | spec.md FR-005 / FR-007 / tasks.md T025 | Exit codes de `qa_startup.py` não são definidos na spec (FR-005/FR-007). Implementação usa: 0=ok/warn, 1=blocker, 2=config error (testing: ausente), 3=unexpected. T025 (Phase 4) referencia "exit code 2" como sinal de testing: ausente — correto na implementação mas sem base na spec. | Adicionar tabela de exit codes em FR-005 ou FR-007 da spec. Já implementado corretamente; spec está defasada. |
| C1 | Subespecificação | MEDIUM | tasks.md T015 | J-002 em `platforms/madruga-ai/testing/journeys.md` descrita como "Pipeline status visible via CLI" com step `api GET http://localhost:4321 assert_status: 200` — step testa URL do portal web, não CLI. Título e step são inconsistentes. | Renomear J-002 para "Portal homepage responds" OU mudar step para executar `python3 platform_cli.py status madruga-ai` (CLI real). Escolher conforme propósito: validar infraestrutura web (URL) ou validar ferramenta CLI (output). |
| C2 | Subespecificação | MEDIUM | tasks.md T033 | "flag opcional para CI lento" em `.github/workflows/ci.yml` para Docker build é vaga — nenhum mecanismo definido (nome da flag, valor padrão, implementação). | Definir mecanismo antes de T033: ex. `workflow_dispatch` input `skip_docker_build: false`, ou GitHub Actions env var `SKIP_DOCKER_BUILD`. Adicionar à spec FR-018/FR-019 antes de Phase 6. |
| E1 | Inconsistência | MEDIUM | tasks.md T022 vs T025–T026 | T022 (Phase 3) adiciona mensagem BLOCKER quando testing: block existe mas serviços inacessíveis no momento de L5. T025–T026 (Phase 4) adiciona Phase 0 que inicia serviços ANTES de L5. Após Phase 4, o caminho de T022 só pode ser atingido se o startup da Phase 0 falhou — mas Phase 0 já emite BLOCKER nesse caso. T022 torna-se logicamente inacessível. | Manter ambos para defense-in-depth (não remover). Documentar T022 como "fallback safety net se Phase 0 não estiver presente" para clareza. Adicionar comentário em qa.md ao implementar. |
| A1 | Duplicação | LOW | tasks.md fases múltiplas | T024, T028, T031, T034 são tarefas de verificação `skill-lint + make test` repetidas em cada phase. Padrão intencional (guardrail), mas cria ruído e pode confundir o implementador se duas rodarem em paralelo. | Manter como guardrails explícitos — não consolidar. Adicionar nota de que são checkpoints, não tarefas de implementação. |
| B3 | Ambiguidade | LOW | tasks.md T030 | "docker adiciona `docker compose build` antes de start" na Deployment Smoke Phase gerada é ambíguo: deve ser task separada ou parte do start command? | Especificar que é task separada T{N}00: `docker compose build` (verificação de build), antes de T{N}01 (start). Isso mapeia para o bug exato do Epic 007 (Dockerfile com COPY path inválido). |
| C3 | Subespecificação | LOW | spec.md FR-021 | Schema de steps do `journeys.md` (campos `action`, `assert_status`, `assert_redirect`, `assert_contains`, `screenshot`) é referenciado apenas via `contracts/journeys_schema.md` — não está resumido em FR-021. Spec sem acesso ao contrato fica incompleta. | FR-021 já tem um exemplo mínimo. Adicionar link explícito: "Schema completo em `contracts/journeys_schema.md`." Já adequado para propósito prático. |
| E2 | Inconsistência | LOW | tasks.md — dependências | Comentário de dependência: "Phase 3 BLOCKS Phase 4 (Wave 2 adiciona ao qa.md que Wave 1 modificou)" é tecnicamente impreciso — ambas editam seções diferentes de qa.md (Wave 1 modifica comportamento L5; Wave 2 insere Phase 0 no início). Blocking é precautório (evitar conflitos de arquivo), não dependência lógica. | Alterar comentário para: "Phase 3 precede Phase 4 (ambas editam qa.md — executar sequencialmente para evitar conflitos de edição)." |
| E3 | Inconsistência | LOW | tasks.md T036 | T036 usa `--cwd .` (madruga.ai root) para `--parse-config` de prosauai. `--parse-config` lê `platform.yaml` via REPO_ROOT (não usa --cwd para lookup). O `--cwd .` é ignorado neste contexto, tornando o teste potencialmente enganoso. | Alterar T036 para documentar que `--cwd` é irrelevante para `--parse-config` (que usa REPO_ROOT para localizar platform.yaml). O teste ainda é válido; adicionar comentário explicativo. |

---

## Tabela de Cobertura de Requisitos

| Requisito | Task(s) | Fase | Status |
|-----------|---------|------|--------|
| FR-001 (testing: block opcional) | T013, T014 | Phase 2 | ⏳ Pendente |
| FR-002 (lint valida testing: schema) | T018, T019, T020 | Phase 2 | ⏳ Pendente |
| FR-003 (Copier template) | T017 | Phase 2 | ⏳ Pendente |
| FR-004 (retrocompatibilidade) | T018, T019, T020 | Phase 2 | ⏳ Pendente |
| FR-005 (qa_startup.py CLI) | T001, T011 | Phase 1 | ✅ Completo |
| FR-006 (startup types: docker/npm/make/venv/script/none) | T007 | Phase 1 | ✅ Completo |
| FR-007 (JSON output estruturado) | T011 | Phase 1 | ✅ Completo |
| FR-008 (--platform + --cwd) | T001, T011 | Phase 1 | ✅ Completo |
| FR-009 (env diff pré-runtime no QA skill) | T021 | Phase 3 | ⏳ Pendente |
| FR-010 (required_env ausente → BLOCKER) | T005, T021 | Phase 1 ✅ + Phase 3 ⏳ | Parcial |
| FR-011 (auto-start serviços no QA skill) | T025, T026 | Phase 4 | ⏳ Pendente |
| FR-012 (health check fail → BLOCKER) | T008, T022, T026 | Phase 1 ✅ + Phase 3 ⏳ + Phase 4 ⏳ | Parcial |
| FR-013 (validate URL reachability) | T009, T027 | Phase 1 ✅ + Phase 4 ⏳ | Parcial |
| FR-014 (screenshots frontend URLs) | T023 | Phase 3 | ⏳ Pendente |
| FR-015 (executar journeys) | T029 | Phase 5 | ⏳ Pendente |
| FR-016 (analyze URL coverage check) | T032 | Phase 6 | ⏳ Pendente |
| FR-017 (route detection FastAPI/Next.js + WARN) | T032 | Phase 6 | ⏳ Pendente |
| FR-018 (blueprint gera testing: skeleton) | T033 | Phase 6 | ⏳ Pendente |
| FR-019 (blueprint gera journeys.md template) | T033 | Phase 6 | ⏳ Pendente |
| FR-020 (speckit.tasks gera Deployment Smoke) | T030 | Phase 5 | ⏳ Pendente |
| FR-021 (journeys.md formato YAML machine-readable) | T015, T016, T029 | Phase 2 ⏳ + Phase 5 ⏳ | ⏳ Pendente |
| FR-022 (nunca expor valores de env vars) | T004, T005, T012 | Phase 1 | ✅ Completo |
| FR-023 (placeholder HTML 4 critérios) | T010, T012 | Phase 1 | ✅ Completo |

---

## Issues de Alinhamento com a Constituição

**Verificação realizada** — nenhuma violação encontrada:

| Princípio | Status | Evidência |
|-----------|--------|-----------|
| Pragmatismo (stdlib only) | ✅ PASS | qa_startup.py usa apenas subprocess, pathlib, urllib, re, json, argparse, time, os, yaml (pyyaml já presente) |
| TDD (testes antes/junto da implementação) | ✅ PASS | T012 (testes) concluído junto com T001–T011; 83 testes passando |
| Observability (JSON output estruturado) | ✅ PASS | --json flag disponível, saída estruturada com status/findings/health_checks/env_diff/urls |
| Aditivo/Retrocompatível | ✅ PASS | testing: block ausente → comportamento atual preservado (FR-004 explícito) |
| Automação de tarefas manuais | ✅ PASS | startup, env diff, health checks e URL validation eram manuais; agora automatizados |

---

## Tasks sem Requisito Mapeado

Nenhuma — todas as 39 tasks mapeiam para pelo menos 1 FR ou SC.

**Exceção intencional**: T024, T028, T031, T034 são guardrails de processo (skill-lint + make test) sem FR correspondente. Isso é correto — guardrails são infraestrutura de processo, não funcionalidade.

---

## Estado da Implementação (Phase 1)

| Artefato | LOC | Estimativa do Plano | Razão da Diferença |
|----------|-----|--------------------|--------------------|
| `qa_startup.py` | 883 | ~300 LOC | Docstrings, argparse, logging, tratamento de erros abrangente |
| `test_qa_startup.py` | 981 | ~250 LOC | 83 testes vs. estimativa base; cobertura mais completa que o mínimo |
| **Total Phase 1** | **1864** | ~550 LOC | 3.4x — consistente com fator CLAUDE.md "multiply by 1.5–2x" (levemente acima) |

**Qualidade da implementação Phase 1**:
- ✅ CLI interface completa: todos os 5 modos (--parse-config, --start, --validate-env, --validate-urls, --full)
- ✅ Exit codes corretos: 0=ok/warn, 1=blocker, 2=config error, 3=unexpected (verificado por testes)
- ✅ FR-022 respeitado: `env_present`/`env_missing` contêm apenas keys, nunca valores
- ✅ FR-023 implementado: 4 critérios de placeholder HTML, testados individualmente
- ✅ Invariante ADR: `docker compose down` nunca chamado
- ⚠️ `make test` global falha com INTERNALERROR em `test_sync_memory_module.py` (pré-existente, não causado por este epic) — ver issue D2

---

## Métricas

| Métrica | Valor |
|---------|-------|
| Total de Requisitos Funcionais | 23 FRs |
| Total de Critérios de Sucesso | 7 SCs |
| Total de Tasks | 39 |
| Tasks Completas | 12 (Phase 1) |
| Tasks Pendentes | 27 (Phases 2–7) |
| Cobertura FR→Task | 23/23 (100%) |
| Cobertura SC→Task | 7/7 (100%) |
| Issues CRITICAL | 0 |
| Issues HIGH | 2 (D1, D2) |
| Issues MEDIUM | 4 (B1, B2, C1, C2, E1) |
| Issues LOW | 6 (A1, B3, C3, E2, E3) |
| Total Issues | 12 |
| Contagem de Ambiguidades | 3 (B1, B2, B3) |
| Contagem de Duplicações | 1 (A1 — intencional) |
| Issues Críticos | 0 |

---

## Próximas Ações

### Antes de Phase 2 (Ação Imediata)

**Issue D2 — BLOCKER para SC-005**: O `make test` global falha com INTERNALERROR em `test_sync_memory_module.py` (pré-existente). T039 ("confirmar 0 failures") é impossível de atender.  
→ **Ação**: Documentar no tasks.md que T039 deve ser interpretado como "make test passes for test files owned by this epic + pre-existing failures excluded" OU investigar e corrigir `test_sync_memory_module.py` (pode ser out-of-scope).

**Issue C1 — Inconsistência em J-002**: Decidir se J-002 de madruga-ai testa URL web ou CLI.  
→ **Ação**: Antes de T015, alinhar título e step da jornada.

### Durante Phase 6 (Antes de T033)

**Issue C2 — Subespecificação em CI yml**: Definir o mecanismo de "flag opcional para Docker build lento" antes de implementar T033.  
→ **Ação**: Adicionar detalhe em FR-018 ou no body de T033 com o mecanismo escolhido (`workflow_dispatch` input recomendado).

### Prosseguir sem bloqueio

- Issues D1, B1, B2, E1, E2, E3, A1, B3, C3: podem ser resolvidos durante a implementação das phases respectivas sem impacto crítico.
- **Phase 2 pode iniciar imediatamente** — issue D2 é risco para Phase 7 (não para Phase 2).
- Ordem de implementação recomendada está correta; nenhuma dependência quebrada identificada.

---

## Oferta de Remediação

Para os 2 issues HIGH e 1 MEDIUM crítico, seguem rascunhos de remediação sem aplicação automática:

**D1 — Rascunho de task de regressão**:
```markdown
- [ ] T039b Validar detecção dos 7 bug-classes do Epic 007 via mocks:
  (1) validate_env com JWT_SECRET ausente → BLOCKER confirmado
  (2) execute_startup com Dockerfile inválido → returncode != 0 → BLOCKER confirmado  
  (3) validate_urls com localhost:8050 connection refused → BLOCKER confirmado
  (4) validate_urls com localhost:3000 retornando placeholder → WARN confirmado
  Executar: `python3 -m pytest tests/test_qa_startup.py -k "regression" -v`
```

**D2 — Rascunho de emenda para SC-005**:
```markdown
- **SC-005**: `make test` permanece verde para todos os testes relacionados a este epic.
  `test_qa_startup.py` passa com 0 falhas. Issues pré-existentes em `test_sync_memory_module.py`
  (INTERNALERROR pré-epic, não causado por mudanças deste epic) são excluídas desta verificação.
```

**C1 — Título correto para J-002 de madruga-ai** (se opção URL web):
```markdown
- J-002: Portal homepage responds (required: false)
  steps:
    - type: api
      action: GET http://localhost:4321
      assert_status: 200
```

---

---
handoff:
  from: speckit.analyze
  to: speckit.implement
  context: "Análise pós-Phase-1 completa. Phase 1 (qa_startup.py + 83 testes) implementada com qualidade alta — 100% cobertura FR-005, FR-006, FR-007, FR-008, FR-022, FR-023. 2 issues HIGH identificados: (D1) SC-001 não testado individualmente para os 7 bug-classes; (D2) make test global tem INTERNALERROR pré-existente em test_sync_memory_module.py impedindo verificação de SC-005 — documentar na interpretação de T039. Prosseguir com Phase 2 (T013-T020: platform.yaml + lint + journeys.md). Resolver C1 (J-002 título) antes de T015."
  blockers:
    - "D2: make test global falha com INTERNALERROR pré-existente — documentar exclusão antes de T039"
    - "C1: alinhar título/step de J-002 madruga-ai antes de T015"
  confidence: Alta
  kill_criteria: "Se _lint_testing_block() em platform_cli.py exigir refatoração breaking que quebre os testes existentes em test_platform.py, ou se a extensão do schema YAML de platform.yaml invalidar plataformas existentes sem testing: block."
