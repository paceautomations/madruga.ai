---
title: "Codebase Context"
updated: 2026-05-04
repo_sha: 09abf73
repo_branch: develop
---
# ResenhAI — Codebase Context

> Mapeamento brownfield gerado a partir de `paceautomations/resenhai-expo@09abf73`. Última atualização: 2026-05-04.

---

## 1. Status

`[BROWNFIELD]` — `package.json:66` declara `"expo": "~54.0.33"` e `app/_layout.tsx` segue Expo Router (file-based routing).

---

## 2. Resumo Executivo

App multi-plataforma (iOS/Android/Web) de gestão de futevôlei. Stack TypeScript 5.9 + React Native 0.81 + Expo SDK 54 + Supabase (Postgres + RLS). ~58k LOC produção (`app/`+`components/`+`services/`+`hooks/`+`lib/`+`utils/`+`contexts/`+`providers/`) + ~38k LOC testes (`__tests__/` Jest 1695 testes + `e2e/` Playwright 203 testes). 370 commits totais, 144 commits últimos 90d (2 contributors), HEAD em `2026-03-24`. 40 migrations Supabase aplicadas, 15 tabelas + 22 views analíticas em produção.

---

## 3. Repo Context

| Campo | Valor | Evidência |
|-------|-------|-----------|
| Org/Name | paceautomations/resenhai-expo | `platforms/resenhai/platform.yaml:repo` |
| Branch base | develop | `platform.yaml:repo.base_branch` |
| HEAD SHA | 09abf73 | `git rev-parse --short origin/develop` |
| Último commit | 2026-03-24T05:49:07-03:00 | `git log -1 --format=%cI origin/develop` |
| Total commits | 370 | `git rev-list --count origin/develop` |
| Contributors (90d) | 2 (gabrielhamu-srna 140, Gabriel Hamu 4) | `git shortlog -sn --since=90.days` |
| Commits (30d) | 0 | `git log --since=30.days origin/develop --oneline` |

> Sinal: zero commits últimos 30 dias, mas 144 nos 90d → atividade concentrada e depois pausada (último commit em Mar/2026).

---

## 4. Stack & Versões

| Categoria | Tecnologia | Versão | Evidência |
|-----------|-----------|--------|-----------|
| Linguagem | TypeScript | 5.9.2 | `package.json:118` |
| Framework UI | React Native + Expo SDK + Expo Router | RN 0.81.5 / Expo 54.0.33 / Router 6.0.23 | `package.json:66,81,93` |
| State server | TanStack Query (+persist) | 5.90 | `package.json:62` |
| Forms | React Hook Form + Zod | 7.66 / 4.1.12 | `package.json:92,102` |
| Styling | NativeWind + Tailwind CSS | 4.1 / 3.4 | `package.json:88,101` |
| Backend | Supabase (Postgres + Auth + Storage + Realtime + Edge Functions Deno) | client 2.80.0 / CLI 2.72.8 | `package.json:60,115`; `supabase/functions/whatsapp-webhook/index.ts` |
| Test | Jest 29.7 (unit) + Playwright 1.57 (E2E) | — | `package.json:106,111` |
| Analytics | PostHog (`posthog-react-native`) | 4.34 | `package.json:89` |
| Workflow externo | n8n Community (self-hosted Easypanel) | v2.x | `n8n_backend/*.json` (spec 007) |

---

## 5. Folder Structure

```text
resenhai-expo/
├── app/                  # Expo Router file-based — (auth)/, (app)/, (app)/(tabs)/, (app)/management/ (~14.9k LOC / 24 files)
├── components/           # Design system + dominio: common/ ui/ header/ resenha/ management/ (~11k LOC / 44 files)
├── services/             # Integrações: supabase/{client,auth,database,invites,logging,storage,userStatus,users}, whatsapp/sendMessage, analytics (~4.6k / 12)
├── hooks/                # React Query hooks + queryKeys factory (~5.7k / 28 files / 27 hooks)
├── lib/                  # design-system, validation (1.2k LOC), supabase helpers (~3k / 9 files)
├── utils/                # logger PII-masking + helpers (~1.4k / 11 files)
├── contexts/             # AppContext.tsx (~1.1k / 3 files)
├── providers/            # React Query persist provider (~600 LOC)
├── supabase/             # 40 migrations idempotentes + dumps (staging+prod) + functions/whatsapp-webhook (Deno) (~22.7k / 65 files)
├── n8n_backend/          # 4 workflows JSON: Magic Link OTP, Create User For Invite, WhatsappGroup_{New,Prod} + test_payloads.json
├── __tests__/            # Jest 1695 testes (~38k / 104 files, 10 subdirs)
├── e2e/                  # Playwright 203 testes (~13.6k / 51 files, 5 grupos)
├── scripts/              # db-sync.sh + tsx scripts (cleanup, seed, generate)
├── docker/               # Dockerfile + nginx.conf (deploy web Hostinger via SSH)
├── plugins/              # withForceLightMode (Expo config plugin)
└── .github/workflows/    # deploy-hostinger.yml, deploy-supabase.yml
```

