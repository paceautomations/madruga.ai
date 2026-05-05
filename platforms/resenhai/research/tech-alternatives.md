---
title: "Tech Alternatives"
updated: 2026-05-04
---
# ResenhAI — Alternativas Tecnológicas

> Pesquisa retroativa de alternativas para 12 decisões técnicas — 11 já em produção + 1 gap (error tracking). Brownfield: cada matriz marca a escolha **(atual)** e a recomendação confirma manter ou migrar com kill criteria explícito. Última atualização: 2026-05-04.

---

## Resumo Executivo

ResenhAI é app mobile-first em produção (TypeScript 5.9, ~58k LOC, 370 commits, 2 contributors) para comunidades de esportes de areia. Stack atual é coerente e bem alinhada às melhores práticas 2025-2026: Expo+RN como camada cliente unificada (iOS/Android/web), TanStack Query+RHF+Zod no estado/forms, NativeWind no design, Supabase como BaaS consolidado (Postgres+RLS+Auth+Storage+Realtime+Edge), n8n self-hosted como camada transitória de orquestração, Evolution API como gateway WhatsApp, PostHog como product analytics e EAS+GH Actions no build/deploy.

**11 decisões existentes mantidas** (10 com confiança Alta, 1 — Styling — com confiança Média). **2 mudanças confirmadas no roadmap retroativo**: (a) **Workflow orchestration** muda de n8n self-hosted para **Supabase Edge Functions** (consolida runtime, elimina VM, reduz superfície operacional — épico-002-edge-migration); (b) **Payment processor** entra com **Stripe** (não-implementado — épico-001-stripe destrava monetização). **1 gap identificado**: **error tracking** — produção rodando sem stack-trace observability; recomenda-se adotar **Sentry** com epic dedicado.

Riscos principais: lock-in moderado em Supabase (mitigado por Postgres puro + RLS portável), risco regulatório de Evolution API ser não-oficial (sem alternativa hoje porque Cloud API não cobre group sync), e custo PIX do Stripe vs concorrentes BR (mitigação se margem cair < 70%).

---

## Decisão 1: Mobile framework

### Contexto
ResenhAI já roda em produção com Expo + RN. Pergunta: vale migrar para Flutter ou nativo dado escala (1.7M TAM, 2 devs)?

### Matriz de Alternativas

| Critério | **Expo+RN** (atual) | Flutter 3.x | Native (Swift+Kotlin) |
|----------|---------------------|-------------|------------------------|
| **Custo dev** | 1 codebase TS, 2 devs OK | 1 codebase Dart, +1 lang | 2 codebases, 4x esforço |
| **Performance** | JS bridge + Hermes; OK p/ social/CRUD | AOT compilado, ~60fps consistente | Nativo, máximo |
| **Complexidade** | low (EAS Build, OTA updates) | med (toolchain própria) | high (2 pipelines) |
| **Comunidade** | RN 122k stars, expo 38k; ~3.5M downloads/sem | Flutter 173k stars; ~1M pub.dev | N/A |
| **Fit p/ resenhai** | high — TS já no stack web, OTA crítico p/ iterar | med — reescrita total em Dart | low — inviável c/ 2 devs |
| **Maturidade** | RN 0.81 (2025), 10+ anos | Flutter 3.27 (2025), 7 anos | Décadas |

### Análise
**Expo+RN:** Pros: TS unificado web/mobile, EAS Build, OTA via expo-updates; Cons: bridge JS, libs nativas custom exigem prebuild; Used by: Shopify, Discord, Coinbase, Microsoft Teams. https://reactnative.dev/showcase
**Flutter:** Pros: render próprio (Skia/Impeller), perf consistente, hot reload maduro; Cons: Dart isolado do ecossistema TS, libs Brasil (PIX, gateways) menos cobertas; Used by: Google Pay, Nubank (parcial), BMW, Alibaba. https://flutter.dev/showcase
**Native:** Pros: APIs novas dia 1, perf máxima; Cons: 2x devs/tempo, sem code-sharing c/ web; Used by: apps de bancos tier-1 (Itaú, BB).

