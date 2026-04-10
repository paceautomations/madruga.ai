# Research — Epic 002: Observability

**Branch**: `epic/prosauai/002-observability` | **Date**: 2026-04-10

## R1: Phoenix (Arize) Self-Hosted com Postgres Backend

### Decisão
Phoenix self-hosted com Postgres backend via `PHOENIX_SQL_DATABASE_URL`, apontando para Supabase com schema dedicado `observability`.

### Rationale
- Phoenix é o único tooling que é simultaneamente OTel-native, LLM-ready (datasets, experiments, prompt management nativos), single container, e compatível com Postgres backend
- Constraint "Supabase como BD" elimina LangFuse v3 (requer ClickHouse), SigNoz (requer ClickHouse), e Grafana Tempo (requer object storage)
- ADR-007 já documentava Phoenix como fallback aceito — agora é o caminho principal

### Alternativas Consideradas
| Alternativa | Prós | Contras | Decisão |
|-------------|-------|---------|---------|
| **Phoenix self-hosted (Postgres)** | Single container, OTel-native, LLM evals nativos, Postgres backend | UI de logs fraca, sem auth robusto nativo | ✅ Escolhido |
| **LangFuse v3 self-hosted** | UI madura, LLM-first, boa DX | Requer PG + ClickHouse + Redis + MinIO (4 containers); incompatível com constraint Supabase-only | ❌ Incompatível |
| **SigNoz** | APM completo, métricas + traces | Requer ClickHouse; APM-first, não LLM-first; precisaria de tooling adicional para evals | ❌ Incompatível |
| **Grafana LGTM** | Ecossistema maduro, comunidade grande | Tempo usa S3/object storage; configuração pesada; nada LLM-native | ❌ Incompatível |
| **Jaeger** | Simples, bem estabelecido | Sem LLM features; storage limitado (Elasticsearch/Cassandra, não Postgres) | ❌ Sem forward-compat |

### Configuração Phoenix
```yaml
# docker-compose.yml
phoenix:
  image: arizephoenix/phoenix:latest  # pin to specific tag in prod
  ports:
    - "6006:6006"    # UI
    - "4317:4317"    # OTLP gRPC collector
    - "4318:4318"    # OTLP HTTP collector
  environment:
    PHOENIX_SQL_DATABASE_URL: "postgresql://${SUPABASE_USER}:${SUPABASE_PASSWORD}@${SUPABASE_HOST}:5432/${SUPABASE_DB}?options=-csearch_path=observability"
    PHOENIX_PROJECT_NAME: prosauai
    PHOENIX_WORKING_DIR: /phoenix/data
  volumes:
    - phoenix_data:/phoenix/data
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:6006/healthz"]
    interval: 15s
    timeout: 5s
    retries: 3
    start_period: 30s
```

### Fontes
- Phoenix docs: https://docs.arize.com/phoenix
- Phoenix GitHub: https://github.com/Arize-AI/phoenix
- OTel Postgres backend: configuração via `PHOENIX_SQL_DATABASE_URL`

---

## R2: OpenTelemetry Python SDK — Setup e Auto-Instrumentation

### Decisão
OTel Python SDK com auto-instrumentation para FastAPI, httpx e redis-py. Exporter OTLP gRPC apontando para Phoenix collector.

### Rationale
- Vendor-agnóstico — permite swap futuro para LangFuse/SigNoz/Jaeger sem reescrever instrumentação
- Auto-instrumentation cobre ~80% dos spans necessários (HTTP requests, Redis commands) sem código manual
- Spans manuais cirúrgicos apenas para pontos de domínio (route_message, debounce.append/flush, send_echo)

### Padrão de Setup
```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased

def configure_observability(settings: Settings) -> None:
    resource = Resource.create({
        "service.name": settings.otel_service_name,  # "prosauai-api"
        "service.version": __version__,
        "deployment.environment": settings.deployment_env,
        "tenant_id": settings.tenant_id,
    })
    
    sampler = ParentBased(root=TraceIdRatioBased(settings.otel_sampler_arg))
    provider = TracerProvider(resource=resource, sampler=sampler)
    provider.add_span_processor(BatchSpanProcessor(
        OTLPSpanExporter(endpoint=settings.phoenix_grpc_endpoint, insecure=True)
    ))
    trace.set_tracer_provider(provider)
    
    # Auto-instrument
    FastAPIInstrumentor.instrument_app(app)
    HttpxInstrumentor().instrument()
    RedisInstrumentor().instrument()
```