---

## 6. Entrypoints

| Tipo | Comando/Arquivo | Evidência |
|------|----------------|-----------|
| Mobile dev | `npm run start` (ou `start:tunnel` para WSL2+iOS) | `package.json:6,7` |
| Web dev | `npm run web` | `package.json:12` |
| Mobile build | `eas build --platform <ios\|android>` | `package.json:13,14` ; `eas.json:6` |
| Web build | `npx expo export --platform web` | `package.json:26` |
| OTA update | `eas update --branch <production\|preview>` | `package.json:18,19` |
| App entry | `index.ts` → `app/_layout.tsx` | `package.json:4` ; `app/_layout.tsx` |
| Edge Function | `supabase/functions/whatsapp-webhook/index.ts` | `supabase/functions/whatsapp-webhook/index.ts` |
| DB sync | `npm run db:sync` (`bash scripts/db-sync.sh --all`) | `package.json:23` |
| Tests unit | `npm test` (Jest) | `package.json:28` |
| Tests E2E | `npm run test:e2e:batches` (Playwright) | `package.json:38` |

---

## 7. Data Schemas

Schema final extraído de `supabase/dumps/prod_schema.sql` (committed em git para tracking + AI context, conforme `CLAUDE.md:309-318`).

### Tabelas (15) — agrupadas por bounded context

- **Users & Auth** — `users` (extends `auth.users` via `handle_new_user`), `convites` (token), `pending_whatsapp_links` (TTL 30min auto-expire), `whatsapp_events` (audit)
- **Grupos** — `grupos`, `participantes_grupo`
- **Campeonatos & Jogos** — `campeonatos`, `participantes_campeonato`, `jogos`
- **Stats agregadas** — `user_stats_daily`, `user_stats_weekly`, `user_stats_camp`
- **Ops** — `tickets_suporte`, `logs_sistema`, `admin_audit_log`

### Views analíticas (22)

3 rankings (`ranking_geral`, `ranking_por_campeonato`, `ranking_por_campeonato_por_dia`) + 16 `vw_player_*` / `vw_duo_*` (chemistry, winrate, attendance, sangue_frio, rival_saldo etc.) + `vw_active_groups`, `vw_active_users`, `jogos_enriquecidos`. Lista completa em `prod_schema.sql:CREATE VIEW`.

### Backend metadata

| Aspecto | Valor | Evidência |
|---------|-------|-----------|
| Migrations aplicadas | 40 (idempotentes, regra em `CLAUDE.md:362`) | `supabase/migrations/` |
| RLS policies | 32 | `prod_schema.sql` (grep `CREATE POLICY`) |
| Funções/triggers | 48 | `prod_schema.sql` (grep `CREATE.*FUNCTION`) |
| Realtime habilitado | grupos | `supabase/migrations/20260304000000_enable_realtime_grupos.sql` |
| Tipos TS gerados | `types/database.ts` (linkado a staging) | `package.json:20` |

> Detalhe de colunas, FKs e invariantes vai para `engineering/domain-model.md`.

---

## 8. Integrações Externas

| Serviço | Função | Evidência |
|---------|--------|-----------|
| Supabase (DB+Auth+Storage+Realtime) | Backend principal — RLS, OTP custom, buckets `images/*`, canal Realtime `grupos` | `services/supabase/{client,auth,database,storage}.ts` ; migration `20260304_enable_realtime_grupos.sql` |
| Supabase Edge Functions (Deno) | Webhook WhatsApp (handlers + validators + types) | `supabase/functions/whatsapp-webhook/index.ts` (spec 008) |
| n8n (Easypanel self-hosted) | Workflow runner — Magic Link OTP, Create User For Invite, WhatsApp group sync | `n8n_backend/*.json` (spec 007) |
| WhatsApp Evolution API | Gateway — disparo de mensagens via n8n + Edge Function | `services/whatsapp/sendMessage.ts` + `WhatsappGroup_{New,Prod}.json` |
| PostHog (US Cloud) | Product analytics | `services/analytics.ts` + init em `app/_layout.tsx` ; `.env.example:17-18` |
| EAS (Build/Submit/Update) | Build iOS/Android, OTA, submit App Store + Google Play (service account JSON) | `eas.json` ; `package.json:13-19` ; `CLAUDE.md:281-283` |
| Stripe | **Planejado — próximo épico** (`006-stripe-pricing`); código ausente em `services/` `[VALIDAR]` na implementação | `CLAUDE.md:376-377` |