### Recomendação
**Manter Expo+RN** — única opção com fit `high` na matriz: reaproveita TS/Zod/RHF do web, EAS+OTA permite iterar rápido em comunidade ativa, custo dev compatível com 2 contribuidores. Confiança: Alta. Kill criteria: render 3D pesado (replays de jogadas), AR de quadra, ou p95 de render < 30fps em devices Android baixos do TAM brasileiro mesmo com Hermes+New Architecture.

---

## Decisão 2: State/data layer (server state)

### Contexto
ResenhAI consome REST backend; precisa cache, dedup, optimistic updates e persistência offline. Hoje usa TanStack Query + persist + Zod.

### Matriz de Alternativas

| Critério | **TanStack Query** (atual) | SWR | Apollo Client | RTK Query |
|----------|----------------------------|-----|----------------|-----------|
| **Custo runtime** | ~13kb gzip | ~4kb gzip | ~33kb gzip | depende RTK (~15kb+) |
| **Performance** | cache normalizado por chave, dedup | dedup + revalidate-on-focus | cache normalizado + GraphQL | cache + middleware Redux |
| **Complexidade** | med (queryKey discipline) | low | high (schema, codegen) | med-high (Redux setup) |
| **Comunidade** | 44k stars, ~9M dl/sem | 31k stars, ~3M dl/sem | 19k stars, ~3.5M dl/sem | parte de RTK 11k, ~5M dl/sem |
| **Fit p/ resenhai** | high — REST + persist + RN | med — REST OK mas sem persist robusto | low — sem GraphQL no backend | low — força adoção Redux |
| **Maturidade** | v5.90 (2025), 6+ anos | v2.3 (2025), 5 anos | v3.13 (2025), 9 anos | v2.x (2025), 4 anos |

### Análise
**TanStack Query:** Pros: persistência via `query-async-storage-persister`, devtools, optimistic mutations, RN-first; Cons: queryKey discipline; Used by: Vercel, Sentry, Linear, Cal.com. https://tanstack.com/query
**SWR:** Pros: API minimalista, ótima DX p/ Next.js; Cons: persist não é first-class, comunidade mobile menor; Used by: Vercel (próprio), HashiCorp. https://swr.vercel.app
**Apollo Client:** Pros: cache normalizado top-tier; Cons: requer GraphQL — backend ResenhAI é REST; Used by: Airbnb, Expedia, GitHub. https://www.apollographql.com/customers
**RTK Query:** Pros: integra Redux, codegen OpenAPI; Cons: arrasta Redux store inteiro; Used by: apps Redux-heavy `[FONTE?]`.

### Recomendação
**Manter TanStack Query** — único `high` fit: REST + persist nativo + RN, downloads ~3x SWR, ecossistema maduro. Confiança: Alta. Kill criteria: migração do backend para GraphQL ou necessidade de cache normalizado cross-entity (feed social).

---

## Decisão 3: Form library

### Contexto
ResenhAI tem fluxos de cadastro de evento, perfil, registrar jogo — formulários médios com validação. Hoje: RHF + Zod, integrado ao schema de API.

### Matriz de Alternativas

| Critério | **RHF + Zod** (atual) | Formik + Yup | Final Form |
|----------|------------------------|---------------|-------------|
| **Custo runtime** | ~9kb (RHF) + ~14kb (zod) | ~13kb (formik) + ~22kb (yup) | ~5kb (core) |
| **Performance** | uncontrolled, re-render mínimo | controlled, re-render por field | uncontrolled, subscription-based |
| **Complexidade** | low-med | low | med (subscriptions) |
| **Comunidade** | RHF 43k stars, ~12M dl/sem; Zod 38k stars, ~30M dl/sem | Formik 34k stars, ~3M dl/sem; Yup 23k stars, ~9M dl/sem | 7.5k stars, ~500k dl/sem |
| **Fit p/ resenhai** | high — Zod já valida API/types, RN OK | med — controlled re-render dói em listas RN | low — comunidade declinante |
| **Maturidade** | RHF v7.66 (2025); Zod v4.1 (2025) | Formik v2.4, último release 2024 | v4.20, manutenção lenta |

### Análise
**RHF + Zod:** Pros: uncontrolled (perf RN), `zodResolver`, schema reaproveitado p/ types e API; Cons: API menos óbvia p/ junior; Used by: Vercel, Cal.com, Shadcn ecosystem. https://react-hook-form.com
**Formik + Yup:** Pros: API didática, docs maduras; Cons: controlled re-renderiza todos os fields, manutenção desacelerou; Used by: Airbnb (legacy) `[FONTE?]`. https://formik.org
**Final Form:** Pros: arquitetura subscription elegante; Cons: comunidade pequena; Used by: nichos React legacy. https://final-form.org

