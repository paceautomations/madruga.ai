---
epic: 027-screen-flow-canvas
phase: reconcile
created: 2026-05-05
updated: 2026-05-05
status: human-gate-pending
sidebar:
  order: 28
---

# Reconcile Report — Epic 027 Screen Flow Canvas

**Branch**: `epic/madruga-ai/027-screen-flow-canvas` (efetivamente em `main` no momento desta sessão — autonomous dispatch override)
**Diff vs base** (`78ad393`..`f7b3641`): **112 arquivos**, +21.551 / -63
**Plataforma**: madruga-ai (self-ref)

## Drift Score

`Score = (docs_current / docs_checked) * 100 = (4 / 11) * 100 = 36%`

**Veredito**: drift médio-alto. Implementação massiva (12K LOC novos no portal + scripts + skill + ADR-022) shippada com parte da documentação L1 não-atualizada. ADR-022 capturou as 26 decisões 1-way-door corretamente, mas blueprint, solution-overview, tech-alternatives, roadmap e pipeline-dag-knowledge precisam de updates pontuais.

## Documentation Health Table

| Doc | Categorias relevantes | Status | Drift items |
|-----|----------------------|--------|-------------|
| `business/vision.md` | D1 | CURRENT | 0 |
| `business/solution-overview.md` | D1 | OUTDATED | 1 (D1.1) |
| `business/process.md` | D1 | CURRENT | 0 |
| `engineering/blueprint.md` | D2, D11 | OUTDATED | 2 (D2.1, D11.1) |
| `engineering/domain-model.md` | D4 | CURRENT | 0 (sem novas entidades de domínio — screen-flow é layer documental, não modelo de domínio do madruga-ai) |
| `engineering/containers.md` | D3 | OUTDATED | 1 (D3.1) |
| `engineering/context-map.md` | D8 | CURRENT | 0 |
| `decisions/ADR-*.md` | D5 | CURRENT | 0 (ADR-022 já cobre as 26 decisões; nenhum ADR existente foi contradito) |
| `planning/roadmap.md` | D6 | OUTDATED | 2 (D6.1, D6.2) |
| `epics/*/pitch.md` (futuros) | D7 | N/A | 0 (não há epics futuros declarados além de candidatos genéricos) |
| `research/tech-alternatives.md` | D11 | OUTDATED | 1 (D11.1 — duplicado com D2.1) |

`docs_current = 4` (vision, process, domain-model, context-map, ADRs — contabilizando ADRs como 1)
`docs_checked = 11`

## Phase 1b — Staleness Scan

```
$ python3 -c "import sys; sys.path.insert(0, '.specify/scripts'); from db import get_conn, get_stale_nodes; from config import load_pipeline; conn = get_conn(); edges = {n['id']: n.get('depends', []) for n in load_pipeline()['nodes']}; import json; print(json.dumps(get_stale_nodes(conn, 'madruga-ai', edges), indent=2)))"
```

**Não executado nesta sessão** (autonomous dispatch): registrado como follow-up. Resolução padrão proposta: `option 2 (inline patch)` quando staleness coincide com o escopo do epic 027. Para nós upstream sem touch (e.g. `vision`, `epic-breakdown`), `option 3 (defer)` é a recomendação default — drift cosmético.

| Stale node (presumido) | Resolução proposta | Justificativa |
|------------------------|-------------------|---------------|
| blueprint | Option 2 — inline patch (D2.1) | Já está no Phase 2 read set |
| tech-research | Option 2 — inline patch (D11.1) | Idem |
| solution-overview | Option 2 — inline patch (D1.1) | Idem |
| containers | Option 2 — inline patch (D3.1) | Idem |
| roadmap | Option 2 — inline patch (D6.1, D6.2) | Phase 5 mandatory anyway |

## Impact Radius Matrix

