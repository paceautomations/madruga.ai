---
title: "Vision"
updated: 2026-04-10
sidebar:
  order: 1
---
# ProsaUAI — Business Vision

> Framework: Playing to Win (Lafley & Martin). Ultima atualizacao: 2026-04-07.

---

## 1. Tese & Aspiracao

ProsaUAI transforma WhatsApp no canal de atendimento inteligente de qualquer PME brasileira. A plataforma e **configuration-driven**: cada novo cliente e uma configuracao — persona, tom de voz, catalogo, regras de negocio — sem escrever codigo. O primeiro cliente e o ResenhAI (app de futevolei), mas a arquitetura nasce multi-tenant desde o dia zero.

O diferencial estrutural e o **agente de grupo**: ProsaUAI e o unico player que faz IA conversacional em grupos WhatsApp — espaco nao-contestado por nenhum concorrente relevante. Quanto mais comunidades usam, mais dados de interacao em grupo alimentam a qualidade do agente — criando um flywheel defensavel.

**North Star Metric:** conversas resolvidas autonomamente / mes.

| Horizonte | Clientes ativos | MRR | Resolucao autonoma | Churn mensal |
|-----------|----------------|-----|---------------------|-------------|
| **6 meses** | 50 | R$ 25K | 40% | < 10% |
| **18 meses** | 500 | R$ 250K | 70% | < 5% |

---

## 2. Where to Play

### Mercado

- **TAM:** ~6 milhoes de PMEs brasileiras que ja usam WhatsApp comercialmente (SEBRAE + Meta Business)
- **SAM:** E-commerce + servicos com atendimento ativo via WhatsApp Business (~1.2M)
- **SOM:** 500 PMEs em 18 meses, via self-service + inside sales

### Cliente-alvo

| Dimensao | Detalhe |
|----------|---------|
| **Persona** | Dono(a) de PME, 28-55 anos, usa WhatsApp Business como canal principal, sem time de TI |
| **Dor principal** | Atendimento manual nao escala — mensagens perdidas, tempo de resposta alto, cliente insatisfeito |
| **Alternativa atual** | Responde manualmente ou usa chatbot tree-based (rigido, sem IA) |
| **Job-to-be-Done** | "Quero atender meus clientes fora do horario sem contratar mais gente" |

### Personas

| Persona | O que faz | O que ganha | Jornada principal |
|---------|-----------|-------------|-------------------|
| **Dono(a) da PME** | Configura agente, define regras de negocio, acompanha metricas de atendimento | Atendimento 24/7 sem contratar, mais vendas, menos mensagens perdidas | Cadastro → config agente → conecta WhatsApp → monitora painel |
| **Cliente final** | Envia mensagem no WhatsApp, interage com agente ou humano | Resposta rapida, fora do horario, sem esperar em fila | Envia duvida → recebe resposta IA → resolve ou fala com humano |
| **Operador / Atendente** | Recebe conversas escaladas, responde com contexto completo | Produtividade maior, sem repetir perguntas ao cliente | Recebe notificacao → ve resumo IA → responde → encerra |
| **Admin ProsaUAI** | Gerencia plataforma, monitora saude dos tenants, resolve incidentes | Visibilidade operacional, acao rapida em problemas | Monitora dashboard → identifica anomalias → intervem → documenta |

### Segmentos prioritarios

1. **Comunidades esportivas** — ResenhAI como caso de referencia. Agente em grupo que publica ranking, responde stats, organiza jogos. Nenhum player faz isso.
2. **E-commerce** — Pedidos, rastreio, trocas, carrinho abandonado. Maior volume de mercado.
3. **Servicos** — Agendamento, duvidas, pos-venda. Alto potencial de resolucao autonoma.

### Onde NAO jogamos

| ProsaUAI NAO e... | Porque |
|-----------------|--------|
| **CRM** | Nao gerencia pipeline de vendas. Integra com CRMs existentes. |
| **Call center** | Nao faz voz nem telefonia. Foco em mensageria. |
| **Marketplace** | Nao intermedia transacoes nem cobra comissao. |
| **Plataforma de anuncios** | Nao faz marketing automation nem campanhas em massa. Foco em atendimento. |

---

## 3. How to Win

### Moat estrutural: Group AI Agent

Nenhum concorrente relevante — Blip, Botpress, Respond.io, Chatbase — faz IA conversacional em grupos WhatsApp. Todos sao construidos para conversas 1:1. ProsaUAI ocupa esse espaco nao-contestado.