### Recomendação
**Manter RHF + Zod** — Zod é fonte de verdade dos types/API, RHF uncontrolled = perf superior em RN, downloads 4x Formik. Confiança: Alta. Kill criteria: form-builder visual no roadmap ou queda na manutenção do RHF (issues abertas >6m sem triage).

---

## Decisão 4: Styling system (RN)

### Contexto
ResenhAI usa NativeWind p/ compartilhar classes Tailwind c/ web e padronizar design tokens.

### Matriz de Alternativas

| Critério | **NativeWind** (atual) | Tamagui | Restyle (Shopify) | StyleSheet.create |
|----------|-------------------------|---------|---------------------|---------------------|
| **Custo runtime** | compilado p/ StyleSheet via Babel | compilador AOT, atom CSS p/ web | runtime theme resolver | zero |
| **Performance** | ~equivalente a StyleSheet pós-compile | top — flatten estático | médio — runtime resolution | máxima |
| **Complexidade** | low (Tailwind conhecido) | high (compiler config + tokens) | med (theme typing) | low mas verbosa |
| **Comunidade** | 7.5k stars, ~400k dl/sem | 11k stars, ~80k dl/sem | 1.9k stars, ~50k dl/sem | builtin |
| **Fit p/ resenhai** | high — design tokens compartilhados c/ web Tailwind | med — ganho perf não justifica reescrita | low — só RN, sem code-share | low p/ design system escalável |
| **Maturidade** | v4.1 (2025), 4 anos | v1.x (2025), 3 anos | v2.x (2024), 5 anos | desde RN 0.x |

### Análise
**NativeWind:** Pros: classes Tailwind idênticas web/mobile, jit compiler, dark mode nativo; Cons: debug de classes geradas exige plugin VSCode; Used by: Expo team examples, Shadcn-RN, Solito. https://www.nativewind.dev
**Tamagui:** Pros: compilador extrai estilos estáticos, tokens tipados; Cons: setup pesado, lock-in; Used by: BeatGig, FUBO `[FONTE?]`. https://tamagui.dev
**Restyle:** Pros: theming tipado pelo TS, simplicidade; Cons: só RN (sem web), runtime overhead; Used by: Shopify Mobile (próprio). https://github.com/Shopify/restyle
**StyleSheet:** Pros: zero deps, performance máxima; Cons: sem theming, sem code-share, verbosa.

### Recomendação
**Manter NativeWind** — único `high` fit: code-sharing com web Tailwind, complexidade `low`. Confiança: Média (Tamagui é alternativa real se perf de listas grandes virar problema). Kill criteria: feed >100 cards c/ jank em Android low-end mesmo com FlashList+memoization, ou NativeWind v5 atrasar suporte a New Architecture/RN 0.82+.

---

## Decisão 5: Backend-as-a-Service (BaaS) — consolidado

### Contexto
40 migrations idempotentes, 32 RLS policies, 48 functions, 22 views analíticas. Heavy SQL + type generation acoplado ao staging.

### Matriz de Alternativas

| Critério | **Supabase** (atual) | Firebase | AWS Amplify |
|----------|----------------------|----------|-------------|
| **Custo** | Pro $25/mo + uso | Blaze pay-as-you-go | Pay-per-service |
| **Performance** | Postgres nativo, RLS server-side | NoSQL, latência baixa global | Variável (DDB rápido, AppSync ok) |
| **Complexidade** | SQL + RLS (média) | NoSQL paradigm shift (alta migração) | Multi-serviço (alta) |
| **Comunidade** | 78k+ stars, Discord ativo | Massiva, Google-backed | AWS ecosystem |
| **Fit p/ resenhai** | Alta — SQL nativo, 40 migrations já escritas | Baixa — reescrever 32 RLS + views | Baixa — fragmentação operacional |
| **Maturidade** | GA, multi-region 2024 | GA desde 2014 | GA, Gen2 ainda evoluindo |

