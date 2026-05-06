---
title: "ADR-014: Convidado como pseudo-user global (retroativo)"
status: accepted
date: 2026-05-05
decision: >
  Modelar jogador avulso ("Convidado") como **pseudo-user global** com UUID fixo
  `00000000-0000-0000-0000-000000000001` (`users.user_type='guest'`), auto-injetado em todo grupo
  via trigger e excluído de rankings. Permite ocupar múltiplas posições no mesmo Jogo por design,
  formalizando uma exceção ao invariante "4 jogadores distintos".
alternatives: >
  Campo `is_guest` por jogador-no-grupo; tabela separada de avulsos; sem suporte a avulsos
rationale: >
  Decisão tomada em fev/2025 (migration `20250221000000_add_guest_player_system.sql`); documentada
  retroativamente porque (a) cria exceção ao invariante de Jogo, (b) altera ranking, (c) acopla
  trigger automático a criação de grupo.
---
# ADR-014: Convidado como pseudo-user global (retroativo)

## Status

Accepted (retroativo — 2026-05-05). Decisão em produção desde fev/2025
(migration `20250221000000_add_guest_player_system.sql`). Conecta com
[domain-model.md BC 1 + BC 3](../../engineering/domain-model/).

## Context

Times de areia constantemente jogam com **avulsos** — alguém que apareceu uma vez para completar
quadra mas não é membro permanente. Cadastrar formalmente cada avulso (com OTP, perfil, foto) é
fricção desproporcional ao valor: o avulso provavelmente não volta, e poluir o ranking com
jogadores com 1 jogo distorce as métricas (winrate, química).

A solução já em produção (ver [`lib/guest-player.ts`](../../resenhai-expo/lib/guest-player.ts) +
migration `20250221000000_add_guest_player_system.sql`) usa um **único registro pseudo-user**
com UUID fixo `00000000-0000-0000-0000-000000000001` que:

1. Existe globalmente (não por grupo).
2. É auto-vinculado a todo grupo recém-criado via trigger `add_guest_to_new_group()`.
3. **Não aparece** no ranking, lista de membros, ou seletor de admins.
4. **Aparece** apenas no seletor de jogadores ao registrar/editar Jogo.
5. Pode ser **selecionado em múltiplas posições do mesmo Jogo** (ver
   [`lib/guest-player.ts:166-176`](../../resenhai-expo/lib/guest-player.ts#L166-L176) — `canSelectPlayer`
   retorna `true` direto se `isGuestUser(userId)`, sem checar duplicatas).
6. Para FairPlay (cálculo de pontos por ELO), recebe **ELO mediano** via função SQL
   `get_guest_median_position()` — posição `(N+1)/2` do ranking do grupo.

Sem ADR formal, isso fica invisível: o domain-model.md tem invariante #1 do Jogo
("4 jogadores distintos") que **contradiz frontalmente** o comportamento do código. Quem confiar
nesse invariante para escrever testes ou novas features vai falhar.

## Decision

Formalizar o **Convidado como Aggregate especial** dentro do BC `Identidade & Acesso`:

1. **Identidade**: pseudo-user `Jogador { user_id = GUEST_USER_ID, user_type='guest', apelido='convidado' }`.
   UUID fixo permite referência cross-system sem lookup.
2. **Lifecycle**: criado uma única vez no seed; protegido por triggers contra `DELETE`/`UPDATE`
   destrutivos.
3. **Auto-injeção em grupos**: trigger `add_guest_to_new_group()` insere
   `participantes_grupo (grupo_id=NEW.grupo_id, user_id=GUEST_USER_ID)` em todo `INSERT` em `grupos`.
4. **Filtragem em queries**: hooks `useGroupMembers`, `useRanking`, `useChampionshipParticipants`
   filtram por `user_type != 'guest'` por default; passam parâmetro explícito (ex:
   `includeGuest: true`) só onde o seletor de jogador precisa.
5. **Exceção ao invariante de Jogo**: o invariante "4 jogadores distintos" do `Jogo` em
   domain-model.md ganha cláusula formal: *"4 jogadores distintos, **exceto Convidado**, que pode
   ocupar de 1 a 4 posições no mesmo Jogo"*.
6. **FairPlay**: Convidado contribui com ELO mediano fixo no cálculo, evitando distorção do ranking.

## Alternatives Considered

### Alternative A: Pseudo-user global com UUID fixo (escolhido — retroativo)
- **Pros:** zero novas tabelas; reaproveita FK de `jogos.dupla{1,2}_jogador{1,2}_id`; UI única no
  seletor (sem case especial estrutural).
- **Cons:** quebra invariante DDD natural (Jogador como entidade única); UUID hard-coded no código
  + DB; trigger automático em criação de grupo é magia escondida.
- **Fit:** escolhida pela simplicidade de implementação dado que era feature pequena.

### Alternative B: Campo `is_guest` por `participantes_grupo` (jogador local ao grupo)
- **Pros:** sem mágica global; cada grupo tem seu Convidado próprio; sem trigger.
- **Cons:** explosão de UUIDs Convidado (1 por grupo); FairPlay teria que calcular ELO mediano do
  grupo dinamicamente em cada Jogo (já é, mas ficaria mais frágil); query mais complexa para
  filtrar avulsos do ranking global.
- **Why rejected:** complexidade adicional sem ganho funcional claro; UUID único permite "Convidado"
  ser conceito *do produto* não *do grupo*.

### Alternative C: Tabela `avulsos` separada
- **Pros:** clean DDD — Avulso é entidade distinta de Jogador.
- **Cons:** `jogos.dupla*_jogador*_id` precisaria ou ser polimórfico (dois FKs nullable e CHECK)
  ou migrar dados. Refactor amplo de queries.
- **Why rejected:** custo de migração desproporcional ao benefício; pseudo-user é "barato" e
  funciona.

### Alternative D: Não suportar avulsos
- **Pros:** modelo limpo.
- **Cons:** UX hostil — toda quadra incompleta exige cadastro completo do avulso.
- **Why rejected:** conflita com casual-first do produto.

## Consequences

### Positive
- UX fluida — seleção de avulso em 1 clique.
- Ranking não polui com jogadores de 1 jogo.
- FairPlay continua justo (ELO mediano evita inflar/deflar pontos).
- Reaproveitamento total do schema de Jogo existente.

### Negative
- **Invariante #1 de `Jogo` é parcial**: testes que assumem "4 jogadores distintos" falham
  silenciosamente quando Convidado entra; documentação tem que explicitar a exceção (este ADR +
  edit em domain-model.md).
- **Trigger mágico**: dev pode estranhar `participantes_grupo` ter row de Convidado em todo grupo
  novo. Mitigação: comentário no trigger + nota em domain-model.md.
- **UUID hard-coded**: refatorar para outro identificador (ex: enum) é caro. Mitigação: já está
  encapsulado em `lib/guest-player.ts:GUEST_USER_ID`.

### Risks
- **Risco**: Convidado deletado por engano via super_admin/SQL direto. **Mitigação**: trigger
  protege contra `DELETE`/`UPDATE` destrutivo (em `20250221000000`).
- **Risco**: novo dev escreve invariante "4 jogadores distintos" em teste/feature. **Mitigação**:
  domain-model.md atualizado com a exceção; este ADR como fonte canônica.
- **Risco**: alguém remove o filtro `user_type != 'guest'` em ranking. **Mitigação**: hook
  `useRanking` filtra por default (passar `includeGuest: true` é opt-in).

## References

- [`lib/guest-player.ts:161-187`](../../resenhai-expo/lib/guest-player.ts#L161-L187) — `canSelectPlayer`, `countGuestsInGame`
- `supabase/migrations/20250221000000_add_guest_player_system.sql` — schema + triggers + função `get_guest_median_position()`
- [`hooks/useGroupMembers.ts`](../../resenhai-expo/hooks/useGroupMembers.ts) — parâmetro `includeGuest`
- [`hooks/useRanking.ts`](../../resenhai-expo/hooks/useRanking.ts) — filtra Convidado por default
- [domain-model.md — BC 3 Operação de Jogo](../../engineering/domain-model/) — invariante atualizado
