---
title: "ADR-013: Phone-to-Email synthetic identifier + OTP via n8n (retroativo)"
status: accepted
date: 2026-05-05
decision: >
  Usar `{phone}@resenhai.com` como email sintético em `auth.users` para destravar Supabase Auth
  (que opera com email) com identidade real de telefone E.164. OTP de 6 dígitos é gerado por n8n
  via Admin API do Supabase e entregue via Evolution API no WhatsApp.
alternatives: >
  Supabase Phone Auth (Twilio); Magic Link de email puro (sem WhatsApp);
  passwordless custom (sem auth nativo)
rationale: >
  Decisão tomada antes do épico-002 (edge migration); documentada retroativamente porque é
  load-bearing — telefone E.164 é o PK efetivo da identidade e n8n é o único caminho de OTP hoje.
---
# ADR-013: Phone-to-Email synthetic identifier + OTP via n8n (retroativo)

## Status

Accepted (retroativo — 2026-05-05). Decisão já em produção desde o lançamento; ADR criado para
fechar gap de documentação. Conecta com [ADR-005](../ADR-005-baas-supabase/) (Supabase como BaaS),
[ADR-006](../ADR-006-workflow-orchestration-edge-functions/) (n8n → Edge Functions) e
[ADR-007](../ADR-007-whatsapp-gateway-evolution-api/) (Evolution API).

## Context

ResenhAI prioriza onboarding por **telefone** (jogadores brasileiros não querem digitar email),
mas Supabase Auth nativo usa **email** como identificador primário. Cobrar Supabase Phone Auth
(via Twilio) seria caro em escala BR; manter app sem auth nativo perderia recursos como RLS por
`auth.uid()`, sessions e refresh tokens.

A solução já em produção (ver [`services/supabase/auth.ts:39-44`](../../resenhai-expo/services/supabase/auth.ts#L39-L44),
função `phoneToEmail`) **converte telefone para um email sintético**: `5521999999999` →
`5521999999999@resenhai.com`. O usuário nunca digita ou vê esse email — é detalhe interno do schema
de `auth.users`. O OTP de 6 dígitos é gerado por **n8n** (workflows em `n8n_backend/`), que chama
Admin API do Supabase e envia via Evolution API.

Sem ADR formal, essa cola fica invisível: quem entrar no épico-002 (migrar n8n → Edge Functions)
ou refatorar auth pode acidentalmente quebrar a invariante "email derivado de telefone E.164".

## Decision

Manter a estratégia **phone-to-email** como **identidade primária do produto** até que o
épico-002 finalize, com o seguinte contrato:

1. Toda criação de usuário passa por `phoneToEmail(phone)` antes de chamar `auth.admin.createUser`.
2. `users.phone_id` é a forma canônica de telefone E.164 (sem máscara), redundante com
   `auth.users.email` por design (a redundância é a cola entre os dois mundos).
3. OTP é gerado **server-side** (Admin API), nunca client-side. Hoje em n8n; após épico-002, em
   Edge Function `auth-otp` (substitui o workflow n8n equivalente).
4. Email sintético **nunca é exibido ao usuário**. UI sempre mostra telefone formatado.
5. Migração de identidade (caso futuro com Supabase Phone Auth nativo BR) requer:
   (a) backfill de `auth.users.phone` a partir de `auth.users.email`,
   (b) remoção do prefixo `phoneToEmail` em `signIn`,
   (c) deprecação dos workflows n8n.

## Alternatives Considered

### Alternative A: Phone-to-Email synthetic + n8n OTP (escolhido — retroativo)
- **Pros:** desbloqueio imediato de Supabase Auth nativo (sessions, RLS, refresh); zero custo de SMS;
  OTP via WhatsApp tem entrega ~100% no Brasil.
- **Cons:** acoplamento forte com n8n (load-bearing); `auth.users.email` não é email real (quebra
  features de Supabase que pressupõem email válido — ex: password recovery por email).
- **Fit:** alta para a fase atual (custo zero, entrega WhatsApp); planejado migrar para Edge.

### Alternative B: Supabase Phone Auth (Twilio)
- **Pros:** padrão de fato; sem hack de email; suporte oficial em RN/Web.
- **Cons:** SMS BR custa ~R$ 0,30/envio; em escala (10k OTPs/mês) sai a ~R$ 3.000/mês; alguns
  carriers BR têm latência alta. Sem entrega WhatsApp (que é o canal preferido do público).
- **Why rejected:** custo + UX (SMS é segunda escolha vs WhatsApp para o público de areia).

### Alternative C: Magic Link de email puro
- **Pros:** zero hack; email é real; recovery flows nativos.
- **Cons:** público alvo majoritariamente não acessa email no celular durante a hora marcada;
  conversão de "abrir email no celular + clicar no link" foi mensurada baixa em piloto interno
  `[VALIDAR — número exato]`.
- **Why rejected:** entrega no WhatsApp tem conversão >70% vs <30% de email no público alvo
  `[VALIDAR — pré-pivot]`.

### Alternative D: Auth custom (sem Supabase Auth)
- **Pros:** sem hack; total controle.
- **Cons:** perde RLS por `auth.uid()` (precisaria reimplementar policies); JWT custom; refresh
  tokens; revogação. Custo de manutenção alto.
- **Why rejected:** RLS é o principal benefício de Supabase Auth; abrir mão dele dobra a
  complexidade do backend.

## Consequences

### Positive
- Onboarding em < 60s (telefone → OTP WhatsApp → app aberto).
- Zero custo de SMS.
- Conversão `link enviado → cadastro completo` alta.
- Reaproveita 100% do stack Supabase (RLS, sessions, refresh).

### Negative
- **`auth.users.email` não é email** — features de Supabase que pressupõem email válido (recovery
  via email link, magic link de email) ficam quebradas por design. Mitigação: nunca usar essas
  features; recuperação é sempre via OTP WhatsApp.
- **n8n é load-bearing**: enquanto rodar, qualquer queda de n8n bloqueia onboarding. Mitigação:
  épico-002 migra para Edge Functions.
- **Acoplamento com Evolution API**: ban/queda da Evolution bloqueia OTP. Mitigação: ADR-007
  (rotação de instâncias).
- **Migração futura cara**: trocar para Phone Auth nativo exige backfill + refactor coordenado.

### Risks
- **Risco**: Supabase muda contrato de `auth.users.email` (ex: validação MX). **Mitigação**:
  domínio `resenhai.com` tem MX válido (Google Workspace) — emails sintéticos passam validação
  básica de domínio.
- **Risco**: ban em massa do número Evolution. **Mitigação**: ADR-007 + plano de saída para
  Cloud API oficial em > 1k grupos pagantes.
- **Risco**: dev não-familiarizado faz `auth.signIn(email, ...)` com email real do usuário.
  **Mitigação**: comentário em `auth.ts` + lint rule `[VALIDAR — adicionar a constitution.md]`.

## References

- [`services/supabase/auth.ts:39-44`](../../resenhai-expo/services/supabase/auth.ts#L39-L44) — `phoneToEmail` implementação atual
- `n8n_backend/Magic_Link_OTP.json` — workflow gerador de OTP
- `services/whatsapp/sendMessage.ts:requestMagicLink` — entrypoint cliente
- [ADR-006](../ADR-006-workflow-orchestration-edge-functions/) — plano de migração n8n → Edge