### Análise
**Supabase:** Pros: Postgres puro, RLS no DB, Edge Functions Deno integradas, type-gen via CLI; Cons: vendor lock-in em Auth/Storage, region BR ainda em São Paulo single-AZ. Used by: Mobbin, Maergo, Krea AI. https://supabase.com/customers
**Firebase:** Pros: realtime maduro, escala global, Auth provider rico; Cons: Firestore não suporta SQL/joins/views, custo cresce não-linear com reads. Used by: Duolingo, NYT, Alibaba. https://firebase.google.com/customers
**AWS Amplify:** Pros: integração full AWS, Cognito enterprise; Cons: Gen2 mudou DX, multi-serviço aumenta MTTR. Used by: Neiman Marcus, Orangetheory. https://aws.amazon.com/amplify/customers/

### Recomendação
**Manter Supabase** — migração custaria reescrever 22 views + 32 RLS sem ROI. Confiança: Alta. Kill criteria: latência p99 BR > 300ms sustentada, ou Supabase encerrar plano Pro / dobrar pricing.

---

## Decisão 6: Workflow orchestration / serverless functions

### Contexto
4 workflows stateless (Magic Link OTP, Create User Invite, WhatsApp group sync). Hoje em n8n self-hosted Easypanel — decisão é consolidar no BaaS via Edge Functions.

### Matriz de Alternativas

| Critério | **Supabase Edge Functions** (escolha) | n8n self-hosted (legado) | Inngest |
|----------|----------------------------------------|--------------------------|---------|
| **Custo** | Incluso no plano Supabase | VPS Easypanel ~$15/mo | Free tier 50k steps/mo, depois $20+ |
| **Performance** | Cold start ~50-200ms (Deno) | Sempre quente, mas single-VM | Edge global, durable execution |
| **Complexidade** | Baixa — Deno + secrets via CLI | Média — UI no-code mas ops manual | Média — SDK + dashboard |
| **Comunidade** | Cresce com Supabase | 70k+ stars, comunidade ativa | 5k+ stars, crescente |
| **Fit p/ resenhai** | Alta — colado ao DB, RLS context | Média — quebra em 2 runtimes | Baixa — overkill para 4 workflows |
| **Maturidade** | GA 2024, secrets/cron 2025 | v1.0+ estável | GA, durable workflows 2024 |

### Análise
**Edge Functions:** Pros: zero infra extra, mesmo deploy do BaaS, JWT/RLS herdados, cron nativo; Cons: 150s timeout máx, Deno ecosystem menor que Node. Used by: 1Password, Maergo. https://supabase.com/edge-functions
**n8n:** Pros: visual debugging, 400+ integrations prontas; Cons: VM extra, sem versionamento Git nativo robusto, escalabilidade horizontal complexa. Used by: Delivery Hero, T-Mobile. https://n8n.io/case-studies/
**Inngest:** Pros: durable execution, retries automáticos, step functions; Cons: vendor extra, custo cresce com volume. Used by: Resend, SoundCloud. https://www.inngest.com/customers

### Recomendação
**Supabase Edge Functions** (já escolha estratégica; n8n legado a deprecar pelo épico-002-edge-migration) — consolida runtime, elimina VM n8n, simplifica observability. Confiança: Alta. Kill criteria: workflow precisar de durable execution > 150s ou orquestração multi-step com retries complexos → reavaliar Inngest.

---

## Decisão 7: WhatsApp Gateway

### Contexto
Trade-off central: custo/recursos vs. risco regulatório de ban. Hoje Evolution API self-hosted (Baileys, não-oficial).

### Matriz de Alternativas

| Critério | **Evolution API** (atual) | WhatsApp Cloud API (Meta) | Z-API |
|----------|----------------------------|---------------------------|-------|
| **Custo** | VPS ~$10-20/mo, sem por-msg | $0.005-0.08/conversa + verificação | R$ 99-199/mo + por mensagem |
| **Performance** | Boa, depende da VM | SLA Meta, global | Boa, infra BR |
| **Complexidade** | Alta — manter sessão QR, ban-recovery | Média — webhook + templates aprovados | Baixa — API REST simples |
| **Comunidade** | Brazilian-heavy, Discord ativo | Docs Meta oficiais | Suporte BR em PT |
| **Fit p/ resenhai** | Alta hoje (group sync funciona) | Baixa — group API limitada | Média — group sync via Baileys-like |
| **Maturidade** | v2 estável, mas unofficial | GA, política Meta restritiva | GA desde 2019 |

