---
id: 015
title: "Subagent Judge + Decision Classifier"
status: shipped
delivered_at: 2026-04-01
appetite: 2w
priority: 2
updated: 2026-04-01
---
# Subagent Judge + Decision Classifier

## Problem

Specs e artefatos gerados pelo pipeline nao passam por review multi-perspectiva antes de serem aprovados. Nao ha mecanismo automatico para classificar decisoes como 1-way-door vs 2-way-door, nem para detectar problemas antes que cheguem ao human gate.

## Appetite

**2w** — Paralelo com 014. Agent tool ja provado no pipeline. Risco em calibracao de personas/judge.

## Dependencies

- Depends on: 013 (dispatch de subagents via executor)
- Blocks: nenhum



## Resumo do Epic

Implementar um sistema de review multi-perspectiva extensível (**tech-reviewers**) com 4 personas paralelas + 1 Judge pass, integrado ao pipeline como substituto do verify (L2) e do Tier 3 (L1). Inclui Decision Classifier independente com score de risco para escalação de decisões 1-way-door via Telegram.

## Captured Decisions

| # | Area | Decisão | Referência Arquitetural |
|---|------|---------|------------------------|
| 1 | Escopo | 3 componentes: SubagentJudge (tech-reviewers), DecisionClassifier, StressTester (como 4a persona) | ADR-019 / domain-model Intelligence |
| 2 | Arquitetura do Judge | Sistema de **times de revisores extensível**. Time inicial: `engineering` (Arch Reviewer, Bug Hunter, Simplifier, Stress Tester). Futuramente: `product` (PM, Designer), etc. | ADR-019 (extensão) |
| 3 | Implementação | **Knowledge files + YAML config** — zero Python runtime custom. Config de times em YAML, prompts das personas em arquivos separados, lógica do Judge em knowledge file | ADR-019 ("zero runtime custom") |
| 4 | Posição no DAG L2 | Judge **substitui o verify**. Posição: após analyze-post, antes de qa. Analyze (pre+post) foca em **aderência** (spec/tasks/arquitetura). Judge foca em **qualidade funcional** (vai funcionar bem?) | pipeline-contract-base / ADR-019 |
| 5 | Posição no DAG L1 | Judge **substitui Tier 3** (1-way-door gates). Sistema unificado L1+L2 — um único mecanismo de review | pipeline-contract-base Step 3 |
| 6 | Decision Classifier | **Independente** do Judge. São sistemas separados. Classifier usa score de risco (risco × reversibilidade) com threshold para 1-way-door. Apenas decisões críticas vão para Telegram — decisões pequenas são automáticas | ADR-013 |
| 7 | Detecção 1-way-door | **Inline** (patterns/heurística no contrato) + Judge como **safety net** (flagga 1-way-doors que escaparam como BLOCKER) | ADR-013 |
| 8 | Notificação Telegram | **Estender telegram_adapter existente** para suportar notificação de decisões 1-way-door. Reutiliza inline keyboard approve/reject | ADR-018 |
| 9 | Report | Judge gera report com **score numérico** (100 - blockers×20 - warnings×5 - nits×1). Score permite threshold para auto-escalate | Novo |
| 10 | L1 vs L2 | L1 continua no terminal Claude Code. Automação (daemon/Telegram) é apenas L2 | Escopo |
| 11 | Nome do time | `tech-reviewers` (não "judge" — o judge é o filtro, o time são os revisores) | Novo |

## Resolved Gray Areas

### 1. Separação de responsabilidades: Analyze vs Judge (tech-reviewers)

**Pergunta:** Com o Judge substituindo o verify, como se diferencia do analyze que já existe?

**Resposta:** São complementares com focos distintos:
- **Analyze** (pre + post implement) → **Aderência**: spec está consistente com plan? Tasks cobrem a spec? Código implementa as tasks? Checa conformidade documental.
- **Judge / tech-reviewers** (substitui verify) → **Qualidade funcional**: o que foi implementado vai funcionar bem? Tem bugs? Viola arquitetura? Está over-engineered? Aguenta stress?

**Rationale:** Analyze é checagem de conformidade (determinística). Judge é review de engenharia (qualitativo, multi-perspectiva). Não há sobreposição — um checa "fez o que disse que faria", outro checa "o que fez está bem feito".

### 2. Score de risco para Decision Classifier

**Pergunta:** Como definir o threshold para 1-way-door?

**Resposta:** Matriz score = Risco (1-5) × Reversibilidade (1=minutos, 2=horas, 3=dias, 5=impossível). Threshold ≥15 = 1-way-door → Telegram. Apenas decisões críticas escalam — decisões pequenas (score <15) são automáticas.

| Pattern | Risco | Reversibilidade | Score | Resultado |
|---------|-------|-----------------|-------|-----------|
| schema migration (add nullable) | 2 | 1 (minutos) | 2 | 2-way (auto) |
| schema migration (drop column) | 5 | 5 (impossível) | 25 | 1-way → Telegram |
| API pública (novo endpoint) | 3 | 2 (horas) | 6 | 2-way (auto) |
| API pública (remove endpoint) | 5 | 3 (dias) | 15 | 1-way → Telegram |
| rename/refactor interno | 1 | 1 (minutos) | 1 | 2-way (auto) |
| delete dados em produção | 5 | 5 (impossível) | 25 | 1-way → Telegram |
| nova dependência externa | 3 | 2 (horas) | 6 | 2-way (auto) |
| remover feature/breaking change | 4 | 3 (dias) | 12 | 2-way (auto) |
| mudar contrato de API pública | 5 | 5 (impossível) | 25 | 1-way → Telegram |

