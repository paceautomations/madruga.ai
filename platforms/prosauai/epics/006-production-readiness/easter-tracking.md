# Easter Tracking — prosauai 006-production-readiness

Started: 2026-04-12

## Melhoria — madruga.ai
<!-- bullets: eficiencia de tokens/contexto, dispatch, DB, skills, docs -->
- **Branch drift em todos os dispatches**: `claude -p` mudou para main em specify, clarify e plan (3/3 nodes). Executor reverteu automaticamente a cada vez. Pattern sistematico — nao e um skill especifico, algo no dispatch ou no `claude -p` esta causando checkout para main ao finalizar. Investigar `dag_executor.py` post-dispatch cleanup.
- **Plan: 3.26M tokens combinados ($3.13, 43 turns)**: Deep dive revelou que o custo NAO vem de prompt inflado (prompt inicial ~76KB = 19K tokens). Vem de: (a) Opus output $2.22 (71% do custo Opus — 29.6K tokens × $75/M); (b) 43 turns acumulando cache reads (2.06M cache_read); (c) 7 web searches via Haiku ($0.58). Principal alavanca: pre-injetar docs no prompt (reduzir turns de 43 para ~20, economia ~$0.25 em cache). `MADRUGA_SCOPED_CONTEXT` nao se aplica — so funciona para `compose_task_prompt` (implement), nao `compose_skill_prompt` (plan).

## Melhoria — prosauai
<!-- bullets: codigo, arquitetura, testes da plataforma -->

## Incidents criticos

## Sintese (2026-04-12)

### Metricas

| Metrica | Valor |
|---------|-------|
| Duracao total (wall) | 111min (21:42 → 23:33 UTC) |
| Nodes executados | 20 (6 design + 10 implement + 4 post-implement) |
| Tasks implementadas | 34 (10 phases) |
| Custo total | **$35.63** |
| Incidents criticos | **0** |
| Fixes commitados | **0** |
| Testes adicionados | **0** (pelo pair-program) |
| Falhas de pipeline | **0** |

### Breakdown de custo por fase

| Fase | Nodes | Custo | % do total |
|------|-------|-------|------------|
| Design (specify→analyze) | 5 | $6.87 | 19% |
| Implement (10 phases) | 10 | $13.96 | 39% |
| Post-implement (analyze-post→roadmap) | 5 | $14.81 | 42% |

### Top 3 nodes por custo

1. **judge** — $4.81 (13.5%) — 4 personas Opus em paralelo + judge pass
2. **qa** — $4.19 (11.8%) — static analysis + code review + testes
3. **plan** — $3.13 (8.8%) — 43 turns, research + design artifacts

### Melhorias madruga.ai (consolidado)

1. **Branch drift sistematico**: `claude -p` muda para main ao finalizar em TODOS os dispatches. O executor reverte, mas e overhead + risco. Causa raiz nao investigada — provavel comportamento do `claude -p` ao fechar sessao (volta para branch default). Impacto: baixo (guarda funciona), mas ruidoso nos logs.

2. **`compose_skill_prompt` nao tem scoped context**: diferente do `compose_task_prompt` (implement), os nodes de design (plan, tasks, analyze) usam `compose_skill_prompt` que nao tem `MADRUGA_SCOPED_CONTEXT` nem `MADRUGA_CACHE_ORDERED`. O agente le manualmente o que precisa, causando 43 turns no plan. Alavanca: pre-injetar docs relevantes no prompt reduz turns e melhora cache hit. Economia estimada: ~$0.25/epic no plan (modesta).

3. **Post-implement e 42% do custo**: judge ($4.81) + qa ($4.19) + analyze-post ($2.62) + reconcile ($2.40) = $14.02. E mais caro que o implement inteiro ($13.96). Investigar se judge e qa tem overlap de analise — ambos leem todo o codigo, talvez o judge report possa alimentar o qa para evitar releitura.

### Melhorias prosauai

Nenhuma melhoria de plataforma observada nesta run. O epic foi inteiramente de infra (schema isolation, migration runner, Docker compose, log persistence) — nao houve oportunidade de avaliar arquitetura de aplicacao ou gaps de teste em runtime.

### Veredicto

**Run impecavel** — zero falhas, zero incidents, zero intervencoes manuais. Pipeline L2 completa de 20 nodes em 111 minutos com custo de $35.63. A melhor run observada ate agora.