### Análise
**Evolution API:** Pros: gratuito, group sync completo, PT-BR community; Cons: viola ToS WhatsApp, ban imprevisível, sem SLA. Used by: ecossistema brasileiro de SaaS WhatsApp. https://github.com/EvolutionAPI/evolution-api
**Cloud API:** Pros: oficial, sem risco ban, templates HSM; Cons: group messaging API ausente para uso massivo, setup BSP burocrático. Used by: Meta-verified BSPs, grandes marcas. https://developers.facebook.com/docs/whatsapp/cloud-api
**Z-API:** Pros: SaaS BR, suporte PT, sem self-host; Cons: também usa protocolo não-oficial (mesmo risco), custo recorrente. Used by: PMEs brasileiras. https://z-api.io/

### Recomendação
**Manter Evolution API** — Cloud API não suporta group sync (core feature do produto). Z-API tem mesmo risco regulatório com custo maior. Confiança: Média. Kill criteria: ban recorrente em > 5% das instâncias, ou Meta liberar Group Messaging API oficial.

---

## Decisão 8: Payment Processor (PLANEJADO — épico-001-stripe)

### Contexto
Pricing R$ 49,90 / R$ 79,90 / Enterprise. Precisa: subscriptions, coupons, pro-rata, webhooks idempotentes, PIX/Boleto. Mercado BR. Não implementado hoje.

### Matriz de Alternativas

| Critério | **Stripe** (proposto) | Pagar.me | Asaas |
|----------|------------------------|----------|-------|
| **Custo** | 3.99% + R$0,39 cartão; PIX 1,49% (BR) | 3.99% cartão; PIX 0,99%; Boleto R$3,49 | 1.99% cartão; PIX R$1,99; Boleto R$1,99 |
| **Performance** | API global madura | API BR estável | API BR estável |
| **Complexidade** | Baixa — SDK e docs best-in-class | Média — docs PT, DX inferior | Média — REST simples |
| **Comunidade** | Massiva, devs globais | BR-focused, Stone-backed | BR SMB community |
| **Fit p/ resenhai** | Alta — Billing nativo, coupons, pro-rata | Alta — BR nativo, PIX recorrente | Média — sem pro-rata nativo |
| **Maturidade** | GA, líder global | GA desde 2013, Stone 2016 | GA, foco PME |

### Análise
**Stripe:** Pros: Stripe Billing resolve subs/coupons/pro-rata out-of-box, webhooks idempotentes nativos, PIX/Boleto BR desde 2024; Cons: dispute handling em USD/conversão, custo PIX > concorrentes BR. Used by: Shopify, Notion, Hotmart. https://stripe.com/customers
**Pagar.me:** Pros: PIX recorrente nativo, antifraude Stone, BR-first; Cons: Billing menos rico que Stripe, pro-rata manual. Used by: iFood, Méliuz. https://pagar.me/clientes
**Asaas:** Pros: custo mais baixo BR, ideal SMB, split nativo; Cons: sem subscription engine completo (pro-rata/coupons via lógica própria). Used by: PMEs e infoprodutores BR. https://www.asaas.com/

### Recomendação
**Stripe** — Billing entrega subs/coupons/pro-rata sem reinventar; PIX/Boleto BR já suportados desde 2024. Confiança: Alta. Kill criteria: custo PIX inviabilizar tier R$49,90 (margem < 70%), ou disputas BR exigirem mediação local que Stripe não cobre → migrar Pagar.me.

---

## Decisão 9: Test stack

### Contexto
1898 testes (1695 unit Jest + 203 E2E Playwright web). Native E2E iOS/Android é gap. Migração tem custo alto (~38k LOC test code).

### Matriz de Alternativas