---

## 9. CI/CD & Deploy

| Pipeline | Trigger | Target | Evidência |
|----------|---------|--------|-----------|
| `deploy-hostinger.yml` | push `main`/`develop`; manual | Web via SSH + Docker (`docker/Dockerfile`+`nginx.conf`) | `.github/workflows/deploy-hostinger.yml:3-15` |
| `deploy-supabase.yml` | push paths-filtered em `migrations/`/`functions/`; manual | Supabase staging (`whpfdlkmjqznwhdhnvnd`) / prod (`awtlybgerwqbbaeddnkt`) | `.github/workflows/deploy-supabase.yml:3-21` |
| EAS Build/Submit/Update | manual via `npm run build\|submit\|update:*` | TestFlight, App Store, Google Play, OTA channels | `eas.json:6-46` ; `package.json:13-19` |

> Convenção: `develop` → staging (`dev.resenhai.com`); `main` → produção (`resenhai.com`) — `CLAUDE.md:303-305`.

---

## 10. Env & Secrets

Declarados em `.env.example` (sem valores):

- `EXPO_PUBLIC_ENVIRONMENT` — `.env.example:6` — switch staging/production
- `EXPO_PUBLIC_PRODUCTION_SUPABASE_URL` — `.env.example:9`
- `EXPO_PUBLIC_PRODUCTION_SUPABASE_ANON_KEY` — `.env.example:10`
- `EXPO_PUBLIC_STAGING_SUPABASE_URL` — `.env.example:13` (comentado)
- `EXPO_PUBLIC_STAGING_SUPABASE_ANON_KEY` — `.env.example:14` (comentado)
- `EXPO_PUBLIC_POSTHOG_API_KEY` — `.env.example:17`
- `EXPO_PUBLIC_POSTHOG_HOST` — `.env.example:18` (default `us.i.posthog.com`)

Secrets adicionais usados em scripts/CI mas **não em `.env.example`** (`[VALIDAR]`):
- `STAGING_DB_URL`, `PRODUCTION_DB_URL` — `CLAUDE.md:337` (requeridos por `scripts/db-sync.sh`)
- `SUPABASE_PROJECT_REF` — `package.json:21`
- Service account `resenhai-489819-cc95049ab312.json` — `eas.json:54` (Google Play)
- Apple-Specific Password — `CLAUDE.md:284` (login EAS para submit iOS)

---

## 11. Tests

| Aspecto | Valor | Evidência |
|---------|-------|-----------|
| Unit | Jest 29.7 + jest-expo + @testing-library/react-native — **1695 testes** em 10 subdirs (`unit`, `hooks`, `services`, `utils`, `components`, `contexts`, `providers`, `screens`, `supabase-functions`, `ui`) | `package.json:108-117` ; `CLAUDE.md:141` ; `__tests__/` (104 files, ~38k LOC) |
| E2E | Playwright 1.57 — **203 testes** em 5 grupos: auth (68), ui (79), responsive (26), a11y (16), perf (15) | `package.json:106` ; `CLAUDE.md:158-162` ; `e2e/` (51 files, ~13.6k LOC) |
| Coverage | Standard: 70% min / 80% novo / 90% critical (auth/payments/invites). Atual: `[VALIDAR]` — sem `lcov.info` committed | `CLAUDE.md:172-174` |

---

## 12. Decisões Pré-Existentes

Decisões encodadas pelo time em `CLAUDE.md` / `AGENTS.md` — fonte para `tech-research` e ADRs retroativos.

- **Stack**: RN + Expo + Supabase (PG + RLS), single codebase iOS/Android/Web — `CLAUDE.md:7`
- **State server**: React Query + `hooks/queryKeys.ts` factory (centralizado) — `CLAUDE.md:59,71-83`
- **Forms**: React Hook Form + Zod — `CLAUDE.md:60`
- **Platform branching**: extensões `.web.ts` / `.web.tsx`, Metro resolve por plataforma — `CLAUDE.md:64-65`
- **PII safety**: nunca logar raw IDs/emails/phones; usar `maskUserId/maskEmail/maskPhone` — `CLAUDE.md:117-125`
- **Design system**: tokens via `lib/design-system.ts`; nunca hardcoded colors — `CLAUDE.md:113,217`
- **Subscription cleanup**: cleanup mandatório em todo useEffect com Supabase Realtime — `CLAUDE.md:97-105`
- **Migrations idempotentes**: `IF NOT EXISTS` + `DO $$ ... END IF; $$` em ALTER/POLICY/PUBLICATION — `CLAUDE.md:362-366`
- **Coverage targets**: 70% mín, 80%+ novo, 90%+ critical (auth/payments/invites) — `CLAUDE.md:172-174`
- **Test impact discipline**: ao mudar função, atualizar testes; bug-fix começa com teste reproduzindo — `CLAUDE.md:130-134`
- **Types DB**: gerados sempre do **staging linkado** (`supabase gen types --linked`) — `CLAUDE.md:336`
- **EAS env switching**: `.env` local = staging; profiles em `eas.json` definem produção — `CLAUDE.md:296`
- **Spec-Kit workflow**: Constitution → Specify → Plan → Tasks → Implement — `AGENTS.md:30-35`

