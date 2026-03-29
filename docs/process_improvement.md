# Process Improvement — Revisão Completa do Sistema de Skills

> Revisão conduzida por 6 agentes revisores + 3 agentes de pesquisa em 2026-03-29.
> Recomendações revisadas priorizando: **longo prazo > valor entregue > performance > consistência > qualidade**.
> Critério: cada decisão é avaliada perguntando "isso escala para 10 plataformas e 50 epics?"
> Premissa: **SQLite desde o início**. Todo estado estruturado (pipeline nodes, decisions, registries, provenance) vai direto para banco. Zero arquivos intermediários de estado (JSON/NDJSON). Artefatos continuam em markdown/LikeC4 no filesystem — BD trackeia metadata e estado.

---

## Equipe de Revisão

| Agente | Persona | Foco |
|--------|---------|------|
| PM | Senior Product Manager | Fluxo, gates, fricção, time-to-value |
| Architect | Staff Architect (15+ anos) | Consistência de contrato, DRY, simplicidade |
| AI Specialist | LLM/Prompt Engineer | Tokens, prompts, alucinação, contexto |
| Designer | UX/DX Specialist | Naming, descoberta, onboarding, carga cognitiva |
| SWE | Senior Software Engineer | Scripts, robustez, testes, CI/CD |
| Data Engineer | Senior Data Engineer | DAG, lineage, staleness, idempotência |

---

## Sumário Executivo

O sistema é bem estruturado — contrato uniforme de 6 passos, framework de perguntas estruturadas e gate types são patterns genuinamente eficazes. A revisão identificou **2 bloqueantes** (B1 + B2/B3 unificados), **12 alta prioridade** e **~25 melhorias**.

**Princípios diretores:**
1. **Definitivo > paliativo** — Band-aids acumulam dívida. "Fazer direito de primeira" é mais barato que refatorar depois.
2. **SQLite desde o início** — Todo estado vai para BD. `sqlite3` é built-in no Python, zero infra, zero dependência. Queries reais em vez de `jq`. Constraints e FKs em vez de "esperamos que o JSON esteja correto". Migração para PostgreSQL é mecânica quando precisar.

---

## 🔴 BLOQUEANTES (3)

---

### B1. Plataformas existentes sem seção `pipeline:` no platform.yaml

**Identificado por:** Architect, SWE, Data Engineer (unânime)

As plataformas `fulano` e `madruga-ai` não possuem a seção `pipeline:` no `platform.yaml`. Todo skill falha no step 0.

#### Alternativas

| # | Alternativa | Prós | Contras |
|---|------------|------|---------|
| A | **`copier update` via `platform.py sync`** | Canônico, future-proof, aplica todas melhorias do template | Pode sobrescrever campos customizados. Requer review do diff |
| B | **Copy-paste manual da seção `pipeline:`** | Cirúrgico, zero risco, 5 minutos | Manual, não escala, não traz outras melhorias do template |
| C | **Script de migração em `platform.py`** — Comando `migrate` que adiciona seções faltantes sem sobrescrever existentes | Escala para N plataformas, automatizado, reutilizável | Mais esforço inicial (~1h) |

**Recomendação: A (`copier update`) com review do diff.**

O copy-paste manual resolve hoje mas cria precedente de divergência entre template e plataformas. `copier update` é o mecanismo canônico — foi projetado exatamente para isso. O `_skip_if_exists` protege conteúdo editável. Revisar o diff garante que campos custom do fulano (views extras) sejam preservados. A longo prazo, plataformas devem estar sempre sincronizadas com o template.

**Ação adicional:** Após sync, criar `.github/workflows/lint.yml` com GitHub Actions que roda `platform.py lint --all` em toda PR. Bloqueia merge se lint falhar — garante que nenhum platform.yaml desatualizado entre no main.

---

### B2 + B3. Unificação SpecKit↔Madruga + DAG Completo

**Identificado por:** PM, Architect, AI Specialist, Data Engineer, SWE

**Dois problemas que são na verdade um:**
- B2: SpecKit e Madruga são sistemas paralelos sem integração formal
- B3: Skills do ciclo per-epic (epic-context, verify, reconcile, etc.) não são nós do DAG

**Causa raiz:** O DAG cobre só documentação (14 nós). O ciclo per-epic (implementação) é "solta" — sem rastreamento, sem observabilidade, sem nós no DAG. A solução é unificar tudo num DAG de dois níveis.

#### Princípio: Tudo é nó do DAG

Não faz sentido ter skills "fora" do pipeline. Todo step que gera artefato, tem dependências, e tem gate — é um nó do DAG. A separação entre "platform lifecycle" e "epic lifecycle" é organizacional, não arquitetural.

#### Solução: Unificação por Diretório Compartilhado + DAG de Dois Níveis

**Mudança central:** O diretório do epic (`platforms/<name>/epics/<NNN-slug>/`) passa a ser o diretório de trabalho de **ambos** os sistemas. SpecKit opera dentro do epic dir em vez de `specs/`. Madruga gera artefatos de documentação no mesmo local. Tudo junto, tudo rastreado.

##### Estado Atual (dois mundos separados)

```
platforms/fulano/epics/001-channel-pipeline/
  └── pitch.md                              ← madruga:epic-breakdown gera

specs/001-atomic-skills-dag-pipeline/       ← speckit opera aqui, separado
  ├── spec.md
  ├── plan.md
  ├── tasks.md
  ├── data-model.md
  ├── checklists/
  └── contracts/
```

##### Estado Futuro (mundo unificado)

```
platforms/fulano/epics/001-channel-pipeline/
  ├── pitch.md            ← madruga:epic-breakdown gera
  ├── context.md          ← madruga:epic-context gera
  ├── spec.md             ← speckit.specify gera (dentro do epic dir)
  ├── plan.md             ← speckit.plan gera
  ├── tasks.md            ← speckit.tasks gera
  ├── data-model.md       ← speckit.plan gera (se aplicável)
  ├── checklists/         ← speckit.specify gera
  ├── contracts/          ← speckit.plan gera (se aplicável)
  ├── verify-report.md    ← madruga:verify gera (novo — hoje não persiste)
  ├── qa-report.md        ← madruga:qa gera (hoje salvava em obsidian-vault/)
  └── reconcile-report.md ← madruga:reconcile gera (hoje salvava na raiz da plataforma)
```

**Nota:** Todos os arquivos já existem nos dois sistemas. A única mudança é **onde** vivem. O `verify-report.md` é o único artefato genuinamente novo (hoje verify não persiste resultado — gap de observabilidade).

##### DAG de Dois Níveis

**Nível 1 — Platform DAG (13 nós, documentação):**
```
platform-new → vision → solution-overview → business-process
→ tech-research → adr → blueprint
                           └→ domain-model → containers → context-map
→ epic-breakdown → roadmap
```

**Nível 2 — Epic DAG (10 nós por epic, implementação):**
```
epic-context → specify → clarify? → plan → tasks → analyze → implement → verify → qa? → reconcile?
```

Ambos os níveis são declarados no `platform.yaml`:

```yaml
pipeline:
  # Nível 1: Platform DAG (13 nós)
  nodes:
    platform-new:
      outputs: ["platform.yaml"]
      depends: []
      gate: human
    vision:
      outputs: ["business/vision.md"]
      depends: ["platform-new"]
      gate: human
    # ... demais 11 nós ...

  # Nível 2: Epic DAG (template aplicado a cada epic)
  epic_cycle:
    nodes:
      epic-context:
        outputs: ["{epic}/context.md"]
        depends: []
        gate: human
      specify:
        outputs: ["{epic}/spec.md"]
        depends: ["epic-context"]
        gate: human
      clarify:
        outputs: ["{epic}/spec.md"]
        depends: ["specify"]
        gate: human
        optional: true
        skip_condition: "spec.md has 0 [NEEDS CLARIFICATION] markers"
      plan:
        outputs: ["{epic}/plan.md"]
        depends: ["specify"]
        gate: human
      tasks:
        outputs: ["{epic}/tasks.md"]
        depends: ["plan"]
        gate: human
      analyze:
        outputs: ["{epic}/analyze-report.md"]
        depends: ["tasks"]
        gate: auto
      implement:
        outputs: ["{epic}/tasks.md"]
        depends: ["analyze"]
        gate: auto
      verify:
        outputs: ["{epic}/verify-report.md"]
        depends: ["implement"]
        gate: auto-escalate
      qa:
        outputs: ["{epic}/qa-report.md"]
        depends: ["verify"]
        gate: human
        optional: true
        skip_condition: "epic has no web-facing features or app not running"
      reconcile:
        outputs: ["{epic}/reconcile-report.md"]
        depends: ["verify"]
        gate: human
        optional: true
        skip_condition: "verify score >= 95% and zero drift"
```

`{epic}` é expandido para `epics/<NNN-slug>/` em runtime.

**`checkpoint` é transversal** — não é um step no fluxo, é um trigger automático que roda após qualquer nó salvar. Executa `db.py` para UPDATE/INSERT no SQLite (pipeline_nodes, decisions, artifact_provenance, events). Rastreado no BD mas não aparece na sequência visível.

##### O que muda nas skills (ajustes, não reescrita)

| Skill | Mudança | Esforço |
|-------|---------|---------|
| `speckit.specify` | `create-new-feature.sh` aceita `--base-dir` para operar em `platforms/<name>/epics/<NNN>/` em vez de `specs/`. Lê `pitch.md` como input inicial. Branch name deriva do epic slug | ~30min |
| `speckit.plan` | `setup-plan.sh` lê de `epics/<NNN>/spec.md` em vez de `specs/<NNN>/spec.md` | ~15min |
| `speckit.tasks` | `check-prerequisites.sh` busca em `epics/<NNN>/` | ~15min |
| `speckit.implement` | Mesma mudança de path | ~15min |
| `speckit.clarify` | Mesma mudança de path | ~10min |
| `speckit.analyze` | Mesma mudança de path | ~10min |
| `epic-breakdown` | `pitch.md` inclui metadata SpecKit-compatível (branch name sugerido, feature description formatada) | ~30min |
| `epic-context` | Handoff encadeia para `speckit.specify` com context.md como input | ~15min |
| `verify` | Salva `verify-report.md` no epic dir (hoje não persiste) | ~15min |
| `reconcile` | Salva no epic dir em vez da raiz da plataforma | ~10min |
| `qa` | Salva no epic dir em vez de `obsidian-vault/` | ~10min |
| `check-platform-prerequisites.sh` | Ganha flag `--epic <NNN>` para checar nós do epic cycle. Ganha flag `--check-platform-only` para skills que só precisam validar que a plataforma existe | ~1-2h |
| `/pipeline` (status+next) | Lê `epics/<NNN>/` para determinar progresso. Mostra ambos os níveis | ~1-2h |

**Total estimado: ~6-8 horas de ajustes.**

##### O que NÃO muda

- **Contrato SpecKit** — specify/clarify/plan/tasks/implement continuam com a mesma lógica interna
- **Extension hooks** — `.specify/extensions.yml` mantido e funcional. Hook `before_specify`, `before_plan`, etc. continuam operando
- **Feature branches** — SpecKit cria branch por epic (ex: `001-channel-pipeline`). Mantido
- **Scripts SpecKit** — `create-new-feature.sh`, `setup-plan.sh`, `check-prerequisites.sh` continuam. Só recebem `--base-dir` para apontar ao epic dir
- **Templates SpecKit** — `spec-template.md`, `plan-template.md` iguais
- **Constitution** — `.specify/memory/constitution.md` continua como referência cruzada

##### Fases de implementação

**Fase 1 — Infraestrutura (~3h):**
- Ajustar `create-new-feature.sh` para aceitar `--base-dir` (default: `specs/`, novo: `platforms/<name>/epics/<NNN>/`)
- Ajustar `setup-plan.sh` e `check-prerequisites.sh` para o mesmo
- Ajustar `check-platform-prerequisites.sh` com flags `--epic` e `--check-platform-only`
- Adicionar `epic_cycle` ao template Copier `platform.yaml.jinja`

**Fase 2 — Conexão (~2h):**
- `epic-breakdown` gera `pitch.md` com metadata SpecKit-compatível
- `epic-context` produz `context.md` que `speckit.specify` lê como input
- Handoffs encadeiam o fluxo completo: `epic-context → specify → clarify? → plan → tasks → analyze → implement → verify → qa? → reconcile?`
- `verify` e `reconcile` passam a salvar reports no epic dir

**Fase 3 — Observabilidade (~2h):**
- `/pipeline` lê `epics/<NNN>/` para status do epic cycle
- `.pipeline/state.json` trackeia nós de ambos os níveis (platform + epic)
- Checkpoint automático após cada nó

**Fase 4 — Polish:**
- Renaming (discuss→epic-context, test-ai→qa, adr-gen→adr, vision-one-pager→vision)
- PT-BR como diretiva no constitution (SpecKit skills passam a gerar em PT-BR)
- Adicionar contrato madruga (persona, auto-review tiered, HANDOFF blocks) gradualmente às skills SpecKit via knowledge files em camadas (A1)

##### Output do `/pipeline` unificado

```
## Platform DAG: fulano (13/13 done)
| Nó              | Status  | Gate       |
|-----------------|---------|------------|
| platform-new    | ✅ done  | human      |
| vision          | ✅ done  | human      |
| ...             | ...     | ...        |
| roadmap         | ✅ done  | human      |

## Epic Cycles (15 epics)
| Epic                    | Progress | Current Step | Next Action             |
|-------------------------|----------|-------------|-------------------------|
| 001-channel-pipeline    | 8/10     | verify      | /qa fulano --epic 001   |
| 002-conversation-core   | 4/10     | tasks       | /analyze fulano --epic 002 |
| 003-group-routing       | 1/10     | epic-context| /specify fulano --epic 003 |
| 004-agent-tools         | 0/10     | —           | /epic-context fulano --epic 004 |
| ...                     | ...      | ...         | ...                     |

Next: /tasks fulano --epic 002
```

##### Por que esta solução e não reescrita completa

A reescrita (alternativa D original) partiria do princípio que o SpecKit precisa ser substituído. Na verdade, o SpecKit funciona bem — specify, plan, tasks, implement são skills maduras com quality checks, extension hooks e branch management. O problema não é o SpecKit em si, mas **onde ele opera** (diretório separado) e **a falta de conexão** com o DAG madruga.

A unificação por diretório compartilhado + DAG de dois níveis resolve ambos com ajustes cirúrgicos (~6-8h) em vez de reescrita (~2-3 semanas). Mantém tudo que funciona no SpecKit (hooks, branches, scripts, templates) e adiciona o que faltava (rastreamento no DAG, observabilidade, lineage completo).

---

## 🟠 ALTA PRIORIDADE (12)

---

### A1. Boilerplate massivo duplicado entre skills (~15K tokens)

**Identificado por:** Architect, AI Specialist

#### Alternativas