| Critério | **Jest+Playwright** (atual) | Vitest+Playwright | + Maestro (native E2E) |
|----------|------------------------------|-------------------|--------------------------|
| **Custo** | $0 (sunk) | ~2-4 sem migração 1695 testes | ~1 sem setup + free OSS |
| **Performance/DX** | Jest lento em watch | Vitest 2-5x + HMR | YAML-based, EAS integrado 2025 |
| **Complexidade** | Baixa (estabelecida) | Média (RN preset imaturo) | Baixa (declarativo) |
| **Comunidade** | Massiva (Meta) | Crescente (Vue/Vite) | Crescente (mobile.dev) |
| **Fit p/ resenhai** | Alta (RN preset oficial) | Baixa (RN+Vitest frágil) | Alta (cobre gap nativo) |
| **Maturidade** | Madura | Madura web, fraca RN | Madura (mobile.dev backed) |

### Análise
**Jest+Playwright (atual):** Pros: zero migration, jest-expo preset oficial, Playwright domina web E2E; Cons: Jest watch lento, sem cobertura nativa. Used by: Shopify, Discord, Coinbase. https://docs.expo.dev/develop/unit-testing/
**Vitest+Playwright:** Pros: 2-5x mais rápido, ESM-native, melhor TS DX; Cons: RN/jest-expo incompatível, ROI negativo p/ 1695 testes existentes. Used by: Nuxt, Astro, Vue. https://vitest.dev/
**Maestro (mobile.dev):** Pros: black-box real device, YAML declarativo, EAS Build integration nativa 2025; Cons: gray-box menor que Detox, comunidade ainda crescendo. Used by: Discord (parcial), Brex, Cal.com. https://maestro.mobile.dev/

### Recomendação
**Manter Jest+Playwright + adicionar Maestro para native E2E** (cobre gap iOS/Android sem flakiness do Detox). Confiança: Alta. Kill criteria: Vitest publicar preset RN oficial estável com adapters jest-expo OU Maestro flakiness >15% em CI.

---

## Decisão 10: Build & Deploy stack

### Contexto
EAS (Expo) + GH Actions é o caminho idiomático Expo 54. 2 GH workflows. App Center morreu (EOL mar/2025).

### Matriz de Alternativas

| Critério | **EAS+GH Actions** (atual) | Codemagic | fastlane+GH Actions |
|----------|------------------------------|-----------|------------------------|
| **Custo** | $99/mo Production plan | $0.038/min (~$95/mo equiv) | $0 OSS + GH minutes |
| **Performance/DX** | OTA Updates nativo, EAS Insights | M2 Macs rápidos | Configuração manual extensa |
| **Complexidade** | Baixa (Expo-managed) | Média (YAML próprio) | Alta (Ruby+Fastfile) |
| **Comunidade** | Massiva (Expo team) | Nichada mobile | Massiva mas legacy |
| **Fit p/ resenhai** | Altíssima (Expo 54 nativo) | Média (perde EAS Update) | Baixa (perde Expo features) |
| **Maturidade** | Madura, ativa | Madura | Madura, Google reduziu suporte |

### Análise
**EAS+GH Actions:** Pros: EAS Update OTA, Submit automático stores, integração Expo 54 perfeita; Cons: vendor lock-in, $99/mo. Used by: Brex, Bluesky, Coinbase Wallet. https://docs.expo.dev/eas/
**Codemagic:** Pros: M2 Macs, melhor para flows custom Flutter+RN; Cons: perde EAS Update OTA, sem integração Expo profiles. Used by: Philips, Nubank (Flutter). https://codemagic.io/
**fastlane+GH Actions:** Pros: zero vendor cost, controle total; Cons: Google em modo manutenção desde 2024, sem OTA updates. Used by: legados pré-EAS. https://fastlane.tools/

### Recomendação
**Manter EAS+GH Actions** — Expo 54 + EAS é caminho oficial; OTA via EAS Update vale o $99/mo sozinho. Confiança: Alta. Kill criteria: EAS pricing >$300/mo OU sair do Expo managed workflow.

---

## Decisão 11: Product analytics

### Contexto
PostHog 4.34 RN SDK em produção, US Cloud. PII masking implementado (email/phone/userId).

### Matriz de Alternativas

| Critério | **PostHog** (atual) | Mixpanel | Amplitude | GA4 |
|----------|---------------------|----------|-----------|-----|
| **Custo** | Free 1M events/mo | Free 1M MTU | Free 10M events/mo | Free ilimitado |
| **Performance/DX** | OSS self-host opção, replays | Best-in-class funnels | Forte cohorts/retention | Fraco p/ apps |
| **Complexidade** | Baixa | Baixa | Média | Alta (BigQuery p/ útil) |
| **Comunidade** | Crescente rápido | Madura | Madura enterprise | Massiva mas web-first |
| **Fit p/ resenhai** | Alta (RN SDK + replays + flags) | Alta (funnels esportes) | Média | Baixa (web-centric) |
| **Maturidade** | Madura desde 2023 | Madura | Madura | Madura |

