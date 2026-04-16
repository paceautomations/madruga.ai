---
type: reconcile-report
epic: 007-admin-front-dashboard
platform: prosauai
date: 2026-04-15
drift_score: 33
docs_checked: 9
docs_current: 3
docs_outdated: 6
drift_items: 18
categories_scanned: [D1, D2, D3, D4, D5, D6, D7, D8, D9, D10]
---

# Reconcile Report — Epic 007: Admin Front — Dashboard Inicial

**Data:** 15/04/2026 | **Branch:** `epic/prosauai/007-admin-front-dashboard`
**Drift Score:** 33% (3/9 docs atuais)

---

## Resumo Executivo

O epic 007 introduz mudanças estruturais significativas: monorepo pnpm, autenticação JWT, dual asyncpg pools, frontend Next.js, e dbmate como migration tool. Essas mudanças causam drift em 6 dos 9 documentos verificados — principalmente no roadmap (resequenciamento de epics), solution-overview (features novos não documentados), containers (status atualizado), domain-model (entidades novas), ADRs (divergências formais) e context-map (nova integração admin).

**WARNING:** Verify deveria rodar antes de reconcile — `verify-report.md` não encontrado para este epic.

---

## Tabela de Saúde da Documentação

| Documento | Categorias | Status | Drift Items |
|-----------|-----------|--------|-------------|
| `business/solution-overview.md` | D1 | ❌ OUTDATED | 2 |
| `business/process.md` | D1 | ✅ CURRENT | 0 |
| `engineering/blueprint.md` | D2 | ❌ OUTDATED | 3 |
| `engineering/containers.md` | D3 | ❌ OUTDATED | 2 |
| `engineering/domain-model.md` | D4 | ❌ OUTDATED | 2 |
| `engineering/context-map.md` | D8 | ❌ OUTDATED | 1 |
| `planning/roadmap.md` | D6 | ❌ OUTDATED | 4 |
| `decisions/ADR-*.md` | D5, D10 | ⚠️ PARCIAL | 4 |
| `platforms/prosauai/README.md` | D9 | ⏭️ SKIP | 0 (não existe) |

---

## D1 — Scope Drift

### D1.1 — solution-overview.md: Epic 007 features ausentes da seção "Implementado"

**Severidade:** MEDIUM

**Estado atual no doc:** Seção "Implementado" lista epics 001–006. Epic 007 não existe.

**Estado esperado:** Adicionar seção "Epic 007 — Admin Front: Dashboard Inicial" com features implementados.

**Diff proposto:**

Adicionar após a seção "Epic 006 — Production Readiness":

```markdown
### Epic 007 — Admin Front: Dashboard Inicial

| Feature | Descricao | Epic |
|---------|-----------|------|
| **Monorepo pnpm** | Repositório reestruturado: `apps/api/` (FastAPI), `apps/admin/` (Next.js 15), `packages/types/` (tipos compartilhados). Workspaces pnpm | 007 |
| **Autenticação admin** | JWT HS256 via FastAPI, bcrypt (passlib), cookie `admin_token` (SameSite=Lax). Rate limiting 5/min por IP via slowapi + Redis | 007 |
| **Dashboard de mensagens** | Página `/admin` com gráfico de barras (mensagens/dia últimos 30d, cross-tenant) e KPI total. shadcn Chart + recharts | 007 |
| **Dual asyncpg pools** | `pool_tenant` (role `authenticated`, RLS enforced) + `pool_admin` (role `service_role`, BYPASSRLS). Separação de concern para queries admin vs pipeline | 007 |
| **dbmate migrations** | Substituiu `docker-entrypoint-initdb.d`. Migrations idempotentes com up/down, tracking via `schema_migrations` | 007 |
| **Admin bootstrap** | Primeiro admin criado via env vars (`ADMIN_BOOTSTRAP_EMAIL`/`PASSWORD`) no startup. Idempotente com ON CONFLICT | 007 |
| **Health check** | Endpoint `GET /health` verifica DB + Redis, retorna status detalhado | 007 |
| **Audit log** | Tabela `audit_log` registra eventos de autenticação: login_success, login_failed, rate_limit_hit | 007 |
```