### 3. Extensibilidade de times

**Pergunta:** Como adicionar novos times no futuro?

**Resposta:** Config em YAML dedicado (`judge-config.yaml` ou seção no `platform.yaml`). Cada time define: personas, onde roda (`runs_at`), e referência ao arquivo de prompt de cada persona. Adicionar um time = adicionar entrada YAML + arquivos de prompt das personas.

Exemplo da estrutura futura:
```yaml
review_teams:
  engineering:
    name: "Tech Reviewers"
    personas:
      - id: arch-reviewer
        prompt: ".claude/knowledge/personas/arch-reviewer.md"
      - id: bug-hunter
        prompt: ".claude/knowledge/personas/bug-hunter.md"
      - id: simplifier
        prompt: ".claude/knowledge/personas/simplifier.md"
      - id: stress-tester
        prompt: ".claude/knowledge/personas/stress-tester.md"
    runs_at: [judge-l2, tier3-l1]
  # product:  # futuro
  #   personas: [pm-reviewer, designer-reviewer]
  #   runs_at: [specify, plan]
```

### 4. Fluxo completo L2 com Judge

```
epic-context → specify → clarify → plan → tasks → analyze (aderência pre)
→ implement → analyze-post (aderência post) → JUDGE/tech-reviewers (qualidade)
→ qa → reconcile → PR/merge
```

O verify é **removido** do DAG. O Judge ocupa sua posição (após analyze-post, antes de qa).

### 5. Fluxo de 1-way-door detection no L2

```
Skill L2 executando (ex: implement)
    → Decisão surge durante execução
    → Classifier inline: calcula score (risco × reversibilidade)
    → Score < 15: 2-way-door, segue automaticamente
    → Score ≥ 15: 1-way-door
        → Pausa execução
        → telegram_adapter.notify_oneway_decision(decisão, contexto, alternativas)
        → Espera approve/reject via inline keyboard
        → Continua ou ajusta

Judge (final, safety net)
    → Revisa todas as decisões tomadas durante o ciclo
    → Se encontra 1-way-door que escapou: BLOCKER
    → Escala para Telegram antes do merge
```

## Applicable Constraints

### Do Blueprint
- **Stack**: Claude Code Agent tool nativo, zero runtime Python custom para Judge (ADR-019)
- **Observabilidade**: Review consolidado persiste em `pipeline_runs` (SQLite) como JSON payload (domain-model)
- **Circuit breaker**: Se subagents falharem 5x consecutivas, circuit breaker abre (ADR-011)
- **Telegram**: Outbound HTTPS only, bot token em .env, sem porta inbound (ADR-018)

### Do Domain Model (Intelligence BC)
- Judge **sempre** executa personas em paralelo — ADR-019
- Judge filtra por 3 critérios: Accuracy, Actionability, Severity — ADR-019
- Review results são **imutáveis** após consolidação (append-only em events)
- Toda decisão 1-way-door **deve** gerar ADR automaticamente — ADR-013

### Da Constitution
- **Pragmatismo**: Simplicidade first. Zero over-engineering
- **TDD**: Testes para todos os componentes (não one-off scripts)
- **Performance-aware**: Considerar performance desde o início

## Suggested Approach

### Entregáveis

1. **YAML config de times** — `judge-config.yaml` ou seção no `platform.yaml` com definição do time `engineering` (4 personas)
2. **Prompts de personas** — 4 arquivos em `.claude/knowledge/personas/` (arch-reviewer, bug-hunter, simplifier, stress-tester)
3. **Knowledge file do Judge** — `.claude/knowledge/judge-knowledge.md` com lógica de orquestração (lançar personas paralelas, agregar findings, judge pass, gerar report com score)
4. **Knowledge file do Decision Classifier** — `.claude/knowledge/decision-classifier-knowledge.md` com tabela de scores e lógica de detecção inline
5. **Atualizar pipeline-contract-base.md** — Tier 3 referencia Judge em vez de subagent genérico. Novo gate behavior para 1-way-door com Telegram
6. **Atualizar platform.yaml** — Node `verify` → `judge` no epic_cycle. Manter `analyze` e `analyze-post` inalterados
7. **Estender telegram_adapter.py** — Novo método `notify_oneway_decision()` com inline keyboard
8. **Testes** — Testes para Decision Classifier (score calculation), telegram_adapter (novo método), YAML config parsing
9. **Skill `/madruga:verify`** — Remover ou redirecionar para judge (backwards compat)

### Ordem sugerida
1. YAML config + prompts de personas (fundação)
2. Knowledge file do Judge (orquestração)
3. Atualizar pipeline-contract-base (integração L1)
4. Atualizar platform.yaml epic_cycle (integração L2)
5. Decision Classifier knowledge + tabela de scores
6. Estender telegram_adapter (notificação 1-way-door)
7. Testes
8. Cleanup verify skill

handoff:
  from: madruga:epic-context
  to: speckit.specify
  context: "Judge (tech-reviewers) com 4 personas + Decision Classifier com score de risco. Substitui verify (L2) e Tier 3 (L1). Config em YAML extensível. 1-way-door decisions vão para Telegram. 9 entregáveis definidos."
  blockers: []
  confidence: Alta
  kill_criteria: "Se Agent tool do Claude Code mudar API de subagents paralelos de forma incompatível"
