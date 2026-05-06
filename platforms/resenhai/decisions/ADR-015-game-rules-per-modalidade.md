---
title: "ADR-015: Game rules per modalidade — client-side + débito de schema single-set (retroativo)"
status: accepted
date: 2026-05-05
decision: >
  Centralizar regras de placar por modalidade (futevôlei, beach-tennis, beach-volei) em
  `lib/game-rules.ts` com validação client-side via `validateGameScore`. Reconhecer débito:
  schema atual de `jogos` é single-set integer (`placar_dupla1/placar_dupla2`); beach-volei
  declara `numberOfSets: 3` mas roda como 1-set efetivo até epic-006-multi-set-scoring.
alternatives: >
  Regras no DB (CHECK/trigger); regras por campeonato (config livre por owner)
rationale: >
  Decisão tomada em fev/2025 (migration `20250204000000_add_modalidade_to_campeonatos.sql` +
  `lib/game-rules.ts`); ADR retroativo formaliza débito de schema multi-set para evitar
  surpresas em features novas (telas de placar, exportação, integrações).
---
# ADR-015: Game rules per modalidade — client-side + débito de schema single-set (retroativo)

## Status

Accepted (retroativo — 2026-05-05). Decisão em produção desde fev/2025
(migration `20250204000000_add_modalidade_to_campeonatos.sql` +
[`lib/game-rules.ts`](../../resenhai-expo/lib/game-rules.ts)). Conecta com
[domain-model.md BC 3](../../engineering/domain-model/) e
[planning/roadmap.md → epic-006-multi-set-scoring](../../planning/roadmap/).

## Context

ResenhAI suporta 3 modalidades de areia com regras de placar **distintas**:

| Modalidade | winningScore | allowDraw | minScoreDifference | numberOfSets |
|------------|--------------|-----------|--------------------|--------------|
| futevôlei | 18 | false | 2 | 1 |
| beach-tennis | 21 | false | 2 | 1 |
| beach-volei | 21 | false | 2 | **3 (best-of-3)** |

