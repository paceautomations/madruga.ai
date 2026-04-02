# Research: Daemon 24/7

**Date**: 2026-04-01 | **Spec**: [spec.md](spec.md)

## R1: FastAPI lifespan + asyncio.TaskGroup

**Decision**: Usar FastAPI lifespan context manager com asyncio.TaskGroup para gerenciar background tasks.

**Pattern**:
```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    shutdown_event = asyncio.Event()
    async with asyncio.TaskGroup() as tg:
        tg.create_task(dag_scheduler(shutdown_event))
        tg.create_task(telegram_polling(shutdown_event))
        tg.create_task(gate_poller(shutdown_event))
        tg.create_task(health_checker(shutdown_event))
        yield  # FastAPI serves requests here
        # Shutdown triggered
        shutdown_event.set()
        # TaskGroup cancels all tasks on exit

app = FastAPI(lifespan=lifespan)
```

**Caveat com uvicorn**: uvicorn envia SIGINT/SIGTERM que dispara o shutdown do lifespan. O `yield` retorna, o context manager sai do `async with`, e TaskGroup cancela todas as tasks. Funciona nativamente — sem workaround necessario.

**Caveat com TaskGroup**: se qualquer task levantar excecao nao tratada, TaskGroup cancela TODAS as tasks (fail-fast). Cada coroutine deve ter try/except proprio para isolar falhas. Apenas exceptions fatais (ex: DB corrupto) devem propagar para derrubar o grupo.

**Rationale**: Pattern oficial do FastAPI para background tasks de longa duracao. asyncio.TaskGroup (Python 3.11+) fornece structured concurrency com cancelamento automatico.

**Alternatives considered**:
- `BackgroundTasks` do FastAPI: nao serve — e para tasks curtas por request, nao para tasks de longa duracao.
- `asyncio.create_task()` manual: funciona mas sem structured concurrency. Tasks orfas podem vazar em shutdown.

---

## R2: asyncio.create_subprocess_exec com timeout

**Decision**: Usar `asyncio.wait_for(process.communicate(), timeout)` com cleanup explicito.

**Pattern**:
```python
async def dispatch_node_async(cmd, timeout=600):
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=timeout
        )
        if process.returncode != 0:
            return False, stderr.decode()[:500]
        return True, None
    except asyncio.TimeoutError:
        process.kill()       # SIGKILL
        await process.wait() # reap zombie
        return False, f"timeout after {timeout}s"
```

**Rationale**: `asyncio.wait_for()` e o padrao mais seguro porque:
1. Cancela `communicate()` no timeout.
2. `process.kill()` + `await process.wait()` garante cleanup (sem zombies).
3. `communicate()` le stdout/stderr completamente (sem deadlock de buffers).

**Alternatives considered**:
- `asyncio.timeout()` (Python 3.11+): equivalente mas menos explicito. `wait_for` e mais claro sobre o que e cancelado.
- `process.wait()` com `asyncio.timeout`: nao le stdout/stderr, pode deadlock em buffers grandes.
- `asyncio.to_thread(subprocess.run, ...)`: funciona como fallback se `create_subprocess_exec` tiver problemas com claude CLI, mas bloqueia uma thread do pool.

---

## R3: sd_notify para systemd watchdog

**Decision**: Implementar sd_notify via socket Unix direto (~10 LOC). Sem dependencia externa.

**Pattern**:
```python
import os
import socket

def sd_notify(state: str) -> bool:
    """Send notification to systemd. Returns True if sent."""
    addr = os.environ.get("NOTIFY_SOCKET")
    if not addr:
        return False
    if addr.startswith("@"):
        addr = "\0" + addr[1:]  # abstract socket
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    try:
        sock.connect(addr)
        sock.sendall(state.encode())
        return True
    finally:
        sock.close()
```

**Uso**:
```python
sd_notify("READY=1")           # daemon pronto
sd_notify("WATCHDOG=1")        # keepalive ping
sd_notify("STOPPING=1")       # shutdown iniciando
sd_notify("STATUS=running 3 epics")  # status text
```

**systemd unit**:
```ini
[Service]
Type=notify
WatchdogSec=30
NotifyAccess=all
```

**Rationale**: ~10 LOC, zero deps. O protocolo sd_notify e um sendmsg() no NOTIFY_SOCKET (Unix datagram socket). Nao precisa de pacote `sdnotify` (que e 50 LOC fazendo a mesma coisa).

**Alternatives considered**:
- Pacote `sdnotify` no PyPI: funcional mas adiciona dependencia para 10 LOC triviais. Violaria principio de stdlib-first.
- `systemctl --user` via subprocess: nao — sd_notify e a interface correta para Type=notify.

---

## R4: ntfy.sh HTTP POST

**Decision**: Funcao standalone com urllib (stdlib). Sem dependencia externa.

**Pattern**:
```python
import urllib.request

def ntfy_alert(topic: str, message: str, title: str = "Madruga AI") -> bool:
    """Send alert via ntfy.sh. Returns True if sent."""
    try:
        req = urllib.request.Request(
            f"https://ntfy.sh/{topic}",
            data=message.encode(),
            headers={"Title": title},
        )
        urllib.request.urlopen(req, timeout=5)
        return True
    except Exception:
        return False
```

**Rationale**: ~10 LOC, stdlib only (urllib). Fire-and-forget — falha silenciosa e ok (fallback do fallback e structlog).

---

## R5: Graceful shutdown com subprocessos ativos

**Decision**: Usar shutdown_event + SIGTERM para subprocessos + timeout de 10s.

**Flow**:
1. SIGTERM recebido → `shutdown_event.set()`
2. Coroutines verificam `shutdown_event.is_set()` e saem dos loops
3. Subprocessos ativos recebem `process.terminate()` (SIGTERM)
4. `await asyncio.wait_for(process.wait(), timeout=10)` — aguarda ate 10s
5. Se nao encerrou → `process.kill()` (SIGKILL)
6. TaskGroup cancela tasks restantes
7. DB connection fecha
8. `sd_notify("STOPPING=1")`

**Rationale**: SIGTERM primeiro (gentil) + SIGKILL como ultimo recurso. 10s e margem suficiente para claude -p salvar estado.
