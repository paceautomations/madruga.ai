---
title: "Judge Report — Epic 018 Pipeline Hardening & Safety"
score: 82
verdict: pass
team: engineering
personas_run: [arch-reviewer, bug-hunter, simplifier, stress-tester]
personas_failed: []
updated: 2026-04-04
---
# Judge Report — Epic 018 Pipeline Hardening & Safety

## Score: 82%

**Verdict:** PASS
**Team:** Tech Reviewers (4 personas)

---

## Findings

### BLOCKERs (0)

Nenhum BLOCKER detectado.

### WARNINGs (2)

| # | Persona(s) | Finding | Localização | Sugestão |
|---|------------|---------|-------------|----------|
| W1 | arch-reviewer, bug-hunter, stress-tester | **Tratamento SIGINT apresenta 3 gaps**: (a) `signal.signal(signal.SIGINT, _handle_sigint)` registrado no escopo do módulo — qualquer import de `dag_executor` (daemon, testes) herda o handler que chama `sys.exit(130)`; (b) `except KeyboardInterrupt` em `run_pipeline_async` é redundante porque o signal handler customizado converte SIGINT em `SystemExit`, não `KeyboardInterrupt`; (c) `_active_process` nunca é setado no path async (`dispatch_node_async`), logo SIGINT durante dispatch async não termina o subprocess. | `dag_executor.py:62-78` (handler), `dag_executor.py:1211-1218` (KeyboardInterrupt), `dag_executor.py:846-865` (async dispatch) | Mover `signal.signal()` para dentro de `main()`. Remover o `except KeyboardInterrupt` redundante. Implementar tracking do `asyncio.subprocess.Process` no path async (ou usar `loop.add_signal_handler`). |
| W2 | bug-hunter, simplifier | **`validate_path_safe()` definida e testada mas nunca chamada em nenhum script**. Mais criticamente, o argumento `--epic` do `dag_executor.py` flui sem validação para construção de paths (`platform_dir / resolved`) e `mkdir(parents=True)`. Um epic slug malicioso poderia escapar o diretório esperado. | `errors.py:54-57` (definição), `dag_executor.py:1643` (`args.epic` sem validação), `dag_executor.py:1141-1146` (mkdir com path não validado) | Adicionar `validate_path_safe(args.epic)` ou regex dedicada para epic slug no `main()` de `dag_executor.py`. Integrar `validate_path_safe` nos demais entry points que aceitam paths do usuário. |

### NITs (8)

| # | Persona(s) | Finding | Localização | Sugestão |
|---|------------|---------|-------------|----------|
| N1 | arch-reviewer, simplifier | `DispatchError` e `GateError` definidos mas nunca levantados — dead code. A hierarquia está pré-posicionada para migração futura, mas sem call-site hoje. | `errors.py:31-36` | Aceitar como forward-positioning (pitch diz "começar pelos mais comuns") ou remover e adicionar quando houver call site. |
| N2 | arch-reviewer, bug-hunter | `validate_platform_name()` não aplicado em `post_save.py` — o argumento `--platform` flui direto para paths e queries sem validação, diferente dos outros 3 scripts. | `post_save.py` (record_save, main) | Adicionar `validate_platform_name(args.platform)` no `main()` de `post_save.py` para uniformidade. |
| N3 | bug-hunter | `PLATFORM_NAME_RE` permite hífens no final (`a-`) e não tem limite de comprimento. Trailing hyphens geram branch names estranhos; nomes muito longos podem exceder PATH_MAX. | `errors.py:11` | Mudar para `^[a-z](?:[a-z0-9-]*[a-z0-9])?$` e adicionar `len(name) <= 64`. |
| N4 | simplifier | `test_path_security.py` tem ~69 LOC duplicando cenários já cobertos em `test_errors.py` para as mesmas funções de validação. | `tests/test_path_security.py` (arquivo inteiro) | Consolidar casos únicos (ex: `$(whoami)`, backticks) no `test_errors.py` e remover o arquivo duplicado. |
| N5 | arch-reviewer, bug-hunter | `validate_path_safe` faz split apenas em `"/"`, não em `os.sep`. Em cenários com separadores mistos, `"foo\\..\\.bar"` passaria. Risco baixo (plataforma é Linux, paths vêm de YAML). | `errors.py:54-57` | Usar `pathlib.PurePosixPath` ou normalização antes da checagem, se cross-platform for necessário no futuro. |
| N6 | bug-hunter | Mensagens de erro em `validate_platform_name` ecoam input raw do usuário sem truncagem — risco de log flooding com inputs muito longos. | `errors.py:48-51` | Truncar nome ecoado nos primeiros 50 chars. |
| N7 | stress-tester | `dispatch_with_retry` (sync) usa backoff fixo sem jitter (`time.sleep(backoff)` com [5, 10, 20]s), enquanto o path async adiciona jitter. Thundering herd se múltiplos pipelines sync retentam simultaneamente. | `dag_executor.py:792-793` | Adicionar jitter: `time.sleep(backoff + random.uniform(0, backoff * 0.3))`. |
| N8 | stress-tester | SIGINT não completa a trace — `complete_trace()` nunca é chamado antes do `sys.exit(130)`. Traces ficam em status "running" indefinidamente. O path `--resume` limpa runs stale mas não traces. | `dag_executor.py:74`, `dag_executor.py:1220-1226` | Adicionar `complete_trace(conn, trace_id, status="interrupted")` no handler de SIGINT/KeyboardInterrupt. |