A solução já em produção (ver [`lib/game-rules.ts:53-75`](../../resenhai-expo/lib/game-rules.ts#L53-L75))
centraliza as regras em um record `GAME_RULES` consultado via `getGameRules(modality)` +
validação via `validateGameScore(modality, score1, score2)`. A modalidade é guardada em
`campeonatos.modalidade` (ENUM `modalidade_esporte`), não em `jogos` — ou seja, todo jogo de um
campeonato herda a regra do campeonato.

**Débito reconhecido**: schema de `jogos` tem só `placar_dupla1 integer` + `placar_dupla2 integer`
(ver migration `20250101000000_initial_schema.sql:660-661`). Não há tabela de sets nem colunas para
placar de set 1/2/3. Beach-volei roda hoje como **1-set efetivo** — o usuário registra apenas o
placar agregado, não os 3 sets. Isso é **silenciosamente errado** mas funciona porque a validação
de `numberOfSets: 3` não é exercida em runtime (o frontend só valida `winningScore`,
`minScoreDifference`, `allowDraw`).

Sem ADR formal, esse débito fica invisível: alguém pode importar o `GAME_RULES` para uma feature
nova (export de planilha, integração com torneios oficiais) e descobrir que `numberOfSets: 3` não
tem suporte no backend.

## Decision

1. **Manter regras em `lib/game-rules.ts`** (client-side) como fonte canônica até épico-006.
   Justificativa: modalidades são poucas e estáveis (3 esportes); CHECK constraint no DB seria
   redundante.
2. **Validação obrigatória client-side** via `validateGameScore` antes de qualquer `INSERT` em `jogos`.
3. **Documentar `numberOfSets: 3` como aspiracional** para beach-volei até épico-006:
   - Hoje o campo existe em `GAME_RULES` mas não é exercido (frontend ignora).
   - Beach-volei é registrado como 1 set agregado.
   - Telas devem deixar isso explícito (placeholder "placar agregado por enquanto").
4. **Roadmap entry** — `epic-006-multi-set-scoring` cobre:
   - Nova tabela `jogo_sets (jogo_id, set_index, placar_dupla1, placar_dupla2)` ou colunas
     adicionais em `jogos`.
   - UI de N sets baseada em `GAME_RULES[modality].numberOfSets`.
   - Migração de dados existentes (1 set legado).
   - Trigger de stats atualizado para considerar sets.
5. **Lock de modalidade**: após primeiro Jogo registrado em um campeonato, `modalidade` é imutável
   (já comportamento atual; reforçar com CHECK ou app-level guard).

## Alternatives Considered

### Alternative A: Regras client-side em `lib/game-rules.ts` (escolhido — retroativo)
- **Pros:** zero round-trip; mensagens de erro instantâneas e localizáveis; fácil testar; fácil
  evoluir (acrescentar nova modalidade é 1 entry no record).
- **Cons:** dev mal-intencionado pode bypassar via SQL direto; impossível enforcer multi-set sem
  schema; não é validado em backups/migrações antigas.
- **Fit:** alta enquanto número de modalidades é pequeno.

### Alternative B: Regras no DB (CHECK + trigger)
- **Pros:** enforcement em qualquer caminho de escrita (SQL direto, edge function, app); fonte
  única; impossível bypassar.
- **Cons:** mensagens de erro genéricas; mudar regra exige migration; testes mais lentos; mais
  complexo evoluir.
- **Why rejected:** custo de manutenção de CHECK que muda a cada nova modalidade não compensa o
  ganho de enforcement (já temos RLS para o que importa de segurança).

### Alternative C: Regras por campeonato (config livre por owner)
- **Pros:** owner do grupo customiza ("nosso futevôlei é até 15"); flexibilidade máxima.
- **Cons:** explode complexidade (UI de config, validação por config, suporte); nicho. UX pior
  para o caso comum.
- **Why rejected:** YAGNI — 3 modalidades padrão cobrem 99% dos casos.

### Alternative D: Mover `modalidade` para `jogos` (não em `campeonatos`)
- **Pros:** flexibilidade de jogos avulsos misturarem modalidades.
- **Cons:** ranking/stats por campeonato perde sentido (campeonato é a unidade de ranking, ter
  modalidade ali simplifica todas as queries).
- **Why rejected:** ranking faz sentido só dentro de uma modalidade; mantê-la em campeonatos
  reflete o domínio.

## Consequences

### Positive
- Validação client-side rápida e localizável.
- Adicionar modalidade é trivial (1 entry em `GAME_RULES`).
- Schema atual é simples e reaproveita stats existentes.

### Negative
- **Beach-volei é silenciosamente single-set**: até épico-006, registros de beach-volei perdem
  granularidade de sets. Mitigação: este ADR + roadmap entry visível.
- **Risco de drift `GAME_RULES` ↔ schema**: se `numberOfSets` virar `5` para outra modalidade
  futura sem épico de schema, débito cresce.
- **Validação só client-side**: SQL direto pode inserir placar inválido. Mitigação aceitável
  porque admin user é único caso e RLS já restringe quem escreve.

### Risks
- **Risco**: novo dev importa `GAME_RULES.beach-volei.numberOfSets` para feature de export e
  gera dado fantasma. **Mitigação**: comentário em `lib/game-rules.ts` + este ADR.
- **Risco**: campeonato beach-volei profissional adotado externamente expõe a mentira.
  **Mitigação**: priorizar épico-006 antes de tornar o app um destino oficial.
- **Risco**: regras oficiais de uma modalidade mudam (ex: ITF muda beach-tennis para 24).
  **Mitigação**: 1 PR em `lib/game-rules.ts` cobre.

## References

- [`lib/game-rules.ts:53-75`](../../resenhai-expo/lib/game-rules.ts#L53-L75) — `GAME_RULES` record
- [`lib/game-rules.ts`](../../resenhai-expo/lib/game-rules.ts) — `getGameRules`, `validateGameScore`
- `supabase/migrations/20250204000000_add_modalidade_to_campeonatos.sql` — ENUM `modalidade_esporte`
- `supabase/migrations/20250101000000_initial_schema.sql` (linhas 660-661) — schema single-set de `jogos`
- [planning/roadmap.md → epic-006-multi-set-scoring](../../planning/roadmap/) — débito assumido
