---
epic: 027-screen-flow-canvas
phase: analyze
created: 2026-05-05
sidebar:
  order: 27
---

# Specification Analysis Report — Epic 027 Screen Flow Canvas

**Artefatos analisados**:
- `pitch.md` (Shape Up pitch, 24 decisões 1-way-door)
- `spec.md` (49 FRs, 8 USs P1-P3, 22 SCs, 1 sessão de clarifications)
- `plan.md` (Technical Context, Constitution Check duplo, Project Structure)
- `tasks.md` (89 tasks em 12 fases — count nominal: 86)
- `constitution.md` v1.1.0 (referenciada)

**Modo**: read-only. Nenhum arquivo modificado.

---

## Findings Table

| ID  | Categoria       | Severidade | Localização                         | Resumo                                                                                       | Recomendação                                                                                          |
|-----|-----------------|-----------:|-------------------------------------|----------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------|
| I1  | Inconsistency   | MEDIUM     | spec SC-015 ↔ plan ↔ tasks T121      | spec SC-015 diz "24 decisões"; plan e tasks T121 dizem "26 decisões 1-way-door"               | Alinhar spec SC-015 para "26 decisões (24 pitch + 2 plan)" — plan/tasks são fonte mais recente        |
| I2  | Inconsistency   | LOW        | pitch Decision #10 ↔ spec FR-001     | Pitch Decision #10 lista 5 badges; spec FR-001 e plan/tasks adicionam `FALHOU` (6 total)      | Pitch é histórico (clarification 2026-05-05 introduziu FALHOU). Aceitar drift OU atualizar Decision #10 in-place |
| I3  | Inconsistency   | LOW        | pitch "Applicable Constraints" ↔ plan Technical Context | pitch cita `elkjs ^0.9` como dep nova; plan cita `elkjs ^0.11.1` (já presente devDep)         | Plan reflete o estado atual. Considerar atualizar pitch ou adicionar nota de evolução                  |
| A1  | Ambiguity       | MEDIUM     | tasks T017, T130-T135                | Phase 12 (Deployment Smoke) introduz `platforms/madruga-ai/testing/journeys.md` e referencia `platform.yaml.testing.urls` — não mencionado em spec/plan deste epic | Confirmar se infra `testing:` já existe noutros epics (ex.: 022-mermaid). Se não, é scope creep — mover pra epic separado ou justificar inclusão em decisions.md |
| C1  | Constitution    | LOW        | tasks T044                          | T044 modifica `.claude/settings.json` diretamente; convenções do repo (CLAUDE.md) exigem `/madruga:skills-mgmt` ou skill `update-config` | Reformular T044 para usar fluxo oficial (`update-config` skill) — invariante "edits a `.claude/**` via skills-mgmt" |
| U1  | Underspecified  | MEDIUM     | tasks T070 ↔ T113                   | T070 cria CI gate `size-budget` com placeholder `--limit 1MB` antes de T113 medir baseline   | Mover T070 para depois de T113 (Phase 10) OU explicitar em T070 que limite final é definido por T113   |
| C2  | Coverage gap    | LOW        | spec SC-013 (LFS quota monitoring)  | SC-013 mensura uso de LFS após 30 dias do epic em produção — sem task associada (operacional pós-launch) | Aceitar como outcome metric pós-deploy. OU adicionar T-monitoring criando issue/dashboard para tracking |
| C3  | Coverage gap    | LOW        | spec FR-046 ("workflow exits 1 if any failed") | T065 implementa `status: failed`; T062 testa retry+failure; mas o exit code do workflow é coberto por T069 implicitamente — não há assertion explícita | Adicionar assertion em T062 ou T073 que valida workflow `exit code == 1` quando ≥1 tela tem `status: failed` |
| D1  | Inconsistency   | LOW        | spec "Edge / Flow" entity            | spec usa "Edge / Flow" intercambiavelmente; YAML usa `flows[]`; renderer usa `ActionEdge.tsx` | Padronizar terminologia — sugiro `Flow` (semântico, consistente com YAML key) com `ActionEdge` sendo a representação visual |
| D2  | Duplication     | LOW        | tasks contagem total                | Summary diz "Total tasks: 86"; contagem real T001..T135 = 89 tasks (com gaps reservados)     | Atualizar Summary para 89 OU explicitar "86 tasks ativas + 3 reservadas para futura"                  |
| U2  | Underspecified  | LOW        | spec FR-015 ("pode parsear e2e/")    | "PODE opcionalmente" — comportamento opt-in não declarado em tasks T045                       | Decidir: feature do v1 (priorizar) ou backlog (mover para epic futuro). Atualizar spec accordingly      |
| F1  | Ambiguity       | LOW        | tasks T044                          | "Documentar fallback se hook framework ausente" — fallback não especificado                   | Especificar fallback (ex.: hook bash inline em `.git/hooks/pre-commit`) ou marcar como blocker se hook framework é mandatório |
| F2  | Ambiguity       | LOW        | spec edge case "ELK >30s"           | spec diz "build aborta com erro estruturado"; FR-049 diz "abort do build com erro claro" — mas tasks T025 não declara comportamento de abort, só timeout | Adicionar assertion em T025 ou em fixture-test que valida build aborta limpa quando ELK timeout |