| # | Alternativa | Prós | Contras |
|---|------------|------|---------|
| A | **Diretiva "follow contract in X"** — Skills referenciam knowledge file | Corta 40-60 linhas/skill. Single source of truth | 1 file-read extra. LLM precisa mergear base+overrides |
| B | **Knowledge files em camadas** — `contract-base.md` + `contract-{business,engineering,planning}.md` + skill.md | Máxima deduplicação. Personas centralizadas por camada | 3 file-reads/skill. Mais indireção |
| C | **Code generation (Copier/Jinja2)** | Files self-contained. Tooling já existe | Drift sem re-run. Build step. Duas fontes de verdade |
| D | **Status quo + linter** | Zero mudança runtime | Não reduz duplicação |

**Recomendação: B (knowledge files em camadas).**

A diretiva simples (A) resolve mas com escala (30+ skills, 4 camadas, personas diferentes por camada) o knowledge file único fica monolítico. A estrutura em camadas reflete a arquitetura real do sistema:

```
pipeline-contract-base.md          → Steps 0,1,3,4,5 universais (~80 linhas)
pipeline-contract-business.md      → Persona McKinsey + "zero technical content" (~20 linhas)
pipeline-contract-engineering.md   → Persona Staff Engineer + simplicity rules (~20 linhas)
pipeline-contract-planning.md      → Persona PM + Shape Up rules (~20 linhas)
```

Cada skill: `"Siga contract-base + contract-{layer}. Overrides abaixo."` — **2 file-reads** (não 3, base é sempre carregado, layer é por skill).

**Por que não A:** Com 10 plataformas e personas evoluindo por camada, um arquivo monolítico vira 500+ linhas que toda skill carrega. Camadas mantém each file small and focused.

---

### A2. Perda de contexto estrutural entre skills

**Identificado por:** PM

#### Alternativas

| # | Alternativa | Prós | Contras |
|---|------------|------|---------|
| A | **Bloco HANDOFF YAML no artefato** | Structured, embedded (sem sync). Regenera com artefato | Overhead por skill. Pode driftar |
| B | **Decision-log.md cumulativo** | Single file, audit trail, human-readable | Cresce indefinidamente. Não structured |
| C | **Pipeline-state.yaml** | Machine-parseable. Detecta staleness via hash | Duplicação. Sync problem |
| D | **Resumos por camada** (.context/) | Poucos files. Compressão natural | Harder to attribute decisions |

**Recomendação: A (HANDOFF blocks nos artefatos) + BD (decision-log direto no SQLite).**

**HANDOFF blocks** (view layer) — embutidos no artefato. Quando o artefato regenera, o HANDOFF regenera junto. Zero sync problem. Skills downstream leem o bloco do artefato direto para contexto rápido.

**Decision-log** (data layer) — vai direto para a tabela `decisions` no SQLite. Sem arquivo intermediário (NDJSON eliminado). O step 5 (Save+Report) faz `INSERT INTO decisions` após salvar o artefato.

**Formato do HANDOFF block (no artefato):**
```yaml
<!-- HANDOFF
skill: solution-overview
date: 2026-03-29
decisions:
  - "Prioridade: automação de mensagens é Now, dashboard é Next"
  - "3 personas: owner, operator, end-customer"
assumptions_to_validate:
  - "Owner configura sozinho sem suporte técnico"
open_questions: []
/HANDOFF -->
```

**Query no BD em vez de parsear arquivos:**
```sql
-- Todas decisões de uma plataforma
SELECT skill, decisions, assumptions, created_at
FROM decisions WHERE platform_id = 'fulano' ORDER BY created_at;

-- Decisões de um epic específico
SELECT * FROM decisions WHERE platform_id = 'fulano' AND epic_id = '001-channel-pipeline';

-- Open questions não resolvidas
SELECT * FROM decisions WHERE open_questions != '[]';
```

---

### A3. Nenhuma detecção de staleness no pipeline

**Identificado por:** Data Engineer, SWE

#### Alternativas

| # | Alternativa | Prós | Contras |
|---|------------|------|---------|
| A | **mtime comparison (Make-style)** | Simples (~20 linhas). Zero infra nova | False positives. Não content-aware |
| B | **Content hash (dbt-style)** com `.pipeline-state.json` | Imune a false positives. Detecta mudanças reais | State file para manter. Mais complexo. Atualizar manifest a cada save |
| C | **Git-based (commit hash)** | Imune a mtime quirks. Usa git | Pesado. Complexo |

**Recomendação: B (content hash) direto no SQLite.**

mtime (A) gera false positives em workflows reais (`git checkout`, `copier update`). Content hash é a solução correta.

Com SQLite, staleness é uma query:

```sql
-- Nós que podem estar stale (output_hash difere do hash atual do arquivo)
SELECT pn.node_id, pn.output_hash, pn.completed_at
FROM pipeline_nodes pn
WHERE pn.platform_id = 'fulano'
  AND pn.status = 'done'
  AND pn.output_hash != compute_file_hash(pn.output_files);

-- Nós cujas dependências foram regeneradas depois
SELECT child.node_id as stale_node, parent.node_id as changed_dep
FROM pipeline_nodes child
JOIN pipeline_deps pd ON pd.node_id = child.node_id
JOIN pipeline_nodes parent ON parent.node_id = pd.depends_on
WHERE child.platform_id = 'fulano'
  AND parent.completed_at > child.completed_at;
```

O step 5 (Save+Report) de cada skill faz `UPDATE pipeline_nodes SET output_hash = ?, completed_at = ? WHERE ...` — sem arquivo intermediário, sem overhead manual.

---

### A4. `adr-gen` e `epic-breakdown` não são idempotentes

**Identificado por:** Data Engineer

#### Alternativas

| # | Alternativa | Prós | Contras |
|---|------------|------|---------|
| A | **Guard clause (detect + ask)** | Simples. Consistente com 1-way-door. 10 linhas | Não é idempotência real |
| B | **Slug-based matching** | Verdadeira idempotência | Matching fuzzy |
| C | **Manifest/registry** — `.registry.json` mapeia source_decision → ADR number | Determinístico. Handles renames. Reports "new vs updated" | Outro arquivo. Sync |
| D | **Diff-and-merge** | Mais transparente. User vê exatamente o que mudou | Complexo. Diffing markdown não trivial |

**Recomendação: C (manifest/registry).**

Guard clause (A) é "detect and ask" — não resolve o problema, só expõe. Com 10 plataformas regenerando ADRs e epics regularmente (upstream muda → downstream regenera), a pergunta "Skip/Update/Replace?" aparece dezenas de vezes. Isso é friction, não safety.

O registry é a solução definitiva — direto no SQLite, sem arquivo JSON intermediário.

Re-run:
```sql
-- Buscar ADR existente por source_decision_key
SELECT * FROM decisions WHERE platform_id = 'fulano' AND source_decision_key = 'primary-datastore';
-- Se existe → UPDATE. Se não → INSERT.
```

Reporting:
```sql
-- Resumo do re-run: "3 atualizados, 1 novo, 2 sem mudanças"
SELECT
  CASE WHEN updated_at > :run_start THEN 'updated'
       WHEN created_at > :run_start THEN 'new'
       ELSE 'unchanged' END as action,
  COUNT(*)
FROM decisions WHERE platform_id = 'fulano' GROUP BY action;
```

Funciona com 1-way-door: mostra diff das mudanças para confirmação antes do UPDATE.

**Guard clause como fallback:** Se ADR foi criado manualmente (sem registro no BD), cair em guard clause (detect + ask).

---

### A5. `test-ai` salva em `obsidian-vault/` (path hardcoded externo)

