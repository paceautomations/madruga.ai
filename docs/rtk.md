# RTK — Rust Token Killer

**Repo**: https://github.com/rtk-ai/rtk

## O que é

RTK é um proxy CLI em Rust que fica entre agentes de IA (Claude Code, Copilot, Cursor, Gemini CLI, etc.) e o shell. O objetivo: **reduzir consumo de tokens em 60-90%** filtrando output de comandos antes de chegar ao contexto do LLM.

**O problema**: Agentes de IA rodam `git status`, `cargo test`, `npm install` constantemente. A maior parte do output é boilerplate — progress bars, ANSI codes, testes passando — que consome tokens sem valor. Exemplo: `git push` produz ~200 tokens de "Enumerating objects... Counting objects..."; RTK retorna `ok main` (~10 tokens).

**Stats**: 16k+ stars, Apache-2.0, single binary sem dependências runtime, startup < 10ms.

## Instalação e Uso

```bash
# Instalar
brew install rtk
# ou
curl -fsSL https://raw.githubusercontent.com/rtk-ai/rtk/refs/heads/master/install.sh | sh
# ou
cargo install --git https://github.com/rtk-ai/rtk

# Configurar hook automático
rtk init -g                     # Claude Code (default)
rtk init -g --copilot           # GitHub Copilot
rtk init -g --gemini            # Gemini CLI
rtk init -g --codex             # Codex
rtk init -g --agent cursor      # Cursor
rtk init --agent windsurf       # Windsurf
rtk init --agent cline          # Cline / Roo Code

# Uso direto
rtk git status          # status compacto
rtk cargo test          # só mostra falhas
rtk read file.rs        # leitura inteligente
rtk ls .                # tree otimizado
rtk grep "pattern" .    # resultados agrupados
rtk gain                # dashboard de economia
rtk discover            # oportunidades perdidas
rtk session             # métricas de adoção

# Flags globais
rtk -u git status       # ultra-compact mode
rtk -v cargo test       # verbosity level 1
rtk -vvv cargo test     # verbosity level 3 (debug)
```

## Arquitetura

### Ciclo de vida de um comando (6 fases)

1. **PARSE** — Clap CLI extrai comando, args e flags globais (verbose, ultra-compact)
2. **ROUTE** — `main.rs` faz match contra enum `Commands`, dispatch para módulo correto
3. **EXECUTE** — Spawna comando real via `std::process::Command`, captura stdout/stderr
4. **FILTER** — Aplica estratégia de filtragem específica do comando
5. **PRINT** — Output filtrado com debug info opcional por nível de verbosidade
6. **TRACK** — Registra tokens in/out em SQLite (`~/.local/share/rtk/history.db`)

### Estrutura do código

```
src/
  main.rs          # Entry point, Clap CLI, routing
  cmds/            # Filtros por ecossistema (42 módulos)
    git/ rust/ js/ python/ go/ dotnet/ cloud/ system/ ruby/
  core/            # Infra compartilhada (config, filter, tracking, tee, utils, telemetry)
  hooks/           # Hook installation/integrity/rewrite
  analytics/       # Dashboards read-only (gain, session)
  discover/        # Registry de rewrite (70+ patterns) + análise de sessão
  filters/         # 60+ filtros TOML declarativos
  learn/           # Detecção de correções CLI
  parser/          # Tipos canônicos (TestResult, LintResult, etc.)
```

**Regra de boundary**: Um módulo pertence a `cmds/` se e somente se executa um comando externo e filtra seu output. Infraestrutura que serve múltiplos módulos sem chamar comandos externos pertence a `core/`.

### Sistema de filtros em duas camadas

**Tier 1 — TOML declarativo** (`src/filters/*.toml`): Para filtragem simples baseada em regex. 60+ filtros com testes inline validados no build.

```toml
[filters.brew-install]
match_command = "^brew\\s+(install|upgrade)\\b"
strip_lines_matching = ["^==> Downloading", "^==> Pouring", "^###"]
match_output = [{ pattern = "already installed", message = "ok (already installed)" }]
max_lines = 20

[[tests.brew-install]]
name = "already installed short-circuits"
input = """Warning: rtk 0.27.1 is already installed..."""
expected = "ok (already installed)"
```

**Tier 2 — Rust modules** (`src/cmds/*/`): Para parsing complexo (JSON, NDJSON, state machines), injeção de flags, roteamento cross-command. Seguem o contrato de 6 fases.

**Critério de decisão**:

| Usar TOML | Usar Rust |
|-----------|-----------|
| Output previsível, line-by-line | Output estruturado (JSON, NDJSON) |
| Regex atinge 60%+ de economia | State machine parsing necessário |
| Sem injeção de flags CLI | Precisa injetar `--format json` |

**Build-time**: `build.rs` concatena todos `.toml` em um blob embutido no binário. Zero I/O em runtime. Detecta duplicatas e valida sintaxe no compile time.

### 12 Estratégias de Filtragem