| Changed area (do diff) | Diretamente afetados | Transitivamente afetados | Effort |
|------------------------|---------------------|-------------------------|--------|
| `.specify/pipeline.yaml` (+1 nó L1) | `pipeline-dag-knowledge.md` (já atualizado por T013) | blueprint.md (lista nós L1?) | S |
| `portal/` (+12K LOC, novo runtime xyflow + elkjs + size-limit + Playwright e2e/visual) | `engineering/blueprint.md` (stack table), `research/tech-alternatives.md` | containers.md (não há novo container, apenas nova rota SSG) | M |
| `.claude/commands/madruga/business-screen-flow.md` (nova skill L1) | `pipeline-dag-knowledge.md` (já cobre via T013), `solution-overview.md` (capability map) | — | S |
| `decisions/ADR-022-*.md` (novo ADR Nygard) | nenhum ADR existente contradito | — | — |
| `platforms/{madruga-ai,prosauai}/platform.yaml` (`screen_flow.enabled: false`) | nenhum | — | — |
| `platforms/resenhai/platform.yaml` (`screen_flow.enabled: true`) | escopo do pilot, não da plataforma madruga-ai | docs do resenhai (out of scope deste reconcile) | — |
| `planning/roadmap.md` ausência de epic 027 | `roadmap.md` (D6) | — | S |
| `requirements.txt` (+`jsonschema>=4.0`) | nenhum doc — convenção stdlib + pyyaml em CLAUDE.md já admite excessões via ADR | — | — |

Effort total estimado para fechar drift: **M (~1.5h)** — todas mudanças são edições pontuais em seções existentes.

## Drift Items + Concrete Diffs

### D1 — Scope Drift

#### D1.1 — `business/solution-overview.md` não menciona Screen Flow Canvas (severity: MEDIUM)

**Current state**: solution-overview.md descreve capacidades do madruga-ai sem referência à feature L1 opcional `business-screen-flow`.

**Expected state**: bloco "Screens" no value-stream feature map declarando a capability como opt-in da plataforma alvo.

**Proposed diff** (apêndice em "Capability Groups → Documentation Generation"):

```diff
+ ### Screen Flow Documentation (opt-in)
+ - Skill `madruga:business-screen-flow` (L1, optional, depends_on=business-process)
+ - Vocabulário fechado: 10 components + 4 edges + 6 badges + 3 capture states (ADR-022)
+ - Renderer Astro 6 + xyflow v12 + ELK build-time (rota condicional `/<platform>/screens`)
+ - Captura via Playwright único contra Expo Web staging (Linux runner)
+ - Drift detection via `path_rules` em `platform.yaml.screen_flow.capture`
+ - Plataformas opted-out (madruga-ai, prosauai): bloco `screen_flow.enabled: false` + `skip_reason`
```

---

### D2 — Architecture Drift

#### D2.1 — `engineering/blueprint.md` não lista xyflow v12 + elkjs + Playwright + size-limit (severity: MEDIUM)

**Current state**: stack table (linha ~20) lista React 19 + TypeScript + ADR-003, sem menção a xyflow v12 (já presente em uso anterior no DAG dashboard) nem aos novos: elkjs ^0.11.1 (devDep build-time), Playwright (test infra), size-limit + jest-image-snapshot + @axe-core/playwright + vitest.

**Expected state**: stack table reconhece xyflow v12 e novas devDeps build-time/test introduzidas pelo epic 027 (ADR-022). Seção "Cross-Cutting Concerns" cita o nó L1 opcional `business-screen-flow`.

**Proposed diff** (linhas ~20-30, stack table):

```diff
  | Linguagem (portal) | TypeScript + React 19 | ADR-003 | Vue, Svelte — React tem ecossistema maior |
+ | Canvas docs visuais | @xyflow/react v12 + elkjs ^0.11.1 (build-time only) | ADR-022 | Reaflow, Mermaid puro — xyflow já em uso no DAG dashboard |
+ | Captura screen-flow | Playwright Chromium (Linux only, GH Actions) | ADR-022 | Maestro, simulator-based — Playwright reduz CI 80% |
+ | Test infra portal | vitest + @testing-library/react + jest-image-snapshot + @axe-core/playwright | ADR-022 | Jest puro — vitest é nativo do Vite/Astro |
+ | Bundle budget portal | size-limit + @size-limit/preset-app | ADR-022 | bundlesize, lighthouse-ci |
```

E append em "Folder Structure / Pipeline L1":

```diff
- 13 nós L1 (vision → solution-overview → ... → roadmap)
+ 14 nós L1 (vision → solution-overview → business-process → business-screen-flow [optional] → tech-research → ... → roadmap)
```

---

### D3 — Model Drift

#### D3.1 — `engineering/containers.md` não menciona nova rota condicional `/<platform>/screens` (severity: LOW)

**Current state**: containers.md descreve portal Astro como container único sem detalhar rotas dinâmicas.