---

## Coverage Summary Table

| Requirement Key      | Has Task?   | Task IDs                                     | Notes                                                            |
|----------------------|-------------|----------------------------------------------|------------------------------------------------------------------|
| FR-001 (vocabulary)  | ✅          | T010, T014                                   | 6 badges (incluindo FALHOU)                                      |
| FR-002 (schema_version) | ✅       | T010, T040                                   |                                                                  |
| FR-003 (validator rejects) | ✅    | T042, T040                                   |                                                                  |
| FR-004 (PostToolUse hook) | ✅     | T044                                         | C1: precisa fluxo skills-mgmt                                    |
| FR-005 (platform.yaml ext) | ✅    | T011                                         |                                                                  |
| FR-006/007 (enabled rules) | ✅    | T011, T050                                   |                                                                  |
| FR-008 (auth storage_state) | ✅   | T011, T071                                   |                                                                  |
| FR-009 (determinism) | ✅          | T011, T064                                   |                                                                  |
| FR-010 (path_rules)  | ✅          | T011, T071, T093                             |                                                                  |
| FR-011..015 (skill)  | ✅          | T012, T041, T045, T046                       |                                                                  |
| FR-016 (route conditional) | ✅    | T032, T034                                   |                                                                  |
| FR-017 (xyflow+ELK+SSG) | ✅      | T024, T025, T031                             |                                                                  |
| FR-018..021 (renderer) | ✅        | T029, T030, T031, T110, T116                 |                                                                  |
| FR-022..023 (wireframe/chrome) | ✅ | T027, T028                                   |                                                                  |
| FR-024..028 (hotspots) | ✅        | T080, T082, T083, T084, T065                 |                                                                  |
| FR-029..035 (capture) | ✅         | T064, T065, T066, T067, T069                 |                                                                  |
| FR-036..039 (drift)   | ✅         | T092, T093, T101, T102                       |                                                                  |
| FR-040..041 (bundle)  | ⚠️         | T113, T114, T115                             | U1: T070 precoce                                                 |
| FR-042 (test pyramid 4) | ✅       | T020-T023, T040, T060-T063, T080, T110-T112, T120 |                                                              |
| FR-043..044 (a11y/dark) | ✅       | T015, T022, T111, T116                       |                                                                  |
| FR-045..046 (retry/failed) | ⚠️    | T062, T065                                   | C3: exit code não asserto                                        |
| FR-047 (test_user_marker) | ✅     | T011, T050, T071                             |                                                                  |
| FR-048 (id charset regex) | ✅     | T010, T040                                   |                                                                  |
| FR-049 (limits 50/100, ELK 30s) | ⚠️ | T010, T025, T040                          | F2: comportamento de abort do build não asserto                  |
| US1..US8             | ✅          | (ver fases 3-10)                             | Todas histórias com tasks dedicadas                              |
| SC-013 (LFS monitoring) | ⚠️       | —                                            | C2: sem task — operacional pós-launch                            |

---

## Constitution Alignment Issues

Plan declara zero violações contra os 9 princípios (I-IX) em duas re-checks (pré-Phase 0 e pós-Phase 1). Sem inconsistências detectadas no plan.

⚠️ Atenção operacional (não bloqueante):
- **C1** (T044) potencialmente conflita com convenção CLAUDE.md "Edits a `.claude/commands/` e `.claude/knowledge/` MUST passar por `/madruga:skills-mgmt`". `.claude/settings.json` está fora desse escopo estrito mas conceitualmente similar — recomendar uso da skill `update-config`.

---

## Unmapped Tasks

