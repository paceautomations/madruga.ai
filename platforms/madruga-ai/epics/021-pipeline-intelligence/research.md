# Research: `claude -p --output-format json` Output Structure

**Data**: 2026-04-04
**Claude Code version**: 2.1.90
**Model used in tests**: claude-opus-4-6[1m]

---

## Objetivo

Verificar os campos reais do JSON retornado por `claude -p --output-format json` para garantir que `parse_claude_output()` em `dag_executor.py` extrai métricas corretamente (US1: Cost Tracking) e identificar campos úteis para detecção de alucinação (US2: Hallucination Guard).

---

## Metodologia

Dois dispatches de teste executados:

1. **Sem tool use**: `claude -p --output-format json "Reply with exactly: hello" --max-turns 1`
2. **Com tool use**: `claude -p --output-format json "List files in the current directory using ls" --max-turns 2`

---

## Estrutura JSON Completa (Run 1 — sem tool use)

```json
{
  "type": "result",
  "subtype": "success",
  "is_error": false,
  "duration_ms": 12112,
  "duration_api_ms": 5491,
  "num_turns": 2,
  "result": "hello",
  "stop_reason": "end_turn",
  "session_id": "37d55cfa-cf8a-45f4-a40f-f11ba6c2159b",
  "total_cost_usd": 0.12181700000000001,
  "usage": {
    "input_tokens": 6,
    "cache_creation_input_tokens": 16210,
    "cache_read_input_tokens": 38899,
    "output_tokens": 41,
    "server_tool_use": {
      "web_search_requests": 0,
      "web_fetch_requests": 0
    },
    "service_tier": "standard",
    "cache_creation": {
      "ephemeral_1h_input_tokens": 16210,
      "ephemeral_5m_input_tokens": 0
    },
    "inference_geo": "",
    "iterations": [],
    "speed": "standard"
  },
  "modelUsage": {
    "claude-opus-4-6[1m]": {
      "inputTokens": 6,
      "outputTokens": 41,
      "cacheReadInputTokens": 38899,
      "cacheCreationInputTokens": 16210,
      "webSearchRequests": 0,
      "costUSD": 0.12181700000000001,
      "contextWindow": 1000000,
      "maxOutputTokens": 64000
    }
  },
  "permission_denials": [],
  "fast_mode_state": "off",
  "uuid": "2f6e492c-1eed-4da1-bf09-1a6e23bec33a"
}
```

## Estrutura JSON Completa (Run 2 — com tool use)

```json
{
  "type": "result",
  "subtype": "success",
  "is_error": false,
  "duration_ms": 41736,
  "duration_api_ms": 36742,
  "num_turns": 3,
  "result": "...",
  "stop_reason": "end_turn",
  "session_id": "38f4ee87-8ead-4f6c-a1fe-24e97d1b33a8",
  "total_cost_usd": 0.15880125,
  "usage": {
    "input_tokens": 7,
    "cache_creation_input_tokens": 18379,
    "cache_read_input_tokens": 70145,
    "output_tokens": 353,
    "server_tool_use": {
      "web_search_requests": 0,
      "web_fetch_requests": 0
    },
    "service_tier": "standard",
    "cache_creation": {
      "ephemeral_1h_input_tokens": 18379,
      "ephemeral_5m_input_tokens": 0
    },
    "inference_geo": "",
    "iterations": [],
    "speed": "standard"
  },
  "modelUsage": {
    "claude-opus-4-6[1m]": {
      "inputTokens": 7,
      "outputTokens": 353,
      "cacheReadInputTokens": 70145,
      "cacheCreationInputTokens": 18379,
      "webSearchRequests": 0,
      "costUSD": 0.15880125,
      "contextWindow": 1000000,
      "maxOutputTokens": 64000
    }
  },
  "permission_denials": [],
  "fast_mode_state": "off",
  "uuid": "2c14996f-b117-4ec6-8ef9-c9593437c463"
}
```

## Estrutura JSON (Run com erro — max_turns excedido)

