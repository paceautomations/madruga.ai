# Contract: Conversation Pipeline

**Epic**: 005-conversation-core  
**Tipo**: Internal pipeline interface  
**Date**: 2026-04-12

## Visão Geral

O pipeline de conversação é a interface interna entre o debounce flush callback e o módulo de delivery. Define o contrato de entrada/saída de cada etapa.

## Pipeline Interface

### Entrada (do Debounce Flush)

```python
@dataclass(frozen=True)
class ConversationRequest:
    """Input do pipeline de conversação. Produzido pelo debounce flush."""
    tenant_id: str
    sender_key: str          # Phone ou LID opaque
    group_id: str | None     # None para mensagens individuais
    text: str                # Texto concatenado do buffer
    agent_id: str | None     # UUID string do agent (resolvido pelo router)
    trace_context: dict      # W3C trace context para continuidade OTel
```

### Saída (para Delivery)

```python
@dataclass(frozen=True)
class ConversationResponse:
    """Output do pipeline de conversação. Consumido pelo delivery."""
    tenant_id: str
    sender_key: str
    group_id: str | None
    response_text: str       # Texto final para enviar ao cliente
    conversation_id: UUID
    message_id: UUID         # ID da mensagem outbound salva
    is_fallback: bool        # True se resposta de fallback (não gerada por LLM)
    latency_ms: float        # Tempo total do pipeline
    model_used: str          # Ex: "openai:gpt-4o-mini"
```

## Contratos por Etapa

### 1. Customer Lookup/Create

```python
async def get_or_create_customer(
    pool: asyncpg.Pool,
    tenant_id: str,
    phone: str,           # Raw phone — hasheado dentro da função
    display_name: str | None = None,
) -> Customer:
    """
    Retorna customer existente ou cria novo.
    Phone é hasheado antes de qualquer operação de BD/log.
    
    Raises:
        DatabaseError: Se pool esgotado ou BD indisponível.
    """
```

### 2. Conversation Get/Create

```python
async def get_or_create_conversation(
    pool: asyncpg.Pool,
    tenant_id: str,
    customer_id: UUID,
    agent_id: UUID,
    channel: str = "whatsapp",
    inactivity_timeout_hours: int = 24,
) -> tuple[Conversation, bool]:
    """
    Retorna conversa ativa existente ou cria nova.
    Se conversa existente com last_activity_at > timeout, fecha e cria nova.
    
    Returns:
        (conversation, is_new) — is_new=True se conversa foi criada.
    
    Invariante: No máximo 1 conversa ativa por customer/channel (unique index).
    """
```

### 3. Context Assembly

```python
async def build_context_window(
    pool: asyncpg.Pool,
    conversation_id: UUID,
    tenant_id: str,
    max_messages: int = 10,
    max_tokens: int = 8000,
) -> list[ContextMessage]:
    """
    Retorna as últimas N mensagens da conversa em ordem cronológica.
    
    Cada ContextMessage contém:
    - role: "user" | "assistant"
    - content: str
    - created_at: datetime
    
    Token count estimado por heurística (chars/4).
    Se total > max_tokens, trunca as mensagens mais antigas.
    """
```

### 4. Input Guard

```python
@dataclass(frozen=True)
class GuardResult:
    allowed: bool
    pii_detected: list[str]     # Tipos de PII encontrados: ["cpf", "email", ...]
    sanitized_text: str         # Texto com PII mascarado (para logs)
    original_text: str          # Texto original (para LLM — PII não bloqueia)
    blocked_reason: str | None  # Se allowed=False, motivo do bloqueio

async def check_input(text: str) -> GuardResult:
    """
    Layer A (regex) guardrails na entrada.
    
    - PII: Detecta mas NÃO bloqueia. Hasheia em logs.
    - Tamanho: Bloqueia se > 4000 chars.
    - Malicioso: Bloqueia injection patterns conhecidos.
    
    Latência: <5ms.
    """
```

### 5. Intent Classification

