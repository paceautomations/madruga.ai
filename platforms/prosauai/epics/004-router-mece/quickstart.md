# Quickstart — Epic 004: Router MECE

**Date**: 2026-04-10
**Epic**: 004-router-mece

---

## Pre-requisitos

- Python 3.12+
- Redis 7 rodando localmente (porta 6379)
- Repo `paceautomations/prosauai` clonado com dependencias instaladas
- `tenants.yaml` configurado com pelo menos 1 tenant

## Setup Rapido

```bash
# 1. Entrar no repo externo
cd ~/repos/paceautomations/prosauai

# 2. Checkout do branch do epic
git checkout epic/prosauai/004-router-mece

# 3. Instalar dependencias (se necessario)
pip install -e ".[dev]"

# 4. Copiar config de exemplo
cp tenants.example.yaml tenants.yaml
# Editar tenants.yaml com valores reais ou de teste

# 5. Criar configs de roteamento
mkdir -p config/routing
# Os fixtures ariel.yaml e resenhai.yaml serao criados pelo epic
```

## Verificar Configuracao de Roteamento

```bash
# Verificar um arquivo de config
python -m prosauai.core.router.verify config/routing/ariel.yaml
# Output: ✓ config/routing/ariel.yaml: 9 rules loaded, 0 overlaps, default present

# Explicar qual regra casa para um cenario
python -m prosauai.core.router.verify --explain \
  --tenant pace-internal \
  --facts '{"channel": "individual", "from_me": false, "is_duplicate": false}'
# Output: Rule 'individual_support' (priority 100) matched: action=RESPOND
```

## Rodar Testes

```bash
# Todos os testes do router
pytest tests/unit/test_facts.py tests/unit/test_engine.py tests/unit/test_loader.py -v

# Property tests (exaustivo)
pytest tests/unit/test_mece_exhaustive.py -v

# Integration tests (fixtures reais do 003)
pytest tests/integration/test_captured_fixtures.py -v

# Todos de uma vez
pytest tests/ -v --tb=short
```

## Uso Programatico

```python
from prosauai.core.router import route
from prosauai.core.router.engine import RoutingEngine
from prosauai.core.router.loader import load_routing_config
from prosauai.core.router.matchers import MentionMatchers
from prosauai.core.router.engine import RespondDecision, DropDecision

# Carregar engine de um tenant
engine = load_routing_config(Path("config/routing/ariel.yaml"))

# Construir matchers de um tenant
matchers = MentionMatchers.from_tenant(tenant)

# Rotear uma mensagem (async)
decision = await route(message, redis, engine, matchers, tenant)

# Consumir a decisao (exhaustive match)
match decision:
    case RespondDecision(agent_id=aid):
        print(f"Respond with agent {aid}")
    case DropDecision(reason=reason):
        print(f"Dropped: {reason}")
    # ... demais subtipos
```

## Estrutura de Arquivos (apos implementacao)

```
prosauai/
├── core/
│   ├── router/
│   │   ├── __init__.py        # Public API: route()
│   │   ├── facts.py           # MessageFacts, enums, classify()
│   │   ├── matchers.py        # MentionMatchers value object
│   │   ├── engine.py          # RoutingEngine, Rule, Decision subtypes
│   │   ├── loader.py          # YAML loader + pydantic schema + overlap analysis
│   │   ├── verify.py          # CLI: router verify | explain
│   │   └── errors.py          # RoutingError, RoutingConfigError, AgentResolutionError
│   ├── inbound.py             # InboundMessage (renomeado de formatter.py ParsedMessage)
│   ├── tenant.py              # Tenant + default_agent_id
│   └── tenant_store.py        # TenantStore + _build_tenant atualizado
├── observability/
│   └── conventions.py         # +6 novas constantes (MATCHED_RULE, etc.)
├── api/
│   └── webhooks.py            # Migrado para route() + Decision match/case
└── main.py                    # Lifespan: carrega engines + matchers

config/
└── routing/
    ├── ariel.yaml             # 9 regras para tenant Ariel (pace-internal)
    └── resenhai.yaml          # N regras para tenant ResenhAI (resenha-internal)

tests/
├── unit/
│   ├── test_facts.py          # MessageFacts + classify()
│   ├── test_matchers.py       # MentionMatchers
│   ├── test_engine.py         # RoutingEngine + Decision
│   ├── test_loader.py         # YAML loader + overlap analysis
│   ├── test_mece_exhaustive.py # Property tests + reachability
│   └── test_verify.py         # CLI tests
└── integration/
    └── test_captured_fixtures.py  # 26 fixtures do 003 (atualizado)
```