**Identificado por:** PM, Designer, SWE

#### Alternativas

| # | Alternativa | Prós | Contras |
|---|------------|------|---------|
| A | **Platform dir: `platforms/<name>/reports/qa/`** | Co-localizado, versionado | Reports frequentes poluem |
| B | **Epic dir: `platforms/<name>/epics/<NNN>/qa-report.md`** | Rastreabilidade direta epic↔test | Nesting profundo. Sem home para ad-hoc |
| C | **Reports dir raiz: `reports/qa/<platform>/`** | Separação limpa | Desconectado do contexto |
| D | **Híbrido: B para epic, A para ad-hoc** | Best of both | Dois paths |

**Recomendação: B (epic dir) como padrão + fallback A para ad-hoc.**

QA reports são artefatos do ciclo per-epic — pertencem ao epic. A rastreabilidade `epic → qa-report → fix → reconcile` é o fluxo completo. Runs ad-hoc (sem epic) são edge case e podem usar o fallback.

**Nota:** Resolvido pela unificação B2/B3 — todos os artefatos do epic cycle vivem em `platforms/<name>/epics/<NNN>/`.

---

### A6. LikeC4 não é validado no pipeline

**Identificado por:** SWE, Data Engineer

#### Alternativas

| # | Alternativa | Prós | Contras |
|---|------------|------|---------|
| A | **`likec4 build` pós-geração** | Validação definitiva (parser real) | Requer CLI. ~5-10s |
| B | **Context7 para syntax docs** | Always up-to-date | Não valida output |
| C | **Knowledge file de referência** | Rápido. Sempre disponível. Convenções do repo | Pode ficar stale |
| D | **Híbrido: C + A** | Knowledge previne erros, CLI valida | Dois mecanismos |

**Recomendação: D (knowledge file + `likec4 build`).**

Knowledge file previne erros na geração (proativo). `likec4 build` valida o resultado (reativo). Ambos são necessários:

- `.claude/knowledge/likec4-syntax.md` — specification, model, views syntax + spec.likec4 do template + erros comuns
- Após salvar `.likec4`, rodar `likec4 build <model-dir>` e reportar erros antes do gate

Context7 (B) é útil como exercício único para popular o knowledge file, não como step per-run.

---

### A7. `folder-arch` é dead-end node com baixo valor

**Identificado por:** PM, Architect

#### Alternativas

| # | Alternativa | Prós | Contras |
|---|------------|------|---------|
| A | **Tornar opcional** (como codebase-map) | Zero breaking change | Skill separada com gate que quase ninguém precisa |
| B | **Merge como seção do blueprint** | -1 skill. Complementares | Blueprint fica maior |
| C | **Manter mas gate auto** | Gera sem parar | Output ruim propaga silenciosamente |
| D | **Eliminar** | -1 skill | Perde documentação de intenção |

**Recomendação: B (merge no blueprint).**

Folder structure é consequência direta das decisões do blueprint (stack, patterns, deploy topology). Documentar "como organizar o código" junto de "quais são os NFRs e patterns" é coerente — são facetas do mesmo artefato de engenharia.

A longo prazo, menos skills = menos manutenção, menos boilerplate, menos context loading. O blueprint já tem seção de stack e patterns — adicionar "Folder Structure" como seção final é natural.

**DAG impact:** Remover nó `folder-arch`. Blueprint passa a produzir `engineering/blueprint.md` (que inclui folder structure). Zero mudança em dependentes downstream.

---

### A8. Auto-review é checkbox theater para checks universais

**Identificado por:** Architect, AI Specialist

#### Alternativas

| # | Alternativa | Prós | Contras |
|---|------------|------|---------|
| A | **Checks executáveis (grep/wc)** | Determinístico. Zero sycophancy | Só para checks sintáticos |
| B | **Subagent adversarial** | Contexto fresco. Menos blind spots | Dobra latência. Custo tokens |
| C | **Scorecard para humano** | Honesto sobre confiança. Review eficiente | Depende do humano revisar |
| D | **Tiered por gate** — auto: exec. human: exec+scorecard. 1-way-door: exec+adversarial+scorecard | Custo ∝ risco | 3 tiers de complexidade |

**Recomendação: D (tiered por gate type).**

Investir review proporcional ao custo do erro é o approach correto a longo prazo:

| Gate | Review | Justificativa |
|------|--------|---------------|
| auto | Checks executáveis (grep/wc) | Output de baixo risco. Validação determinística basta |
| human | Executáveis + scorecard para humano | Humano no loop. Scorecard direciona atenção para weak spots |
| 1-way-door | Executáveis + subagent adversarial + scorecard | Decisões irreversíveis. Fresh context do subagent catch blind spots. Custo extra (~1.5x tokens) justificado pelo impacto |

**Implementação:** Definir cada tier no `pipeline-contract-base.md` (A1). Skills não precisam saber qual tier — o gate type determina automaticamente.

---

### A9. `platform-new` não segue o contrato de 6 passos

**Identificado por:** Architect

#### Alternativas

| # | Alternativa | Prós | Contras |
|---|------------|------|---------|
| A | **Alinhar completamente** | Consistente. Primeiro contato = exemplar | Auto-review de prosa em scaffolding parece excesso |
| B | **Alinhar parcialmente** (questions + gate, sem auto-review) | Pragmático | Exceção ao contrato |
| C | **Manter como está** | Simples | Inconsistência |

**Recomendação: A (alinhar completamente).**

Consistência a longo prazo vale mais que pragmatismo pontual. `platform-new` é a **primeira impressão** do sistema. Se a primeira skill quebra o contrato, o padrão perde credibilidade.

Auto-review para scaffolding: verificar que `platform.yaml` tem campos obrigatórios, que diretórios foram criados, que `likec4.config.json` existe. Não é review de prosa — é validação de infraestrutura. Cabe perfeitamente no contrato.

---

### A10. `pipeline-next` não cobre o ciclo per-epic

**Identificado por:** PM, Designer

#### Alternativas

| # | Alternativa | Prós | Contras |
|---|------------|------|---------|
| A | **Estender pipeline-next para per-epic** | Cobertura completa. Um comando | Complexidade (estado do epic cycle) |
| B | **Merge status+next em `/pipeline`** + per-epic | Um comando = tudo. Como users realmente usam | Skill maior |
| C | **Criar `epic-next` separado** | Separação de concerns | Mais uma skill para descobrir |

**Recomendação: B (merge em `/pipeline` com cobertura completa).**

Um único ponto de observabilidade para todo o sistema. Default mostra DAG status + per-epic progress + next step recomendado. Flags `--status` e `--next` para modos específicos.

A longo prazo com 10 plataformas e 50 epics, o usuário precisa de **um comando** para responder "o que devo fazer agora?" — não dois ou três.

---

### A11. Risco de alucinação em tech-research e adr-gen

**Identificado por:** AI Specialist

#### Alternativas

| # | Alternativa | Prós | Contras |
|---|------------|------|---------|
| A | **Escape hatch** — "[DADOS INSUFICIENTES]" quando sem dados | Simples. Honesto | Usuário pode não gostar de "não sei" |
| B | **Require URL/source** para toda afirmação | Auditável | Limita fontes |
| C | **Two-pass research** — list claims, verify each | Robusto | Dobra latência |

**Recomendação: A + B combinados.**

Honestidade é fundação de qualidade. Se o LLM não tem dados, fabricar é pior que admitir. URLs permitem auditoria. Duas linhas na Cardinal Rule de cada skill de research:

