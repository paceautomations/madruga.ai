---
epic: 026-runtime-qa-testing-pyramid
created: 2026-04-16
updated: 2026-04-16
---
# Registro de Decisões — Epic 026

1. `[2026-04-16 epic-context]` Testing config declarada como bloco `testing:` em `platform.yaml` — não arquivo separado `testing/manifest.yaml`. (ref: ADR-004 simplicidade)
2. `[2026-04-16 epic-context]` Implement usa Edit/Write direto em `.claude/commands/**` — skills-mgmt incompatível com bare-lite dispatch do Easter (`--disable-slash-commands`). PostToolUse hook valida automaticamente. (ref: ADR-021 bare-lite flags)
3. `[2026-04-16 epic-context]` Novo comportamento de QA ativa default-on quando `platform.yaml` tem `testing:` block — sem feature flag adicional. (ref: ADR-004 zero config)
4. `[2026-04-16 epic-context]` `qa_startup.py` CLI com `--platform` (para achar `platform.yaml` via REPO_ROOT) e `--cwd` (para executar comandos no repo da plataforma). (ref: padrão implement_remote.py)
5. `[2026-04-16 epic-context]` `journeys.md` separado do `platform.yaml` por ser documento longo e textual; referenciado via `testing.journeys_file`. (ref: ADR-004 pragmatismo)
6. `[2026-04-16 epic-context]` `testing:` block adicionado neste epic a madruga-ai, prosauai e template Copier. Prosauai valida infraestrutura com serviços Docker reais. (ref: validação end-to-end)
7. `[2026-04-16 epic-context]` L5/L6 BLOCKER (não SKIP silencioso) quando `testing:` block existe mas serviços não acessíveis. (ref: MAKE_TEST_GREAT_AGAIN.md GAP-01/03)
8. `[2026-04-16 epic-context]` `madruga:blueprint` passa a gerar `testing:` skeleton em `platform.yaml` + `journeys.md` template + `.github/workflows/ci.yml` para plataformas com `repo:` binding. (ref: GAP-08, GAP-11)
9. `[2026-04-16 epic-context]` `speckit.tasks` adiciona `## Phase N: Deployment Smoke` como última fase obrigatória adaptada ao `startup.type`. (ref: GAP-09)
10. `[2026-04-16 epic-context]` `speckit.analyze` (pós-implement) extrai rotas do diff e compara com `testing.urls` — URLs não declaradas → HIGH finding. (ref: GAP-12)
11. `[2026-04-16 epic-context]` Lifecycle do testing: block: (a) novas plataformas — Copier gera skeleton, blueprint preenche + cria journeys.md; (b) retrofit — speckit.tasks detecta ausência e gera Phase 1: Testing Foundation com T001/T002; (c) manutenção — reconcile verifica journeys.md atualizado após cada epic. (ref: pipeline-dag-knowledge.md L1/L2)