```python
@dataclass(frozen=True)
class ClassificationResult:
    intent: str               # Ex: "general", "scheduling", "pricing", "support"
    confidence: float         # 0.0 - 1.0
    prompt_template: str      # Nome do template a usar
    metadata: dict            # Dados extras para analytics

async def classify_intent(
    text: str,
    context: list[ContextMessage],
    agent_config: AgentConfig,
) -> ClassificationResult:
    """
    Classifica intent da mensagem.
    
    MVP: LLM-based classification com confiança.
    Se confidence < 0.7, retorna intent="general" como fallback.
    """
```

### 6. LLM Generation (pydantic-ai Agent)

```python
async def generate_response(
    agent_config: AgentConfig,
    prompt: PromptConfig,
    context: list[ContextMessage],
    user_message: str,
    classification: ClassificationResult,
    deps: ConversationDeps,
    semaphore: asyncio.Semaphore,
) -> GenerationResult:
    """
    Gera resposta via pydantic-ai agent.
    
    - Aguarda semáforo (max 10 concurrent LLM calls).
    - Timeout: 60s.
    - System prompt: safety_prefix + system_prompt + safety_suffix (sandwich).
    - Tools: Apenas os habilitados em prompt.tools_enabled (whitelist).
    
    Returns:
        GenerationResult com text, model, tokens_used, tool_calls_count, latency_ms.
    
    Raises:
        LLMTimeoutError: Se exceder 60s.
        LLMError: Erro genérico do provider.
    """
```

### 7. Response Evaluation

```python
@dataclass(frozen=True)
class EvalResult:
    passed: bool
    quality_score: float      # 0.0 - 1.0
    checks: dict[str, bool]   # {"empty": False, "too_short": False, "bad_encoding": False}
    action: str               # "deliver" | "retry" | "fallback"
    reason: str | None        # Se action != "deliver", motivo

async def evaluate_response(
    response_text: str,
    context: EvalContext,
) -> EvalResult:
    """
    Avaliação heurística da resposta.
    
    Checks:
    - Vazia: len(text.strip()) == 0 → retry/fallback
    - Muito curta: len(text.strip()) < 10 → retry/fallback
    - Encoding incorreto: \\ufffd ou chars de controle → retry/fallback
    - Muito longa: > 4000 chars → truncar (não retry)
    
    Score: 1.0 se todos checks passam, 0.0 se qualquer falha crítica.
    """
```

### 8. Output Guard

```python
async def check_output(text: str) -> GuardResult:
    """
    Layer A (regex) guardrails na saída.
    
    Diferente da entrada:
    - PII detectado na saída É mascarado/removido (não apenas logado).
    - Retorna texto sanitizado pronto para envio.
    
    Latência: <5ms.
    """
```

## FlushCallback — Nova Signature

### Antes (Echo — current)

```python
FlushCallback = Callable[[str, str, str | None, str], Awaitable[None]]
# (tenant_id, sender_key, group_id, text) -> None
```

### Depois (Conversation Pipeline)

```python
FlushCallback = Callable[[str, str, str | None, str, str | None], Awaitable[None]]
# (tenant_id, sender_key, group_id, text, agent_id) -> None
```

### Backward Compatibility

O `_parse_flush_items()` extrai `agent_id` do JSON item. Se ausente (items legacy), retorna `None`. O pipeline usa `tenant.default_agent_id` como fallback quando `agent_id is None`.

## Fallback Message

```python
FALLBACK_MESSAGE = "Desculpe, não consegui processar sua mensagem. Tente novamente em instantes."
```

Usado quando:
1. LLM falha após retry (timeout, erro de API).
2. Avaliador rejeita resposta após retry.
3. Pool Postgres esgotado (após 5s de wait).
4. Erro inesperado no pipeline.

## Error Handling

| Erro | Ação | Resposta ao Cliente |
|------|------|-------------------|
| LLM timeout (60s) | Log ERROR, retry 1x | Fallback se retry falha |
| LLM API error | Log ERROR, retry 1x | Fallback se retry falha |
| Postgres pool esgotado | Aguarda 5s, log ERROR | Fallback |
| Customer create falha | Log ERROR | Fallback |
| Input guard bloqueia | Log WARN | Mensagem informativa ("Sua mensagem é muito longa...") |
| Agent não encontrado | Log ERROR | Fallback |
| Semáforo timeout (60s) | Log WARN | Fallback |