1. "Se research não retornar dados, marcar `[DADOS INSUFICIENTES]` e recomendar adiar a decisão."
2. "Toda afirmação factual deve ter URL ou referência verificável. Sem URL → `[FONTE NÃO VERIFICADA]`."

---

### A12. DAG duplicado em CLAUDE.md e knowledge file

**Identificado por:** Designer, AI Specialist

#### Alternativas

| # | Alternativa | Prós | Contras |
|---|------------|------|---------|
| A | **CLAUDE.md resumo + ponteiro** | -500 tokens/conversa. Single source of truth | Knowledge file não auto-loaded |
| B | **Mover tudo para knowledge file** | Máxima economia | Contexto perdido fora de skills |
| C | **Manter duplicação + linter sync** | Zero mudança | Não resolve tokens. Mais um script |

**Recomendação: A (resumo + ponteiro).**

CLAUDE.md mantém: fluxo compacto (1 linha ASCII), tabela de 14 nós (referência rápida), tabela de gates (4 linhas). Remove: templates detalhados, handoff examples, per-epic cycle details, contract specification.

Knowledge file é referência completa. Skills o referenciam explicitamente.

---

## 🟡 MÉDIA PRIORIDADE (14)

---

### M1. Gates excessivos na business layer

| # | Alternativa | Prós | Contras |
|---|------------|------|---------|
| A | **Manter todos human** | Máximo controle | Fatigue → rubber-stamping |
| B | **Auto-escalate para business-process e context-map** | -2 paradas | Risco mitigado por threshold |
| C | **Confidence-scored** | Adaptativo | Complexidade. Confuso |

**Recomendação: A (manter todos human).**

Revisão de prioridades: business-process e solution-overview definem o **fundamento** de tudo downstream. Blast radius é alto. Na business layer, 10 minutos de review humano evitam horas de retrabalho em engineering. Rubber-stamping é problema de UX (resolver com melhor apresentação no gate), não de gate type.

**Exceção:** `context-map` → auto-escalate (derivação mecânica, blast radius limitado). `folder-arch` → merge em blueprint (A7).

---

### M2. `speckit.analyze` pós-implementação redundante com `verify`

**Recomendação: B (merge analyze-post no verify).**

Não eliminar — absorver. verify ganha os checks de consistency que analyze faz, resultando em um verify mais completo. Eliminar (A) perde cobertura se verify tiver bugs. Merge é mais seguro a longo prazo.

---

### M3-M5. Renaming: discuss → epic-context, adr-gen → adr, test-ai → qa

| # | Alternativa | Prós | Contras |
|---|------------|------|---------|
| A | **Renomear agora** | Clareza imediata | Breaking changes. Atualizar referências |
| B | **Alias (manter ambos)** | Zero breaking | Confusão |
| C | **Adiar para namespace unification** | Batch | Meses de confusão enquanto espera |

**Recomendação: A (renomear agora).**

Cada dia com nomes confusos é fricção acumulada. "discuss" é invocado em todo ciclo per-epic — nome vago multiplicado por N epics. Namespace unification é feature "Next" (3-6 meses). Não faz sentido conviver com nomes ruins por meses para economizar 1 rename batch.

Renomear agora:
- `discuss` → `epic-context`
- `adr-gen` → `adr`
- `test-ai` → `qa`
- `vision-one-pager` → `vision`
- `folder-arch` → eliminado (merge em blueprint, A7)

O namespace unification futuramente move de `madruga/` para `madruga.` — é uma mudança de prefixo, não de nome. Nomes corretos agora + prefixo correto depois.

---

### M6. Hooks boilerplate duplicado em 4 skills SpecKit

**Recomendação: A (extrair para knowledge file).** Consistente com A1.

---

### M7. Dead code no argument parser

**Recomendação: Deletar linhas 27-67.** Zero risco.

---

### M8. `containers` gera 3 files mas DAG trackeia só 2

**Recomendação: Adicionar `model/views.likec4` aos outputs.** Consistência.

---

### M9. Marcadores de validação inconsistentes

**Recomendação: `[VALIDAR]` (PT-BR).** Artefatos são PT-BR. Consistência de idioma.

---

### M10. Save reports verbosos

**Recomendação:** Encurtar para formato compacto:
```
Auto-review: PASS (N/N). Arquivo: path (N linhas). Próximo: /command name
```

---

### M11. `platform.py` não valida nome de plataforma

**Recomendação:** Regex `^[a-z][a-z0-9-]*$` em `cmd_new`. ~5 linhas.

---

### M12. `speckit.checklist` e `speckit.constitution` são órfãos

**Recomendação: Documentar como utility skills.** Não complicar o ciclo per-epic. Quando namespace unification acontecer, reavaliar se devem ser integrados.

---

### M13. Personas decorativas

**Recomendação: Afiar em diretivas comportamentais específicas:**

| Persona atual | Nova diretiva |
|---------------|---------------|
| "Senior Tech Research Analyst" | "Seu default é `[DADOS INSUFICIENTES]`. Só afirme com source verificável." |
| "Product Manager / Architect" | "Você já mandou 10+ produtos. Seu instinto é REDUZIR escopo, não adicionar." |
| "Pipeline Observer" (pipeline-status) | Remover (read-only, persona não muda comportamento) |
| "Session Recorder" (checkpoint) | Remover (data collection, persona sem efeito) |

---

### M14. Sem validação de conteúdo no prerequisites checker

| # | Alternativa | Prós | Contras |
|---|------------|------|---------|
| A | **Minimum size** (>100 bytes) | Trivial | Arbitrário |
| B | **Frontmatter check** | Semanticamente correto | Mais código per-filetype |
| C | **Marker `<!-- generated-by: skill-id -->`** | Prova definitiva | Todas skills precisam incluir |
| D | **A + C** | Defense in depth | Dois mecanismos |

**Recomendação: C (marker check) + provenance no BD.**

O marker no artefato (`<!-- generated-by: vision | platform: fulano -->`) é a validação visual. A proveniência real vai para a tabela `artifact_provenance` no SQLite. O prerequisites checker consulta o BD:

```sql
-- Artefato foi gerado pelo pipeline?
SELECT generated_by, generated_at FROM artifact_provenance
WHERE platform_id = 'fulano' AND file_path = 'business/vision.md';
-- Se não retornar row → arquivo manual/stub, não gerado pelo pipeline
```

Marker no arquivo + row no BD = defense in depth. O marker é para humanos; o BD é para máquinas.

---

## 🟢 BAIXA PRIORIDADE / QUICK WINS (12)

### L1. TL;DR no topo de cada skill

```
> INPUT: [deps] | OUTPUT: [path] | TEMPO: ~Xmin | GATE: [type]
```

### L2. Checkpoint auto-executar após cada skill

Adicionar ao step 5 do contrato base: "Após salvar artefato, executar `db.py` para: UPDATE pipeline_nodes/epic_nodes, INSERT INTO decisions, INSERT INTO artifact_provenance, INSERT INTO events."

### L3. Tempo estimado no pipeline-status

Coluna `~Tempo` na tabela. Estimativas baseadas em experiência real.

### L4. Handoffs em skills SpecKit

Adicionar: `speckit.implement → verify`, `speckit.tasks → speckit.analyze`.

### L5. Limites de linhas advisory

Mudar de hard limit para "target: N lines". Mermaid diagrams inflam legitimamente.

### L6. context-map → auto-escalate

Derivação mecânica de domain-model + containers. Incluir na recalibração.

### L7. Guidance de quantidade de perguntas

"4-8 perguntas total, mínimo 1 por categoria."

### L8. Reconcile report path