| # | Estratégia | Economia | Exemplo |
|---|-----------|----------|---------|
| 1 | Stats Extraction | 90-99% | git status/log/diff |
| 2 | Error Only | 60-80% | Falhas de teste |
| 3 | Grouping by Pattern | 80-90% | lint, tsc, grep |
| 4 | Deduplication | 70-85% | Arquivos de log |
| 5 | Structure Only | 80-95% | Extração de JSON schema |
| 6 | Code Filtering | 0-90% | read com níveis: none/minimal/aggressive |
| 7 | Failure Focus | 94-99% | Test runners, só falhas |
| 8 | Tree Compression | 50-70% | ls, directory listings |
| 9 | Progress Filtering | 85-95% | wget, pnpm |
| 10 | JSON/Text Dual Mode | 80%+ | ruff, pip |
| 11 | State Machine Parsing | 90%+ | pytest |
| 12 | NDJSON Streaming | 90%+ | go test |

### 100+ Comandos Suportados

- **Git**: status, diff, log, add, commit, push, pull, branch
- **GitHub CLI**: pr, issue, run
- **Rust**: cargo test/build/clippy
- **JS/TS**: vitest, playwright, eslint/biome, tsc, next build, prettier, prisma, pnpm
- **Python**: pytest, ruff, pip, mypy
- **Go**: go test/build/vet, golangci-lint
- **Ruby**: rake, rspec, rubocop, bundle
- **.NET**: dotnet build/test, binlog
- **Cloud**: docker, kubectl, aws, curl, wget, psql
- **System**: ls, tree, read, grep, find, json, log, env, deps

### Hook System

O hook de auto-rewrite intercepta comandos Bash transparentemente e reescreve com prefixo `rtk` antes da execução. O LLM nunca vê o rewrite. Toda lógica de rewrite vive em um registry centralizado (`src/discover/registry.rs`) com 70+ patterns.

**10 integrações**: Claude Code (PreToolUse), GitHub Copilot, Cursor, Gemini CLI, Codex, Windsurf, Cline/Roo Code, OpenCode, OpenClaw.

### Tee Recovery

Em caso de falha, output bruto é salvo em arquivo de log. O LLM recebe um hint path e pode re-ler sem re-executar.

### Configuração

`~/.config/rtk/config.toml` com seções: tracking, display, filters, tee, telemetry, hooks, limits. Cada seção tem defaults sensíveis via `impl Default`.

## Melhores Práticas para o madruga.ai

### A. Filtros TOML declarativos com testes inline

Skills poderiam ter formato declarativo leve (YAML/TOML) para transformações simples, com testes inline validados no build. O `skill-lint.py` já faz validação estrutural — poderia evoluir para incluir assertions declarativas.

### B. Critérios claros "declarativo vs programático"

RTK documenta explicitamente quando usar TOML vs Rust. Para madruga.ai: documentar quando criar uma skill markdown vs um script Python vs um hook bash. Já temos os 3 mecanismos mas falta um decision matrix claro.

### C. Security scan no CI

RTK escaneia PRs por padrões perigosos (`Command::new("sh")`, `unsafe`, `.unwrap()`, rede) e gera warnings no GitHub Step Summary. Para madruga.ai: adicionar job que grepeia por `eval()`, `exec()`, `subprocess.call(shell=True)`, credenciais hardcoded. Custo baixo, valor alto.

### D. AI-powered doc review no CI

RTK usa Claude API com JSON schema output para validar se PRs incluem updates de docs necessários. Para madruga.ai: check automático "skill mudou → knowledge precisa atualizar?" como versão leve do reconcile no CI.

### E. Documentation-change matrix

RTK mapeia "o que mudou" → "que docs atualizar":

| Mudança no madruga.ai | Docs a atualizar |
|------------------------|-----------------|
| Nova skill | pipeline-dag-knowledge.md, CLAUDE.md, portal sidebar |
| Novo script | CLAUDE.md (Common Commands) |
| Nova migration | CLAUDE.md (Active Technologies) |
| Novo ecossistema/platform | portal LikeC4Diagram.tsx, platform.yaml |

### F. Fail-safe com fallback

Cada filtro RTK tem fallback para output bruto se falhar — nunca bloqueia o usuário. Para madruga.ai: `vision-build.py` e `post_save.py` poderiam adotar "tenta otimizado, fallback para bruto" mais consistentemente. Se parse do JSON falhar, continua com o que tem ao invés de abortar.

### G. Contrato uniforme enforced pela arquitetura

RTK enforce o contrato de 6 fases pela estrutura do código (tipos no compilador), não só pela documentação. No madruga.ai o contrato de 6 steps existe em `pipeline-contract-base.md` como instrução para o LLM. Evolução: enforçar steps via código no `dag_executor.py`.

## Priorização de Adoção

| Prática | Esforço | Valor | Próximo passo |
|---------|---------|-------|---------------|
| Documentation-change matrix | Baixo | Alto | Seção no CLAUDE.md |
| Security scan no CI | Baixo | Alto | Job no workflow existente |
| Dangerous patterns grep | Baixo | Médio | Script bash + CI job |
| Decision matrix declarativo vs script | Baixo | Médio | Seção no knowledge |
| Fail-safe fallback nos scripts | Médio | Alto | Refactor vision-build + post_save |
| AI doc review no CI | Médio | Alto | Job com Claude API |
| Testes inline nas skills | Alto | Alto | Evolução do skill-lint |
