---
title: 'ADR-029: Model cost pricing table as code constant (v1)'
status: Accepted
decision: Hardcode MODEL_PRICING dict in apps/api/prosauai/conversation/pricing.py
  with per-model (input, output) $/1k token rates. Promote to DB table when >3
  active models OR when price change cadence exceeds 1/quarter.
alternatives: Editable DB table (public.model_pricing), External SaaS (helicone,
  openai.com/pricing API), Per-tenant overrides via tenants.config JSONB
rationale: v1 has 2–3 active models (gpt-4o, gpt-4o-mini, gpt-5-mini/5.4-mini).
  Prices change infrequently (~1–2x/year from providers). Code constant is PR-diffable,
  auditable, and costs zero operational complexity. Migration path is a 30-line
  change when the trigger conditions are met.
---
# ADR-029: Model cost pricing table as code constant (v1)

**Status:** Accepted | **Data:** 2026-04-17 | **Relaciona:** [ADR-025](ADR-025-gpt5-4-mini-default-model.md), [ADR-012](ADR-012-consumption-billing.md)

> **Escopo:** Epic 008 (Admin Evolution). FR-056 define que o custo por mensagem seja `tokens_in × preço_in + tokens_out × preço_out`, com preços por modelo "em um mapping documentado no código". Esta ADR formaliza **onde**, **como** e **quando promover** para uma solução mais elaborada.

## Contexto

O admin evoluído expõe custo agregado por tenant e por modelo (FR-055, FR-056) — tanto no card de KPI do Overview quanto no gráfico "Custo por Modelo" da aba Performance AI. Para calcular `traces.cost_usd`, o pipeline precisa multiplicar os tokens in/out pelos preços do modelo usado.

Hoje (2026-04) existem três modelos relevantes para a plataforma:

| Modelo | Uso | ADR relacionada |
|--------|-----|-----------------|
| `gpt-4o` | fallback, agentes de alto valor | — |
| `gpt-4o-mini` | classifier legacy + alguns tenants | ADR-025 (deprecation planejada) |
| `gpt-5-mini` / `gpt-5.4-mini` | default atual da família gpt-5 | ADR-025 |

**Observação de auditoria (T006):** o decisions.md do epic 008 (decisão 17) e o research.md R14 referenciam `gpt-5-mini` como o modelo default da família gpt-5; a ADR-025 define explicitamente `gpt-5.4-mini` como default aceito. Esta ambiguidade será resolvida em T006 validando o nome exato do modelo em uso em `agent.py` e usando-o como chave da constante; enquanto `gpt-5-mini` não for confirmado como publicamente priced, o valor vai com `[VALIDAR]` no comentário e `# TODO: confirm pricing`.

A pergunta: qual é a representação mínima viável para esse mapping na v1?

## Decisão

We will hardcode `MODEL_PRICING` como **constante Python** em `apps/api/prosauai/conversation/pricing.py`:

```python
"""Model pricing constants for cost calculation.

Values are US dollars per 1,000 tokens. Update when providers change prices.
Source-of-truth references live as comments next to each entry.

Migration trigger: promote to DB table (prosauai.model_pricing) when any of:
  (a) >3 active models in rotation,
  (b) price change cadence exceeds 1 per quarter,
  (c) per-tenant override requirement emerges (enterprise pricing).
See ADR-029.
"""
from __future__ import annotations

from decimal import Decimal

MODEL_PRICING: dict[str, tuple[Decimal, Decimal]] = {
    # (price_per_1k_input_tokens, price_per_1k_output_tokens) in USD
    # Source: https://openai.com/pricing (confirmed 2026-04-17 — see T006)
    "gpt-4o": (Decimal("0.0025"), Decimal("0.010")),
    "gpt-4o-mini": (Decimal("0.00015"), Decimal("0.0006")),
    # gpt-5-mini pricing: see ADR-025. [VALIDAR] until T006 confirms.
    # TODO: confirm pricing — remove marker once official OpenAI page shows it.
    "gpt-5-mini": (Decimal("0.0015"), Decimal("0.006")),
    # gpt-5.4-mini (ADR-025 default) — reasoning variant, ~3x gpt-5-mini
    # TODO: confirm pricing at 2026-04-17 checkpoint.
    "gpt-5.4-mini": (Decimal("0.00045"), Decimal("0.0027")),
}


def calculate_cost(
    model: str,
    tokens_in: int,
    tokens_out: int,
) -> Decimal | None:
    """Return USD cost or None if model is not mapped.

    None is distinct from Decimal('0') so the UI can render '—' and a tooltip
    explaining the model is unmapped (spec edge case).
    """
    price = MODEL_PRICING.get(model)
    if price is None:
        return None
    price_in, price_out = price
    return (Decimal(tokens_in) / 1000 * price_in) + (
        Decimal(tokens_out) / 1000 * price_out
    )
```

