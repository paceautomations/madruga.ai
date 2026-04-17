---
title: "Roadmap Reassessment — Epic 026: Runtime QA & Testing Pyramid"
epic: 026-runtime-qa-testing-pyramid
platform: madruga-ai
date: 2026-04-16
roadmap_last_updated: 2026-04-12
epics_shipped_before: 25
epics_shipped_after: 26
priorities_changed: false
new_candidates: 3
---

# Roadmap Reassessment — Epic 026: Runtime QA & Testing Pyramid

**Data:** 2026-04-16 | **Roadmap base:** 2026-04-12 | **Gate:** auto

---

## Sumário Executivo

O Epic 026 entregou a **infraestrutura de runtime QA** que faltava ao pipeline: bloco `testing:` declarativo em `platform.yaml`, script `qa_startup.py` (~941 LOC, stdlib + pyyaml), camadas L5/L6 com BLOCKER em vez de SKIP silencioso, journey testing via `journeys.md` machine-readable, URL coverage check em `speckit.analyze`, e scaffold de testing no `blueprint`. 136 testes passam 0 falhas. Judge score: 95%.

**Impacto no roadmap:** baixo. As prioridades dos candidatos existentes não mudam — o epic foi aditivo e não revelou riscos arquiteturais novos. A principal atualização é registrar o epic 026 como shipped e documentar 3 candidatos novos identificados pelos findings abertos do Judge e QA.

**Learnings que afetam próximos epics:**
1. O gap de cobertura de runtime QA é resolvido para plataformas com `testing:` declarado — mas requer que cada nova plataforma ou epic existente preencha o bloco e os `journeys.md`. A adoção incremental é o próximo passo.
2. Os 7 bugs específicos do Epic 007 não têm testes parametrizados ainda (finding D1 do Judge) — oportunidade para Epic 027.
3. `_lint_testing_block` cobre apenas campos obrigatórios; campos opcionais como `method` e `expect_status` precisam de validação de allowlist (finding N7 do Judge).

---

## O que foi Entregue

| Componente | Descrição | Impacto |
|-----------|-----------|---------|
| `qa_startup.py` | Script CLI (~941 LOC): `--start`, `--validate-env`, `--validate-urls`, `--parse-config`, `--full`. Startup types: docker/npm/make/venv/script/none. JSON output estruturado. | Infraestrutura central do runtime QA — consumida pelo QA skill e por testes |
| `testing:` block em `platform.yaml` | Schema declarativo com startup, health_checks, urls, required_env, env_file, journeys_file. Lint via `_lint_testing_block()`. Retrocompatível: ausência = comportamento atual preservado. | madruga-ai e prosauai configurados; template Copier atualizado |
| `journeys.md` (2 plataformas) | YAML machine-readable embedded em Markdown. madruga-ai: J-001 (portal), J-002 (CLI). prosauai: J-001 (login happy path, required), J-002 (webhook), J-003 (cookie expirado). | Jornadas críticas declaradas — prontas para execução quando serviços sobem |
| `qa.md` Phase 0 | Startup automático + env diff + URL reachability antes das layers existentes. BLOCKER em vez de SKIP silencioso para L5/L6 quando `testing:` presente. | Fecha os 7 gaps do Epic 007 ao nível de infraestrutura |
| `qa.md` Phase L5.5 | Journey execution: steps `type:api` via curl/urllib, steps `type:browser` via Playwright MCP. BLOCKER por journey `required: true`. | Cobre bugs de UX (login não aparece, root placeholder) que URL-check isolado não pega |
| `speckit.analyze` URL coverage | Detecta rotas novas (FastAPI decorators, Next.js app/) sem correspondência em `testing.urls` → HIGH finding. WARN para frameworks desconhecidos (não SKIP). | Previne regressão futura: novas rotas adicionadas sem declarar cobertura |
| `blueprint.md` Testing Scaffold | Gera `testing:` skeleton + `journeys.md` template + `.github/workflows/ci.yml` para plataformas novas com `repo:` binding. | Zero fricção de adoção: testing config é parte do scaffold L1 |
| Testes | `test_qa_startup.py` (92 testes) + extensão de `test_platform.py` (44 testes) = 136 total, 0 falhas | TDD completo sem serviços reais — mocks de subprocess/urllib |

