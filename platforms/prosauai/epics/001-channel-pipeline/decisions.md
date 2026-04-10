---
epic: 001-channel-pipeline
created: 2026-04-09
updated: 2026-04-09

---
# Registro de Decisoes — Epic 001

1. `[2026-04-09 epic-context]` Scaffold repo externo paceautomations/prosauai como primeira task do epic (ref: platform.yaml repo binding)
2. `[2026-04-09 epic-context]` Enum MessageRoute com 6 rotas incluindo HANDOFF_ATIVO stub que retorna IGNORE (ref: domain-model Channel BC)
3. `[2026-04-09 epic-context]` HMAC-SHA256 webhook validation obrigatoria desde dia 1 (ref: ADR-017)
4. `[2026-04-09 epic-context]` Redis Lua script atomico + keyspace notifications para debounce flush (ref: ADR-003, blueprint §4.6)
5. `[2026-04-09 epic-context]` Docker Compose apenas api + redis; Evolution API mockada em testes (ref: ADR-005 §hardening)
6. `[2026-04-09 epic-context]` Config via pydantic Settings + .env; Infisical em epic posterior (ref: ADR-017)
7. `[2026-04-09 epic-context]` Log estruturado (structlog) para msgs grupo sem @mention; zero DB nesta fase (ref: blueprint §1)
8. `[2026-04-09 epic-context]` Test fixtures com payloads reais capturados da Evolution API em tests/fixtures/ (ref: ADR-005)
9. `[2026-04-09 epic-context]` Processamento sincrono no webhook; sem ARQ worker nesta fase (ref: containers.md)
10. `[2026-04-09 epic-context]` RouteResult.agent_id presente desde dia 1 — None = tenant default (ref: domain-model Router aggregate)
11. `[2026-04-09 implement]` Dockerfile corrigido para copiar prosauai/__init__.py antes de `pip install .` — hatchling precisa do diretório do pacote para gerar metadata. Sem isso, build falhava com "Unable to determine which files to ship inside the wheel" (ref: T051)