### Política operacional

1. **Mudança de preço** entra via **PR** (`chore(pricing): update gpt-4o to $X`) com link para source (OpenAI pricing page screenshot ou changelog).
2. **Novo modelo** é adicionado ao dicionário; nunca removido — preserva histórico (traces antigos continuam a ter custo calculado).
3. **Deprecation de modelo** mantém a entrada com comentário `# DEPRECATED: unused since YYYY-MM`.
4. **Nenhum default silencioso** — modelo não mapeado retorna `None` e UI mostra `—` com tooltip (spec edge case).
5. **Teste unit** (T021) parametriza sobre todos os modelos mapeados + um modelo desconhecido → None.

### Gatilhos de migração para DB (v2)

Promover `MODEL_PRICING` para tabela `prosauai.model_pricing` **quando qualquer** uma destas condições ocorrer:

| Gatilho | Justificativa |
|---------|--------------|
| >3 modelos ativos em rotação | PR diff vira barulhento, vários deploys/mês por price updates |
| Mudança de preço > 1×/trimestre | Cadence alta exige hot-reload em vez de deploy de código |
| Necessidade de override per-tenant | Enterprise pricing ou beta programs — JSONB em `tenants.config` resolveria, mas tabela dedicada é mais limpa |
| Auditoria de preço histórico pedida | `public.model_pricing` com colunas `effective_from`/`effective_to` permite recalcular custo de trace antigo |

Migração será um epic pequeno (~4 h): migration new table + script de migração dos valores atuais + swap da constante por `SELECT` cached 5min em Redis. Nenhum código cliente muda de forma (função `calculate_cost` continua com mesma assinatura).

## Alternativas consideradas

### A. Tabela editável em DB (`public.model_pricing`) na v1

- **Pros:** edição em runtime sem deploy; auditoria nativa via `updated_at`; base para per-tenant override.
- **Cons:**
  - Over-engineering para 2–3 modelos cujos preços mudam 1–2×/ano.
  - Exige admin UI novo para editar (estava fora de escopo do epic 008).
  - Cache Redis obrigatório (senão DB lookup em cada trace insert vira hot spot).
  - Preço muda sem trilha de código — code review perde a visibilidade.
- **Rejeitada porque:** ganho operacional < custo de infra + UI + cache. Fica no epic de evolução quando gatilhos forem atingidos.

### B. Consumir SaaS externo (Helicone, Portkey, OpenAI pricing API)

- **Pros:** sempre atualizado; agregação por tenant nativa em alguns fornecedores.
- **Cons:**
  - Nova dependência externa síncrona no hot path (se não cacheado) ou eventual inconsistência (se cacheado).
  - Custo $ adicional.
  - Privacy — enviar tokens/custo de cada mensagem para terceiro.
  - Ariel é proprietary — fornecer dados de uso para SaaS viola policy Pace.
- **Rejeitada porque:** inviável por privacy + custo marginal não justifica abdicar de controle.

### C. JSONB per-tenant em `tenants.config.pricing_override`