Resolvido por B2/B3: reconcile salva em `platforms/<name>/epics/<NNN>/reconcile-report.md`.

### L9. verify/reconcile leem context.md

Resolvido por B2/B3: tudo no mesmo epic dir. verify e reconcile leem `context.md` naturalmente.

### L10. Testes automatizados

| Script | Framework | Tests | Esforço |
|--------|-----------|-------|---------|
| `vision-build.py` | pytest | 6-8 (pure functions) | ~2h |
| `platform.py` | pytest | 8-10 (user-facing) | ~3h |
| `check-prerequisites.sh` | bats | 6-8 (mock dirs) | ~2h |

### L11. Skill `/getting-started`

DAG simplificado + gates em 3 linhas + `/pipeline fulano` como primeiro comando.

### L12. Diretório `planning/`

Manter. Roadmap justifica. Sprint plans podem vir depois.

---

## Ciclo Per-Epic Revisado (Nível 2 do DAG Unificado)

### Ciclo Atual (11 steps, fora do DAG)

```
discuss → specify → clarify → plan → tasks → analyze → implement → analyze → verify → test-ai? → reconcile
```

### Ciclo Revisado (10 nós no DAG, 3 condicionais)

```
epic-context → specify → clarify? → plan → tasks → analyze → implement → verify → qa? → reconcile?
```

Todos operando dentro de `platforms/<name>/epics/<NNN-slug>/` (diretório unificado, ver B2/B3).

| Step | Skill | Gate | Condicional? | Output | Mudança |
|------|-------|------|-------------|--------|---------|
| 1 | `epic-context` | human | Não | `context.md` | Renomeado de `discuss`. Captura contexto arquitetural |
| 2 | `specify` | human | Não | `spec.md` + `checklists/` | SpecKit opera no epic dir. Lê `pitch.md` + `context.md` |
| 3 | `clarify` | human | **Sim** | `spec.md` (atualiza) | Só se spec tem [NEEDS CLARIFICATION] |
| 4 | `plan` | human | Não | `plan.md` + `data-model.md` + `contracts/` | SpecKit opera no epic dir |
| 5 | `tasks` | human | Não | `tasks.md` | SpecKit opera no epic dir |
| 6 | `analyze` | auto | Não | `analyze-report.md` | Pre-implementation consistency |
| 7 | `implement` | auto | Não | `tasks.md` (marca done) | Feature branch por epic. SpecKit opera no epic dir |
| 8 | `verify` | auto-escalate | Não | `verify-report.md` | **Absorve analyze-post**. Persiste report (novo) |
| 9 | `qa` | human | **Sim** | `qa-report.md` | Só se epic tem UI. Salva no epic dir (não obsidian) |
| 10 | `reconcile` | human | **Sim** | `reconcile-report.md` | Só se drift detectado. Salva no epic dir |

**Por que epic-context permanece separado (não merge em specify):**
- **Concern diferente**: epic-context traduz arquitetura (ADRs, blueprint, domain model) em decisões de implementação. Specify traduz decisões em spec de feature
- **Valor do artefato**: `context.md` é lido por verify e reconcile downstream
- **Fresh context**: specify já tem muito trabalho (spec template, acceptance criteria, quality checks)

**Melhor caso:** 6 steps (epic-context → specify → plan → tasks+implement → verify)
**Pior caso:** 10 steps (epic complexo com ambiguidades, UI, e drift)

**Checkpoint é transversal** — roda automaticamente após cada nó (trigger, não step). Atualiza SQLite (pipeline_nodes, decisions, events).

---

## Calibração de Gates Revisada

### Nível 1 — Platform DAG (13 nós)

| Skill | Atual | Novo | Razão |
|-------|-------|------|-------|
| platform-new | human | human | Fundacional |
| vision | human | human | Fundacional |
| solution-overview | human | human | Alto blast radius — feeds toda business layer |
| business-process | human | human | Fundacional para domain model. 10min de review evita horas de retrabalho |
| tech-research | 1-way-door | 1-way-door | Irreversível |
| codebase-map | auto | auto | Correto |
| adr | 1-way-door | 1-way-door | Irreversível |
| blueprint | human | human | Alto blast radius |
| ~~folder-arch~~ | ~~human~~ | **eliminado** | Merge em blueprint |
| domain-model | human | human | DDD boundaries = fundacionais |
| containers | human | human | Deploy topology = crítica |
| context-map | human | **auto-escalate** | Derivação mecânica. Escala se circular deps |
| epic-breakdown | 1-way-door | 1-way-door | Irreversível |
| roadmap | human | human | Sequenciamento precisa validação |

### Nível 2 — Epic DAG (10 nós por epic)

| Skill | Gate | Condicional? |
|-------|------|-------------|
| epic-context | human | Não |
| specify | human | Não |
| clarify | human | Sim — só se [NEEDS CLARIFICATION] > 0 |
| plan | human | Não |
| tasks | human | Não |
| analyze | auto | Não |
| implement | auto | Não |
| verify | auto-escalate | Não |
| qa | human | Sim — só se epic tem UI e app rodando |
| reconcile | human | Sim — só se drift detectado |

**Mudanças líquidas:** -1 nó platform (folder-arch eliminado), 1 downgrade (context-map → auto-escalate), +10 nós epic (antes fora do DAG).

---

## Banco de Dados — SQLite desde o Início

### Por que SQLite (e não Supabase/PostgreSQL)

O doc `docs/db-first-architecture.md` propôs Supabase (PostgreSQL). Revisando com base no uso real:

| Aspecto | SQLite | Supabase |
|---------|--------|----------|
| **Infra** | Zero. Um arquivo. Built-in no Python | Managed cloud. Requer rede |
| **Use case** | CLI single-user (madruga.ai hoje) | Multi-user, real-time, auth |
| **Offline** | Funciona sempre | Depende de rede |
| **Dependências** | Zero (`import sqlite3`) | `pip install supabase` + API key |
| **Migração para PG** | Mecânica (path mais documentado do mundo) | N/A (já é PG) |
| **Complexidade** | Mínima | Auth, RLS, API, migrations |

**Decisão: SQLite agora.** É CLI single-user que roda local. Quando precisar multi-user ou portal real-time, migra para PostgreSQL/Supabase em ~1 dia — o schema é 95% compatível.

### Arquitetura

```
Skills / CLI / platform.py
        │
        ▼
┌─────────────────────────────────┐
│   .pipeline/madruga.db (SQLite) │
│                                 │
│   platforms ─┬─ pipeline_nodes  │  ← DAG nível 1
│              ├─ epics           │
│              │   └─ epic_nodes  │  ← DAG nível 2
│              ├─ decisions       │  ← ADR registry + decision log
│              ├─ artifact_provenance │
│              ├─ pipeline_runs   │  ← tracking tokens/custo
│              ├─ events          │  ← audit log
│              └─ tags            │  ← cross-references
│                                 │
│   elements ──── relationships   │  ← LikeC4 graph (futuro)
└───────────┬─────────────────────┘
            │
            ▼
┌─────────────────────────────────┐
│   Git (repositório)             │
│   platforms/*/                  │
│     ├─ business/*.md    (prose) │
│     ├─ engineering/*.md (prose) │
│     ├─ epics/*/         (prose + spec + plan + tasks) │
│     ├─ decisions/*.md   (prose) │
│     └─ model/*.likec4   (model) │
└─────────────────────────────────┘
```

**Princípio:** Git = source of truth para **conteúdo** (prose, código, modelos). BD = source of truth para **estado, metadados, relações, tracking**.

### Schema SQLite