### D1.2 — solution-overview.md: "Painel de controle" deve sair de "Next" e ir para "Implementado"

**Severidade:** LOW

**Estado atual no doc:** Seção "Next — Candidatos" lista "Painel de controle — Dashboard com conversas, métricas de resolução, configuração de agentes".

**Estado esperado:** Mover para "Implementado" (parcial) ou atualizar descrição para refletir que a fundação (dashboard com volume de mensagens) já existe, restando conversas, métricas de resolução, e config de agentes.

**Diff proposto:** Atualizar a linha na seção "Next":

```markdown
# Antes:
| **Painel de controle** | Dashboard com conversas, metricas de resolucao, configuracao de agentes | Dono da PME gerencia tudo sozinho |

# Depois:
| **Painel de controle (expansão)** | Fundação entregue (epic 007: login, dashboard volume mensagens). Próximo: conversas, métricas de resolução, configuração de agentes | Dono da PME gerencia tudo sozinho |
```

---

## D2 — Architecture Drift

### D2.1 — blueprint.md: Estrutura monorepo não documentada

**Severidade:** MEDIUM

**Estado atual no doc:** Blueprint referencia folder structure como `core/`, `conversation/`, `safety/`, etc. (layout flat, sem monorepo).

**Estado esperado:** Documentar que o repositório é agora um monorepo pnpm com `apps/api/` (FastAPI — contém os módulos existentes) e `apps/admin/` (Next.js 15). A estrutura interna da API (`core/`, `conversation/`, etc.) permanece dentro de `apps/api/prosauai/`.

**Diff proposto:** Na seção "Folder Structure" do blueprint, adicionar prefixo monorepo:

```markdown
# Antes (layout flat):
core/          # Domain core
conversation/  # LLM pipeline
...

# Depois (monorepo pnpm):
apps/
  api/prosauai/     # FastAPI backend
    core/           # Domain core
    conversation/   # LLM pipeline
    admin/          # NOVO: rotas /admin/*
    auth/           # NOVO: módulo autenticação JWT
    health.py       # NOVO: endpoint /health
    ...
  admin/src/        # NOVO: Next.js 15 App Router
    app/admin/      # Páginas admin (login, dashboard)
    components/     # shadcn/ui + dashboard components
    lib/            # API client, auth provider
packages/
  types/            # @prosauai/types (gerado do OpenAPI)
pnpm-workspace.yaml
docker-compose.yml
```

### D2.2 — blueprint.md: dbmate como migration tool não documentado

**Severidade:** MEDIUM

**Estado atual no doc:** Blueprint menciona "Migration runner" (Python asyncpg, epic 006) como ferramenta de migrations.

**Estado esperado:** Documentar que dbmate substituiu o migration runner Python a partir do epic 007. dbmate é single-binary Go, idempotente, com tracking via `schema_migrations`.

**Diff proposto:** Na seção de NFRs/infra do blueprint, adicionar:

```markdown
- **Migrations**: dbmate (Go binary) — substitui migration runner Python (epic 006). Formato SQL com `-- migrate:up` / `-- migrate:down`. Idempotente. Tracking via `schema_migrations`
```

### D2.3 — blueprint.md: Módulos auth/ e admin/ não listados

**Severidade:** LOW

**Estado atual no doc:** Blueprint lista módulos: `core/`, `conversation/`, `safety/`, `tools/`, `api/`, `channels/`, `db/`, `ops/`, `observability/`, `core/router/`.

**Estado esperado:** Adicionar `auth/` (JWT, passwords, bootstrap, dependencies) e `admin/` (router, auth_routes, metrics_routes) à lista de módulos.

---

## D3 — Container Model Drift