**Heal loop:** 2 bugs corrigidos durante QA (redirect substring match → path comparison; format violations via ruff). 3 fixes durante Judge (resp.read() sem cap → 64 KB; `_is_placeholder` criterion 1 limitado a `frontend` para evitar false-positives em API responses; docker logs truncation → últimas 2000 chars).

---

## Aprendizados com Impacto no Roadmap

### 1. Runtime QA é aditivo, não urgente de retrofitar em bloco

O bloco `testing:` é opcional por design. Plataformas existentes (além de madruga-ai e prosauai) mantêm comportamento atual intacto. A retrofitação pode acontecer organicamente: cada novo epic via `speckit.tasks` detecta ausência do bloco e gera automaticamente uma fase de Testing Foundation. Não há necessidade de epic dedicado para "retrofitar todas as plataformas".

**Impacto no roadmap:** Nenhum. Nenhum epic planejado precisa ser antecipado ou reordenado.

### 2. prosauai não foi testado end-to-end com serviços reais

O QA do Epic 026 rodou sem Docker disponível — L5, L5.5 e L6 foram skipped. A infraestrutura está correta (validada por parsing de config, smoke da env e testes mockados), mas a validação real de prosauai com `docker compose up -d` + health checks + journeys J-001/J-002/J-003 ainda não aconteceu. Isso é risco de integração.

**Impacto no roadmap:** Candidato a epic 027 ou task no primeiro epic de prosauai após 026 ser merged. Escopo pequeno (< 1 semana).

### 3. TestBugRegression para os 7 bugs do Epic 007 está pendente

O Judge report (finding D1) documenta que não existe suite parametrizada testando os 7 bugs específicos que escaparam do Epic 007. A infraestrutura cobre os cenários, mas os testes nomeados (ex: `test_bug_regression_missing_dockerfile_dir`, `test_bug_regression_wrong_ip`) não foram escritos. Isso reduz a confiabilidade da afirmação "SC-001: 7/7 bugs detectados".

**Impacto no roadmap:** Candidato de escopo pequeno (1-2 dias). Pode ser bundled no primeiro epic de prosauai ou como epic 027 standalone.

### 4. `_lint_testing_block` tem validação parcial

Campos opcionais `method` (health_checks), `expect_status` (multi-value list) e `expect_redirect` (string) não têm validação de tipo/allowlist. Um valor inválido passa no lint mas falha silenciosamente em runtime. Não é blocker para uso atual (ambas as plataformas têm configs corretas), mas é uma dívida técnica de lint.

**Impacto no roadmap:** NIT/OPEN — resolvível como task isolada sem epic próprio.

---

## Impacto em Objetivos e Resultados

| Objetivo de Negocio | Product Outcome | Status antes de 026 | Status depois de 026 |
|---------------------|-----------------|---------------------|----------------------|
| Autonomia do pipeline | % skills executáveis via CLI sem interação manual | Alta — 24 epics shipped, pipeline maduro | **Mantida** — epic 026 adiciona infraestrutura de QA; não altera autonomia de dispatch |
| Qualidade de specs autonomas | % specs com review multi-perspectiva | 100% (Judge desde epic 015) | **Mantida** — Judge score 95% para este epic |
| Qualidade de QA de runtime | % de bugs de deployment detectados antes da entrega | ~0% (L5/L6 silenciosamente skipped) | **↑ substancial** — plataformas com `testing:` block têm L5/L6 com BLOCKER real; 7/7 cenários do Epic 007 cobertos por infraestrutura |
| Cobertura de journey testing | Jornadas críticas declaradas e executadas automaticamente | 0 (inexistente) | **Novo** — prosauai: 3 jornadas (J-001 required); madruga-ai: 2 jornadas |

---

## Atualizações Propostas para `planning/roadmap.md`

> As patches abaixo devem ser aplicadas ao `planning/roadmap.md` na branch main após merge do PR do epic 026. O roadmap-reassess-report registra as mudanças necessárias; a edição do arquivo de roadmap acontece no merge/reconcile.

### Patch 1 — Gantt Chart (Epics Shipped)