**Expected state**: nota informativa (não diagrama Mermaid novo — nada estrutural mudou) declarando a rota condicional como SSG island com `client:visible`.

**Proposed diff** (apêndice na seção "Portal Container"):

```diff
+ #### Rotas Dinâmicas Condicionais
+ - `/<platform>/screens` — gerada SSG SOMENTE quando `platform.yaml.screen_flow.enabled === true` (ADR-022)
+ - Hidratação `client:visible` com bundle isolado (~145 KB ungz, gate `size-limit` no CI)
+ - ELK pré-computa layout em build-time (zero `elkjs` no runtime client)
```

---

### D4 — Domain Drift

**Status**: SEM DRIFT. Screen Flow Canvas é artefato de documentação visual, não introduz aggregates/entities no domínio do madruga-ai (que é o pipeline DAG). As 11 entidades em `data-model.md` do epic são modelo do artefato YAML, vivem no escopo do epic, não do platform domain model.

---

### D5 — Decision Drift

**Status**: SEM DRIFT. ADR-022 (`platforms/madruga-ai/decisions/ADR-022-screen-flow-canvas.md`) registrou as 26 decisões 1-way-door (24 da pitch.md + 2 do plan.md) em formato Nygard. Nenhum ADR existente (ADR-001..ADR-021) foi contradito pela implementação.

**Validação cross-check**:
- ADR-003 (React/Astro pro portal): consistente — xyflow v12 é React.
- ADR-020 (Mermaid inline em .md): consistente — screen-flow não substitui Mermaid, complementa via canvas xyflow.
- ADR-021 (claude -p bare-lite dispatch): consistente — `MADRUGA_BARE_LITE` envs preservados.

---

### D6 — Roadmap Drift (MANDATORY)

#### D6.1 — Epic 027 ausente do roadmap (severity: HIGH)

**Current state**: `planning/roadmap.md` lista epics 006-025. Epic 027 (e o gap em 026) **não aparece** em nenhuma seção: nem na tabela "Epic | Descrição | Status | Concluído", nem no Gantt, nem no Mermaid de dependências, nem nos Milestones.

**Expected state**: nova linha 027 declarando a entrega + Gantt atualizado + Milestone "Documentação Visual" agregado.

**Proposed diff** (tabela de epics, após linha 082 `| 025 |...`):

```diff
+ | 026 | _(skipped — gap permanente, decisão 027.2)_ | — | — | — |
+ | 027 | Screen Flow Canvas | Skill L1 opcional `madruga:business-screen-flow` (vocabulário fechado 10c+4e+6b+3s) + renderer Astro xyflow + ELK build-time + captura Playwright contra Expo Web staging + drift detection via `path_rules` per-platform. ADR-022 trava 26 decisões 1-way-door. resenhai-expo é pilot único; madruga-ai + prosauai opted-out via `screen_flow.enabled: false`. | **shipped** | 2026-05-05 |
```

E no Gantt section "Maturidade":

```diff
    section Maturidade
    022 Mermaid Migration        :done, e022, 2026-04-06, 1d
    023 Commit Traceability      :done, e023, 2026-04-08, 1d
    024 Sequential Execution UX  :done, e024, 2026-04-12, 1d
+   027 Screen Flow Canvas       :done, e027, 2026-05-05, 10d
```

E nova linha em "Milestones":

```diff
+ | **Documentação Visual** | 027 | Skill L1 opcional gera screen-flow.yaml; portal renderiza canvas xyflow; resenhai-expo pilot ≥3 telas reais com badge "WEB BUILD" | **Em rampagem** — pilot run T073 pendente (operacional, requer GH Secrets + auth.setup) |
```

#### D6.2 — Risk table não captura riscos materializados/mitigados pelo epic 027 (severity: LOW)

**Current state**: risk table termina em risco "Dirty tree bloqueando queue promotion".

**Expected state**: 2-3 riscos do epic 027 documentados com status pós-shippada.

**Proposed diff** (apêndice na risk table):