### Pacotes Necessários
```
opentelemetry-api
opentelemetry-sdk
opentelemetry-exporter-otlp-proto-grpc
opentelemetry-instrumentation-fastapi
opentelemetry-instrumentation-httpx
opentelemetry-instrumentation-redis
arize-phoenix-otel  # helper para simplificar wiring Phoenix-specific
```

### Alternativas Consideradas
| Alternativa | Prós | Contras | Decisão |
|-------------|-------|---------|---------|
| **OTel SDK + auto-instrument** | Vendor-agnóstico, coverage ampla, padrão indústria | Mais deps (6-7 packages) | ✅ Escolhido |
| **arize-phoenix-otel só** | Setup simplificado (1 package) | Vendor lock-in Phoenix; menos controle sobre sampling e processors | ❌ Lock-in |
| **Manual instrumentation puro** | Zero deps extras | LOC alto, error-prone, perde auto-instrumentation FastAPI/httpx/redis | ❌ Inviável |

### Fontes
- OTel Python SDK: https://opentelemetry.io/docs/languages/python/
- OTel FastAPI instrumentation: https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/fastapi/fastapi.html

---

## R3: W3C Trace Context Propagation via Redis (Debounce)

### Decisão
Propagar W3C Trace Context (`traceparent` + `tracestate`) no payload Redis do DebounceManager. Primeiro append vira parent; subsequentes viram OTel Links.

### Rationale
- Padrão OTel oficial para messaging async
- Sem propagação, trace fica "cortado" no append — flush e echo seriam traces novos sem conexão
- OTel Links para mensagens subsequentes é o pattern documentado para message batching

### Implementação
O payload Redis muda de `text` simples para JSON `{"text": "...", "trace_contexts": [...]}`:

```python
# No append:
carrier: dict[str, str] = {}
propagate.inject(carrier)  # serializa traceparent + tracestate
payload = json.dumps({"text": text, "trace_contexts": [carrier]})

# No flush:
data = json.loads(raw_payload)
if "trace_contexts" in data:
    contexts = data["trace_contexts"]
    parent_ctx = propagate.extract(contexts[0])  # primeiro = parent
    links = [Link(extract_span_context(c)) for c in contexts[1:]]
```

### Retrocompatibilidade
O flush handler tenta parse JSON. Se falhar (payload antigo = text puro), trata como texto sem trace context — degradação graciosa, novo trace.

### Lua Script
O Lua script atual faz `APPEND` de texto com separador `\n`. Para suportar JSON com trace_contexts, a estratégia muda:
- Cada `append` agora chama `RPUSH` em uma lista Redis (em vez de `APPEND` em string)
- O flush faz `LRANGE 0 -1` + `DEL` atomicamente (novo Lua script)
- Cada item da lista é um JSON `{"text": "msg", "trace_context": {...}}`
- O flush reconstrói: concatena textos com `\n`, usa primeiro trace_context como parent, demais como Links

### Alternativas Consideradas
| Alternativa | Prós | Contras | Decisão |
|-------------|-------|---------|---------|
| **JSON payload com trace_context por mensagem (RPUSH lista)** | Trace contínuo, Links por mensagem, clean separation | Muda Lua script de APPEND para RPUSH | ✅ Escolhido |
| **Single trace_context no timer key** | Simples, sem mudar buffer | Perde contexto de appends intermediários, sem Links | ❌ Perda de info |
| **Separate Redis hash para trace contexts** | Não muda buffer | Complexidade extra, race conditions, 2 keys por contexto | ❌ Over-engineering |
| **Sem propagação (traces separados)** | Zero mudança | Perde valor principal: trace contínuo webhook→flush→echo | ❌ Inviável |

