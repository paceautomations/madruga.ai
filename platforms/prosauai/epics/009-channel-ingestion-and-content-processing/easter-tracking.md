# Easter Tracking — prosauai 009-channel-ingestion-and-content-processing

Started: 2026-04-19T20:22:04Z

## Melhoria — madruga.ai

- **Plan em epics grandes passa de 10min**. Observado no epic 009 (plan dispatch em `running` há 10m15s às 17:41, ainda produtivo — `data-model.md` 26KB, `contracts/`, `quickstart.md` 13KB). Causa provável: epic com 5 semanas de appetite + research.md 71KB + 20 seções de spec força plan a iterar por múltiplos arquivos sequencialmente num único dispatch. Heurística `>10min = critical` em `pair-program.md` foi construída para tasks hung; epics grandes geram falso-positivo. Candidatos: (a) baseline de duração por nó ajustada por tamanho do spec/research, (b) split do `speckit.plan` em sub-fases (`plan-architecture`, `plan-data-model`, `plan-contracts`, `plan-quickstart`) com dispatches sequenciais — cada um cacheável, cada um com prompt menor; ganha observabilidade granular no dashboard e reduz prompt size.
- **Overlap de conteúdo entre `data-model.md` (gerado pelo plan) e `research.md`/`pitch.md` (input)**. `research.md` já traz schemas Pydantic completos (`CanonicalInboundMessage`, `ContentBlock`, etc.) e `pitch.md` enumera as 22 decisões chave. `data-model.md` nasceu com 26KB — sem inspeção ainda, mas tamanho sugere reescrita de material existente em vez de extração. Verificar ao final se há duplicação e se o skill `speckit.plan` pode ser instruído a fazer extração/referência em vez de regeneração.

- **Prompt total implement phase-1 = 114KB (user 88KB + system 24KB)**, acima do threshold 80KB do próprio `pair-program.md` §"lente de melhorias". Composição (log `phase_prompt_composed`): plan.md 32KB + data-model.md 27KB + contracts/ 23KB + tasks slice 4KB + header 4KB + cue 64B. Ressalva: com `MADRUGA_CACHE_ORDERED=1` (default on, conforme CLAUDE.md), phases 2-19 fazem cache-hit no prefixo estável 83KB — custo real amortizado é o delta por phase (tasks slice + cue ≈ 4.5KB). A observação vale só para primeira phase dispatchada por epic. **Sugestão**: investigar se plan.md (32KB) pode nascer mais compacto — atualmente parece incluir rationale de design que só é útil para humanos, não para o implement. Se implement lê mas não aplica, é token puro desperdiçado mesmo com cache.

## Melhoria — prosauai

- **Divergência na contagem de steps do pipeline**: pitch.md §7.1 declara 12 → 14 steps (insere `content_process` + outra). Commit `c35bb6a` (18:41, phase-3 self-heal) ajusta admin schemas + retention tests para `STEP_NAMES=13`, não 14. Possibilidades: (a) plan.md consolidou dois steps em um (ex.: merge de `content_process` com algum vizinho), (b) erro de contagem aqui e divergência não intencional do pitch. Para reconcile checar: `apps/api/prosauai/conversation/step_record.py::STEP_NAMES` final vs. `pitch.md` + atualizar o que estiver correto para alinhamento. Não é blocker, mas é inconsistência entre docs de planejamento e implementação.

## Incidents críticos

(nenhum até agora)

## Síntese

(preenchida no último tick)