```sql
-- .pipeline/migrations/001_initial.sql

-- ══════════════════════════════════════
-- Core entities
-- ══════════════════════════════════════

CREATE TABLE platforms (
    platform_id TEXT PRIMARY KEY,              -- "fulano" (kebab-case)
    name        TEXT NOT NULL,
    title       TEXT,
    lifecycle   TEXT NOT NULL DEFAULT 'design'
                CHECK (lifecycle IN ('design', 'development', 'production', 'deprecated')),
    repo_path   TEXT NOT NULL,                 -- "platforms/fulano"
    metadata    TEXT DEFAULT '{}',             -- JSON: views, build configs
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE epics (
    epic_id     TEXT NOT NULL,                 -- "001-channel-pipeline"
    platform_id TEXT NOT NULL REFERENCES platforms(platform_id),
    title       TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'proposed'
                CHECK (status IN ('proposed', 'in_progress', 'shipped', 'blocked', 'cancelled')),
    appetite    TEXT,                           -- "6 weeks"
    priority    INTEGER,
    branch_name TEXT,                          -- feature branch do SpecKit
    file_path   TEXT,                          -- "epics/001-channel-pipeline/pitch.md"
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    PRIMARY KEY (platform_id, epic_id)
);

-- ══════════════════════════════════════
-- DAG Nível 1: Platform nodes
-- ══════════════════════════════════════

CREATE TABLE pipeline_nodes (
    platform_id TEXT NOT NULL REFERENCES platforms(platform_id),
    node_id     TEXT NOT NULL,                 -- "vision", "blueprint", etc.
    status      TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'done', 'stale', 'blocked', 'skipped')),
    output_hash TEXT,                          -- SHA256 do conteúdo do artefato
    input_hashes TEXT DEFAULT '{}',            -- JSON: {dep_file: hash}
    output_files TEXT DEFAULT '[]',            -- JSON array: ["business/vision.md"]
    completed_at TEXT,
    completed_by TEXT,                         -- skill que gerou
    line_count  INTEGER,
    PRIMARY KEY (platform_id, node_id)
);

-- ══════════════════════════════════════
-- DAG Nível 2: Epic cycle nodes
-- ══════════════════════════════════════

CREATE TABLE epic_nodes (
    platform_id TEXT NOT NULL,
    epic_id     TEXT NOT NULL,
    node_id     TEXT NOT NULL,                 -- "specify", "plan", "verify", etc.
    status      TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'done', 'stale', 'blocked', 'skipped')),
    output_hash TEXT,
    completed_at TEXT,
    completed_by TEXT,
    PRIMARY KEY (platform_id, epic_id, node_id),
    FOREIGN KEY (platform_id, epic_id) REFERENCES epics(platform_id, epic_id)
);

-- ══════════════════════════════════════
-- Decisions (ADR registry + decision log unificados)
-- ══════════════════════════════════════

CREATE TABLE decisions (
    decision_id     TEXT PRIMARY KEY,          -- "adr-001" ou auto-generated
    platform_id     TEXT NOT NULL REFERENCES platforms(platform_id),
    epic_id         TEXT,                      -- NULL para platform-level decisions
    skill           TEXT NOT NULL,             -- "adr", "vision", "epic-context"
    slug            TEXT,                      -- "database-choice" (para ADRs)
    title           TEXT NOT NULL,
    number          INTEGER,                   -- ADR number (para ADRs)
    status          TEXT NOT NULL DEFAULT 'accepted'
                    CHECK (status IN ('accepted', 'superseded', 'deprecated', 'proposed')),
    superseded_by   TEXT REFERENCES decisions(decision_id),
    source_decision_key TEXT,                  -- Liga ao tech-research
    file_path       TEXT,                      -- "decisions/ADR-001-database-choice.md"
    decisions_json  TEXT DEFAULT '[]',         -- JSON array: decisões tomadas
    assumptions_json TEXT DEFAULT '[]',        -- JSON array: assumptions
    open_questions_json TEXT DEFAULT '[]',     -- JSON array: open questions
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- ══════════════════════════════════════
-- Artifact provenance
-- ══════════════════════════════════════

CREATE TABLE artifact_provenance (
    platform_id  TEXT NOT NULL REFERENCES platforms(platform_id),
    file_path    TEXT NOT NULL,                -- "business/vision.md"
    generated_by TEXT NOT NULL,                -- skill ID
    epic_id      TEXT,                         -- NULL para platform-level
    output_hash  TEXT,
    generated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    PRIMARY KEY (platform_id, file_path)
);

-- ══════════════════════════════════════
-- Tracking (pipeline runs, cost)
-- ══════════════════════════════════════

CREATE TABLE pipeline_runs (
    run_id       TEXT PRIMARY KEY,
    platform_id  TEXT NOT NULL REFERENCES platforms(platform_id),
    epic_id      TEXT,
    node_id      TEXT NOT NULL,                -- "vision", "specify", etc.
    status       TEXT NOT NULL DEFAULT 'running'
                 CHECK (status IN ('running', 'completed', 'failed', 'cancelled')),
    agent        TEXT,                         -- "claude-opus-4-6"
    tokens_in    INTEGER,
    tokens_out   INTEGER,
    cost_usd     REAL,
    duration_ms  INTEGER,
    error        TEXT,
    started_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    completed_at TEXT
);

-- ══════════════════════════════════════
-- Events (audit log append-only)
-- ══════════════════════════════════════

CREATE TABLE events (
    event_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    platform_id  TEXT REFERENCES platforms(platform_id),
    entity_type  TEXT NOT NULL,                -- "platform", "epic", "decision", "node"
    entity_id    TEXT NOT NULL,
    action       TEXT NOT NULL,                -- "created", "status_changed", "completed"
    actor        TEXT DEFAULT 'system',        -- "human", "claude-opus-4-6", "system"
    payload      TEXT DEFAULT '{}',            -- JSON
    created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- ══════════════════════════════════════
-- Cross-references
-- ══════════════════════════════════════

CREATE TABLE tags (
    platform_id  TEXT NOT NULL REFERENCES platforms(platform_id),
    source_type  TEXT NOT NULL CHECK (source_type IN ('epic', 'decision', 'element', 'node')),
    source_id    TEXT NOT NULL,
    target_type  TEXT NOT NULL CHECK (target_type IN ('epic', 'decision', 'element', 'node')),
    target_id    TEXT NOT NULL,
    relation     TEXT DEFAULT 'related',       -- "implements", "motivates", "impacts"
    UNIQUE (source_type, source_id, target_type, target_id)
);

-- ══════════════════════════════════════
-- Indexes
-- ══════════════════════════════════════

CREATE INDEX idx_epics_platform ON epics(platform_id);
CREATE INDEX idx_pipeline_nodes_platform ON pipeline_nodes(platform_id);
CREATE INDEX idx_epic_nodes_epic ON epic_nodes(platform_id, epic_id);
CREATE INDEX idx_decisions_platform ON decisions(platform_id);
CREATE INDEX idx_decisions_epic ON decisions(epic_id);
CREATE INDEX idx_provenance_platform ON artifact_provenance(platform_id);
CREATE INDEX idx_runs_platform ON pipeline_runs(platform_id);
CREATE INDEX idx_events_entity ON events(entity_type, entity_id);
CREATE INDEX idx_events_platform ON events(platform_id);
```

### O que fica onde

