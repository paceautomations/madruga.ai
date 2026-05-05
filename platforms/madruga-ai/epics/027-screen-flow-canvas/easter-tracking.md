# Easter Tracking — madruga-ai 027-screen-flow-canvas

Started: 2026-05-05T20:41:00Z

## Melhoria — madruga.ai

- pair-program skill guardrail "STOP on main" assume worktree externo; em self-ref (`madruga-ai`) commits direto em `main` são o padrão. Ver `feat(resenhai): complete L1 pipeline` (b5e1b0b) e demais commits recentes. **Sugestão**: skill consultar `platform.yaml.repo.name` — se igual ao próprio repo, branch=main é healthy.
- epic-context com Start via portal/API NÃO cria branch em self-ref (gap conhecido — ver decisions/ADR sobre branch isolation removido em epic 024). Aceitável para madruga-ai mas vale documentar explicitamente.
- **speckit.clarify dispatch contradição**: skill instructions descrevem "Sequential questioning loop (interactive): Present EXACTLY ONE question at a time. After the user answers..." (~4KB de prosa), mas o banner "Autonomous Dispatch Mode" no topo força "Do NOT ask questions or wait for approval. Skip Step 1 questions". Resultado: ~4KB de tokens desperdiçados em prompt que descreve fluxo impossível em `claude -p`. Sugestão: passar flag `--mode=autonomous` ao dispatcher e o `compose_task_prompt` strip seções `interactive questioning loop` quando autônomo.
- **append-system-prompt redundante com system-prompt**: o dispatched prompt traz `--system-prompt` (cabeçalho com Conventions + Autonomous overrides + Pipeline Contract + skill body) E `--append-system-prompt` repetindo guardrails ("MANDATORY: Save all files to..."). Os mandatos já existem no system-prompt. Possível consolidação reduz parsing dupla e ~200B/dispatch.
- **phase-2 prompt 90KB — pipeline-dag-knowledge.md inflado**: phase-2 incluiu `.claude/knowledge/pipeline-dag-knowledge.md` (14.9KB) inteiro porque uma task referencia. Esse arquivo cresce ao longo do tempo (atual 14.9KB). Sugestão: `compose_task_prompt` deveria fatiar `pipeline-dag-knowledge.md` por seção quando uma task individual cita só uma parte (ex: só "L1" ou "L2 cycle"), em vez de incluir o arquivo inteiro. Padrão similar para `blueprint.md` em fases que criam código novo. Phase-1 (sem essa inclusão) ficou em 63KB; phase-2 saltou para 90KB. **80KB threshold da skill foi cruzado**.
- **phase-2 completou 6/8 tasks** em 21m15s e dispatcher avançou para phase-3 sem retentar T018/T019 (ou que sejam). Loss-of-information silencioso — não ficou claro nos logs por que 2 tasks ficaram pra trás (max_turns esgotou? task tinha bug? auto-fail por contrato?). Sugestão: `phase_completed` log deveria incluir `pending_task_ids` para auditoria; alternativa, `mark_phase_done` poderia agendar uma "tail-pass" só pras pendentes em vez de descartar.
- **phase-3 prompt 114KB**: cruzou 80KB. Spec inteiro (45KB) + plan (24KB) + data_model (16KB) + contract (9KB) + analyze_report (9KB). Spec gigante porque cobre 8 user stories em escopo. Sugestão: para fases User-Story-N, fatiar spec.md por user story (`## User Story N` headers) e incluir só a US ativa + visão geral, em vez do spec inteiro. 12 tasks × 114KB = ~1.4MB de contexto enviado por iteração — alvo de otimização clara.

## Melhoria — madruga-ai

(a coletar conforme observação dos nodes L2)

## Incidents críticos

(nenhum até agora)

## Síntese

(preenchido no último tick)
