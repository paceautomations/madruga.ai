# Melhorias para o SpecKit — Inspiradas no GSD e BMAD

**Data**: 2026-03-27
**Contexto**: Análise comparativa entre SpecKit (SDD), BMAD e GSD para identificar gaps concretos no workflow SpecKit e propor incrementos como custom commands.

---

## Comparativo Rápido dos 3 Frameworks

| | **SpecKit** | **BMAD** | **GSD** |
|---|---|---|---|
| **Org** | GitHub (oficial) | BMad Code, LLC | gsd-build (indie) |
| **Stars** | 83K | 42.5K | 43.3K |
| **Forks** | 7K | 5.1K | 3.5K |
| **Licença** | MIT | MIT | MIT |
| **Versão** | v0.4.3 | V6 (npm) | npm latest |
| **CLI** | `specify` (Python/uv) | `npx bmad-method` (Node) | `npx get-shit-done-cc` (Node) |
| **Filosofia** | Spec como artefato executável | Agile enterprise com agentes especializados | Context engineering minimalista anti-cerimônia |
| **Público** | Qualquer dev/team | Teams enterprise-agile | Solo devs / pequenos times |

### Workflow comparado

| Fase | **SpecKit** | **BMAD** | **GSD** |
|---|---|---|---|
| Setup | `constitution` | `bmad-init` + módulos | `new-project` (Q&A) |
| Discovery | `specify` | `bmad-product-brief` + analyst | Embutido no `new-project` |
| Clarificação | `clarify` (5 perguntas) | `bmad-advanced-elicitation` | `discuss-phase` (gray areas) |
| Planning | `plan` (tech plan + arch) | PRD → Architecture → Epics | `plan-phase` (research + atomic plans) |
| Tasks | `tasks` (dependency-ordered) | `bmad-sprint-planning` + stories | Embutido nos plans (XML tasks) |
| Review | `analyze` (cross-artifact) | `bmad-check-implementation-readiness` | `validate-phase` + plan-checker |
| Implementação | `implement` (executa tasks.md) | `bmad-dev-story` / `bmad-quick-dev` | `execute-phase` (wave parallelism) |
| QA | — | `bmad-qa-generate-e2e-tests` + QA agent | `verify-work` + `ui-review` |
| Post-impl | `taskstoissues` (GitHub) | `bmad-retrospective` + `bmad-code-review` | `review` + `session-report` |

### Artefatos produzidos

| **SpecKit** | **BMAD** | **GSD** |
|---|---|---|
| `constitution.md` | Project brief | `PROJECT.md` |
| `spec.md` | PRD (Product Requirements) | `REQUIREMENTS.md` |
| `plan.md` | Architecture doc | `ROADMAP.md` |
| `tasks.md` | Epics & Stories | `{N}-PLAN.md` (XML tasks) |
| `checklist.md` | Sprint backlog | `STATE.md` (memory) |
| — | UX Design doc | `CONTEXT.md` (por fase) |
| — | Test architecture | `research/` (por fase) |

### Agentes/Personas

| **SpecKit** | **BMAD** | **GSD** |
|---|---|---|
| Sem agentes especializados — templates guiam o AI genérico | **12+ agentes**: PM, Analyst, Architect, UX, Dev, QA, Scrum Master, Tech Writer + "Party Mode" | **18 agentes**: executor, planner, researcher, debugger, verifier, UI auditor, codebase mapper, etc. |

---

## Gaps Identificados no SpecKit

### Gap 1: Context Rot (degradação de qualidade por contexto cheio)

**Origem**: GSD

**Problema**: O `implement` do SpecKit executa todas as tasks numa sessão única. Conforme o context window enche (200K tokens), a qualidade do output degrada — o AI começa a simplificar, esquecer requisitos, e produzir código cada vez pior. O GSD chama isso de "context rot" e é o problema central que resolve.

**Como o GSD resolve**: Cada plan é executado como um subagent com contexto fresh (200K tokens puros para implementação). Plans são agrupados em "waves" por dependência — plans independentes rodam em paralelo, waves rodam sequencialmente.

**Proposta — `/speckit.execute-wave`**:
- Quebra o `tasks.md` em waves (grupos de tasks sem dependência mútua)
- Cada wave é executada como um Agent subagent com contexto limpo
- Cada subagent recebe apenas: `plan.md` + tasks da wave + arquivos do projeto relevantes
- Commit atômico por wave
- Orchestrator thin coordena waves e passa resultados entre elas

**Artefatos**:
- `WAVE-PLAN.md` — mapa de waves com dependências
- Commits granulares por wave no git

**Impacto**: Alto. Features com 15+ tasks hoje degradam significativamente na segunda metade.

