#!/usr/bin/env python3
"""screen_capture.py — Python orchestrator for the screen-flow capture pipeline.

Implements the contract documented at:
    platforms/madruga-ai/epics/027-screen-flow-canvas/contracts/capture-script.contract.md

Public surface used by tests + CI workflow:
    main(argv) -> int                        — CLI entry; returns process exit code
    load_capture_config(platform_dir)        — read platform.yaml.screen_flow.capture
    load_screen_flow(yaml_path)              — read screen-flow.yaml
    save_screen_flow(yaml_path, doc)         — write back, lock-protected
    validate_env_vars(prefix)                — raises if required env vars missing
    capture_with_retries(...)                — pure retry/backoff state machine
    apply_capture_result(doc, screen_id, r)  — mutate doc with success/failure record
    compute_workflow_exit_code(results)      — 0 if all captured, 1 if any failed
    acquire_yaml_lock(yaml_path)             — fcntl-based exclusive lock (FR-035)

The Python side intentionally stays pure (zero Playwright dep) so unit/integration
tests can drive it without spinning up a browser. Each Screen is captured by a
runner callable injected at the top level — production replaces it with an
``npx playwright test screen_capture.spec.ts`` subprocess; tests replace it with
a deterministic stub.

Logs are emitted as NDJSON on stdout. Each event obeys the schema documented in
the contract: timestamp, level, message, correlation_id, context.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
SPEC_FILENAME = "screen_capture.spec.ts"

# Failure reasons mirror screen-flow.schema.json $defs.CaptureFailure.reason
FAILURE_REASONS: set[str] = {
    "timeout",
    "auth_expired",
    "network_error",
    "app_crash",
    "sw_cleanup_failed",
    "mock_route_unmatched",
    "unknown",
}

DEFAULT_BACKOFF: tuple[float, ...] = (1.0, 2.0, 4.0)
DEFAULT_GOTO_TIMEOUT_MS = 30_000
DEFAULT_TOTAL_TIMEOUT_S = 30 * 60  # 30 minutes (FR-045 total)
MAX_PNG_BYTES = 500_000  # FR-034


# ───────────────────────────────────────────────────────────────────────────────
# Structured logging (NDJSON on stdout)
# ───────────────────────────────────────────────────────────────────────────────


def emit_event(
    level: str,
    message: str,
    *,
    correlation_id: str | None = None,
    stream=None,
    **context: Any,
) -> None:
    """Write one NDJSON line to stdout (or override) per event."""
    record = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        "level": level,
        "message": message,
    }
    if correlation_id is not None:
        record["correlation_id"] = correlation_id
    if context:
        record["context"] = context
    out = stream if stream is not None else sys.stdout
    out.write(json.dumps(record, default=str) + "\n")
    out.flush()


# ───────────────────────────────────────────────────────────────────────────────
# Filesystem helpers
# ───────────────────────────────────────────────────────────────────────────────


def load_capture_config(platform_dir: Path) -> dict[str, Any]:
    """Read platforms/<name>/platform.yaml and return the screen_flow.capture block.

    Raises FileNotFoundError if platform.yaml is missing, KeyError if the platform
    is opted out (enabled=false), and ValueError if mandatory fields are absent.
    """
    pyaml = platform_dir / "platform.yaml"
    if not pyaml.exists():
        raise FileNotFoundError(f"platform.yaml not found at {pyaml}")
    data = yaml.safe_load(pyaml.read_text(encoding="utf-8")) or {}
    sf = data.get("screen_flow") or {}
    if not sf.get("enabled"):
        raise KeyError(
            f"Platform {platform_dir.name!r} has screen_flow.enabled=false "
            f"or missing — capture skipped (skip_reason={sf.get('skip_reason')!r})"
        )
    capture = sf.get("capture")
    if not capture:
        raise ValueError(
            f"Platform {platform_dir.name!r} has enabled=true but no capture block"
        )
    if not capture.get("test_user_marker"):
        raise ValueError(
            "capture.test_user_marker is required when enabled=true (FR-047) — "
            f"platform={platform_dir.name!r}"
        )
    return capture


def load_screen_flow(yaml_path: Path) -> dict[str, Any]:
    return yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}


def save_screen_flow(yaml_path: Path, doc: dict[str, Any]) -> None:
    """Re-serialize the YAML.

    Note: stdlib + pyyaml is the project policy. Comments are NOT preserved on
    rewrite — the contract documents this fallback. Callers that need comment
    preservation must adopt ruamel.yaml as an explicit, justified extra dep.
    """
    yaml_path.write_text(
        yaml.safe_dump(doc, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


@contextlib.contextmanager
def acquire_yaml_lock(yaml_path: Path):
    """POSIX exclusive lock on the YAML file (FR-035 local side).

    Used by tests (and concurrent dev runs) to verify two simultaneous writers
    serialize cleanly. CI workflow has its own GH Actions ``concurrency`` block;
    this is the in-process safety net.
    """
    yaml_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = yaml_path.with_suffix(yaml_path.suffix + ".lock")
    f = open(lock_path, "w", encoding="utf-8")
    try:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        finally:
            f.close()


# ───────────────────────────────────────────────────────────────────────────────
# Auth + env validation
# ───────────────────────────────────────────────────────────────────────────────


def validate_env_vars(test_user_env_prefix: str, env: dict[str, str] | None = None) -> None:
    """Ensure ``<PREFIX>_TEST_EMAIL`` and ``<PREFIX>_TEST_PASSWORD`` are present."""
    e = env if env is not None else os.environ
    missing = [
        f"{test_user_env_prefix}_{k}"
        for k in ("TEST_EMAIL", "TEST_PASSWORD")
        if not e.get(f"{test_user_env_prefix}_{k}")
    ]
    if missing:
        raise EnvironmentError(
            f"auth_setup_failed: missing env vars {missing}. "
            f"Set them locally or configure GitHub Secrets."
        )


def compute_app_version(repo_dir: Path | None = None) -> str:
    """Short git SHA (7 chars) of the app under test; "unknown" if not a repo."""
    cwd = str(repo_dir) if repo_dir else None
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=cwd,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        return out or "unknown"
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


# ───────────────────────────────────────────────────────────────────────────────
# Retry/failure state machine (pure)
# ───────────────────────────────────────────────────────────────────────────────


@dataclass
class CaptureResult:
    """Outcome of capturing a single screen."""

    screen_id: str
    status: str  # "captured" | "failed"
    image_path: Path | None = None
    image_md5: str | None = None
    viewport: dict[str, int] | None = None
    reason: str | None = None
    last_error_message: str | None = None
    retry_count: int = 0
    durations_ms: list[int] = field(default_factory=list)


def capture_with_retries(
    screen_id: str,
    runner: Callable[[], dict[str, Any]],
    *,
    max_retries: int = 3,
    backoff: Iterable[float] = DEFAULT_BACKOFF,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> CaptureResult:
    """Drive the runner with up to ``max_retries`` retries and exponential backoff.

    runner() must return a dict ``{success: bool, ...}``:
    - On success: ``{"success": True, "image_path": Path, "image_md5": str,
      "viewport": {"w": int, "h": int}}``
    - On failure: ``{"success": False, "reason": str, "error": str}``

    Backoff sequence is exhausted in order; exhaustion → status=failed with the
    last reason. Conforms to FR-045 (3 retries, 1s/2s/4s).
    """
    backoff = tuple(backoff)
    durations: list[int] = []
    last_reason = "unknown"
    last_error = ""
    last_retry_count = 0
    for attempt in range(max_retries + 1):
        start = clock()
        try:
            outcome = runner()
        except Exception as exc:  # treat raised exceptions as transient
            outcome = {"success": False, "reason": "unknown", "error": repr(exc)}
        elapsed_ms = int((clock() - start) * 1000)
        durations.append(elapsed_ms)
        last_retry_count = attempt
        if outcome.get("success"):
            return CaptureResult(
                screen_id=screen_id,
                status="captured",
                image_path=outcome.get("image_path"),
                image_md5=outcome.get("image_md5"),
                viewport=outcome.get("viewport"),
                retry_count=attempt,
                durations_ms=durations,
            )
        last_reason = outcome.get("reason", "unknown")
        if last_reason not in FAILURE_REASONS:
            last_reason = "unknown"
        last_error = (outcome.get("error") or "")[:500]
        if attempt < max_retries:
            sleep(backoff[min(attempt, len(backoff) - 1)])
    return CaptureResult(
        screen_id=screen_id,
        status="failed",
        reason=last_reason,
        last_error_message=last_error,
        retry_count=last_retry_count,
        durations_ms=durations,
    )


# ───────────────────────────────────────────────────────────────────────────────
# YAML mutation (pure)
# ───────────────────────────────────────────────────────────────────────────────


def apply_capture_result(
    doc: dict[str, Any],
    result: CaptureResult,
    *,
    app_version: str,
    captured_at: str | None = None,
) -> dict[str, Any]:
    """Mutate ``doc`` in place: update the screen with capture/failure metadata.

    Status transitions enforced (cf. data-model.md E2):
    - any → captured: requires image, image_md5, viewport
    - any → failed: requires reason

    Returns ``doc`` for chaining.
    """
    captured_at = captured_at or _utc_iso()
    for screen in doc.get("screens") or []:
        if screen.get("id") != result.screen_id:
            continue
        if result.status == "captured":
            screen["status"] = "captured"
            screen.pop("failure", None)
            if result.image_path is not None:
                # Path is normalized to be relative to platform repo root
                screen["image"] = str(result.image_path)
            screen["capture"] = {
                "captured_at": captured_at,
                "app_version": app_version,
                "image_md5": result.image_md5 or "0" * 32,
                "viewport": result.viewport or {"w": 0, "h": 0},
            }
        elif result.status == "failed":
            screen["status"] = "failed"
            screen.pop("capture", None)
            screen["failure"] = {
                "reason": result.reason or "unknown",
                "occurred_at": captured_at,
                "retry_count": result.retry_count,
            }
            if result.last_error_message:
                screen["failure"]["last_error_message"] = result.last_error_message[:500]
        return doc
    raise KeyError(f"screen.id={result.screen_id!r} not present in document")


def compute_workflow_exit_code(results: Iterable[CaptureResult]) -> int:
    """Exit 1 if any screen ended in failed; exit 0 otherwise (FR-046)."""
    return 1 if any(r.status == "failed" for r in results) else 0


def md5_of(path: Path) -> str:
    h = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def png_size_ok(path: Path, *, max_bytes: int = MAX_PNG_BYTES) -> bool:
    return path.exists() and path.stat().st_size <= max_bytes


def _utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


# ───────────────────────────────────────────────────────────────────────────────
# Production runner: dispatch to the Playwright spec via subprocess
# ───────────────────────────────────────────────────────────────────────────────


def _spawn_playwright_runner(
    yaml_path: Path,
    capture_config: dict[str, Any],
    *,
    only_screen: str | None = None,
    timeout_s: int = DEFAULT_TOTAL_TIMEOUT_S,
) -> int:
    """Invoke ``npx playwright test screen_capture.spec.ts`` with config in env.

    The Playwright spec reads SCREEN_FLOW_YAML / SCREEN_FLOW_PLATFORM_DIR
    environment variables and emits its own NDJSON lines on stdout. Exit code
    is propagated unchanged.
    """
    env = dict(os.environ)
    env["SCREEN_FLOW_YAML"] = str(yaml_path)
    env["SCREEN_FLOW_CAPTURE_CONFIG"] = json.dumps(capture_config)
    if only_screen:
        env["SCREEN_FLOW_ONLY"] = only_screen
    cmd = ["npx", "playwright", "test", str(SCRIPTS_DIR / SPEC_FILENAME)]
    proc = subprocess.run(cmd, env=env, timeout=timeout_s, check=False)
    return proc.returncode


# ───────────────────────────────────────────────────────────────────────────────
# CLI
# ───────────────────────────────────────────────────────────────────────────────


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("platform", help="Platform name (e.g. resenhai)")
    p.add_argument("--screen", help="Capture only this screen id (debug)")
    p.add_argument("--dry-run", action="store_true", help="Skip Playwright invocation")
    p.add_argument(
        "--platforms-dir",
        default=str(REPO_ROOT / "platforms"),
        help="Override platforms root (tests).",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    run_id = uuid.uuid4().hex
    platform_dir = Path(args.platforms_dir) / args.platform
    yaml_path = platform_dir / "business" / "screen-flow.yaml"

    emit_event(
        "INFO",
        "capture_run_init",
        correlation_id=run_id,
        platform=args.platform,
        only_screen=args.screen,
        dry_run=args.dry_run,
    )

    try:
        capture_config = load_capture_config(platform_dir)
    except KeyError as exc:
        # Opted out — informational, not an error
        emit_event("INFO", "capture_skipped", correlation_id=run_id, reason=str(exc))
        return 0
    except (FileNotFoundError, ValueError) as exc:
        emit_event("ERROR", "capture_config_invalid", correlation_id=run_id, error=str(exc))
        return 2

    try:
        validate_env_vars(capture_config["auth"]["test_user_env_prefix"])
    except EnvironmentError as exc:
        emit_event("ERROR", "auth_setup_failed", correlation_id=run_id, error=str(exc))
        return 2

    if not yaml_path.exists():
        emit_event("ERROR", "screen_flow_yaml_missing", correlation_id=run_id, path=str(yaml_path))
        return 2

    if args.dry_run:
        emit_event("INFO", "dry_run_complete", correlation_id=run_id)
        return 0

    rc = _spawn_playwright_runner(
        yaml_path,
        capture_config,
        only_screen=args.screen,
    )
    emit_event(
        "INFO" if rc == 0 else "ERROR",
        "capture_run_complete",
        correlation_id=run_id,
        exit_code=rc,
    )
    return rc


if __name__ == "__main__":
    sys.exit(main())