### D3.1 — containers.md: prosauai-admin status desatualizado

**Severidade:** MEDIUM

**Estado atual no doc:** `prosauai-admin (:3000)` listado como "planejado" com capabilities: dashboard, conversation viewer, prompt manager, handoff queue.

**Estado esperado:** Status = "operacional (fundação)". Capabilities implementadas neste epic: login, dashboard volume mensagens. Conversation viewer, prompt manager, handoff queue continuam planejados.

**Diff proposto:**

```markdown
# Antes:
| prosauai-admin (:3000) | dashboard, conversation viewer, prompt manager, handoff queue | planejado |

# Depois:
| prosauai-admin (:3000) | **login, dashboard volume mensagens** (operacional — epic 007). Planejado: conversation viewer, prompt manager, handoff queue | operacional (fundação) |
```

### D3.2 — containers.md: Comunicação API → Admin não detalhada

**Severidade:** LOW

**Estado atual no doc:** Comunicação entre containers não inclui Admin ↔ API (CORS, cookie-based auth).

**Estado esperado:** Adicionar relação: `prosauai-admin → prosauai-api`: REST via `/admin/*` (cookie JWT, CORS com `ADMIN_FRONTEND_ORIGIN`).

---

## D4 — Domain Model Drift

### D4.1 — domain-model.md: Entidades admin_users e audit_log ausentes

**Severidade:** HIGH

**Estado atual no doc:** Domain model lista 5 bounded contexts (Channel, Conversation, Safety, Operations, Observability). Nenhum bounded context "Admin" existe. Tabelas `admin_users` e `audit_log` não aparecem.

**Estado esperado:** Adicionar entidades ao domain model:

- **admin_users**: id (UUID PK), email (UNIQUE), password_hash, is_active, created_at, last_login_at. Schema: `public` (ADR-024 drift — deveria ser `admin` mas não aplicado).
- **audit_log**: id (UUID PK), action (VARCHAR — login_success/login_failed/rate_limit_hit/logout), actor_id (FK admin_users, nullable), ip_address (INET), details (JSONB), created_at. Schema: `public`.

**Nota:** Essas entidades pertencem a um bounded context "Admin" (ou "Operations" ampliado). O domain model deve registrar onde vivem e seus invariantes (email único, audit append-only, bootstrap idempotente).

### D4.2 — domain-model.md: Índice idx_messages_created_at não documentado

**Severidade:** LOW

**Estado atual no doc:** Tabela `messages` listada sem índice em `created_at`.

**Estado esperado:** Adicionar `CREATE INDEX idx_messages_created_at ON messages(created_at DESC)` — necessário para query de agregação cross-tenant do dashboard admin.

---

## D5 — Decision Drift

### D5.1 — ADR-010: Divergência implementada (JWT+bcrypt vs Supabase Auth)

**Severidade:** HIGH

**Estado atual no ADR:** ADR-010 especifica "Socket.io para real-time no handoff inbox" e implica Supabase Auth como provider.

**Estado implementado:** Epic 007 usa JWT HS256 via PyJWT + bcrypt (passlib). Sem Supabase Auth. Sem Socket.io (não necessário para dashboard).

**Ação proposta:** **AMEND** — ADR-010 continua válida para stack frontend (Next.js + shadcn/ui), mas auth e real-time devem ter exceção documentada:

```markdown
## Amendment (Epic 007 — 2026-04-15)
- **Auth**: JWT HS256 via PyJWT substituiu Supabase Auth (GoTrue) para fase 0 (~3 users em Tailscale). Migração para GoTrue planejada como follow-up.
- **Real-time**: Socket.io adiado — não necessário para dashboard de métricas. Implementação prevista para epic de conversations/handoff.
```

### D5.2 — ADR-022: Divergência implementada (JWT vs X-Admin-Token)

**Severidade:** MEDIUM

**Estado atual no ADR:** ADR-022 especifica auth via `X-Admin-Token` (master token estático) para Fase 2. Status: Proposed.