O moat e dificil de copiar: requer engenharia especifica para contexto de grupo (multiplos participantes, @mentions, historico coletivo), alem de profundidade vertical em comunidades (ranking, stats, moderacao, engajamento). Quanto mais comunidades usam, mais dados de interacao em grupo alimentam a qualidade do agente.

### Posicionamento

ProsaUAI nao compete no eixo "chatbot generico". A categoria e **community AI agent** — grupo + proativo + vertical depth. Players enterprise (Blip, Zenvia) sao caros e complexos demais para PME. Builders globais (Botpress, Respond.io) so fazem 1:1. ProsaUAI ocupa a intersecao de grupo AI + comunidade + Brasil mid-market.

### Batalhas criticas

| # | Batalha | Metrica de sucesso | Por que importa |
|---|---------|-------------------|-----------------|
| 1 | **ResenhAI como caso de referencia** | 70% resolucao autonoma | Prova a tese. Sem case, sem credibilidade. |
| 2 | **Self-service onboarding** | PME ativa em < 15 min | Sem isso, nao escala. Cada cliente manual = gargalo. |
| 3 | **Unit economics positivo** | Margem bruta > 70% no Starter+ | Se custo por tenant > receita, crescer = queimar caixa. |
| 4 | **Grupo AI que funciona** | Engajamento em grupo > baseline sem IA | O moat so vale se o produto entrega. |
| 5 | **Retencao** | Churn < 10% (6m), < 5% (18m) | PMEs tem mortalidade alta. Precisa de stickiness. |

---

## 4. Landscape

| Player | Foco | Preco entry | Grupo AI |
|--------|------|-------------|----------|
| **Blip** | Enterprise BR, grandes contas | R$ 5K+/mes | Nao |
| **Zenvia** | Enterprise BR, omnichannel | R$ 1K+/mes | Nao |
| **Botpress** | Agent builder global, SMB | Free tier (PAYG) | Nao |
| **Respond.io** | Messaging platform, mid-market | $79/mo | Nao |
| **ProsaUAI** | Community AI, PME BR | R$ 0-997/mo | **Sim** |

**Tese competitiva:** O mercado de chatbots 1:1 e lotado e comoditizado. ProsaUAI nao entra nessa briga. A aposta e criar a categoria "community AI agent" — onde ninguem compete — e expandir lateralmente para 1:1 e proativo a partir dessa base. A profundidade vertical (comunidades esportivas → e-commerce → servicos) cria switching costs que "adicionar portugues" nao replica.

---

## 5. Riscos & Premissas

### Riscos

| # | Risco | Prob. | Impacto | Mitigacao |
|---|-------|-------|---------|-----------|
| 1 | Meta muda pricing da API WhatsApp | Media | Alto | Monitorar announcements. Respostas a msgs do usuario sao gratis desde Nov/2024. |
| 2 | Concorrente copia Group AI | Media | Medio | First-mover + vertical depth. Copiar feature e facil; copiar dados de comunidade, nao. |
| 3 | Custo de IA por conversa explode | Media | Alto | Classificador leve como router. Cache de respostas frequentes. Fallback para modelos menores. |
| 4 | Ban de numero WhatsApp | Media | Alto | Quality score monitoring, opt-in rigoroso, rate limiting, warm-up. |
| 5 | Conteudo toxico gerado pela IA | Media | Alto | Filtros de entrada e saida, avaliador antes de enviar, blocklist por tenant. |
| 6 | Commoditization de IA conversacional | Alta | Alto | Se toda IA e boa, diferencial morre. Moat esta na verticalizacao e dados de grupo, nao na IA generica. |
| 7 | Dependencia de canal unico (WhatsApp) | Media | Alto | WhatsApp-first, nao WhatsApp-only. Adaptador para expansao futura. Nao dispersar foco agora. |

### Premissas criticas

Se qualquer uma for falsa, a tese precisa ser revisada:

1. **PMEs pagam por atendimento automatizado** — R$197/mes e acessivel para o publico-alvo. Validar com 10+ entrevistas antes do lancamento.
2. **70% de resolucao autonoma e atingivel** — para PMEs genericas, nao so para o caso controlado do ResenhAI. Validar com metricas reais nos primeiros 3 meses.
3. **WhatsApp continua dominante no BR** — nenhum canal alternativo ganha tracao significativa em 18 meses.
4. **Custo de IA por conversa continua caindo** — tendencia historica se mantem, viabilizando margem >70%.
5. **Churn de PME e gerenciavel** — taxa de mortalidade de pequenos negocios nao inviabiliza SOM de 500.

