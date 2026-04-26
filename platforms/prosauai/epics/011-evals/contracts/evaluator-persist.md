# Contract: EvalPersister Protocol + DeepEval Metric Wrapper

**Escopo**: API estavel entre produtores de score (heuristic, deepeval, human) e a camada de persistencia em `eval_scores`. Espelha o pattern `HelpdeskAdapter` do epic 010.

---

## 1. Protocol `EvalPersister`

```python
# apps/api/prosauai/evals/persist.py
from typing import Protocol, runtime_checkable

from prosauai.evals.models import EvalScoreRecord


@runtime_checkable
class EvalPersister(Protocol):
    """Persistidor de score de avaliacao em eval_scores.

    Qualquer implementacao MUST:
      - Ser fire-and-forget (caller usa asyncio.create_task, nao awaits).
      - Nunca levantar excecao para o caller (log interno + metrica).
      - Respeitar tenant isolation (RLS via SET LOCAL tenant_id).
      - Emitir span OTel attached ao trace do caller.
      - Incrementar metrica `eval_scores_persisted_total{tenant, evaluator, metric, status}`.
    """

    async def persist(self, record: EvalScoreRecord) -> None:
        """Persiste `record` em `eval_scores`.

        Raises:
            Nada. Falhas sao capturadas internamente e logadas com
            `evaluator`, `metric`, `message_id`, `reason` no structlog.
        """
        ...
```

### 1.1 Reference implementation — `PoolPersister`

```python
# apps/api/prosauai/evals/persist.py

class PoolPersister:
    """Persistidor canonico usando o pool asyncpg (RLS-aware)."""

    def __init__(self, pool: asyncpg.Pool, metrics: EvalMetricsFacade):
        self._pool = pool
        self._metrics = metrics
        self._logger = structlog.get_logger(__name__)

    async def persist(self, record: EvalScoreRecord) -> None:
        try:
            async with self._pool.acquire() as conn:
                # Set tenant_id for RLS pushdown.
                await conn.execute("SET LOCAL app.tenant_id = $1", str(record.tenant_id))
                await conn.execute(
                    """
                    INSERT INTO eval_scores
                      (tenant_id, conversation_id, message_id, evaluator_type, metric, quality_score, details)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                    record.tenant_id,
                    record.conversation_id,
                    record.message_id,
                    record.evaluator_type,
                    record.metric,
                    record.quality_score,
                    record.details,
                )
            self._metrics.scores_persisted_total(
                tenant=str(record.tenant_id),
                evaluator=record.evaluator_type,
                metric=record.metric,
                status="ok",
            )
            # Below-threshold alert emission (if evals.mode=on).
            self._metrics.maybe_emit_below_threshold(record)
        except Exception as exc:
            self._logger.warning(
                "eval_score_persist_failed",
                tenant_id=str(record.tenant_id),
                conversation_id=str(record.conversation_id),
                message_id=str(record.message_id) if record.message_id else None,
                evaluator=record.evaluator_type,
                metric=record.metric,
                score=record.quality_score,
                reason=repr(exc),
            )
            self._metrics.scores_persisted_total(
                tenant=str(record.tenant_id),
                evaluator=record.evaluator_type,
                metric=record.metric,
                status="error",
            )
```

---

## 2. DeepEval metric wrapper contract

Cada metrica DeepEval (AnswerRelevancy, Toxicity, Bias, Coherence) e envelopada num wrapper que converte resposta DeepEval → `EvalScoreRecord` e respeita isolamento de falha.

```python
# apps/api/prosauai/evals/deepeval_batch.py
from typing import Protocol

from prosauai.evals.models import EvalScoreRecord, Metric


class DeepEvalMetric(Protocol):
    """Wrapper para uma metrica DeepEval."""

    metric_name: Metric  # one of: answer_relevancy, toxicity, bias, coherence

    async def evaluate(
        self,
        *,
        tenant_id: UUID,
        message_id: UUID,
        conversation_id: UUID,
        message_content: str,
        intent: str | None,
        trace_id: str | None,
    ) -> EvalScoreRecord:
        """Avalia uma mensagem, retorna EvalScoreRecord com evaluator_type='deepeval'.

        Raises:
            DeepEvalFailure: quando LLM backend falha apos retry esgotado.
            InvalidContentError: quando content excede 32K caracteres (pre-filter falhou).
        """
        ...
```

### 2.1 Reference wrappers

```python
class AnswerRelevancyWrapper:
    metric_name: Metric = "answer_relevancy"

    def __init__(self, bifrost_client: httpx.AsyncClient, model: str = "gpt-4o-mini"):
        self._client = bifrost_client
        self._model = model

    async def evaluate(self, *, tenant_id, message_id, conversation_id, message_content, intent, trace_id):
        # Retry com jitter (max 3 attempts) em 429/timeout.
        raw = await _call_with_retry(
            lambda: self._client.post("/v1/chat/completions", json=_build_prompt(...))
        )
        score = _parse_score(raw)  # returns float ∈ [0,1]
        return EvalScoreRecord(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            message_id=message_id,
            evaluator_type="deepeval",
            metric="answer_relevancy",
            quality_score=score,  # clipped by pydantic validator
            details={
                "model": self._model,
                "intent": intent,
                "trace_id": trace_id,
                "explanation": _parse_explanation(raw),
            },
        )
```

### 2.2 Metric isolation contract