Quando `--max-turns 1` e o modelo tenta usar tool use, o exit code é 1 e o JSON contém:

```json
{
  "type": "result",
  "subtype": "error_max_turns",
  "is_error": true,
  "stop_reason": "tool_use",
  "errors": ["Reached maximum number of turns (1)"]
}
```

Todos os demais campos (`usage`, `total_cost_usd`, `duration_ms`, etc.) ainda estão presentes.

---

## Mapeamento de Campos: Código Atual vs JSON Real

### `parse_claude_output()` (dag_executor.py:183-201)

| Campo no código | Path esperada | Path real no JSON | Match? | Ação necessária |
|----------------|--------------|-------------------|--------|----------------|
| `tokens_in` | `usage.input_tokens` | `usage.input_tokens` | **SIM** | Nenhuma |
| `tokens_out` | `usage.output_tokens` | `usage.output_tokens` | **SIM** | Nenhuma |
| `cost_usd` | `data["cost_usd"]` | `data["total_cost_usd"]` | **NÃO** | Corrigir: `cost_usd` → `total_cost_usd` |
| `duration_ms` | `data["duration_ms"]` | `data["duration_ms"]` | **SIM** | Nenhuma |

### Impacto do mismatch `cost_usd`

O campo `cost_usd` **não existe** no JSON. O campo correto é `total_cost_usd`. Isso significa que **todas as execuções do pipeline estão com `cost_usd = NULL` no banco**, já que `data.get("cost_usd")` retorna `None`.

**Fix necessário em T005**: Trocar `data.get("cost_usd")` por `data.get("total_cost_usd")` na linha 197.

---

## Campos Adicionais Relevantes (Não Capturados Atualmente)

| Campo | Path | Tipo | Utilidade |
|-------|------|------|-----------|
| `total_cost_usd` | top-level | float | **Custo real** — valor autoritativo |
| `duration_api_ms` | top-level | int | Duração só da API (sem overhead local) |
| `num_turns` | top-level | int | Número de turnos da conversa |
| `type` | top-level | str | Sempre "result" |
| `subtype` | top-level | str | "success", "error_max_turns", etc. |
| `is_error` | top-level | bool | Se o dispatch falhou |
| `stop_reason` | top-level | str | "end_turn", "tool_use", "max_tokens" |
| `session_id` | top-level | str | UUID da sessão (já capturado por `parse_session_id()`) |
| `uuid` | top-level | str | UUID do dispatch individual |
| `usage.cache_creation_input_tokens` | usage | int | Tokens usados para criar cache |
| `usage.cache_read_input_tokens` | usage | int | Tokens lidos do cache |
| `usage.server_tool_use` | usage | dict | Contagem de web search/fetch |
| `modelUsage` | top-level | dict | Breakdown por modelo (camelCase) |
| `modelUsage.*.costUSD` | nested | float | Custo por modelo |
| `permission_denials` | top-level | list | Permissões negadas durante execução |
| `fast_mode_state` | top-level | str | Estado do modo fast ("off", etc.) |
| `errors` | top-level | list[str] | Mensagens de erro (só quando is_error=true) |

---

## Análise para Hallucination Guard (US2)

### Campo `tool_use_count` existe?

**NÃO.** O JSON de output do `claude -p` **não contém** um campo explícito `tool_use_count`, `num_tool_calls`, ou equivalente.

### Alternativas para Detectar Zero Tool Calls

