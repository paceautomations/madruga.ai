# Easter Tracking — madruga-ai 027-screen-flow-canvas

Started: 2026-05-05T20:41:00Z

## Melhoria — madruga.ai

- pair-program skill guardrail "STOP on main" assume worktree externo; em self-ref (`madruga-ai`) commits direto em `main` são o padrão. Ver `feat(resenhai): complete L1 pipeline` (b5e1b0b) e demais commits recentes. **Sugestão**: skill consultar `platform.yaml.repo.name` — se igual ao próprio repo, branch=main é healthy.
- epic-context com Start via portal/API NÃO cria branch em self-ref (gap conhecido — ver decisions/ADR sobre branch isolation removido em epic 024). Aceitável para madruga-ai mas vale documentar explicitamente.
- **speckit.clarify dispatch contradição**: skill instructions descrevem "Sequential questioning loop (interactive): Present EXACTLY ONE question at a time. After the user answers..." (~4KB de prosa), mas o banner "Autonomous Dispatch Mode" no topo força "Do NOT ask questions or wait for approval. Skip Step 1 questions". Resultado: ~4KB de tokens desperdiçados em prompt que descreve fluxo impossível em `claude -p`. Sugestão: passar flag `--mode=autonomous` ao dispatcher e o `compose_task_prompt` strip seções `interactive questioning loop` quando autônomo.
- **append-system-prompt redundante com system-prompt**: o dispatched prompt traz `--system-prompt` (cabeçalho com Conventions + Autonomous overrides + Pipeline Contract + skill body) E `--append-system-prompt` repetindo guardrails ("MANDATORY: Save all files to..."). Os mandatos já existem no system-prompt. Possível consolidação reduz parsing dupla e ~200B/dispatch.

## Melhoria — madruga-ai

(a coletar conforme observação dos nodes L2)

## Incidents críticos

(nenhum até agora)

## Síntese

(preenchido no último tick)