**Estado implementado:** Epic 007 usa JWT HS256 com identidade (admin_id, email) em cookie. Mais seguro que token estático (audit trail por admin). Rate limiting por IP.

**Ação proposta:** **SUPERSEDE** — A decisão de auth evoluiu significativamente. Propor nova ADR:

```markdown
# Header para nova ADR
Title: ADR-026: Admin Auth JWT HS256 (substitui abordagem X-Admin-Token do ADR-022)
Status: Proposed
Supersedes: ADR-022 (parcialmente — apenas seção de auth; endpoints CRUD tenants ainda não implementados)
```

**Nota:** A nova ADR deve ser gerada pelo skill `/madruga:adr`, não neste report.

### D5.3 — ADR-024: Drift confirmado (tabelas em public, não em admin)

**Severidade:** MEDIUM

**Estado atual no ADR:** ADR-024 reserva schema `admin` para "tenants, audit_log — epic 013".

**Estado implementado:** Epic 007 cria `admin_users` e `audit_log` em schema `public`. Decisão #6 do epic-context documenta isso como drift intencional — cleanup vira epic separado.

**Ação proposta:** **AMEND** — Adicionar nota ao ADR-024:

```markdown
## Amendment (Epic 007 — 2026-04-15)
- Tabelas `admin_users` e `audit_log` criadas em `public` (não em `admin`). Drift intencional documentado na decisão #6 do epic 007. Migração para schema `admin` planejada como epic de cleanup.
- Schema `admin` continua reservado para consolidação futura.
```

### D5.4 — Decisão #14: dbmate sem ADR formal

**Severidade:** MEDIUM

**Estado atual:** Decisão #14 do decisions.md registra adoção de dbmate como migration tool. Nenhum ADR cobre essa decisão.

**Estado esperado:** Decisão de migration tool é arquitetural (afeta todos os epics futuros, substitui ferramenta existente). Deve ter ADR.

**Ação proposta:** Rodar `/madruga:adr` para criar ADR-026 (ou próximo número disponível) documentando:
- Decisão: dbmate (Go binary) como migration tool
- Substitui: migration runner Python (epic 006)
- Alternativas: Alembic, Flyway, golang-migrate

---

## D6 — Roadmap Drift

### D6.1 — Resequenciamento: 007 é Admin Dashboard, não Configurable Routing

**Severidade:** HIGH

**Estado atual no doc:** Roadmap diz `007: Configurable Routing (DB) + Groups` com status "sugerido". `011: Admin Dashboard` com status "sugerido".

**Estado real:** Epic 007 é "Admin Front: Dashboard Inicial". Configurable Routing foi empurrado para 008+. Decisão #1 do decisions.md.

**Diff proposto para Epic Table:**

```markdown
# Antes:
| 7 | 007: Configurable Routing (DB) + Groups | 004, 006 | baixo | Post-MVP | sugerido — escopo reduzido pelo 004 |
| 11 | 011: Admin Dashboard | 008 | medio | Admin | sugerido |

# Depois:
| 7 | 007: Admin Front — Dashboard Inicial | 006 | baixo | Admin | **shipped** (56 tasks, 824 testes unit, judge 85%, QA 87%) |
| 8 | 008: Configurable Routing (DB) + Groups | 004, 007 | baixo | Post-MVP | sugerido — escopo reduzido pelo 004 |
```

### D6.2 — Epic Table: Status e métricas do 007

**Severidade:** HIGH

**Estado atual:** Epic 007 ausente como "Admin Dashboard". Linha 007 diz "Configurable Routing".

**Estado esperado:** Epic 007 = Admin Front Dashboard Inicial, status **shipped** ou **in_progress** (conforme estado real). Métricas: 56 tasks, 824 testes unit, judge 85%, QA 87%.

### D6.3 — Milestones: "Admin" milestone atualizar

**Severidade:** MEDIUM