---

## Findings Descartados pelo Judge

| # | Persona | Finding Original | Motivo do Descarte |
|---|---------|-----------------|-------------------|
| D1 | bug-hunter | ensure_repo.py lock file race on cleanup (flock + unlink TOCTOU) | Código pré-existente, não modificado por este epic. |
| D2 | bug-hunter | Gate coercion silently hides config errors — should fail-fast | By-design per spec FR-002: "treat unrecognized values as human (fail-closed)". Pitch define este comportamento explicitamente. |
| D3 | stress-tester | ensure_repo.py git clone/fetch no timeout | Código pré-existente, não modificado por este epic. |
| D4 | stress-tester | ensure_repo.py flock blocks indefinitely | Código pré-existente, não modificado por este epic. |
| D5 | stress-tester | _handle_auto_escalate raw SQL outside transaction | Código pré-existente, não modificado por este epic. |
| D6 | simplifier | TestConstants e TestErrorHierarchy triviais | Testes não são código de produção; testes triviais não prejudicam e servem como documentação da hierarquia. |
| D7 | arch-reviewer | Mutable lists in frozen dataclass (outputs, depends) | Pattern padrão Python; frozen aplica-se a field reassignment. O risk de mutação é teórico — nenhum call site modifica as listas. |

---

## Reclassificações pelo Judge

| # | Persona | Severidade Original | Severidade Final | Justificativa |
|---|---------|---------------------|-----------------|---------------|
| R1 | bug-hunter | HIGH (SIGINT race) | WARNING (W1) | O signal handler customizado converte SIGINT em SystemExit, não KeyboardInterrupt. Os handlers não competem — o `except KeyboardInterrupt` é dead code (redundante), não racy. O risco real é a falta de tracking async, não a race condition. |
| R2 | bug-hunter | HIGH (trailing hyphens, no max length) | NIT (N3) | Edge case em ferramenta CLI interna usada por equipe pequena. Trailing hyphen não é security vulnerability. |
| R3 | bug-hunter | MEDIUM (validate_path_safe backslash) | NIT (N5) | Plataforma Linux-only, paths de YAML. Risco cross-platform é teórico. |
| R4 | bug-hunter | MEDIUM (ensure_repo lock file race) | DESCARTADO (D1) | Código pré-existente fora do escopo do epic. |
| R5 | bug-hunter | MEDIUM (_active_process async) | WARNING (combinado em W1) | Issue real mas severidade MEDIUM é adequada, não HIGH. Combinado com outros gaps de SIGINT. |

---

## Safety Net — Decisões 1-Way-Door

| # | Decisão | Score de Risco | Detectado por Classifier? | Veredicto |
|---|---------|----------------|--------------------------|-----------|
| — | Nenhuma decisão 1-way-door encontrada neste epic | — | — | N/A |

Este epic aplica patterns já provados (context managers, dataclasses, signal handlers). Não há decisões arquiteturais irreversíveis — todas as mudanças são incrementais e reversíveis.

---

## Personas que Falharam

Nenhuma — todas 4 personas completaram com sucesso.

---

## Resumo por Persona

| Persona | Findings Brutos | Aceitos | Descartados | Reclassificados |
|---------|-----------------|---------|-------------|-----------------|
| arch-reviewer | 5 | 4 | 1 (D7) | 0 |
| bug-hunter | 11 | 6 | 2 (D1, D2) | 3 (R1→W, R2→N, R3→N) |
| simplifier | 5 | 3 | 2 (D6) | 0 |
| stress-tester | 9 | 4 | 3 (D3, D4, D5) | 0 |
| **Total** | **30** | **17** | **8** | **3** |

Nota: findings duplicados entre personas foram consolidados (ex: SIGINT tracking → W1 combina 3 personas).

---

## Recomendações

### Antes do merge (W1 + W2)

1. **W1 — SIGINT handler**: Mover `signal.signal(signal.SIGINT, ...)` para dentro de `main()` para evitar side-effects no import. Remover o `except KeyboardInterrupt` redundante em `run_pipeline_async`. O gap do async dispatch pode ser endereçado em epic futuro (020 — refactoring de db.py/executor).

2. **W2 — Epic slug sem validação**: Adicionar `validate_path_safe(args.epic)` no `main()` de `dag_executor.py` (1 linha). Opcionalmente, criar regex dedicada para epic slugs (ex: `^[0-9]{3}-[a-z0-9-]+$`).

### Nice-to-have (NITs — podem ir para backlog)

3. **N1**: DispatchError/GateError podem ficar como forward-positioning, mas documentar a intenção com comentário.
4. **N2**: Adicionar `validate_platform_name` em `post_save.py` para uniformidade.
5. **N3**: Refinar regex para bloquear trailing hyphens e limitar comprimento.
6. **N8**: Completar trace em status "interrupted" no handler de shutdown.

---

## Métricas

| Métrica | Valor |
|---------|-------|
| Personas executadas | 4/4 |
| Findings brutos (total) | 30 |
| Findings aceitos (após Judge) | 10 (2 WARNING + 8 NIT) |
| Findings descartados | 8 |
| Reclassificados | 3 |
| Duplicados consolidados | 7 |
| Score final | 82% |
| Verdict | **PASS** |