Nenhuma task órfã detectada. Todas as 89 tasks mapeiam a FRs ou seções estruturais (Setup, Foundational, Polish, Deployment Smoke).

⚠️ Phase 12 (Deployment Smoke) tasks T017 + T130-T135 mapeiam parcialmente a SCs (SC-001 build OK), mas a infraestrutura `testing:` em platform.yaml (URLs + journeys) não tem origem em pitch/spec deste epic — ver A1.

---

## Metrics

- **Total Requirements (FRs)**: 49
- **Total User Stories**: 8 (3×P1, 4×P2, 1×P3)
- **Total Success Criteria**: 22 (mensuráveis)
- **Total Tasks**: 89 (T001-T135 com gaps reservados; summary diz 86)
- **Coverage %**: ~98% (FRs com ≥1 task) — 1 SC operacional (SC-013) sem task
- **Ambiguity Count**: 4 (A1, F1, F2, U2)
- **Inconsistency Count**: 4 (I1, I2, I3, D1, D2)
- **Underspecified Count**: 2 (U1, U2)
- **Coverage Gaps**: 2 (C2, C3)
- **Constitution Issues**: 1 (C1, low)
- **Critical Issues Count**: 0
- **High Issues Count**: 0

---

## URL Coverage Check

`platform.yaml.testing` block referenciado em tasks T017/T130-T135. Plataforma alvo (madruga-ai) tem stack Astro/portal — framework reconhecido (Astro page-based + dynamic routes `/[platform]/screens.astro`).

⚠️ Nova rota `[platform]/screens.astro` introduzida em T032. Se `testing.urls` será populado nesta epic (ver A1), considerar declarar:
- `http://localhost:4321/madruga-ai/screens` → expect 404 (madruga-ai opt-out)
- `http://localhost:4321/[fixture-platform]/screens?fixture=true` → expect 200 (dev only)

Como madruga-ai é opt-out, a rota `/madruga-ai/screens` NÃO será gerada — coerente com SC-002.

---

## Next Actions

**Status**: nenhum BLOCKER ou CRITICAL. Epic está pronto para `/speckit.implement` após decisões pontuais nos itens MEDIUM:

1. **I1** (decisões 24 vs 26): editar spec.md SC-015 para alinhar com plan/tasks. 1 linha.
2. **A1** (testing infra): decidir scope — manter (justificar em decisions.md) ou mover Phase 12 para epic separado.
3. **U1** (size-limit T070): mover task ou explicitar baseline-after.

Itens LOW podem ser tratados em PR de polish sem bloquear implementação:
- I2, I3: drift histórico aceitável.
- C1: refatorar T044 para usar `update-config` skill.
- D1, D2: padronização terminológica + count fix.
- C2: aceitar como outcome metric.
- C3: assertion adicional em test E2E.
- F1, F2: especificar fallback / abort behavior.
- U2: decidir parser e2e/ in/out v1.

**Comando sugerido**:
```bash
# Após resolver I1, A1, U1 manualmente:
/speckit.implement
```

---

## Remediation Offer

Posso sugerir edits concretos para os top issues (I1, A1, U1) — porém em modo autônomo (sem human-in-loop), não vou aplicar. Os itens são todos não-bloqueantes para `/speckit.implement` proceder, com a ressalva de que:

- I1 vai gerar pequena confusão na ADR final (T121) se não corrigido — recomendar fix antes do Polish phase.
- A1 (Deployment Smoke) é o item mais relevante para discussão: scope creep ou infra compartilhada?

---

handoff:
  from: speckit.analyze
  to: speckit.implement
  context: "Análise cross-artifact concluída. Zero CRITICAL, zero HIGH. 4 MEDIUM (I1 24-vs-26 decisões, A1 Deployment Smoke scope, U1 size-limit ordering, C2/C3 minor coverage gaps). 8 LOW (terminologia, drift histórico, fallbacks). Coverage de FRs ~98%, todas as 8 USs com tasks dedicadas. Test pyramid 4-layer integralmente tarefado. Recomendação: resolver I1+A1+U1 antes de implement; demais podem ir para polish PR. Vocabulário fechado e schema versioning consistentes em pitch/spec/plan/tasks."
  blockers: []
  confidence: Alta
  kill_criteria: "Se A1 (testing infra Phase 12) revelar dependência não documentada em outros epics que não foi shippada, Phase 12 vira blocker e deve ser reavaliada antes de implement."