---

## 6. Modelo de Negocio

### Pricing

| Tier | Preco/mes | Msgs/mes | Agents | Numbers |
|------|-----------|----------|--------|---------|
| **Free** | R$ 0 | 100 | 1 | 1 |
| **Starter** | R$ 197 | 2.000 | 3 | 2 |
| **Growth** | R$ 497 | 10.000 | 10 | 5 |
| **Business** | R$ 997 | 50.000 | Ilimitado | 10 |
| **Enterprise** | Custom | Custom | Custom | Custom |

### Tailwind estrutural

Desde novembro de 2024, **respostas a mensagens iniciadas pelo usuario sao gratis** na API do WhatsApp (service conversations). O core do produto — atender mensagens de clientes — tem custo zero de canal. Custo variavel apenas em mensagens proativas (templates).

### Unit economics

- **Custo de IA:** pass-through sem markup. Estimativa: ~R$0.05/conversa [VALIDAR com dados reais nos primeiros 30 dias].
- **Margem bruta target:** >70% a partir do tier Starter.
- **Break-even por tenant:** ~R$60/mes (infra + IA). Starter (R$197) ja e positivo.

---

## 7. Linguagem Ubiqua

> Padronizar estes termos em todos os documentos, codigo e comunicacao do projeto.

| Termo | Definicao | Exemplo |
|-------|-----------|---------|
| **Tenant** | Empresa/negocio que usa ProsaUAI. Cada tenant tem dados, configuracao e cobranca isolados | "O tenant ResenhAI tem 3 agentes configurados" |
| **Agente** | Assistente conversacional configurado pelo tenant. Tem persona, tom de voz e regras proprias | "O agente do ResenhAI responde sobre ranking e jogos" |
| **Conversa** | Troca de mensagens entre cliente final e agente (ou humano) num canal | "A conversa foi resolvida autonomamente em 3 turnos" |
| **Resolucao autonoma** | Conversa encerrada pelo agente sem intervencao humana | "Meta: 70% de resolucao autonoma em 18 meses" |
| **Handoff** | Transferencia de conversa do agente para atendente humano com todo o contexto | "Score baixo dispara handoff para o operador" |
| **Pipeline** | Sequencia de etapas que cada mensagem percorre: recepcao → analise → resposta → entrega | "A mensagem entrou no pipeline e foi respondida em 3 segundos" |
| **Guardrails** | Filtros de seguranca que bloqueiam conteudo indesejado antes e depois da resposta do agente | "Os guardrails barraram uma tentativa de manipulacao" |
| **Debounce** | Agrupamento de mensagens rapidas numa unica interacao (evita respostas multiplas) | "O cliente digitou 3 msgs em 2s — debounce agrupou em 1" |
| **Canal** | Meio de comunicacao (WhatsApp, futuro: outros). Cada canal tem um adaptador | "ProsaUAI e WhatsApp-first mas suporta multiplos canais" |
| **Trigger** | Mensagem proativa enviada pelo agente por evento ou agendamento | "Trigger de lembrete enviado 1h antes do jogo" |

---

---

## 8. Multi-Tenant End-State (Faseamento)

A vision multi-tenant nao e implementada num unico salto — segue 3 fases que mapeiam a maturidade comercial da plataforma. Cada fase tem trigger explicito; nao se antecipa fase sem dor real para evita-la.

### Fase 1 — Fundacao Multi-Tenant Estrutural (epic 003)

**Quando:** agora. Pre-requisito de qualquer outro epic.

**O que entrega:**

- Codigo ja e multi-tenant: `Tenant` abstraction, `TenantStore` (file-backed YAML), per-tenant credentials, per-tenant Redis keys (debounce + idempotency)
- Auth via `X-Webhook-Secret` per-tenant (substitui HMAC imaginario que rejeitava 100% dos webhooks reais)
- 2 tenants reais operando em paralelo desde o dia 1: **Pace Ariel** + **Pace ResenhAI** (ambas instancias internas Pace)
- Parser corrigido contra Evolution v2.3.0 real (12 correcoes empiricas validadas com 26 fixtures capturadas)
- Deploy isolado por rede: Tailscale no dev, Docker network privada na prod Fase 1 — **superficie de ataque zero** ate Fase 2