### Análise
**PostHog (atual):** Pros: feature flags+analytics+session replay no mesmo SDK, OSS, EU/US cloud; Cons: funnels menos refinados que Mixpanel. Used by: Y Combinator, Airbus, Raycast, ClickHouse. https://posthog.com/customers
**Mixpanel:** Pros: melhores funnels e impact reports, JQL queries; Cons: sem feature flags nativos, sem session replay. Used by: Uber, Netflix, Yelp. https://mixpanel.com/customers/
**Amplitude:** Pros: cohort analysis e behavioral predictions; Cons: pricing enterprise opaco >100k MTU, RN SDK menos polido. Used by: Microsoft, NBC, Shopify. https://amplitude.com/customers
**GA4:** Pros: gratuito ilimitado; Cons: sampling, latência 24-48h, modelo event web-centric. Used by: tudo no mundo (raramente como primário em apps). https://analytics.google.com/

### Recomendação
**Manter PostHog** — combo analytics+flags+replays é único e fit perfeito para brownfield iterativo. Confiança: Alta. Kill criteria: PostHog cobrar >$0.0001/event OU LGPD exigir hosting BR (migrar para EU Cloud antes de self-host).

---

## Decisão 12: Error tracking [DECISÃO PENDENTE — adoção sugerida]

### Contexto
**GAP**: atualmente apenas `services/supabase/logging.ts` (logging ad-hoc, sem stack traces, sem release tracking, sem source maps Hermes). Crashes em produção são invisíveis.

### Matriz de Alternativas

| Critério | Logging ad-hoc (atual) | **Sentry** (proposto) | Bugsnag | Rollbar |
|----------|------------------------|-------------------------|---------|---------|
| **Custo** | $0 | Free 5k errors/mo, $26/mo | Free 7.5k events, $59/mo | Free 5k events, $31/mo |
| **Performance/DX** | Inexistente | Source maps RN+web auto, replays | Stable releases, dashboard limpo | Telemetry boa, UX datada |
| **Complexidade** | N/A | Baixa (`@sentry/react-native`) | Baixa | Média |
| **Comunidade** | — | Massiva, padrão de fato | Média (SmartBear) | Pequena |
| **Fit p/ resenhai** | Inaceitável | Altíssima (RN+web+Hermes) | Alta | Média |
| **Maturidade** | — | Madura, líder de mercado | Madura | Madura |

### Análise
**Logging ad-hoc:** Pros: zero custo; Cons: invisibilidade total de crashes prod, sem alerting, sem source maps Hermes — risco operacional alto.
**Sentry:** Pros: padrão indústria RN+web, source maps Hermes auto, session replay, performance tracing, release health, OTel-compatível; Cons: pricing escala com volume. Used by: Disney+, Riot, GitHub, Cloudflare, Vercel, Atlassian. https://sentry.io/customers/
**Bugsnag:** Pros: stability scores por release, melhor UX p/ release gates; Cons: comunidade RN menor, sem session replay nativo. Used by: Airbnb, Lyft, Yelp. https://www.bugsnag.com/customers
**Rollbar:** Pros: telemetry e RQL queries; Cons: RN SDK menos maduro. Used by: Salesforce, Twilio. https://rollbar.com/customers/

### Recomendação
**Adotar Sentry** — padrão de fato para RN+Hermes+web, integração EAS Build oficial via `@sentry/react-native` com source maps automáticos no build. Confiança: Alta. Kill criteria: volume >100k errors/mo (avaliar self-host GlitchTip OSS) OU LGPD requerer hosting BR.

---

## Tabela Consolidada

