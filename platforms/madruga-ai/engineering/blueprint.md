---
title: "Blueprint"
---
# Blueprint de Engenharia

Referencia tecnica consolidada da plataforma **Madruga AI — Architecture Documentation & Spec-to-Code System**: concerns transversais, requisitos de qualidade, topologia de deploy, mapa de dados e glossario.

> **Convencao**: esta pagina consolida o **O QUE** e **COMO**. Para o **POR QUE** de cada decisao, consulte os [ADRs](../decisions/).

---

## 1. Concerns Transversais

### 1.1 Autenticacao & Autorizacao

N/A — sistema local, single-operator. Autenticacao delegada ao Claude Code (API key gerenciada pelo CLI).

### 1.2 Seguranca & Safety

| Camada | Mecanismo | Latencia | ADR |
|--------|-----------|----------|-----|
| API Keys | Claude API key gerenciada pelo Claude Code CLI, nao exposta no codigo | N/A | — |
| Subprocess isolation | `claude -p` roda em env limpo (CLAUDECODE unset, temp config dir) | ~50ms overhead | ADR-010 |
| Circuit breaker | Suspende chamadas apos 5 falhas consecutivas, recovery em 5min | 0ms (check local) | ADR-011 |
| Path traversal | Obsidian bridge opera somente dentro do vault_path configurado | N/A | — |

### 1.3 Secrets & Encryption

API keys gerenciadas pelo Claude Code CLI (nao pelo Madruga AI). Nenhum secret armazenado no repo. `.env` no `.gitignore`.

### 1.4 Observabilidade

| Ferramenta | Papel | Integracao |
|------------|-------|------------|
| Portal Dashboard | Pipeline status visual (L1 + L2), Mermaid DAG, filtros por plataforma | Portal Astro, le SQLite |
| CLI `status` | Pipeline status em tabela + JSON | `platform.py status`, le SQLite |
| Python logging | Logs de operacoes CLI e scripts | platform.py, db.py, post_save.py |

### 1.5 Multi-Tenancy

N/A — sistema single-operator. Cada plataforma (`platforms/<name>/`) e um "tenant logico" mas sem isolamento de dados ou autenticacao.

### 1.6 Error Handling

| Cenario | Estrategia | Fallback |
|---------|------------|----------|
| Claude API timeout | Retry 3x com backoff exponencial (5s, 10s, 20s) | Fase marcada `failed`, epic fica `blocked` |
| Claude API rate limit | Circuit breaker abre apos 5 falhas, recovery em 300s | Pipeline pausado, slot liberado |
| Obsidian vault inacessivel | Skip do ciclo de polling, retry no proximo ciclo (60s) | Log warning, daemon continua |
| LikeC4 compilation error | Build abortado com mensagem descritiva | Artefatos nao atualizados, warning no log |
| GitHub API 429 | Backoff exponencial automatico | Retry ate 3x, depois falha |
| SQLite write lock | busy_timeout=5000ms (WAL mode) | Leituras concorrentes ok, writes serializados |
| Fase falha 3x consecutivas | Epic marcado `blocked` | Notificacao WhatsApp, requer intervencao |

---

## 2. Qualidade & NFRs

| # | Cenario | Metrica | Target | Mecanismo | Prioridade |
|---|---------|---------|--------|-----------|------------|
| Q1 | Portal build time | Tempo de SSG build | < 30s | Astro static build | Alta |
| Q2 | Storage ops | Overhead operacional | Zero (sem servidor) | SQLite WAL mode, file-based | Alta |
| Q3 | Extensibilidade | Plataformas suportadas | N ilimitado | Copier template + auto-discovery | Alta |
| Q4 | Idempotencia | Skills re-executaveis | Sem side effects em re-run | Check de pre-condicoes + overwrite | Media |
| Q5 | Versionamento | Tudo em Git | 100% artefatos versionados | Filesystem-first, zero lock-in | Alta |
| Q6 | Concorrencia SQLite | Writers paralelos | Sem SQLITE_BUSY | WAL mode + busy_timeout=5000ms | Media |
| Q7 | HMR dev experience | Editar .md/.likec4 e ver resultado | < 2s hot reload | Vite watch + symlinks + LikeC4 plugin | Media |

---

## 3. Deploy & Infraestrutura

### 3.1 Topologia

| Componente | Runtime | Porta/Protocolo | Scaling |
|------------|---------|-----------------|---------|
| Portal (Astro + Starlight) | Node.js 20+ | :4321 (dev) / SSG | Single instance |
| Platform CLI | Python 3.11+ | CLI | N/A |
| SQLite BD | SQLite 3 WAL mode | File (.pipeline/madruga.db) | Single writer, N readers |
| LikeC4 serve | Node.js (likec4 CLI) | :5173 (dev) | Single instance |
| Claude Code | CLI | Terminal | Single instance |

### 3.2 Ambientes

| Ambiente | Finalidade | Infra |
|----------|------------|-------|
| local | Desenvolvimento + producao | WSL2 Ubuntu, systemd service |
| staging | N/A | — |
| production | N/A (local = production) | — |

### 3.3 CI/CD

| Etapa | Ferramenta | Gate |
|-------|------------|------|
| Lint Python | ruff | Zero warnings |
| Testes | pytest (51 testes) | 100% pass |
| Portal build | `npm run build` | Build sem erros |
| Template tests | pytest (.specify/templates/) | 100% pass |
| Platform lint | `platform.py lint --all` | Estrutura valida |

---

## 4. Mapa de Dados & Privacidade

### 4.1 Fluxo de Dados Pessoais

N/A — sistema nao processa dados pessoais. Artefatos sao documentacao tecnica (markdown, YAML, JSON, .likec4). SQLite armazena metadata operacional (epic status, metricas, patterns).

### 4.2 Direitos do Titular

N/A — sem PII.

### 4.3 Compliance Checklist

N/A — sistema interno, single-operator, sem dados de terceiros.

---

## 5. Glossario

Remeter a Linguagem Ubiqua em business/vision.md:

| Termo | Definicao | Dominio |
|-------|-----------|---------|
| Platform | Unidade central de documentacao em `platforms/<name>/` | Core |
| Vision | Conjunto de artefatos de arquitetura de uma plataforma | Core |
| Epic | Folder autocontido `epics/NNN-slug/` com progressao pitch→spec→plan→tasks | Planning |
| Skill | Comando Claude Code em `.claude/commands/` | Tooling |
| SpeckitBridge | Compositor de skills interativas em prompts autonomos | Runtime |
| RECONCILE | Loop que compara diff vs arquitetura e auto-atualiza Vision | Runtime |
| AUTO marker | Marcador `<!-- AUTO:name -->` para conteudo auto-gerado | Pipeline |
| Drift score | Metrica 0.0-1.0 de divergencia implementacao vs arquitetura | Runtime |
| Wave | Unidade de execucao com subagent fresco (anti-context-rot) | Runtime |
| 1-way door | Decisao irreversivel que requer aprovacao humana | Decisions |
| 2-way door | Decisao reversivel, auto-aprovavel pelo daemon | Decisions |
| Constitution | Documento com regras que governam artefatos gerados | Governance |