| Dado | Source of truth | Por que |
|------|----------------|---------|
| Pipeline state (nós, status, hashes) | **SQLite** | Queries, staleness detection, tracking |
| Epic state (progress, branch, status) | **SQLite** | Queries cross-epic, dashboard |
| Decisions (ADR registry + log) | **SQLite** | Idempotência, lineage, queries |
| Artifact provenance | **SQLite** | Validação de prerequisites |
| Pipeline runs (tokens, custo) | **SQLite** | Tracking, otimização |
| Events (audit log) | **SQLite** | Timeline, auditoria |
| Cross-references (epic↔ADR↔element) | **SQLite** | Impact analysis |
| Vision, pitch, spec, plan, tasks **prose** | **Git (markdown)** | Conteúdo narrativo, diff-friendly, LLM-consumível |
| LikeC4 model files | **Git (.likec4)** | DSL, compilável |
| Templates (Copier, SpecKit) | **Git** | Versionados |

### Implementação: módulo `db.py`

```python
# .specify/scripts/db.py — ~200 linhas
# Thin wrapper sobre sqlite3

import sqlite3, os, hashlib, json

DB_PATH = os.path.join(os.path.dirname(__file__), '../../.pipeline/madruga.db')

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn

def migrate():
    """Aplica migrations de .pipeline/migrations/*.sql em ordem."""
    ...

def upsert_platform(platform_id, name, repo_path, **kwargs): ...
def upsert_pipeline_node(platform_id, node_id, status, output_hash, **kwargs): ...
def upsert_epic(platform_id, epic_id, title, **kwargs): ...
def upsert_epic_node(platform_id, epic_id, node_id, status, **kwargs): ...
def insert_decision(platform_id, skill, title, **kwargs): ...
def insert_provenance(platform_id, file_path, generated_by, **kwargs): ...
def insert_run(platform_id, node_id, **kwargs): ...
def insert_event(platform_id, entity_type, entity_id, action, **kwargs): ...
def get_platform_status(platform_id): ...
def get_epic_status(platform_id, epic_id): ...
def get_stale_nodes(platform_id): ...
def compute_file_hash(path):
    return "sha256:" + hashlib.sha256(open(path,'rb').read()).hexdigest()[:12]
```

### Integração nas skills

| Onde | Mudança |
|------|---------|
| **Step 0 (prerequisites)** | `check-platform-prerequisites.sh` consulta SQLite em vez de checar file existence |
| **Step 5 (save+report)** | Após salvar artefato: `db.upsert_pipeline_node()`, `db.insert_decision()`, `db.insert_provenance()`, `db.insert_event()` |
| **`/pipeline`** | `SELECT` no BD em vez de scan de diretórios |
| **`platform.py new`** | `db.upsert_platform()` após copier |
| **`epic-breakdown`** | `db.upsert_epic()` para cada epic criado |
| **SpecKit skills** | `db.upsert_epic_node()` no final de cada skill |

### Queries que se tornam possíveis

```sql
-- Progresso geral por plataforma
SELECT p.platform_id, COUNT(*) as total,
       SUM(CASE WHEN pn.status = 'done' THEN 1 ELSE 0 END) as done
FROM pipeline_nodes pn JOIN platforms p ON pn.platform_id = p.platform_id
GROUP BY p.platform_id;

-- Epics com progresso por plataforma
SELECT e.epic_id, e.title, e.status,
       COUNT(en.node_id) as total_steps,
       SUM(CASE WHEN en.status = 'done' THEN 1 ELSE 0 END) as done_steps
FROM epics e LEFT JOIN epic_nodes en ON e.epic_id = en.epic_id AND e.platform_id = en.platform_id
WHERE e.platform_id = 'fulano'
GROUP BY e.epic_id;

-- Custo total por plataforma
SELECT platform_id, SUM(cost_usd), SUM(tokens_in + tokens_out)
FROM pipeline_runs WHERE status = 'completed' GROUP BY platform_id;

-- Decisões abertas (open questions)
SELECT platform_id, skill, title, open_questions_json
FROM decisions WHERE open_questions_json != '[]';

-- Artefatos stale (dependência regenerada depois)
SELECT child.node_id, child.completed_at as node_date, parent.completed_at as dep_date
FROM pipeline_nodes child
JOIN json_each(
  (SELECT value FROM json_each(
    (SELECT depends FROM pipeline_dag WHERE node_id = child.node_id)
  ))
) deps
JOIN pipeline_nodes parent ON parent.node_id = deps.value
WHERE child.platform_id = 'fulano'
  AND parent.completed_at > child.completed_at;
```

### Esforço de implementação

| Item | Esforço |
|------|---------|
| Schema SQL + migrations | ~1h |
| `db.py` module (init, migrate, CRUD) | ~2h |
| Integrar em `check-platform-prerequisites.sh` | ~1h |
| Integrar step 5 das skills (via knowledge file) | ~1h |
| `/pipeline` lê do BD | ~1h |
| `platform.py` sync existing data | ~1h |
| Testes básicos (pytest) | ~1h |
| **Total** | **~8h** |

### Migração futura para PostgreSQL/Supabase

Quando precisar multi-user, portal real-time, ou pgvector:
1. `pg_dump` compatível — SQLite → PostgreSQL é mecânico
2. Trocar `sqlite3.connect()` por `psycopg2.connect()` em `db.py`
3. Ajustar tipos: `TEXT DEFAULT '{}'` → `JSONB DEFAULT '{}'`, `INTEGER PRIMARY KEY AUTOINCREMENT` → `SERIAL`
4. Adicionar RLS, auth, real-time subscriptions (features do Supabase)
5. Estimativa: ~1 dia de trabalho

---

## Top 10 Ações por Prioridade

| # | Ação | Tipo | Esforço | Impacto a Longo Prazo |
|---|------|------|---------|----------------------|
| 1 | **`copier update` nas plataformas existentes** + GitHub Actions lint | Bloqueante | 30min | Desbloqueia pipeline + previne reincidência |
| 2 | **SQLite + `db.py`** — Schema, migrations, CRUD. Fundação de todo estado | Bloqueante | ~8h | Queries reais, constraints, provenance, tracking. Fundação |
| 3 | **Unificação diretório + DAG dois níveis (B2/B3)** — SpecKit opera em `epics/<NNN>/`, DAG trackeia epic cycle no BD | Bloqueante | 6-8h (4 fases) | Um sistema, um DAG, observabilidade total |
| 4 | **Knowledge files em camadas** (contract-base + por-layer) | Arquitetura | 3-4h | -15K tokens. Consistência. Manutenção 5x mais fácil |
| 5 | **Auto-review tiered** (exec + adversarial + scorecard) | Qualidade | 3-4h | Review real proporcional ao risco |
| 6 | **Merge folder-arch em blueprint** + renaming batch | Simplificação | 2h | -1 skill, nomes claros, DAG mais limpo |
| 7 | **LikeC4 knowledge file + `likec4 build` validation** | Qualidade | 2h | .likec4 sempre válido |
| 8 | **HANDOFF blocks nos artefatos** | Context preservation | 1h/skill | View layer para contexto entre skills |
| 9 | **`/pipeline` unificado (status+next+per-epic)** — lê SQLite | Observabilidade | 2h | Um comando = visibilidade total dos dois níveis |
| 10 | **Hallucination guardrails** (escape hatch + URL format) | Qualidade | 30min | Honestidade em research skills |

**Nota:** A3 (staleness), A4 (idempotência/registry), A5 (test-ai path), M14 (provenance), L2 (checkpoint) são **todos resolvidos pelo BD** (ação #2). Não são itens separados — são features do schema SQLite.

---

*Documento gerado por 9 agentes especializados. Recomendações revisadas priorizando longo prazo, valor, performance, consistência e qualidade. SQLite como BD desde o início — zero arquivos intermediários de estado.*