| Abordagem | Campo | Lógica | Confiabilidade | Recomendação |
|-----------|-------|--------|----------------|--------------|
| A) `num_turns` | `num_turns` | Se `num_turns == 2` → provavelmente sem tool use (1 user turn + 1 assistant turn). `num_turns > 2` → tool use provável. | **BAIXA** — um dispatch pode ter `num_turns=2` e ter usado tools (se terminou no mesmo turno), ou `num_turns > 2` sem tools (multi-turn system prompt). | Não recomendada como heurística primária |
| B) `stop_reason` | `stop_reason` | `stop_reason == "end_turn"` com `num_turns == 2` → sem tool use | **MÉDIA** — boa heurística, mas sujeita a falsos positivos | Útil como sinal complementar |
| C) `output_tokens` | `usage.output_tokens` | Número muito baixo de output_tokens (< 50) em skill que espera output substancial → suspeito | **BAIXA** — muito dependente do skill | Não recomendada isoladamente |
| D) `num_turns` threshold | `num_turns` | `num_turns <= 2` para skills que DEVEM usar ferramentas (implement, plan, etc.) → warning | **MÉDIA-ALTA** — pragmática, simples, funciona para os casos mais perigosos | **RECOMENDADA para MVP** |
| E) `stream-json` format | stdout stream | Usar `--output-format stream-json` e contar eventos `tool_use` | **ALTA** — informação precisa | Requer mudança significativa na captura de stdout (parsing incremental) — desproporcional para MVP |

### Recomendação para T010 (`_check_hallucination`)

Usar **abordagem D** (threshold em `num_turns`):

```python
def _check_hallucination(stdout: str) -> bool:
    """Detect likely hallucinated output (zero tool calls heuristic).

    Returns True if dispatch likely fabricated output without using tools.
    Heuristic: num_turns <= 2 means no tool was invoked (1 user + 1 assistant).
    """
    if not stdout:
        return False
    try:
        data = json.loads(stdout)
        num_turns = data.get("num_turns", 0)
        return num_turns <= 2 and not data.get("is_error", False)
    except (ValueError, TypeError):
        return False
```

**Limitações conhecidas**:
- False positives: skills que legitimamente não usam tools (ex: `vision` que só gera texto)
- False negatives: execuções com muitos turns mas sem tool calls reais (edge case raro)
- Mitigação: whitelist de skills isentos (mencionada no pitch como rabbit hole, não priorizada para MVP)

---

## Observações Adicionais

### Token Counting — `usage.input_tokens` é Parcial

Os `input_tokens` no campo `usage` **não incluem cache tokens**. O total real de input é:

```
total_input = input_tokens + cache_creation_input_tokens + cache_read_input_tokens
```

Para cost tracking preciso, considerar capturar também os campos de cache. No entanto, `total_cost_usd` já calcula o custo total corretamente (incluindo cache), então para fins de custo basta usar `total_cost_usd`.

### `modelUsage` vs `usage`

- `usage`: campos em snake_case, valores agregados
- `modelUsage`: campos em camelCase, breakdown por modelo
- Para pipelines single-model, os valores são equivalentes
- `modelUsage.*.costUSD` === `total_cost_usd` (confirmado nos dois runs)

### Error Handling

Quando o dispatch falha (`is_error: true`), os campos de usage/cost **ainda são populados**. O `parse_claude_output()` atual retorna métricas mesmo em caso de erro, o que é o comportamento correto (queremos rastrear custos inclusive de dispatches falhados).

---

## Resumo de Ações para Tasks Downstream

| Task | Ação Necessária | Prioridade |
|------|----------------|------------|
| T005 | **Corrigir `cost_usd` → `total_cost_usd`** na linha 197 de `parse_claude_output()` | CRÍTICA — é a única mudança necessária para US1 funcionar |
| T006 | **Provavelmente desnecessária** — `total_cost_usd` já vem calculado pelo CLI. Manter como fallback apenas se `total_cost_usd` vier `None` (edge case) | BAIXA |
| T010 | Implementar `_check_hallucination()` usando heurística `num_turns <= 2` (abordagem D) | ALTA |
| T003 | Usar os JSONs deste documento como fixtures de teste | ALTA |

---
handoff:
  from: research
  to: speckit.implement (T002+)
  context: "JSON structure verified. Critical finding: cost_usd field is actually total_cost_usd (1 line fix). No tool_use_count field exists — hallucination guard must use num_turns heuristic. Two real JSON samples documented as test fixtures."
  blockers: []
  confidence: Alta
  kill_criteria: "If claude CLI changes JSON output format in a future version, field paths need re-verification."