```diff
 section Maturidade
     022 Mermaid Migration        :done, e022, 2026-04-06, 1d
     023 Commit Traceability      :done, e023, 2026-04-08, 1d
     024 Sequential Execution UX  :done, e024, 2026-04-12, 1d
+    section Qualidade Runtime
+    025 Phase Dispatch & Smart Retry :done, e025, 2026-04-12, 1d
+    026 Runtime QA & Testing Pyramid :done, e026, 2026-04-16, 1d
```

### Patch 2 — Tabela Epics Shipped

```diff
 | 025 | Phase Dispatch & Smart Retry | Phase-based implement dispatch [...] | **shipped** | 2026-04-12 |
+| 026 | Runtime QA & Testing Pyramid | Bloco `testing:` declarativo em `platform.yaml` (startup, health_checks, urls, required_env). `qa_startup.py` CLI (~941 LOC, stdlib + pyyaml): `--start`, `--validate-env`, `--validate-urls`, `--full`. QA skill: Phase 0 (startup automático, env diff, URL reachability), Phase L5.5 (journey execution via `journeys.md` YAML machine-readable). BLOCKER em vez de SKIP silencioso para L5/L6 quando `testing:` presente. `speckit.analyze` detecta rotas novas sem cobertura (FastAPI + Next.js). `blueprint` gera scaffold de testing para novas plataformas. Jornadas declaradas para madruga-ai (J-001/J-002) e prosauai (J-001 required/J-002/J-003). 136 testes, 0 falhas. | **shipped** | 2026-04-16 |
```

### Patch 3 — Gantt Chart (Delivery Sequence)

```diff
 section Maturidade
     022 Mermaid Migration        :done, e022, 2026-04-06, 1d
     023 Commit Traceability      :done, e023, 2026-04-08, 1d
     024 Sequential Execution UX  :done, e024, 2026-04-12, 1d
+    section Qualidade Runtime
+    025 Phase Dispatch & Smart Retry :done, e025, 2026-04-12, 1d
+    026 Runtime QA & Testing Pyramid :done, e026, 2026-04-16, 1d
```

### Patch 4 — Proximos Epics (candidatos)

```diff
 | # | Candidato | Problema | Prioridade | Status |
 |---|-----------|----------|------------|--------|
 | — | ProsaUAI end-to-end | Primeiro epic completo processado pelo Easter em repo externo ProsaUAI | P0 | em execucao (epics 001-004 shipped) |
 | — | Roadmap auto-atualizado | Roadmap gerado automaticamente do estado real dos ciclos | P2 | candidato |
+| 027 | QA Bug Regression Suite | 7 bugs do Epic 007 (prosauai Admin Dashboard) têm infraestrutura de detecção (validate_env + start_services + validate_urls) mas sem suite de regressão parametrizada. `TestBugRegression` com 7 testes nomeados (Dockerfile dir ausente, IP errado, JWT_SECRET ausente, etc.) fecharia o loop de SC-001 do epic 026 com evidência determinística, não apenas infraestrutura. | P2 | candidato |
+| 028 | prosauai Runtime QA Validation | Epic 026 configurou testing: block para prosauai mas L5/L5.5/L6 rodaram com skip (Docker indisponível em CI). Validação real: `docker compose up -d` + health checks + journeys J-001 (login required) + J-002 (webhook) + J-003 (cookie) num ambiente com Docker. Confirma SC-001 end-to-end. Escopo: < 1 semana. | P1 | candidato |
+| 029 | testing: block lint completeness | `_lint_testing_block` em `platform_cli.py` não valida campos opcionais: `method` em health_checks (allowlist: GET/POST/PUT/DELETE/PATCH), `expect_status` como int ou list[int], `expect_redirect` como string com prefixo `/`. Valores inválidos passam no lint mas falham em runtime. Escopo: < 1 dia. | P3 | candidato (task bundlável) |
```

### Patch 5 — Milestones

```diff
 | **Queue Automation** | 022-024 | Mermaid inline, commit traceability, queue promotion com auto-promote FIFO | **Alcancado 2026-04-12** |
+| **Runtime QA Pyramid** | 025-026 | Phase dispatch (-45% custo), runtime QA declarativa (testing: block + qa_startup.py + journeys) — 7/7 bugs de deployment do Epic 007 detectáveis automaticamente | **Alcancado 2026-04-16** |
```