**Estado atual no doc:** Milestone "Admin" = epics 011-012. Critério: "Dashboard + fila de atendimento humano funcionais". Estimativa: ~3 semanas.

**Estado esperado:** Milestone "Admin" deve refletir que 007 (Dashboard fundação) está shipped. Epics restantes do milestone Admin: Handoff Inbox + expansão dashboard. Numeração reajustada.

### D6.4 — Gantt chart: Desatualizado

**Severidade:** MEDIUM

**Estado atual no doc:** Gantt mostra `007 Configurable Routing` e `011 Admin Dashboard` como blocos separados.

**Estado esperado:** Gantt atualizado com 007=Admin Dashboard (done), numeração subsequente ajustada.

**Diff proposto consolidado para roadmap.md:**

Atualizar seções: Status, Epic Table, Gantt, Milestones, Dependencies, e adicionar ao bloco de riscos:

```markdown
## Status (atualizar)
**L2 Status:** ... Epic 007 shipped (Admin Front Dashboard — 56 tasks, 824 testes unit, judge 85%, QA 87%).
**Próximo:** epic 008 (Configurable Routing DB + Groups) ou epic 009 (Agent Tools).

## Riscos (adicionar)
| Risco | Status | Impacto | Prob | Mitigação |
| ADR-024 drift (tabelas admin em public) | Ativo | Baixo | Alta | Cleanup planejado como epic separado. Funcional em public |
| Cookie JWT non-httpOnly | Ativo | Baixo | Baixa | Escopo Tailscale (~3 users). Migração com GoTrue |
```

---

## D7 — Future Epic Impact

Nenhum epic futuro possui pitch file criado além de 001–007. Análise baseada nas descrições do roadmap:

| Epic | Premissa no Roadmap | Impacto do 007 | Ação |
|------|--------------------|--------------------|------|
| 008 (Configurable Routing) | Deps: 004, 006. Sem menção a monorepo. | Baixo — deve considerar estrutura monorepo (`apps/api/`) | Nenhuma |
| 009 (Handoff Engine) | Deps: 006. | Baixo — pode usar `pool_admin` para queries cross-tenant de handoff | Nenhuma |
| 011→agora TBD (Admin Handoff Inbox) | Deps: 009. Assume admin dashboard existe. | **Positivo** — 007 entrega a fundação (monorepo, auth, layout admin). Inbox é incremental | Atualizar deps: depende de 007+009 |
| 013 (Public API Fase 2) | ADR-022: auth via X-Admin-Token. | **Afetado** — 007 implementou JWT, não X-Admin-Token. ADR-022 precisa amendment | Amend ADR-022 |

**Conclusão:** Nenhum epic futuro é bloqueado. Epic 013 precisa considerar que auth admin já é JWT (não token estático).

---

## D8 — Integration Drift

### D8.1 — context-map.md: Admin API não documentada

**Severidade:** MEDIUM

**Estado atual no doc:** Context map lista 5 bounded contexts sem "Admin". Relações não incluem Admin ↔ Conversation (admin consulta messages cross-tenant).

**Estado esperado:** Adicionar relação ou nota:

```markdown
# Admin → Conversation (Customer-Supplier)
- Admin consome dados de `messages` via `pool_admin` (BYPASSRLS) para dashboard de métricas.
- Padrão: Customer-Supplier (Admin é downstream, Conversation é upstream).
- Protocolo: SQL direto via asyncpg (não API).
```

---

## D9 — README Drift

⏭️ SKIP — `platforms/prosauai/README.md` não existe.

---

## D10 — Epic Decision Drift

22 decisões registradas em `decisions.md`. Análise:

### Contradições com ADRs

| # | Decisão | ADR | Contradição? | Ação |
|---|---------|-----|-------------|------|
| 7 | JWT HS256 PyJWT | ADR-010 (Supabase Auth implícito), ADR-022 (X-Admin-Token) | ✅ SIM | Amend ADR-010, Supersede ADR-022 auth (ver D5.1, D5.2) |
| 6 | Tabelas em public | ADR-024 (schema admin reservado) | ✅ SIM | Amend ADR-024 (ver D5.3) |
| 14 | dbmate | Nenhum ADR | ❌ Gap | Criar ADR (ver D5.4) |