**O que NAO entrega:** admin API, Caddy publico, rate limit per-tenant, billing.

**Stakeholder:** time interno Pace.

**Trigger de saida:** primeiro cliente externo pagando R$ 0/mes (free tier validado) ou R$ 197/mes (Starter). Sem cliente externo, nao avanca para Fase 2 — Fase 1 e suficiente para validar a tese com clientes internos.

### Fase 2 — Public API Multi-Tenant (epic 012)

**Quando:** quando existir 1+ cliente externo disposto a configurar webhook na sua propria instancia Evolution.

**O que entrega:**

- Caddy reverse proxy com TLS automatico (Let's Encrypt) na frente da prosauai-api
- Endpoint publico `https://api.prosauai.com/webhook/whatsapp/{instance}`
- Admin API: `POST/GET/PATCH/DELETE /admin/tenants` com auth via master token (+ futura JWT scoped)
- Rate limiting per-tenant (Redis sliding window por minuto + per dia, integrado com Bifrost spend caps — ja documentado em ADR-015)
- Onboarding doc para clientes externos: como configurar webhook na sua Evolution, como gerar secret, validacao end-to-end
- Metricas basicas per-tenant expostas (requests/s, errors, debounces flushed) — pre-requisito visual para cobranca
- Hot reload de tenants (FS watcher) ou reload via admin API — sem restart

**O que NAO entrega:** Postgres, billing automatizado (pagamento manual), self-service signup.

**Stakeholder:** primeiros clientes externos, time interno Pace.

**Trigger de entrada:** primeiro cliente externo dizendo "sim, quero pagar/testar". Estimativa: ~2 semanas de implementacao.

**Trigger de saida:** >= 5 tenants reais simultaneos OU dor operacional de gerenciar `tenants.yaml` manualmente (quem editou? quando? rollback?).

**ADRs novos:** [ADR-021](../decisions/ADR-021-caddy-edge-proxy.md) (Caddy como edge proxy), [ADR-022](../decisions/ADR-022-admin-api.md) (Admin API).

### Fase 3 — Operacao em Producao Multi-Tenant (epic 013)

**Quando:** dor operacional real, nao antes. Trigger objetivo: >=5 tenants em producao OU primeiro incidente de "tenant noisy neighbor" derrubando outros.

**O que entrega:**

- `TenantStore` migrado de YAML para Postgres (schema gerenciado em Supabase, RLS para futuro self-service)
- Circuit breaker per-tenant (ja documentado em ADR-015) — tenant doente nao derruba os outros
- Billing/usage tracking automatizado (contagem de mensagens processadas, custo LLM via Bifrost — ja documentado em ADR-012)
- Alertas Prometheus/Grafana per-tenant (requests/s, error rate, queue depth, spend approaching cap)
- Auditoria: log imutavel de operacoes administrativas (quem criou/editou/disabilitou cada tenant)
- Backup/restore do estado dos tenants (config + secrets via Infisical)

**O que NAO entrega:** UI admin (provavelmente so API + scripts no inicio); migracao para outras regioes geograficas.

**Stakeholder:** ops team Pace, SREs, finance team (billing).

**Trigger de entrada:** dor operacional real e mensuravel. Estimativa: ~3 semanas de implementacao.

**ADR novo:** [ADR-023](../decisions/ADR-023-tenant-store-postgres-migration.md) (trigger e migration plan YAML → Postgres).

### Sintese das fases

| Fase | Epic | Trigger entrada | Output principal | Stakeholder |
|------|------|----------------|------------------|-------------|
| **1 — Fundacao** | 003 (now) | Bloqueio do servico em producao real | Codigo multi-tenant operando com 2 tenants internos | Time interno Pace |
| **2 — Public API** | 012 (later) | Primeiro cliente externo | Caddy + Admin API + rate limit + onboarding externo | Clientes externos + Pace |
| **3 — Operacao** | 013 (later) | >=5 tenants OU dor operacional | Postgres + circuit breaker + billing + alertas | Ops + finance |

Cada fase e independente — implementar Fase 2 sem cliente real seria overengineering. Implementar Fase 3 sem >=5 tenants seria desperdicio. **A disciplina e nao antecipar trigger.**

---

> **Proximo passo:** `/madruga:solution-overview prosauai` — gerar visao de solucao a partir desta visao validada.