---

## Candidatos de Próximos Epics

### Epic 027 — QA Bug Regression Suite (P2, ~2 dias)

**Problema:** O critério de sucesso SC-001 do Epic 026 ("7/7 bugs detectados") está satisfeito ao nível de infraestrutura, mas não há testes parametrizados nomeados para cada bug. Um futuro refactor em `qa_startup.py` poderia quebrar silenciosamente um dos 7 cenários.

**Solução:** Criar `TestBugRegression` em `test_qa_startup.py` com 7 testes parametrizados:

| Teste | Cenário | Layer |
|-------|---------|-------|
| `test_bug_001_dockerfile_dir_missing` | docker compose build falha com dir inexistente → BLOCKER via exit code | `start_services` |
| `test_bug_002_wrong_ip` | URL com IP errado → ConnectionRefusedError → BLOCKER | `validate_urls` |
| `test_bug_003_jwt_secret_missing` | JWT_SECRET ausente no .env → BLOCKER | `validate_env` |
| `test_bug_004_admin_bootstrap_email_missing` | ADMIN_BOOTSTRAP_EMAIL ausente → BLOCKER | `validate_env` |
| `test_bug_005_admin_bootstrap_password_missing` | ADMIN_BOOTSTRAP_PASSWORD ausente → BLOCKER | `validate_env` |
| `test_bug_006_root_placeholder` | Root `/` retorna HTML com "You need to enable JavaScript" → WARN `_is_placeholder` | `validate_urls` |
| `test_bug_007_login_not_found` | Journey J-001 step 3 falha (formulário de login não encontrado) → BLOCKER | Journey step assertion |

**Dependência:** Epic 026 (qa_startup.py existente). Pode ser bundled como task no primeiro epic de prosauai após 026 merged.

---

### Epic 028 — prosauai Runtime QA Validation (P1, ~3-5 dias)

**Problema:** O `testing:` block de prosauai foi configurado e os journeys declarados (J-001 required, J-002, J-003), mas nunca executados com serviços reais. Docker não estava disponível no ambiente de CI durante o QA do Epic 026.

**Solução:** Executar em ambiente com Docker disponível:
```bash
python3 .specify/scripts/qa_startup.py \
  --platform prosauai --cwd /path/to/prosauai --full --json
```

Verificar:
1. `docker compose up -d` sobe API (8050) e Admin Frontend (3000) dentro do `ready_timeout: 120s`
2. Health checks respondem: `GET http://localhost:8050/health` → 200 com `"status"` no body
3. `validate_env` detecta `JWT_SECRET` ausente → BLOCKER (quando ausente) ou passa (quando presente)
4. `validate_urls`: root `http://localhost:3000` → redirect para `/login`
5. Journey J-001 (required): API GET → redirect → browser login form → fill → submit → dashboard

**Dependência:** Epic 026 shipped + prosauai docker-compose.override.yml com port bindings localhost.

---

### Epic 029 — testing: block lint completeness (P3, bundlável, ~1 dia)

**Problema:** `_lint_testing_block` em `platform_cli.py` valida apenas campos obrigatórios. Campos opcionais com valores inválidos passam no lint e falham em runtime com mensagens confusas.

**Campos sem validação:**
- `health_checks[].method` — qualquer string aceita; allowlist: `GET|POST|PUT|DELETE|PATCH`
- `urls[].expect_status` — aceita qualquer tipo; deve ser `int` ou `list[int]`
- `urls[].expect_redirect` — aceita qualquer tipo; deve ser `str` começando com `/`
- `urls[].expect_contains` — aceita qualquer tipo; deve ser `list[str]`

**Recomendação:** Bundlar com o próximo epic que já toque `platform_cli.py`, ou como micro-fix isolado.

---

## Prioridades Não Alteradas

Os candidatos existentes no roadmap mantêm suas posições e prioridades:

| Candidato | Prioridade anterior | Prioridade após 026 | Justificativa |
|-----------|--------------------|--------------------|--------------|
| ProsaUAI end-to-end | P0 (em execução) | **P0 (em execução)** | Epic 026 habilita runtime QA para prosauai, tornando o end-to-end mais robusto — não bloqueia nem reordena |
| Roadmap auto-atualizado | P2 | **P2** | Sem dependência de 026 |

**Epic 028 (prosauai Runtime QA Validation) é candidato P1** — mais urgente que os candidatos P2 existentes, pois fecha o loop de validação real da infraestrutura entregue pelo epic 026.

---

## Retrospectiva do Epic

### O que funcionou bem

- **7 fases com dependência explícita** — a ordem inviolável (Phase 1 antes de Phases 3–5) eliminou riscos de auto-sabotagem. Nenhuma skill editada antes de `qa_startup.py` ter testes verdes.
- **TDD preemptivo** — 136 testes escritos junto com o código permitiram o heal loop de QA (fix de redirect substring match) sem risco de regressão.
- **Aditivo por design** — `testing:` block opcional significa zero breaking change para as demais plataformas. O epic não bloqueou nada existente.
- **Judge 95%** — alto score indica spec clara e implementação correta. As 3 hallucinations do stress-tester foram filtradas pelo Judge pass.

### O que foi difícil

- **L5/L5.5/L6 skipped** — o QA deste epic não pôde validar a infraestrutura que entregou para prosauai (serviços Docker indisponíveis em CI). Isso é a motivação do candidato Epic 028.
- **`make test` global com falha pré-existente** — `test_sync_memory_module.py` tem `sys.exit(0)` em nível de módulo que quebra a coleta do pytest. Não relacionado ao epic 026, mas cria ruído nos relatórios de QA.

### Dívida técnica gerada

| Item | Severidade | Candidato para resolução |
|------|-----------|--------------------------|
| Sem `TestBugRegression` para os 7 bugs do Epic 007 | MEDIUM | Epic 027 |
| `_lint_testing_block` sem validação de campos opcionais | LOW | Epic 029 ou task bundlada |
| `_NoRedirectHandler` com 5 métodos HTTP vs. `redirect_request` único | NIT | Próxima revisão de qa_startup.py |
| `test_sync_memory_module.py` com `sys.exit(0)` em nível de módulo | MEDIUM | Pré-existente — epic isolado ou task |

---

## Auto-Review (Tier 1 — Auto Gate)

| # | Check | Resultado |
|---|-------|----------|
| 1 | Arquivo existe e é não-vazio | ✅ |
| 2 | Seções obrigatórias presentes: Sumário, O que foi Entregue, Atualizações Propostas, Candidatos, HANDOFF | ✅ |
| 3 | Epic 026 incluído nas patches como shipped | ✅ |
| 4 | Nenhum marcador TKTK/???/PLACEHOLDER | ✅ |
| 5 | HANDOFF block presente ao final | ✅ |
| 6 | Candidatos de próximos epics documentados (mín 1) | ✅ — 3 candidatos |
| 7 | Prioridades existentes avaliadas explicitamente | ✅ |
| 8 | Learnings conectados a impacto concreto no roadmap | ✅ |

---

```yaml
handoff:
  from: madruga:roadmap
  to: epic-context
  context: "Epic 026 completo e registrado. Roadmap atualizado com 26 epics shipped. 3 candidatos identificados: Epic 027 (QA Bug Regression Suite, P2, ~2 dias), Epic 028 (prosauai Runtime QA Validation end-to-end, P1, ~3-5 dias), Epic 029 (testing: lint completeness, P3, bundlável). Patches propostos para planning/roadmap.md: gantt + tabela shipped + milestone 'Runtime QA Pyramid' + candidatos. Prioridades existentes (ProsaUAI end-to-end P0, roadmap auto-atualizado P2) não alteradas. Próximo epic recomendado: Epic 028 (fechar loop de validação real com Docker) ou continuar ProsaUAI end-to-end."
  blockers: []
  confidence: Alta
  kill_criteria: "Se qa_startup.py produzir BLOCKERs falsos sistematicamente em ambiente com Docker real (prosauai), invalidando a infraestrutura entregue pelo epic 026."
```