---

## 13. Hot Spots

Top 5 por LOC (arquivos de produção em `app/`, `services/`, `components/`, `lib/`):

| Arquivo | LOC | Sinal |
|---------|-----|-------|
| `app/(app)/management/resenha.tsx` | 2200 | God-screen — gestão de resenha (também #1 em churn) |
| `services/supabase/database.ts` | 1598 | Camada DB monolítica (todos CRUDs num arquivo) |
| `app/(app)/games/add.tsx` | 1397 | Tela de criação de jogo grande (~5x média) |
| `components/management/CreateChampionshipModal.tsx` | 1230 | Modal único com lógica completa de campeonato |
| `lib/validation.ts` | 1212 | Schemas Zod centralizados (esperado, mas auditável) |

Top 5 por churn em 90 dias (`origin/develop`, excluindo `.cursor/`, `.claude/`, `.specify/`, `specs/`, `docs/`, `dumps/`, `package-lock`):

| Arquivo | Commits 90d |
|---------|-------------|
| `app/(app)/management/resenha.tsx` | 18 |
| `package.json` | 16 |
| `app/(app)/profile/edit.tsx` | 16 |
| `app.json` | 15 |
| `components/management/CreateChampionshipModal.tsx` | 14 |
| `app/_layout.tsx` | 14 |
| `app/(auth)/set-password.tsx` | 12 |

---

## 14. Observações

- **God-screen `resenha.tsx`** — 2.2k LOC + 18 commits/90d → maior risco da base, combina UI de gestão + fluxo de resenha + regras de campeonato. Candidato a decomposição — `app/(app)/management/resenha.tsx:1-2200`.
- **DB monolítico `services/supabase/database.ts:1-1598`** — toda camada de acesso a dados num arquivo, sem separação por aggregate (grupos/jogos/users). Quebrar por bounded context vai ajudar `domain-model.md`.
- **n8n + Edge Functions coexistem (débito de consolidação)** — spec 007 começou em n8n, spec 008 migrou parte para Edge Functions Deno; hoje convivem: Magic Link OTP + Create User For Invite ainda em `n8n_backend/`, webhook WhatsApp já em `supabase/functions/whatsapp-webhook/`. Candidato a ADR de consolidação.
- **Stripe é o próximo épico** — spec `006-stripe-pricing` declarada (`CLAUDE.md:376-377`), código ausente em `services/`. Tabelas `plans`, `subscriptions`, `stripe_customers`, `invoices` ainda **não criadas**.
- **`[VALIDAR]` coverage atual** — sem `coverage/lcov.info` versionado; alvo `CLAUDE.md:172` é 70%, valor efetivo precisa medição em CI.
- **`[VALIDAR]` secrets fora de `.env.example`** — `STAGING_DB_URL`, `PRODUCTION_DB_URL`, `SUPABASE_PROJECT_REF`, Apple-Specific Password e service account Google Play são usados em `scripts/db-sync.sh`, `package.json:21`, `eas.json:54`, `CLAUDE.md:284` mas não documentados → fricção de onboarding.
- **Atividade pausada (30d)** — zero commits últimos 30d em `origin/develop` (último `2026-03-24`); confirma ausência de merge race ao iniciar novos épicos.
- **Tipos DB acoplados a staging** (`CLAUDE.md:336`) — `types/database.ts` gerado sempre do staging linkado; divergências staging↔prod (há 2 dumps separados) podem causar TS pass + runtime fail. Mitigação: comparar `staging_schema.sql` vs `prod_schema.sql` antes de épicos schema-touching.

---
handoff:
  from: codebase-map
  to: tech-research
  context: "Stack: TypeScript 5.9 + RN 0.81 + Expo 54 + Supabase. 11 integrações externas (8 ativas + 3 [VALIDAR]/planejadas). 13 decisões pré-existentes capturadas em CLAUDE.md/AGENTS.md (queryKeys, PII masking, design system, migrations idempotentes). Tech-research deve tratar a stack atual como default, focar em decisões pendentes (Stripe, consolidação n8n↔Edge Functions) e ADRs retroativos."
  blockers: []
  confidence: Alta
  kill_criteria: "Repo migra para outra stack primária OU base_branch muda OU >50% dos arquivos mapeados são deletados"