---

### Gap 2: Discuss/Context Phase (preferências de implementação)

**Origem**: GSD (`discuss-phase`)

**Problema**: O SpecKit vai de `specify` (o quê) direto para `plan` (como). O `clarify` foca em ambiguidade funcional da spec. Não há passo para capturar **preferências de implementação** — como o usuário imagina o layout, que padrões de interação prefere, que trade-offs aceita.

**Como o GSD resolve**: O `discuss-phase` analisa a fase e identifica "gray areas" baseado no tipo de feature:
- Features visuais → Layout, densidade, interações, empty states
- APIs/CLIs → Formato de resposta, flags, error handling
- Content systems → Estrutura, tom, profundidade
- Organization tasks → Critérios de agrupamento, naming, exceções

**Proposta — `/speckit.discuss`**:
- Lê a spec e identifica decisões de implementação com múltiplas abordagens válidas
- Apresenta gray areas categorizadas por tipo de feature
- Para cada área selecionada, pergunta até o usuário estar satisfeito
- Gera `context.md` na feature dir, que o `plan` lê automaticamente
- O researcher lê o context ("user quer card layout" → pesquisa component libraries)
- O planner lê o context ("infinite scroll decidido" → plan inclui scroll handling)

**Artefatos**:
- `context.md` — decisões de implementação capturadas antes do planning

**Impacto**: Médio-alto. Reduz retrabalho por expectativa desalinhada.

---

### Gap 3: Codebase Mapping para Brownfield

**Origem**: GSD (`map-codebase`)

**Problema**: O SpecKit assume greenfield. Quando se adiciona uma feature num projeto existente, o `plan` não conhece o código — não sabe que patterns existem, que utils estão disponíveis, que convenções seguir.

**Como o GSD resolve**: O `map-codebase` spawna agents paralelos para analisar: stack, arquitetura, convenções e concerns. O resultado alimenta todo o workflow subsequente.

**Proposta — `/speckit.map`**:
- Spawna 2-3 Agent subagents em paralelo:
  - **Stack agent**: detecta linguagens, frameworks, dependências, versões
  - **Architecture agent**: identifica patterns (MVC, DDD, etc.), módulos, boundaries
  - **Conventions agent**: detecta naming, formatação, padrões de teste, estrutura de diretórios
- Consolida em `codebase-context.md` no root do `.specify/`
- O `plan` e `tasks` leem automaticamente e reusam patterns/utils existentes
- Inclui seção de "reuse candidates" — funções e componentes existentes que podem ser reaproveitados

**Artefatos**:
- `.specify/codebase-context.md` — snapshot do codebase para orientar planning

**Impacto**: Alto. Essencial para qualquer projeto brownfield. O madruga.ai é brownfield (portal Astro + LikeC4 + scripts Python).

---

### Gap 4: Research com Subagents Paralelos

**Origem**: GSD (stage de Research no `plan-phase`)

**Problema**: A Phase 0 (Research) do `plan` roda tudo sequencial no mesmo contexto. Pesquisa de stack, patterns, pitfalls e libs acontece em série, consumindo contexto do planner.

**Como o GSD resolve**: 4 researchers paralelos, cada um com foco diferente (stack, features, architecture, pitfalls). Orchestrator thin coleta e consolida.

**Proposta — melhorar `/speckit.plan` Phase 0**:
- Na Phase 0, spawnar 2-4 Agent subagents em paralelo:
  - **Stack researcher**: best practices para a stack escolhida
  - **Pattern researcher**: patterns similares em projetos open source
  - **Pitfall researcher**: problemas conhecidos, breaking changes, gotchas
  - **Lib researcher**: bibliotecas e APIs relevantes (usando Context7 MCP)
- Consolidar findings no `research.md` com formato estruturado
- Cada researcher retorna: decisão, racional, alternativas consideradas

**Artefatos**:
- `research.md` aprimorado com research paralelo e mais profundo

**Impacto**: Médio. Melhora qualidade do research e reduz tempo total.

---

### Gap 5: Verify/Review Post-Implementation

**Origem**: BMAD (`bmad-qa-generate-e2e-tests`, `bmad-code-review`, `bmad-retrospective`) + GSD (`verify-work`, `review`)

**Problema**: O SpecKit termina no `implement`. Não existe verificação se: o código compila, testes passam, a implementação cobre a spec, tasks foram realmente implementadas (vs marcadas [X] sem código).

**Como BMAD e GSD resolvem**:
- BMAD: QA agent gera e2e tests, code review agent revisa código, retrospective analisa o que funcionou/falhou
- GSD: `verify-work` checa o codebase contra goals da fase, `review` faz code review completo