- **Pros:** per-tenant nativo; zero novas tabelas.
- **Cons:**
  - Sem gatilho real v1 — nenhum tenant negocia pricing enterprise hoje.
  - Schema-less = fácil introduzir bug.
  - Queries agregadas cross-tenant ficam lentas (JSONB parse em 3.6M rows).
- **Rejeitada porque:** YAGNI. Quando o primeiro tenant pedir override, fica trivial adicionar `MODEL_PRICING_OVERRIDES: dict[tenant_slug, dict[model, tuple]]` como segunda constante ou migrar para DB (gatilho B).

### D. YAML externo (`config/model_pricing.yaml`)

- **Pros:** separação dados/código; ops pode editar sem tocar Python.
- **Cons:**
  - Precisa de watcher para hot-reload (inotify/watchfiles) OU restart — adiciona componente.
  - Mesma desvantagem de audit trail vs. git PR.
  - YAML parsing overhead em cada worker startup.
- **Rejeitada porque:** ganho zero vs. constante Python; adiciona operations.

## Consequências

- [+] **Simplicidade máxima** — 1 arquivo, 1 função, 1 teste. Zero infra nova.
- [+] **Auditoria via git** — `git blame` mostra quando e por quem cada preço foi ajustado.
- [+] **Fail-loud** — modelo não mapeado retorna `None` (distinto de `0`), UI mostra `—`, operador percebe cedo.
- [+] **Path de migração claro** — gatilhos documentados, estimativa de 4h para promover para tabela.
- [+] **Compatível com LGPD** — nenhum dado do cliente sai da máquina; preços são públicos.
- [-] **Mudança de preço exige deploy** — ~15min para PR + CI + deploy. Aceitável dado cadence de 1–2×/ano.
- [-] **Sem override per-tenant v1** — todo tenant usa mesmo preço. Aceitável — nenhum tenant negociou enterprise ainda.
- [-] **Risco de drift entre ADR-025 e constant** — manter comentário linkando ADR-025 + teste unit que assert presença das chaves ativas.
- [-] **Custo histórico imutável** — se mudarmos preço no PR e traces antigos foram calculados com preço antigo, o `cost_usd` já persistido fica "congelado" (bom — representa o preço em vigor na hora). Novo recalculo exigiria query manual com OLD_PRICING mapping — aceitável pois é audit, não billing ao cliente.

## Teste de regressão

`apps/api/tests/unit/conversation/test_pricing.py`:

```python
import pytest
from decimal import Decimal
from prosauai.conversation.pricing import MODEL_PRICING, calculate_cost

@pytest.mark.parametrize("model,tokens_in,tokens_out,expected", [
    ("gpt-4o", 1000, 1000, Decimal("0.0125")),        # 0.0025 + 0.010
    ("gpt-4o-mini", 1000, 1000, Decimal("0.00075")),  # 0.00015 + 0.0006
    ("gpt-5-mini", 1000, 1000, Decimal("0.0075")),    # 0.0015 + 0.006
])
def test_calculate_cost_known_models(model, tokens_in, tokens_out, expected):
    assert calculate_cost(model, tokens_in, tokens_out) == expected

def test_calculate_cost_unknown_model_returns_none():
    assert calculate_cost("claude-3-opus-20240229", 1000, 1000) is None

def test_precision_6_decimals():
    """Cost must preserve 6 decimal precision (per traces.cost_usd NUMERIC(10,6))."""
    result = calculate_cost("gpt-4o-mini", 500, 250)
    assert result is not None
    assert result.quantize(Decimal("0.000001")) == result

def test_active_models_present():
    """Smoke-test: at least the 3 active models must be in the dict."""
    for required in ("gpt-4o", "gpt-4o-mini", "gpt-5-mini"):
        assert required in MODEL_PRICING, f"ADR-029 active model {required!r} missing"
```

---

> **Próximo passo:** PR 2 implementa `pricing.py` + testes (T020, T021). Nenhum código cliente muda fora da função `calculate_cost`. Promoção para DB fica em backlog vinculado aos gatilhos acima.