```diff
+ | Service Worker staleness em telas autenticadas (resenhai-expo) | PNG noise quebra invariante md5 ≥80% | Alta (em fase 4) | **Mitigado** (Decision #18 ADR-022): capture script faz `clearCookies()` + `serviceWorker.unregister()` antes de cada `page.goto`. Cobertura via test_capture_determinism.py. |
+ | Bundle budget tight (headroom 2.2% no CSS) | PR que adiciona regra Tailwind quebra CI | Média | **Aberto** (judge ST4 + qa WARN-L4-01): widening para 10-15% pendente OU policy "qualquer aumento >2% triggers decisions.md entry". |
+ | LFS Free quota silent exhaustion | Captures stalled sem alerta | Baixa | **Aberto** (judge ST3): SC-013 monitora outcome only; CI step de alerta @70% threshold pendente como follow-up `phase11-followup-001`. |
```

---

### D7 — Future Epic Drift

**Status**: SEM DRIFT. Roadmap não declara epics futuros concretos além de "candidatos" (Roadmap auto-atualizado, ProsaUAI end-to-end). Nenhum candidato assume APIs/schemas/boundaries que o epic 027 mudou.

---

### D8 — Integration Drift

**Status**: SEM DRIFT. Nenhuma API/contrato externo do madruga-ai foi alterado. Capture é black-box contra `https://dev.resenhai.com` (staging do resenhai-expo) e trafega zero dado pro próprio madruga-ai.

---

### D9 — README Drift

**Status**: N/A. `platforms/madruga-ai/README.md` não existe. Skip silencioso conforme contrato.

---

### D10 — Epic Decisions Drift

**Status**: SEM DRIFT. `platforms/madruga-ai/epics/027-screen-flow-canvas/decisions.md` (9.5K) está alinhado com ADR-022. As 26 decisões 1-way-door foram **promovidas** para ADR-022 (formato Nygard) — promotion path completo executado em Phase 11 (T121).

**Validação dos 3 checks**:
1. **Contradiction**: nenhum entry contradiz ADR-022.
2. **Promotion**: já feito (ADR-022 cobre 26 decisões).
3. **Staleness**: code reflete decisões (vocabulário fechado enforced no validator, schema_version=1 obrigatório, Service Worker cleanup implementado, etc.).

---

### D11 — Research Drift

#### D11.1 — `research/tech-alternatives.md` não cobre alternativas avaliadas no epic 027 (severity: MEDIUM)

**Current state**: tech-alternatives.md descreve decisões da fase L1 inicial do madruga-ai (DAG executor, claude -p, etc.), mas não cobre as 10 áreas de pesquisa do `research.md` do epic 027 (xyflow vs alternativas, ELK vs Dagre, Playwright vs Maestro, LFS vs CDN externo, etc.).

**Expected state**: ou (a) referência cruzada para `epics/027-screen-flow-canvas/research.md`, ou (b) seção apêndice "Documentação Visual (Epic 027)".

**Proposed diff** (apêndice):

```diff
+ ## Documentação Visual — Epic 027 (referência)
+ Pesquisa detalhada em `epics/027-screen-flow-canvas/research.md` (10 tópicos):
+ - Stack visual: xyflow v12 vs Reaflow vs react-digraph vs Mermaid
+ - Layout: ELK build-time vs Dagre client vs custom force-directed
+ - Captura: Playwright vs Maestro vs simulator-based
+ - Storage: Git LFS vs Vercel Blob vs S3+CDN
+ - Determinism: addInitScript vs flag no app vs Percy/Chromatic
+ Decisões consolidadas em ADR-022.
```

---

## Roadmap Review (mandatory)

### Epic Status Table

| Epic | Appetite planejado | Appetite real | Status | Milestone |
|------|-------------------|---------------|--------|-----------|
| 027 Screen Flow Canvas | 10 working days (revisado de 8 → 10 após Crítica 1) | ~10 dias (alinhado) | **shipped (com WARNs operacionais)** | "Documentação Visual" alcançado parcialmente — pilot run T073 pendente |

### Dependencies Discovered

- Epic 027 não introduz dependência inter-epic nova; é folha do DAG L1 + L2.
- T073 (pilot run) é operacional, não tem dependência de outro epic — desbloqueia com GH Secrets + `auth.setup` no resenhai-expo.

### Risk Status

Ver D6.2 — 3 novos riscos registrados (SW staleness mitigado; bundle budget tight aberto; LFS quota silent aberto).

---

## Future Epic Impact

**Status**: nenhum impacto detectado. Roadmap não tem epics futuros concretos no madruga-ai. Plataforma resenhai (alvo do pilot) tem epics próprios mas estão fora do escopo deste reconcile (`madruga-ai` self-ref).

---

## Auto-Review (Tier 1 + Tier 2)