Em `deepeval_batch.py`, chamada consolidada usa `asyncio.gather(return_exceptions=True)` por metrica-msg:

```python
async def _process_message(persister, wrappers, msg):
    tasks = [w.evaluate(...) for w in wrappers]  # 4 metric tasks
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for wrapper, result in zip(wrappers, results):
        if isinstance(result, Exception):
            logger.warning(
                "deepeval_metric_failed",
                metric=wrapper.metric_name,
                message_id=msg.id,
                reason=repr(result),
            )
            metrics.batch_duration_seconds(job="deepeval", status="error", metric=wrapper.metric_name)
            continue
        await persister.persist(result)  # fire-and-forget
```

**Invariante**: falha em 1 metric task nao aborta as outras 3 da mesma msg nem as demais msgs do chunk.

---

## 3. Contract tests

Em `tests/contract/test_eval_persister_contract.py`:

```python
import pytest
from prosauai.evals.persist import EvalPersister, PoolPersister
from prosauai.evals.deepeval_batch import DeepEvalMetric, AnswerRelevancyWrapper, ToxicityWrapper


@pytest.mark.parametrize("impl_class", [PoolPersister])
def test_eval_persister_protocol_conformance(impl_class, pg_pool, metrics_facade):
    impl = impl_class(pg_pool, metrics_facade)
    assert isinstance(impl, EvalPersister)


@pytest.mark.parametrize("wrapper_class", [
    AnswerRelevancyWrapper,
    ToxicityWrapper,
    BiasWrapper,
    CoherenceWrapper,
])
def test_deepeval_metric_wrapper_conformance(wrapper_class, bifrost_mock):
    wrapper = wrapper_class(bifrost_mock)
    assert isinstance(wrapper, DeepEvalMetric)
    assert wrapper.metric_name in {"answer_relevancy", "toxicity", "bias", "coherence"}


async def test_persist_never_raises(pg_pool, metrics_facade, invalid_record):
    """Fire-and-forget invariant: persist must not raise for caller."""
    impl = PoolPersister(pg_pool, metrics_facade)
    # invalid_record e um registro que causa IntegrityError (ex: conversation_id inexistente).
    try:
        await impl.persist(invalid_record)  # MUST NOT raise
    except Exception:
        pytest.fail("persist() raised; must be swallowed internally")


async def test_metric_isolation(deepeval_batch_runner, msgs, wrappers_with_one_failing):
    """Falha em Toxicity nao aborta as outras 3 metrics."""
    result = await deepeval_batch_runner.run(msgs, wrappers_with_one_failing)
    assert result["persisted"]["answer_relevancy"] == len(msgs)
    assert result["persisted"]["bias"] == len(msgs)
    assert result["persisted"]["coherence"] == len(msgs)
    assert result["failed"]["toxicity"] == len(msgs)
```

---

## 4. Observability contract

Cada persistencia MUST emitir:

1. **Log structlog** (canonical keys):
   - `tenant_id: str`
   - `conversation_id: str`
   - `message_id: str | None`
   - `evaluator: str` (evaluator_type)
   - `metric: str`
   - `score: float`
   - `status: "ok" | "error"`
   - `reason: str | None` (quando error)

2. **Metrica Prometheus** (structlog facade, sem `prometheus_client` dep):
   - `eval_scores_persisted_total{tenant, evaluator, metric, status}` — counter
   - `eval_score_below_threshold_total{tenant, metric}` — counter (so incrementa em `mode=on`)

3. **OTel span**:
   - Nome: `eval.score.persist`
   - Attributes: `evaluator`, `metric`, `score`, `tenant_id`
   - Attached ao trace corrente (propagado via asyncio contextvar do `asyncio.create_task`).

DeepEval batch adiciona span root `eval.batch.deepeval` com child per metric (`eval.batch.deepeval.answer_relevancy`).

---

## 5. Error handling contract

| Cenario | Comportamento |
|---------|---------------|
| DB indisponivel durante persist | Log warning + counter error + retorna None. Caller nao sabe. |
| Score invalido ([-0.1] ou [1.5]) | Pydantic validator clipa a [0,1] + log warn. Persiste clippado. |
| FK violation (conversation_id inexistente) | Log warning + counter error. Nao levanta. |
| RLS policy violation | Log warning. Caller nao sabe. Indica bug de tenant_id setup upstream. |
| DeepEval library retorna score None | Wrapper levanta `InvalidScoreError` → `gather(return_exceptions=True)` isola → log warn, counter error. |
| Bifrost 429 rate limit | Wrapper retenta com jitter (max 3); apos esgotar, `RateLimitError` capturada pelo batch runner. |
| Bifrost timeout | Mesmo que 429. |
| Bifrost 5xx | Wrapper retenta; apos esgotar, `UpstreamError`. |
| Content >32K chars | Sampler filtra antes; se passar, wrapper levanta `ContentTooLongError` + log error. |

---

## 6. References

- [data-model.md §3 Pydantic models](../data-model.md#3-pydantic-models)
- [data-model.md §5 Query patterns](../data-model.md#5-query-patterns)
- [spec.md FR-001..FR-008 (online)](../spec.md#requirements)
- [spec.md FR-019..FR-027 (DeepEval)](../spec.md#requirements)
- [spec.md FR-049..FR-051 (observabilidade)](../spec.md#requirements)
- Epic 010 referencia: `apps/api/prosauai/handoff/base.py` — `HelpdeskAdapter` Protocol (espelho deste).