### Fontes
- OTel Messaging Semantic Conventions: https://opentelemetry.io/docs/specs/semconv/messaging/
- W3C Trace Context: https://www.w3.org/TR/trace-context/

---

## R4: Structlog ↔ OTel Bridge

### Decisão
Processor customizado no structlog que injeta `trace_id` e `span_id` do span OTel ativo em todo event dict.

### Rationale
- Correlação bidirecional log↔trace é o mecanismo que conecta logs (stdout/JSON) com traces (Phoenix UI)
- Zero-friction: processor automático, sem mudança em nenhum `logger.info(...)` existente
- Pattern documentado na comunidade OTel

### Implementação
```python
from opentelemetry import trace

def add_otel_context(logger, method_name, event_dict):
    span = trace.get_current_span()
    if span and span.get_span_context().is_valid:
        ctx = span.get_span_context()
        event_dict["trace_id"] = format(ctx.trace_id, "032x")
        event_dict["span_id"] = format(ctx.span_id, "016x")
    return event_dict
```

O processor é adicionado no `shared_processors` do `configure_logging()` em `main.py`, **após** `merge_contextvars` e **antes** do renderer.

### Fontes
- structlog processors: https://www.structlog.org/en/stable/processors.html
- OTel trace API: https://opentelemetry-python.readthedocs.io/en/latest/api/trace.html

---

## R5: Head-Based Sampling

### Decisão
`ParentBased(root=TraceIdRatioBased(rate))` com `rate` configurável via `OTEL_SAMPLER_ARG` no `.env`. Default: 1.0 (100%) em dev, 0.1 (10%) em prod.

### Rationale
- `ParentBased` respeita decisão do parent span — importante para distributed traces futuros (epic 003 worker)
- `TraceIdRatioBased` é determinístico por trace_id — mesma decisão para todos os spans de um trace
- Env var permite ajuste por deploy sem mudar código

### Alternativas Consideradas
| Alternativa | Prós | Contras | Decisão |
|-------------|-------|---------|---------|
| **Head-based ParentBased + TraceIdRatioBased** | Simples, determinístico, env-configurable | Pode perder traces de erros raros em prod | ✅ Escolhido (tail-based deferred) |
| **Tail-based sampling** | 100% de erro traces capturados | Requer OTel Collector standalone, complexidade ops | ❌ Over-engineering para volume atual |
| **Always-on (100%)** | Zero perda | Custo storage alto em prod scale | ❌ Não escalável |

---

## R6: Testes com InMemorySpanExporter

### Decisão
- Testes regulares: `OTEL_SDK_DISABLED=true` → no-op TracerProvider (zero overhead)
- Testes de observability: `InMemorySpanExporter` + `SimpleSpanProcessor` como fixture pytest

### Rationale
- `OTEL_SDK_DISABLED=true` é o mecanismo oficial OTel para desabilitar SDK
- `InMemorySpanExporter` permite assertar spans sem dependência de Phoenix
- `SimpleSpanProcessor` (não Batch) garante export síncrono em testes

### Implementação
```python
@pytest.fixture
def otel_spans():
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import InMemorySpanExporter, SimpleSpanProcessor
    
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    yield exporter
    exporter.clear()
    trace.set_tracer_provider(trace.NoOpTracerProvider())
```

---

## R7: Health Endpoint — Extensão para Observability Status

### Decisão
Estender `HealthResponse` existente com campo `observability: ObservabilityHealth` contendo `status` ("ok"|"degraded") e `last_export_success: bool`. Nunca retorna 503 por falha OTel.

### Rationale
- Observabilidade é não-crítica para funcionamento do API
- Campo adicional no response existente (não endpoint separado) mantém simplicidade
- `last_export_success` indica se o último batch de spans foi exportado com sucesso

### Implementação
```python
class ObservabilityHealth(BaseModel):
    status: Literal["ok", "degraded"]
    last_export_success: bool

class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    redis: bool = True
    observability: ObservabilityHealth | None = None
```

O status geral continua sendo determinado apenas pelo Redis. O campo `observability` é informacional.