**Proposta — `/speckit.verify`**:
- Roda testes existentes e reporta resultado
- Compara implementação vs `spec.md`:
  - Cada functional requirement tem código correspondente?
  - Success criteria são verificáveis no código?
- Compara implementação vs `tasks.md`:
  - Tasks marcadas [X] têm código real? (detecta phantom completions)
  - Existem arquivos criados não previstos nas tasks?
- Gera relatório de aderência com score percentual
- Lista gaps encontrados com recomendação de ação

**Artefatos**:
- `verify-report.md` — relatório de aderência spec ↔ implementação

**Impacto**: Alto. Fecha o loop de qualidade que hoje fica aberto.

---

### Gap 6: State/Memory entre Sessões

**Origem**: GSD (`STATE.md`, `threads/`, `seeds/`)

**Problema**: O SpecKit não mantém estado entre sessões de Claude. Se a implementação leva 3 sessões, cada vez que volta precisa re-explicar: onde parou, que decisões tomou, que problemas encontrou.

**Como o GSD resolve**:
- `STATE.md`: posição atual, decisões, blockers — memória entre sessões
- `threads/`: contexto persistente para trabalho cross-session
- `seeds/`: ideias forward-looking que surgem no momento certo

**Proposta — `/speckit.checkpoint`**:
- Executado automaticamente no final de cada sessão de `implement` (ou manualmente)
- Atualiza `STATE.md` na feature dir com:
  - Tasks completadas nesta sessão
  - Decisões de implementação tomadas (e por quê)
  - Problemas encontrados e como foram resolvidos
  - Próximos passos para a sessão seguinte
  - Arquivos tocados nesta sessão
- No início do próximo `implement`, lê `STATE.md` automaticamente para retomar contexto

**Artefatos**:
- `STATE.md` — memória de sessão por feature

**Impacto**: Médio-alto. Essencial para features que levam múltiplas sessões.

---

## Priorização

| Prioridade | Incremento | Comando | Esforço | Impacto |
|---|---|---|---|---|
| **P1** | Context Rot (wave execution) | `/speckit.execute-wave` | Alto | Alto |
| **P1** | Codebase Mapping (brownfield) | `/speckit.map` | Médio | Alto |
| **P1** | Verify post-implementation | `/speckit.verify` | Médio | Alto |
| **P2** | State/Memory entre sessões | `/speckit.checkpoint` | Baixo | Médio-alto |
| **P2** | Discuss/Context phase | `/speckit.discuss` | Médio | Médio-alto |
| **P3** | Research paralelo | Melhoria no `/speckit.plan` | Baixo | Médio |

---

## Diagrama do Workflow Incrementado

```
                        SpecKit Atual                    Incrementos Propostos
                        ─────────────                    ─────────────────────

                    ┌─────────────────┐
                    │   constitution   │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │     specify      │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐         ┌─────────────────┐
                    │     clarify      │         │  speckit.map    │ ◄── P1: brownfield
                    └────────┬────────┘         │  (codebase)     │     context
                             │                  └────────┬────────┘
                             │                           │
                             │         ┌─────────────────┐
                             │         │ speckit.discuss  │ ◄── P2: preferências
                             │         │ (gray areas)     │     de implementação
                             │         └────────┬────────┘
                             │                  │
                    ┌────────▼──────────────────▼┐
                    │          plan               │ ◄── P3: research paralelo
                    │  (Phase 0 com subagents)    │     com subagents
                    └────────┬───────────────────┘
                             │
                    ┌────────▼────────┐
                    │      tasks       │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │     analyze      │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐         ┌─────────────────┐
                    │    implement     │────────►│  checkpoint     │ ◄── P2: state entre
                    │  (ou execute-    │◄────────│  (STATE.md)     │     sessões
                    │   wave P1)       │         └─────────────────┘
                    └────────┬────────┘
                             │
                             │                  ┌─────────────────┐
                             └─────────────────►│  speckit.verify  │ ◄── P1: fecha loop
                                                │  (aderência)     │     de qualidade
                                                └────────┬────────┘
                                                         │
                                                ┌────────▼────────┐
                                                │  taskstoissues   │
                                                └─────────────────┘
```

---

## Referências

- **SpecKit**: https://github.com/github/spec-kit (v0.4.3)
- **BMAD**: https://github.com/bmad-code-org/BMAD-METHOD (V6)
- **GSD**: https://github.com/gsd-build/get-shit-done (latest)
- **SpecKit Extensions**: https://github.com/github/spec-kit/blob/main/extensions/catalog.community.json
- **GSD Architecture**: https://github.com/gsd-build/get-shit-done/blob/main/docs/ARCHITECTURE.md