| # | Decisão | Recomendação | Confiança | Gate |
|---|---------|--------------|-----------|------|
| 1 | Mobile framework | **Manter** Expo + RN | Alta | 1-way-door |
| 2 | State/data layer | **Manter** TanStack Query + Zod | Alta | 1-way-door |
| 3 | Form library | **Manter** RHF + Zod | Alta | 1-way-door |
| 4 | Styling system | **Manter** NativeWind | Média | 1-way-door |
| 5 | BaaS (consolidado) | **Manter** Supabase | Alta | 1-way-door |
| 6 | Workflow orchestration | **Migrar** n8n → Supabase Edge Functions | Alta | 1-way-door |
| 7 | WhatsApp Gateway | **Manter** Evolution API | Média | 1-way-door |
| 8 | Payment Processor (planejado) | **Adotar** Stripe | Alta | 1-way-door |
| 9 | Test stack | **Manter** Jest+Playwright + adicionar Maestro | Alta | 1-way-door |
| 10 | Build & Deploy | **Manter** EAS + GH Actions | Alta | 1-way-door |
| 11 | Product analytics | **Manter** PostHog | Alta | 1-way-door |
| 12 | Error tracking | **Adotar** Sentry (gap) | Alta | 1-way-door |

---

## Premissas e Riscos

### Premissas
1. Equipe segue com 2 devs e expertise primária em TypeScript/RN/Supabase — confirmado no codebase-context.md §2.
2. Mercado BR mantém crescimento de esportes de areia (+175% beach tennis 2021-2023) viabilizando 1.000 grupos pagantes/2026.
3. Stripe continua suportando PIX/Boleto BR sem mudança regulatória de pricing.
4. Supabase mantém plano Pro $25/mo + uso linear sem inflação súbita.
5. Evolution API (Baileys) continua funcional sem ban massivo de Meta nos próximos 12-18 meses `[VALIDAR — risco contínuo]`.

### Riscos Tecnológicos

| Risco | Probabilidade | Impacto | Mitigação |
|-------|---------------|---------|-----------|
| Ban WhatsApp via Evolution API (não-oficial) | Média | Alto | Monitorar instâncias; ter playbook de rotação de números; avaliar Cloud API quando Group Messaging API oficial sair |
| Lock-in Supabase em Auth/Storage | Baixa | Médio | Postgres puro + RLS são portáveis; Auth/Storage são as áreas mais acopladas e exigirão refactor caso saia da plataforma |
| Crashes em produção invisíveis até Sentry adoption | Alta agora | Alto | Priorizar épico-error-tracking logo após Stripe; bug em prod hoje só é detectado via reclamação manual |
| Custo PIX Stripe (1,49%) inviabilizar margem | Média | Médio | Monitor margem por tier; gatilho < 70% → migrar para Pagar.me |
| n8n Easypanel down trava onboarding (Magic Link OTP) | Média | Crítico | Migração para Edge Functions é épico-002, prioridade alta |
| NativeWind v5 atrasar suporte a New Architecture | Baixa | Médio | Avaliar Tamagui se RN 0.82+ chegar antes do v5 |

---

## Fontes

1. https://reactnative.dev/showcase — Expo+RN production users
2. https://flutter.dev/showcase — Flutter production users
3. https://tanstack.com/query — TanStack Query
4. https://swr.vercel.app — SWR
5. https://www.apollographql.com/customers — Apollo Client users
6. https://react-hook-form.com — React Hook Form
7. https://www.nativewind.dev — NativeWind
8. https://tamagui.dev — Tamagui
9. https://supabase.com/customers — Supabase customers
10. https://firebase.google.com/customers — Firebase customers
11. https://aws.amazon.com/amplify/customers/ — AWS Amplify customers
12. https://supabase.com/edge-functions — Supabase Edge Functions
13. https://n8n.io/case-studies/ — n8n case studies
14. https://www.inngest.com/customers — Inngest customers
15. https://github.com/EvolutionAPI/evolution-api — Evolution API
16. https://developers.facebook.com/docs/whatsapp/cloud-api — WhatsApp Cloud API
17. https://z-api.io/ — Z-API
18. https://stripe.com/customers — Stripe customers
19. https://pagar.me/clientes — Pagar.me clients
20. https://www.asaas.com/ — Asaas
21. https://docs.expo.dev/develop/unit-testing/ — Expo testing
22. https://maestro.mobile.dev/ — Maestro
23. https://docs.expo.dev/eas/ — EAS
24. https://posthog.com/customers — PostHog customers
25. https://sentry.io/customers/ — Sentry customers