### Candidatos a promoção para ADR

| # | Decisão | Afeta mais de 1 epic? | Constrains futuro? | 1-way-door? | Promover? |
|---|---------|----------------------|--------------------|-----------|---------:|
| 14 | dbmate como migration tool | ✅ Todos epics futuros | ✅ Formato de migrations | Sim | ✅ SIM |
| 4 | Dual asyncpg pools | ✅ Todos epics com admin queries | ✅ Pattern de acesso DB | Não (aditivo) | ⚠️ CONSIDERAR |
| 21 | app.state.pg_pool alias backward compat | Não | Não | Não | ❌ NÃO |

### Staleness check

| # | Decisão | Refletida no código? | Stale? |
|---|---------|---------------------|--------|
| 8 | slowapi 5/min por IP+email | ⚠️ Parcial — implementado IP-only (judge finding #2) | Parcialmente stale |
| 9 | Cookie não-httpOnly | ✅ Implementado conforme | Atual |
| 19 | CREATE INDEX sem CONCURRENTLY | ✅ Documentado na migration | Atual |
| 22 | Route group (authenticated) | ✅ Implementado no Next.js | Atual |

**Ação para #8:** Atualizar decisions.md #8 para refletir que rate limit é IP-only (não IP+email) por limitação do slowapi. Adicionar nota sobre follow-up.

---

## Raio de Impacto

| Área Alterada | Docs Diretamente Afetados | Docs Transitivamente Afetados | Esforço |
|---------------|--------------------------|------------------------------|---------|
| Monorepo (estrutura repo) | blueprint.md | containers.md (paths) | M |
| Auth admin (JWT, bootstrap) | ADR-010, ADR-022 | context-map.md | M |
| Tabelas admin (admin_users, audit_log) | domain-model.md, ADR-024 | — | S |
| Dashboard (features novos) | solution-overview.md | — | S |
| Resequenciamento epics | roadmap.md | — | L |
| dbmate (migration tool) | blueprint.md | — | S (ADR) |
| Dual pools | ADR-011 | blueprint.md | S |

---

## Revisão do Roadmap (Obrigatória)

### Epic Status Table

| Campo | Planejado (roadmap) | Real (epic 007) | Drift? |
|-------|--------------------|--------------------|--------|
| Número | 007 = Configurable Routing | 007 = Admin Front Dashboard | ✅ Resequenciado |
| Status | sugerido | shipped (ou in_progress) | ✅ Atualizar |
| Milestone | Post-MVP | Admin | ✅ Mudou de milestone |
| Appetite | N/A (sugerido) | 3 semanas | ✅ Adicionar |
| Deps | 004, 006 | 006 | ✅ Diferente |
| Riscos | — | ADR-024 drift, cookie non-httpOnly | ✅ Adicionar |

### Dependências Descobertas

| De | Para | Tipo | Descoberta |
|----|------|------|-----------|
| 007 (Admin Dashboard) | Qualquer epic futuro admin | Estrutural | Monorepo + auth + layout admin são fundação |
| Futuro Handoff Inbox | 007 + 009 | Funcional | Inbox precisa de auth + layout do 007 |
| 013 (Public API) | 007 | Auth | JWT substitui X-Admin-Token planejado no ADR-022 |

### Status de Riscos

| Risco (do roadmap) | Status |
|--------------------|--------|
| Evolution API payload muda | Não impactado pelo 007 |
| Custo LLM | Não impactado pelo 007 |
| Schema collision Supabase | **Agravado parcialmente** — tabelas em `public` (ADR-024 drift). Cleanup necessário |
| Disco VPS cheio | Não impactado — audit_log append-only, mas sem retention policy. **Novo risco menor** |

### Novos Riscos Identificados

| Risco | Impacto | Probabilidade | Mitigação |
|-------|---------|---------------|-----------|
| audit_log crescimento ilimitado (sem retention) | Baixo | Média | Adicionar política de retenção em epic futuro (QA finding) |
| Cookie JWT non-httpOnly (XSS) | Baixo | Baixa | Escopo Tailscale. Migrar com GoTrue |
| Roles DB sem password (migration 001) | Médio | Baixa | Verificar se Supabase gerencia. Se não, adicionar passwords |

### Diffs Concretos para roadmap.md

**1. Status (linha 17):**
```markdown
# Antes:
**Proximo marco:** primeiro deploy de producao VPS. Post-MVP: epic 007 (Configurable Routing DB + Groups).

# Depois:
**L2 Status:** ... Epic 007 shipped (Admin Front Dashboard Inicial — monorepo pnpm, auth JWT, dashboard mensagens/dia, dual asyncpg pools, dbmate — 56 tasks, 824 testes unit, judge 85%, QA 87%).
**Proximo marco:** primeiro deploy de producao VPS. Post-MVP: epic 008 (Configurable Routing DB + Groups).
```

**2. Epic Table (linhas 73-78):** Renumerar conforme resequenciamento. Epic 007 = Admin Dashboard (shipped). Antigo 007 (Configurable Routing) → 008. Renumerar subsequentes.

**3. Gantt:** Atualizar bloco `007` para `Admin Front Dashboard (DONE)`, mover `Configurable Routing` para `008`.

**4. Milestones:** "Admin" milestone agora inclui 007 (parcialmente entregue).

---

## Propostas de Atualização

| # | ID | Cat | Doc Afetado | Estado Atual | Estado Esperado | Severidade |
|---|-----|-----|------------|--------------|-----------------|------------|
| 1 | D1.1 | Scope | solution-overview.md | Epic 007 features ausentes | Adicionar seção epic 007 | MEDIUM |
| 2 | D1.2 | Scope | solution-overview.md | "Painel de controle" em Next | Marcar como parcialmente implementado | LOW |
| 3 | D2.1 | Arch | blueprint.md | Folder structure sem monorepo | Adicionar estrutura monorepo | MEDIUM |
| 4 | D2.2 | Arch | blueprint.md | dbmate não documentado | Documentar como migration tool | MEDIUM |
| 5 | D2.3 | Arch | blueprint.md | Módulos auth/ e admin/ ausentes | Adicionar à lista de módulos | LOW |
| 6 | D3.1 | Model | containers.md | prosauai-admin planejado | Atualizar para operacional (fundação) | MEDIUM |
| 7 | D3.2 | Model | containers.md | Comunicação admin↔api ausente | Adicionar relação REST/cookie | LOW |
| 8 | D4.1 | Domain | domain-model.md | Entidades admin ausentes | Adicionar admin_users + audit_log | HIGH |
| 9 | D4.2 | Domain | domain-model.md | Índice messages ausente | Documentar idx_messages_created_at | LOW |
| 10 | D5.1 | Decision | ADR-010 | Sem amendment | Amend: JWT HS256, sem Socket.io | HIGH |
| 11 | D5.2 | Decision | ADR-022 | Auth X-Admin-Token | Supersede auth section: JWT HS256 | MEDIUM |
| 12 | D5.3 | Decision | ADR-024 | Schema admin reservado | Amend: tabelas em public (drift intencional) | MEDIUM |
| 13 | D5.4 | Decision | Nenhum ADR | dbmate sem ADR | Criar ADR para migration tool | MEDIUM |
| 14 | D6.1 | Roadmap | roadmap.md | 007=Configurable Routing | 007=Admin Dashboard (shipped) | HIGH |
| 15 | D6.2 | Roadmap | roadmap.md | Métricas 007 ausentes | Adicionar métricas shipped | HIGH |
| 16 | D6.3 | Roadmap | roadmap.md | Milestone Admin = 011-012 | Incluir 007 no milestone | MEDIUM |
| 17 | D6.4 | Roadmap | roadmap.md | Gantt desatualizado | Atualizar sequência | MEDIUM |
| 18 | D8.1 | Integration | context-map.md | Admin API ausente | Adicionar relação Admin→Conversation | MEDIUM |

---

## Impacto em Epics Futuros

| Epic | Premissa no Pitch/Roadmap | Como Afetado | Impacto | Ação Necessária |
|------|--------------------------|-------------|---------|-----------------|
| 013 (Public API) | Auth via X-Admin-Token (ADR-022) | JWT HS256 já implementado | Médio | Amend ADR-022; 013 deve estender JWT, não criar token estático |
| Handoff Inbox | Depende de dashboard admin | Fundação entregue pelo 007 | Positivo | Atualizar deps no roadmap |
| Cleanup ADR-024 | Tabelas em schemas corretos | admin_users/audit_log em public | Baixo | Registrar como epic futuro |
| Auth GoTrue | Cookie httpOnly + refresh | Cookie non-httpOnly intencional | Baixo | Follow-up documentado |

---

## Auto-Review

### Tier 1 — Checks Determinísticos

| # | Check | Resultado |
|---|-------|-----------|
| 1 | Report file exists and is non-empty | ✅ PASS |
| 2 | All 10 drift categories scanned (D1-D10) | ✅ PASS |
| 3 | Drift Score computed | ✅ PASS — 33% (3/9 docs current) |
| 4 | No placeholder markers remain | ✅ PASS |
| 5 | HANDOFF block present at footer | ✅ PASS |
| 6 | Impact radius matrix present | ✅ PASS |
| 7 | Roadmap review section present | ✅ PASS |

### Tier 2 — Scorecard

| # | Item | Self-Assessment |
|---|------|-----------------|
| 1 | Every drift item has current vs expected state | ✅ Yes |
| 2 | Roadmap review completed with actual vs planned | ✅ Yes |
| 3 | ADR contradictions flagged with recommendation (amend/supersede) | ✅ Yes — 3 amends, 1 supersede propostos |
| 4 | Future epic impact assessed (top 4) | ✅ Yes |
| 5 | Concrete diffs provided (not vague descriptions) | ✅ Yes — diffs com antes/depois |
| 6 | Trade-offs explicit for each proposed change | ⚠️ Parcial — trade-offs implícitos na maioria |
| 7 | Confidence level stated | ✅ Alta — drift é factual |

---

## Gate: Human

**Resumo para aprovação:**

- **18 propostas de atualização** (4 HIGH, 9 MEDIUM, 5 LOW)
- **3 ADR amendments** propostos (ADR-010, ADR-022, ADR-024)
- **1 nova ADR** necessária (dbmate)
- **Roadmap requer resequenciamento completo** (maior mudança)
- **Nenhum epic futuro bloqueado**

**Recomendação:** Aprovar todas as 18 propostas. As de HIGH severidade (D4.1, D5.1, D6.1, D6.2) devem ser aplicadas primeiro.

**WARNING:** verify-report.md não encontrado. Recomenda-se rodar `/madruga:judge` (que substituiu verify) antes de aplicar mudanças.

---
handoff:
  from: madruga:reconcile
  to: madruga:roadmap
  context: "Reconcile detectou 18 drift items (33% docs atuais). Principal drift: resequenciamento de epics no roadmap (007=Admin Dashboard em vez de Configurable Routing). 3 ADR amendments + 1 nova ADR (dbmate) propostos. Roadmap reassess necessário para refletir epic 007 shipped e re-priorizar epics 008+."
  blockers: []
  confidence: Alta
  kill_criteria: "Se as propostas de amendment dos ADRs (010, 022, 024) forem rejeitadas, o drift entre docs e código se torna permanente e afetará todos os epics futuros que referenciem esses ADRs."
