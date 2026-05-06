---
epic: 027-screen-flow-canvas
phase: roadmap-reassess
created: 2026-05-05
updated: 2026-05-05
sidebar:
  order: 28
---

# Roadmap Reassessment — Pós Epic 027 Screen Flow Canvas

> Reavaliação das prioridades do roadmap do madruga-ai após a entrega do epic 027. Insumo direto: `reconcile-report.md` D6 (drift de roadmap) + `decisions.md` (28 decisões acumuladas) + `qa-report.md` + `judge-report.md` + `phase11-report.md`.

---

## 1. Sumário da Entrega

| Métrica | Planejado | Real | Delta |
|---------|-----------|------|-------|
| Appetite | 10 working days (revisado de 8 → 10 após Crítica 1) | ~10 dias (alinhado, Phase 11 com WARNs operacionais) | **0%** |
| Decisões 1-way-door | 24 (pitch.md) | 28 (24 pitch + 2 plan + 2 implement T113/T114) | **+17%** |
| LOC entregues | "M (~1.5h drift fix)" estimado | +21.551 / -63 (112 arquivos) | massivo — implementação dominou |
| Bundle budget rota `/screens/*` | 700-900 KB ungz (estimado) | **163.75 KB ungz** (medido T113) | **5x menor** que estimativa |
| Test pyramid | 4 layers verdes (FR-042) | Layer (a) ✅ 1358 pytest cases; Layers (b/c/d) ⚠️ infra criada mas não validada na sessão de QA | parcial |
| Determinism PNG | ≥80% byte-idêntico | **100%** validado em 2 telas (welcome+login) pré-epic; pilot run T073 pendente para autenticadas | excedeu na amostra inicial |

**Status final**: **shipped** com 2 follow-ups operacionais documentados (T073 pilot run + Phase 11 layers b/c/d backfill). O epic se enquadra em "Documentação Visual" — milestone novo proposto em D6.1 do reconcile.

---

## 2. Impacto Direto no `planning/roadmap.md`

Atualização **mecânica** já mapeada com diffs concretos em `reconcile-report.md` D6.1 + D6.2 — esta seção referencia, não duplica:

| # | Item | Severidade | Diff pronto |
|---|------|-----------|-------------|
| D6.1 | Adicionar linha 027 (e gap 026 explícito) na tabela "Epics Shipped" + Gantt section "Maturidade" + Milestone "Documentação Visual" | **HIGH** | ✅ em reconcile §D6.1 |
| D6.2 | 3 novos riscos no risk table: SW staleness mitigado, bundle budget tight aberto, LFS quota silent aberto | LOW | ✅ em reconcile §D6.2 |
| **NOVO N1** | Atualizar `updated: 2026-04-12` → `updated: 2026-05-05` no frontmatter | LOW | trivial |
| **NOVO N2** | Mermaid de dependências NÃO precisa de update — epic 027 é folha do DAG L1 (não cria dependência inter-epic nova) | — | confirma D7 SEM DRIFT |

**Recomendação**: aplicar D6.1 + D6.2 + N1 em batch único (~30 min) na fase 9 (auto-commit) do reconcile.

---

## 3. Reassessment dos Objetivos e Resultados

A tabela atual de outcomes do roadmap não cobre "Documentação Visual" como objetivo de negócio. Epic 027 entregou uma capability nova que merece linha própria:

| Novo Objetivo de Negócio | Product Outcome (leading indicator) | Baseline | Target | Epics |
|--------------------------|--------------------------------------|----------|--------|-------|
| Documentação visual de plataformas | % plataformas com screen-flow.yaml habilitado **OU** opt-out documentado com skip_reason | 0/3 (33% se contar resenhai como 1 e opt-outs como 0) | 100% das plataformas declaram intent (enabled OU opt-out justificado) — 3/3 ao final do pilot | 027 |
| Mental model em <30s | Tempo médio para stakeholder não-técnico identificar fluxo principal lendo `/<platform>/screens` vs lendo `business/process.md` | ~5min lendo markdown (estimado, sem instrumentação) | <30s no canvas (medido via teste com usuário) | 027 (validação externa pendente) |

