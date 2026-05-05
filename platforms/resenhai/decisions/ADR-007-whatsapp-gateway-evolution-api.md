---
title: "ADR-007: WhatsApp Gateway — Evolution API (não-oficial, com risco regulatório)"
status: accepted
date: 2026-05-04
decision: >
  Adotar Evolution API self-hosted (protocolo Baileys, WhatsApp Web não-oficial) como gateway de mensagens WhatsApp para envio de OTP, ranking público e sync de grupos.
alternatives: >
  WhatsApp Cloud API (Meta oficial); Z-API; Twilio
rationale: >
  É a única opção que suporta sincronização completa de grupos WhatsApp — feature core do produto (Magic Link OTP, ranking público, convites). Cloud API oficial não cobre group messaging em escala; alternativas SaaS BR usam o mesmo protocolo não-oficial com custo maior.
---
# ADR-007: WhatsApp Gateway — Evolution API

## Status

Accepted — 2026-05-04 (retroativo) — confiança Média (risco regulatório explícito)

## Context

ResenhAI depende criticamente do WhatsApp para 3 features core: (a) **Magic Link OTP** — única forma de cadastro de novo usuário; (b) **convites de grupo** — Dono manda link no zap, jogador entra; (c) **ranking público** — app posta ranking diário/semanal no grupo do WhatsApp. Os 3 use cases exigem **enviar mensagem em grupo do WhatsApp e receber eventos de grupo** (membros entrando/saindo, mudanças de admin). A WhatsApp Cloud API oficial da Meta tem limitações severas em group messaging — não permite enviar mensagens em grupos via API (apenas individual ou business-to-customer); recebimento de eventos de grupo também é restrito a business-conversations API que não cobre o caso de uso. Sem capacidade de operar em grupos, o produto não roda.

## Decision

Adotar **Evolution API** self-hosted (protocolo Baileys), com instância(s) gerenciada(s) `[VALIDAR — host atual: provavelmente Easypanel ao lado do n8n, mas não confirmado em codebase-context.md]`. Webhook do Evolution aponta para `supabase/functions/whatsapp-webhook` (codebase-context.md §8). Envio de mensagens via `services/whatsapp/sendMessage.ts` (codebase-context.md §8). Reconhecemos explicitamente que esta é uma escolha **não-oficial** com risco regulatório.

## Alternatives Considered

### Alternative A: Evolution API (chosen)
- **Pros:** gratuito (open source); group sync completo (envio + eventos); comunidade BR ativa em Discord; PT-BR docs; integra com qualquer instância WhatsApp via QR code.
- **Cons:** **viola Termos de Uso do WhatsApp** — risco de banimento de número; sem SLA; manutenção de sessão QR é frágil; ban-recovery exige rotação de número.
- **Fit:** Único `high` fit em group sync.

### Alternative B: WhatsApp Cloud API (Meta oficial)
- **Pros:** oficial, sem risco de ban, templates HSM (mensagens fora de janela 24h), SLA Meta.
- **Cons:** **group messaging API não cobre uso massivo do produto**; setup BSP burocrático (verificação de número, templates aprovados); custo $0.005-0.08/conversa.
- **Why rejected:** **bloqueador funcional** — não cobre group sync, que é core do produto.

### Alternative C: Z-API
- **Pros:** SaaS BR; suporte PT; sem self-host.
- **Cons:** usa o mesmo protocolo não-oficial (mesmo risco regulatório); custo recorrente R$ 99-199/mo + por mensagem; lock-in em vendor BR.
- **Why rejected:** mesmo risco de Evolution + custo maior + lock-in.

### Alternative D: Twilio (incluído como referência global)
- **Pros:** SaaS global maduro; SLA forte.
- **Cons:** preço por mensagem alto; group messaging via WhatsApp Cloud API herdado (mesmas limitações de Meta).
- **Why rejected:** não resolve o bloqueador de group sync.

## Consequences

### Positive
- Produto consegue operar 100% das features WhatsApp (envio + eventos + grupos).
- Sem custo por mensagem.
- Total controle sobre infraestrutura de gateway.

### Negative
- **Risco de ban**: Meta pode banir números que usam Baileys/Evolution; recuperação exige rotação de números e re-verificação de instâncias.
- **Frágil em manutenção**: sessão QR cai eventualmente; precisa re-scan; em produção isso vira incidente.
- **Sem SLA**: downtime do Evolution = onboarding e ranking parado; não há contrato de support.
- **Compliance**: documento legal/ToS pode evoluir; cliente Enterprise (Arena) pode exigir gateway oficial.

### Risks
- **Risco:** ban recorrente em > 5% das instâncias. **Mitigação:** monitoramento + playbook de rotação de números; reservar 2-3 números secundários verificados.
- **Risco:** Meta liberar Group Messaging API oficial. **Mitigação:** revisitar este ADR e migrar — Evolution permanece como fallback durante transição.
- **Risco:** ToS WhatsApp endurecer e tornar protocolo Baileys instável. **Mitigação:** monitorar comunidade Evolution + GitHub issues; ter Z-API como standby comercial.

## References

- https://github.com/EvolutionAPI/evolution-api — projeto oficial
- https://developers.facebook.com/docs/whatsapp/cloud-api — Cloud API limitations
- codebase-context.md §8 — gateway hoje em produção
- business-process.md §1-§4 — pipeline depende deste gateway