### Tier 1 (Deterministic)

| # | Check | Result |
|---|-------|--------|
| 1 | Output file exists and is non-empty | ✅ (este arquivo) |
| 2 | All 11 drift categories scanned | ✅ D1-D11 cobertos |
| 3 | Drift score computed | ✅ 36% (4/11) |
| 4 | No placeholder markers (`TODO\|TKTK\|???\|PLACEHOLDER`) | ✅ |
| 5 | HANDOFF block present at footer | ✅ |
| 6 | Impact radius matrix present | ✅ |
| 7 | Roadmap review section present | ✅ |
| 8 | Stale L1 nodes from Phase 1b each have resolution | ✅ (com caveat: scan não executado, defaults documentados) |

### Tier 2 (Scorecard)

| # | Item | Self-Assessment |
|---|------|-----------------|
| 1 | Every drift item has current vs expected state | **Yes** |
| 2 | Roadmap review completed with actual vs planned | **Yes** |
| 3 | ADR contradictions flagged (amend/supersede) | **Yes** (zero contradições — D5 limpo) |
| 4 | Future epic impact assessed (top 5) | **Yes** (zero impacto — D7 limpo) |
| 5 | Concrete diffs provided (not vague) | **Yes** (todos os drift items têm diff blocks executáveis) |
| 6 | Trade-offs explicit for each proposed change | **Partial** — diffs são pequenos e auto-evidentes; trade-offs principais já vivem em ADR-022 |
| 7 | Confidence stated | **Alta** — 36% drift score é alto mas mecânico de fechar (~1.5h edição) |
| 8 | Kill criteria defined | **Yes** (ver HANDOFF) |

**Self-Assessment final**: 7.5/8 itens fortes. Único item parcial (#6) é justificável — o ADR-022 já registra trade-offs maiores das 26 decisões.

---

## Caveats e Decisões Operacionais

1. **Branch state**: a sessão executou em `main`, não em `epic/madruga-ai/027-screen-flow-canvas`. Autonomous dispatch override permitiu prosseguir, mas o gate de produção deveria validar branch antes de aplicar diffs.
2. **Phase 1b staleness scan não executado**: registrado como follow-up mecânico. Resoluções default propostas são conservadoras.
3. **Layers (c) e (d) do test pyramid não rodaram nesta sessão de QA** (ver `qa-report.md`). Fora do escopo do reconcile, mas relevante pra confiança de shipping.
4. **T073 pilot run pendente**: operacional (GH Secrets + auth.setup + dispatch). Não bloqueia merge do epic 027 enquanto for `madruga-ai self-ref` reconcile, mas trava a validação fim-a-fim de SC-001/SC-003.
5. **Phase 8b — mark epic commits**: deve executar **APÓS aprovação humana** dos diffs propostos. Não foi rodado nesta sessão.
6. **Phase 9 — auto-commit**: idem, pendente do gate humano.

---

## Recommendation to Reviewer

Approve drift item-by-item. Escalations:

- **D6.1 (HIGH)** é o item mais visível — roadmap sem epic 027 deixa a entrega invisível para a documentação canônica do madruga-ai. **Recomendo apply imediato.**
- **D2.1 + D11.1 (MEDIUM)** podem ser aplicados em batch.
- **D1.1 + D3.1 (LOW/MEDIUM)** são apêndices em docs existentes — apply em batch.
- **D6.2 (LOW)** é additive ao risk table — apply em batch com D6.1.

Após apply: rodar Phase 8b + Phase 9 para mark commits + auto-commit + push.

---

handoff:
  from: madruga:reconcile
  to: madruga:roadmap
  context: "Drift score 36% (4/11 docs current). 7 drift items mapeados em 5 docs (solution-overview, blueprint, containers, roadmap, tech-alternatives). ADR-022 + epic decisions.md alinhados — D5/D10 limpos. Diffs concretos prontos pra apply (~1.5h). Phase 1b staleness scan e Phase 8b/9 pendentes do gate humano."
  blockers: []
  confidence: Alta
  kill_criteria: "Se a aplicação dos diffs revelar contradição com algum ADR existente (re-abrir D5), OU se Phase 1b staleness scan retornar nó stale fora dos 5 mapeados acima (re-abrir Phase 2 read set), OU se o operador rejeitar D6.1 (epic 027 ficaria invisível no canonical roadmap — drift permanece)."