**Status atual** (pós-shipped, pré-pilot run T073):
- 3/3 plataformas declararam intent ✅ (resenhai enabled, madruga-ai + prosauai opt-out)
- Validação fim-a-fim com usuário externo: **pendente** — depende de T073 + 1 sessão de UX test (não está no escopo do epic nem do reconcile, é roadmap input).

**Ação recomendada**: adicionar 1 linha à tabela "Objetivos e Resultados" do roadmap.md — outcome 1 (intent declarado) já está alcançado, registrar como tal evita o débito de aparecer como "novo objetivo sem resultado".

---

## 4. Candidatos a Próximos Epics (surfaced from this epic)

Aprendizados do epic 027 + WARNs abertos do judge/QA produziram 4 candidatos novos (todos opcionais, prioridade a calibrar):

| # | Candidato | Problema | Origem | Prioridade sugerida | Esforço estimado |
|---|-----------|----------|--------|---------------------|------------------|
| C1 | **Screen-flow pilot validation (resenhai)** | T073 pilot run pendente (operacional): GH Secrets na org paceautomations + `e2e/auth.setup.ts` produzindo storageState + dispatch real do `capture-screens.yml`. Sem isso, SC-001 + SC-003 não estão validados fim-a-fim. | T073 skipped no implement (falta de scope organizacional na sessão) | **P1** — desbloqueia validação real do epic 027 | XS (~0.5d operacional) |
| C2 | **Test pyramid backfill (portal layers b/c/d)** | Infra criada no epic 027 (vitest + Playwright + jest-image-snapshot + axe-core) mas layers (b) component, (c) visual, (d) E2E não rodaram na sessão de QA. SC-009 só alcança 100% após backfill. | phase11-report.md T120 parcial | **P1** — gate constitucional VII (TDD) | S (~1d) |
| C3 | **Bundle budget governance** | Headroom CSS 6.6% (22 KB cap vs 20.64 KB baseline) é apertado. PRs futuros que adicionem regras Tailwind / tokens podem quebrar CI silenciosamente. judge ST4 + qa WARN-L4-01 sinalizaram. | judge + qa | **P2** — preventivo, não bloqueia | XS (~0.25d — widening 6.6% → 10-15% OU policy "qualquer aumento >2% gera entry em decisions.md") |
| C4 | **LFS quota observability** | SC-013 monitora outcome (≤30% após 30 dias) mas sem instrumentação ativa. Alerta @70% threshold pendente como follow-up `phase11-followup-001`. | judge ST3 | **P3** — proativo, baixa probabilidade de breach no ano 1 | XS (~0.25d — workflow CI step lendo `gh api orgs/paceautomations/settings/billing/lfs-status`) |
| C5 | **Multi-platform screen-flow rollout** | Hoje só resenhai (pilot). Próximas plataformas que onboarding (genérico) podem habilitar `screen_flow.enabled: true` se forem produtos com UI. Opt-out invisível já valida o caminho. | epic 027 deliverable per-platform | **P3** — aguarda 4ª plataforma com UI ser onboarded | depende da plataforma |

**Recomendação de sequenciamento** se executados:
1. **C1 + C2 em paralelo** — desbloqueiam confiança total no epic 027 (SC-001/003/009).
2. **C3** logo após C2 — antes que algum outro epic toque `/screens/*`.
3. **C4** quando convier (não há sinal de breach iminente).
4. **C5** reativo, não prospectivo.

---

## 5. Riscos do Roadmap — Reassessment

Atualização da risk table do roadmap (já capturada em reconcile §D6.2), com 1 risco extra surfaced agora:

| Risco | Status | Ação |
|-------|--------|------|
| SW staleness em telas autenticadas | **Mitigado** (Decision #19 ADR-022) — `clearCookies()` + `serviceWorker.unregister()` antes de cada `page.goto`; cobertura via `test_capture_determinism.py` | Manter no risk table como histórico |
| Bundle budget tight (headroom 6.6% CSS) | **Aberto** | Resolver via C3 acima |
| LFS Free quota silent exhaustion | **Aberto** (probabilidade Baixa) | Resolver via C4 quando convier |
| **NOVO**: Pilot run depende de scope organizacional externo (paceautomations org admin) | **Aberto** | Documentar em runbook que PRs operacionais (T073-like) requerem gh auth com escopo elevado; esta sessão não conseguiu setar GH Secrets nem confirmar workflow no default branch |

---

## 6. Re-priorização do Roadmap Backlog

Estado atual do backlog ("Próximos Epics — candidatos") em `roadmap.md`:

```
| ProsaUAI end-to-end       | em execução (epics 001-004 shipped) | P0 |
| Roadmap auto-atualizado   | candidato                            | P2 |
```

**Recomendação pós-epic 027**:

| # | Candidato | Antes | Depois | Justificativa |
|---|-----------|-------|--------|---------------|
| ProsaUAI end-to-end | P0 | **P0** (sem mudança) | Continua sendo o marco mais visível de autonomia real |
| Roadmap auto-atualizado | P2 | **P2** (sem mudança) | Continua nice-to-have; reconcile manual sustentável enquanto há ≤3 plataformas |
| **NOVO C1** Screen-flow pilot validation (resenhai) | — | **P1** | Desbloqueia SC-001/003 do epic 027 — entrega prometida ainda não validada |
| **NOVO C2** Test pyramid backfill | — | **P1** | Gate constitucional (TDD) — SC-009 não está em 100% |
| **NOVO C3** Bundle budget governance | — | **P2** | Preventivo, baixo esforço |
| **NOVO C4** LFS quota observability | — | **P3** | Reativo, baixíssima probabilidade |
| **NOVO C5** Multi-platform screen-flow rollout | — | **P3 reativo** | Aguarda demanda externa |

**Ação concreta no roadmap.md**: substituir tabela atual "Próximos Epics (candidatos)" pela versão expandida acima (5 novos candidatos + 2 originais) — diff trivial, mecânico.

---

## 7. Milestones — Reassessment

Estado atual (pós reconcile §D6.1):

| Milestone | Status | Reassessment |
|-----------|--------|--------------|
| ProsaUAI Operacional | Alcançado 2026-03-31 | sem mudança |
| Runtime Funcional | Alcançado 2026-03-31 | sem mudança |
| Autonomia MVP | Alcançado 2026-04-01 | sem mudança |
| Maturidade Pipeline | Alcançado 2026-04-05 | sem mudança |
| Queue Automation | Alcançado 2026-04-12 | sem mudança |
| **NOVO** Documentação Visual | Em rampagem (pilot T073 pendente) | adicionar via reconcile §D6.1 |

Sem necessidade de novos milestones além do que reconcile já propôs.

---

## 8. Não Este Ciclo — Confirmações

Revisão da seção "Não Este Ciclo" do roadmap atual à luz do epic 027:

| Item da exclusão | Continua excluído? | Justificativa |
|------------------|-------------------|---------------|
| Namespace Unification | **Sim** | Epic 027 reforçou: skill `madruga:business-screen-flow` no namespace `madruga:` funciona perfeitamente; nenhum sintoma de fricção |
| Developer Portal público | **Sim** | Epic 027 é interno; rota `/<platform>/screens` é interna |
| Migração de código de general/ | **Sim** | Sem mudança |
| Multi-tenant | **Sim** | Sem mudança |
| Supabase migration | **Sim** | Sem mudança — DB local cresceu marginalmente (registro de 1 nó L1 a mais) |
| Wave-based parallel execution | **Sim** | Epic 027 confirmou: 5 fases sequenciais funcionaram bem |
| Portal pipeline dashboard (visual DAG) | **Sim** | Sem mudança |
| Pre-commit hooks (detect-secrets, shellcheck) | **Re-avaliar** | Epic 027 ADICIONOU 2 pre-commit hooks (`screen_flow_validator` + `pre_commit_png_size`) — abre precedente. Ainda não é "detect-secrets/shellcheck" especificamente, mas a aversão original a pre-commit perdeu força. **Não bloquear o item, mas downgrade de "permanente" para "considerar quando for o caso"** |

**Ação concreta**: 1 linha de update na coluna "Motivo da Exclusão" do item Pre-commit hooks: `"Overhead para solo dev. CI scan (epic 019) cobre o essencial. Epic 027 adicionou 2 hooks específicos sem fricção — futuro pode ampliar caso a caso."` Diff trivial.

---

## 9. Auto-Review (Tier 1)

| # | Check | Result |
|---|-------|--------|
| 1 | Output file exists and is non-empty | ✅ (este arquivo) |
| 2 | Línea count razoável (50-300 linhas) | ✅ (~180 linhas) |
| 3 | Required sections present (Sumário, Impacto, Reassessment, Candidatos, Riscos, Re-priorização, Milestones, Não Este Ciclo) | ✅ 8 seções |
| 4 | No unresolved placeholder markers (TODO/TKTK/???/PLACEHOLDER) | ✅ |
| 5 | HANDOFF block present at footer | ✅ |
| 6 | Insumo de reconcile referenciado, não duplicado | ✅ (§2 cita reconcile §D6.1/D6.2) |
| 7 | Concrete actions com effort estimado | ✅ |
| 8 | Decisões kill_criteria preservadas (epic 027 confirmou as 28; nenhuma reaberta) | ✅ |

**Veredito**: gate **auto** — sem necessidade de aprovação humana. Saída pronta pra commit + push (próximo step do L2 cycle: end of cycle).

---

## 10. Recomendação Final

1. **Imediato (0 esforço adicional)** — aplicar diffs do reconcile §D6.1 + §D6.2 + §N1 (frontmatter) no `planning/roadmap.md`. ~30 min.
2. **Curto prazo (P1)** — endereçar C1 (T073 pilot run) e C2 (test pyramid backfill) — ~1.5d total. Desbloqueia SC-001/003/009.
3. **Médio prazo (P2)** — C3 (bundle budget governance) — preventivo, ~0.25d.
4. **Reativo** — C4 + C5 quando triggers concretos aparecerem.

**Drift score do roadmap pós-aplicação dos diffs propostos**: 0% (CURRENT). O roadmap volta a ser fonte autoritativa do estado real das entregas.

---

handoff:
  from: madruga:roadmap
  to: end-of-cycle
  context: "Roadmap reassessment pós epic 027 completo. 7 ações concretas mapeadas (4 candidatos novos: C1 pilot validation P1, C2 test pyramid backfill P1, C3 bundle budget governance P2, C4 LFS observability P3, C5 multi-platform reativo) + diffs já prontos em reconcile §D6.1/D6.2 para aplicar mecanicamente. Drift score do roadmap pós-apply: 0%. Nenhuma re-priorização disruptiva — backlog original (ProsaUAI P0, Roadmap auto-atualizado P2) mantido. Cycle L2 completo, próximo passo do operador é apply dos diffs do reconcile + decidir C1/C2."
  blockers: []
  confidence: Alta
  kill_criteria: "Se a aplicação dos diffs propostos no reconcile §D6.1 + D6.2 falhar (e.g. conflito de merge no roadmap.md), reabrir o reassessment para ajustar formato. Se o operador rejeitar a inclusão do milestone 'Documentação Visual' (D6.1), C1 perde sentido como P1 — re-classificar como P3 reativo."
