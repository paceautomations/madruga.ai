"""qa_startup.py — Runtime QA & Testing Pyramid infrastructure.

CLI script that reads the testing: block from platform.yaml and provides:
  --parse-config   Parse and validate the testing manifest
  --start          Start services and wait for health checks
  --validate-env   Compare required_env vs actual .env file
  --validate-urls  Check reachability and content of declared URLs
  --full           Sequence: start → validate-env → validate-urls

Invariants (ADR-004 / FR-022):
  - Only stdlib + pyyaml used (no external deps)
  - env_present / env_missing contain ONLY key names, never values
  - Never executes docker compose down or any destructive commands
  - Idempotent: safe to call multiple times

Exit codes:
  0 — ok or warn
  1 — BLOCKER found
  2 — Configuration error (platform.yaml invalid / testing: absent)
  3 — Unexpected error
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Dataclasses (per data-model.md)
# ---------------------------------------------------------------------------


@dataclass
class StartupConfig:
    type: str  # docker | npm | make | venv | script | none
    command: str | None = None  # override of default command for type
    ready_timeout: int = 60  # seconds to wait for health checks


@dataclass
class HealthCheck:
    url: str
    method: str = "GET"
    expect_status: int = 200
    expect_body_contains: str | None = None
    label: str = ""


@dataclass
class URLEntry:
    url: str
    type: str  # api | frontend
    label: str
    expect_status: int | list[int] = 200
    expect_redirect: str | None = None
    expect_contains: list[str] = field(default_factory=list)
    requires_auth: bool = False


@dataclass
class TestingManifest:
    startup: StartupConfig
    health_checks: list[HealthCheck] = field(default_factory=list)
    urls: list[URLEntry] = field(default_factory=list)
    required_env: list[str] = field(default_factory=list)  # keys only
    env_file: str | None = None
    journeys_file: str | None = None


@dataclass
class Finding:
    level: str  # BLOCKER | WARN | INFO
    message: str
    detail: str = ""


@dataclass
class HealthCheckResult:
    label: str
    url: str
    status: str  # ok | failed | timeout
    detail: str = ""


@dataclass
class URLResult:
    url: str
    label: str
    status_code: int | None = None
    ok: bool = False
    detail: str = ""


@dataclass
class StartupResult:
    status: str  # ok | warn | blocker
    findings: list[Finding] = field(default_factory=list)
    health_checks: list[HealthCheckResult] = field(default_factory=list)
    env_missing: list[str] = field(default_factory=list)  # keys only
    env_present: list[str] = field(default_factory=list)  # keys only
    urls: list[URLResult] = field(default_factory=list)
    skipped_startup: bool = False


# ---------------------------------------------------------------------------
# T002 — load_manifest
# ---------------------------------------------------------------------------


def _parse_health_check(raw: dict) -> HealthCheck:
    return HealthCheck(
        url=raw["url"],
        method=raw.get("method", "GET"),
        expect_status=raw.get("expect_status", 200),
        expect_body_contains=raw.get("expect_body_contains"),
        label=raw.get("label", ""),
    )


def _parse_url_entry(raw: dict) -> URLEntry:
    expect_status = raw.get("expect_status", 200)
    # YAML may parse [200, 401] as a list already
    if not isinstance(expect_status, (int, list)):
        expect_status = 200
    return URLEntry(
        url=raw["url"],
        type=raw.get("type", "api"),
        label=raw.get("label", ""),
        expect_status=expect_status,
        expect_redirect=raw.get("expect_redirect"),
        expect_contains=raw.get("expect_contains") or [],
        requires_auth=raw.get("requires_auth", False),
    )


def _parse_manifest(testing: dict) -> TestingManifest:
    startup_raw = testing.get("startup", {})
    startup = StartupConfig(
        type=startup_raw.get("type", "none"),
        command=startup_raw.get("command"),
        ready_timeout=startup_raw.get("ready_timeout", 60),
    )
    health_checks = [_parse_health_check(hc) for hc in (testing.get("health_checks") or [])]
    urls = [_parse_url_entry(u) for u in (testing.get("urls") or [])]
    required_env = testing.get("required_env") or []
    return TestingManifest(
        startup=startup,
        health_checks=health_checks,
        urls=urls,
        required_env=[str(k) for k in required_env],
        env_file=testing.get("env_file"),
        journeys_file=testing.get("journeys_file"),
    )


def load_manifest(platform: str, repo_root: Path) -> TestingManifest | None:
    """Load and parse testing: block from platform.yaml. Returns None if absent."""
    yaml_path = repo_root / "platforms" / platform / "platform.yaml"
    try:
        data = yaml.safe_load(yaml_path.read_text())
    except FileNotFoundError:
        return None
    except yaml.YAMLError:
        return None
    if not isinstance(data, dict):
        return None
    testing = data.get("testing")
    if not testing:
        return None
    return _parse_manifest(testing)


# ---------------------------------------------------------------------------
# T003 — parse_journeys
# ---------------------------------------------------------------------------


def parse_journeys(content: str) -> list[dict]:
    """Extract YAML fenced journey blocks from journeys.md content.

    Returns only dicts where 'id' starts with 'J-'.
    Malformed blocks are silently ignored.
    """
    blocks = re.findall(r"```yaml\n(.*?)```", content, re.DOTALL)
    journeys = []
    for block in blocks:
        try:
            data = yaml.safe_load(block)
            if isinstance(data, dict) and str(data.get("id", "")).startswith("J-"):
                journeys.append(data)
        except yaml.YAMLError:
            pass  # skip malformed blocks silently
    return journeys


# ---------------------------------------------------------------------------
# T004 — _read_env_keys
# ---------------------------------------------------------------------------


def _read_env_keys(env_path: Path) -> set[str]:
    """Read only variable names (keys) from a .env file.

    FR-022: Never read or expose values.
    Returns empty set if file is absent.
    """
    if not env_path.exists():
        return set()
    keys: set[str] = set()
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if "=" in stripped:
                key = stripped.split("=", 1)[0].strip()
                if key:
                    keys.add(key)
    except OSError:
        return set()
    return keys


# ---------------------------------------------------------------------------
# T005 — validate_env
# ---------------------------------------------------------------------------


def validate_env(manifest: TestingManifest, cwd: Path) -> StartupResult:
    """Compare required_env vs actual .env keys.

    FR-022: env_present and env_missing contain ONLY key names, never values.
    If env_file is None, returns empty ok result.
    """
    if manifest.env_file is None:
        return StartupResult(status="ok")

    env_path = cwd / manifest.env_file
    actual_keys = _read_env_keys(env_path)

    # Also read .env (the real one, not the example) if env_file points to .env.example
    real_env_path = cwd / ".env"
    real_keys = _read_env_keys(real_env_path)

    # Which keys are actually "present" — use the real .env as authoritative
    # If env_file IS .env, use actual_keys; otherwise use real_keys as authoritative presence
    if manifest.env_file in (".env", ".env.local"):
        present_keys = actual_keys
        example_keys: set[str] = set()
    else:
        # env_file is .env.example or similar — compare real .env against example
        present_keys = real_keys
        example_keys = actual_keys  # keys declared in example

    findings: list[Finding] = []
    env_missing: list[str] = []
    env_present: list[str] = []

    for var in manifest.required_env:
        if var in present_keys:
            env_present.append(var)
        else:
            env_missing.append(var)
            findings.append(
                Finding(
                    level="BLOCKER",
                    message=f"{var} ausente — variável obrigatória declarada em testing.required_env",
                    detail="",
                )
            )

    # WARN for vars in example but not in required_env and missing from real .env
    optional_missing = example_keys - set(manifest.required_env) - present_keys
    for var in sorted(optional_missing):
        findings.append(
            Finding(
                level="WARN",
                message=f"{var} ausente em .env (declarado em {manifest.env_file} mas não em required_env)",
                detail="",
            )
        )

    status = "ok"
    if any(f.level == "BLOCKER" for f in findings):
        status = "blocker"
    elif any(f.level == "WARN" for f in findings):
        status = "warn"

    return StartupResult(
        status=status,
        findings=findings,
        env_missing=env_missing,
        env_present=env_present,
    )


# ---------------------------------------------------------------------------
# T006 — quick_check
# ---------------------------------------------------------------------------


def quick_check(health_checks: list[HealthCheck], timeout: int = 3) -> bool:
    """Perform a fast health check of all declared endpoints.

    Returns True only if ALL health checks respond with expected status.
    Exceptions are caught silently.
    """
    for hc in health_checks:
        try:
            req = urllib.request.Request(hc.url, method=hc.method)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status != hc.expect_status:
                    return False
                if hc.expect_body_contains:
                    body = resp.read().decode("utf-8", errors="replace")
                    if hc.expect_body_contains not in body:
                        return False
        except (urllib.error.URLError, OSError, Exception):
            return False
    return True


# ---------------------------------------------------------------------------
# T007 — execute_startup
# ---------------------------------------------------------------------------

_DEFAULT_STARTUP_COMMANDS: dict[str, str] = {
    "docker": "docker compose up -d",
    "npm": "npm run dev",
    "make": "make run",
}


def execute_startup(manifest: TestingManifest, cwd: Path) -> tuple[int, str]:
    """Execute the startup command for the declared startup type.

    Returns (returncode, stderr_output).
    NEVER runs destructive commands (docker compose down, docker stop, etc.).
    """
    startup_type = manifest.startup.type
    command = manifest.startup.command

    if startup_type == "none":
        return (0, "")

    if command is None:
        command = _DEFAULT_STARTUP_COMMANDS.get(startup_type)

    if command is None:
        return (2, f"No command configured for startup type '{startup_type}'")

    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=str(cwd),
            capture_output=True,
            timeout=30,
            text=True,
        )
        return (result.returncode, result.stderr or "")
    except subprocess.TimeoutExpired:
        return (1, "Startup command timed out after 30s")
    except OSError as exc:
        return (1, str(exc))


# ---------------------------------------------------------------------------
# T010 — _is_placeholder
# ---------------------------------------------------------------------------

_PLACEHOLDER_STRINGS = [
    b"You need to enable JavaScript",
    b"React App",
    b"Vite + React",
    b"Welcome to nginx",
    b"It works!",
]


def _is_placeholder(body: bytes, content_type: str, url_type: str) -> bool:
    """Detect if the response body appears to be a placeholder page.

    FR-023 — 4 OR criteria:
    1. Body < 500 bytes after strip
    2. Body contains known placeholder literals
    3. <body> tag contains only whitespace
    4. HTTP 200 with content_type != text/html for url_type == frontend
    """
    stripped = body.strip()

    # Criterion 1: too short
    if len(stripped) < 500:
        return True

    # Criterion 2: known placeholder strings
    for phrase in _PLACEHOLDER_STRINGS:
        if phrase in body:
            return True

    # Criterion 3: <body> with only whitespace
    body_tag_match = re.search(rb"<body[^>]*>(.*?)</body>", body, re.DOTALL | re.IGNORECASE)
    if body_tag_match:
        body_content = body_tag_match.group(1).strip()
        if not body_content:
            return True

    # Criterion 4: non-html content type for frontend URL
    if url_type == "frontend" and "text/html" not in content_type.lower():
        return True

    return False


# ---------------------------------------------------------------------------
# T008 — wait_for_health
# ---------------------------------------------------------------------------


def wait_for_health(
    health_checks: list[HealthCheck],
    startup_type: str,
    timeout: int,
    cwd: Path,
) -> StartupResult:
    """Poll health checks every 2s until all pass or timeout expires.

    On timeout, collects docker compose logs if startup_type == docker.
    Returns StartupResult with per-check results and BLOCKER if timed out.
    """
    print(f"Waiting up to {timeout}s for health checks...", file=sys.stderr)

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if quick_check(health_checks, timeout=3):
            hc_results = [
                HealthCheckResult(label=hc.label, url=hc.url, status="ok")
                for hc in health_checks
            ]
            return StartupResult(status="ok", health_checks=hc_results)
        remaining = deadline - time.monotonic()
        if remaining > 2:
            time.sleep(2)

    # Timeout — determine which checks failed
    hc_results: list[HealthCheckResult] = []
    failed_labels: list[str] = []
    for hc in health_checks:
        try:
            req = urllib.request.Request(hc.url, method=hc.method)
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == hc.expect_status:
                    hc_results.append(HealthCheckResult(label=hc.label, url=hc.url, status="ok"))
                    continue
                detail = f"HTTP {resp.status}, esperado {hc.expect_status}"
                hc_results.append(
                    HealthCheckResult(label=hc.label, url=hc.url, status="failed", detail=detail)
                )
                failed_labels.append(hc.label)
        except (urllib.error.URLError, OSError) as exc:
            detail = str(exc)
            hc_results.append(
                HealthCheckResult(label=hc.label, url=hc.url, status="timeout", detail=detail)
            )
            failed_labels.append(hc.label)

    # Collect docker logs if applicable
    docker_logs = ""
    if startup_type == "docker":
        try:
            log_result = subprocess.run(
                ["docker", "compose", "logs", "--tail", "50"],
                cwd=str(cwd),
                capture_output=True,
                timeout=15,
                text=True,
            )
            docker_logs = log_result.stdout + log_result.stderr
        except (subprocess.TimeoutExpired, OSError):
            docker_logs = "(failed to collect docker logs)"

    failed_str = ", ".join(f"'{lbl}'" for lbl in failed_labels)
    detail = f"Health checks falhados: {failed_str}."
    if docker_logs:
        detail += f" Logs:\n{docker_logs[:2000]}"

    finding = Finding(
        level="BLOCKER",
        message=f"Health checks falharam após {timeout}s: {failed_str}",
        detail=detail,
    )
    return StartupResult(status="blocker", findings=[finding], health_checks=hc_results)


# ---------------------------------------------------------------------------
# T009 — validate_urls + helpers
# ---------------------------------------------------------------------------


def _startup_hint(startup_type: str) -> str:
    hints = {
        "docker": "verifique 'docker compose ps' e port bindings no docker-compose.override.yml",
        "npm": "verifique se 'npm run dev' está rodando",
        "make": "verifique se 'make run' está em execução",
    }
    return hints.get(startup_type, "verifique se os serviços estão em execução")


def validate_urls(manifest: TestingManifest) -> StartupResult:
    """Check reachability and content of all URLs declared in testing.urls.

    FR-013: BLOCKER for inaccessible URLs or unexpected status codes.
    FR-023: WARN for placeholder HTML content.
    Handles expect_redirect by disabling auto-redirect and checking Location header.
    """
    findings: list[Finding] = []
    url_results: list[URLResult] = []
    startup_hint = _startup_hint(manifest.startup.type)

    for entry in manifest.urls:
        url = entry.url
        label = entry.label

        try:
            # Disable automatic redirect following so we can check Location header
            class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
                def http_error_302(self, req, fp, code, msg, headers):
                    raise urllib.error.HTTPError(req.full_url, code, msg, headers, fp)

                http_error_301 = http_error_302
                http_error_303 = http_error_302
                http_error_307 = http_error_302
                http_error_308 = http_error_302

            if entry.expect_redirect:
                opener = urllib.request.build_opener(NoRedirectHandler)
            else:
                opener = urllib.request.build_opener()

            req = urllib.request.Request(url)
            with opener.open(req, timeout=10) as resp:
                status_code = resp.status
                content_type = resp.headers.get("Content-Type", "")
                body = resp.read()

        except urllib.error.HTTPError as exc:
            # Redirect responses come here when expect_redirect is set
            if entry.expect_redirect:
                location = exc.headers.get("Location", "")
                status_code = exc.code
                # Check if redirect goes to expected path
                if entry.expect_redirect in location:
                    url_results.append(
                        URLResult(url=url, label=label, status_code=status_code, ok=True, detail="redirect ok")
                    )
                    continue
                else:
                    detail = f"Redirect para '{location}', esperado '{entry.expect_redirect}'"
                    findings.append(Finding(level="BLOCKER", message=f"{url} redireciona para lugar errado", detail=detail))
                    url_results.append(URLResult(url=url, label=label, status_code=status_code, ok=False, detail=detail))
                    continue
            else:
                status_code = exc.code
                body = b""
                content_type = ""

        except (urllib.error.URLError, OSError) as exc:
            detail = f"{startup_hint}"
            findings.append(
                Finding(
                    level="BLOCKER",
                    message=f"{url} inacessível — {type(exc).__name__}",
                    detail=detail,
                )
            )
            url_results.append(URLResult(url=url, label=label, status_code=None, ok=False, detail=str(exc)))
            continue

        # Check expected status
        expected = entry.expect_status
        if isinstance(expected, int):
            expected_list = [expected]
        else:
            expected_list = expected

        if status_code not in expected_list:
            detail = f"HTTP {status_code}, esperado {expected}"
            findings.append(Finding(level="BLOCKER", message=f"{url} retornou {status_code}, esperado {expected}", detail=detail))
            url_results.append(URLResult(url=url, label=label, status_code=status_code, ok=False, detail=detail))
            continue

        # Check redirect expectation (when we followed redirects and shouldn't have)
        if entry.expect_redirect:
            # We reached here only if opener followed the redirect (shouldn't happen with NoRedirectHandler)
            # But just in case:
            detail = f"Esperava redirect para '{entry.expect_redirect}' mas recebeu HTTP {status_code}"
            findings.append(Finding(level="BLOCKER", message=f"{url} não redirecionou como esperado", detail=detail))
            url_results.append(URLResult(url=url, label=label, status_code=status_code, ok=False, detail=detail))
            continue

        # Check expected body contains
        if entry.expect_contains:
            body_str = body.decode("utf-8", errors="replace")
            missing = [s for s in entry.expect_contains if s not in body_str]
            if missing:
                detail = f"Conteúdo esperado ausente: {missing}"
                findings.append(Finding(level="BLOCKER", message=f"{url} não contém conteúdo esperado", detail=detail))
                url_results.append(URLResult(url=url, label=label, status_code=status_code, ok=False, detail=detail))
                continue

        # Check for placeholder content
        if _is_placeholder(body, content_type, entry.type):
            placeholder_detail = _placeholder_detail(body, content_type, entry.type)
            findings.append(
                Finding(
                    level="WARN",
                    message=f"{url} responde mas conteúdo parece placeholder",
                    detail=placeholder_detail,
                )
            )
            url_results.append(
                URLResult(url=url, label=label, status_code=status_code, ok=False, detail="placeholder detected")
            )
            continue

        url_results.append(URLResult(url=url, label=label, status_code=status_code, ok=True))

    status = "ok"
    if any(f.level == "BLOCKER" for f in findings):
        status = "blocker"
    elif any(f.level == "WARN" for f in findings):
        status = "warn"

    return StartupResult(status=status, findings=findings, urls=url_results)


def _placeholder_detail(body: bytes, content_type: str, url_type: str) -> str:
    stripped = body.strip()
    if len(stripped) < 500:
        return "Body < 500 bytes após strip"
    for phrase in _PLACEHOLDER_STRINGS:
        if phrase in body:
            return f"Body contém placeholder literal: {phrase.decode()}"
    body_match = re.search(rb"<body[^>]*>(.*?)</body>", body, re.DOTALL | re.IGNORECASE)
    if body_match and not body_match.group(1).strip():
        return "<body> contém apenas whitespace"
    if url_type == "frontend" and "text/html" not in content_type.lower():
        return f"Content-Type '{content_type}' não é text/html para URL frontend"
    return "conteúdo suspeito de placeholder"


# ---------------------------------------------------------------------------
# T011 — start_services, run_full, main
# ---------------------------------------------------------------------------


def start_services(manifest: TestingManifest, cwd: Path) -> StartupResult:
    """Start platform services and wait for health checks.

    If services are already healthy (quick_check passes), skip startup.
    NEVER runs destructive commands.
    """
    print("Checking if services are already running...", file=sys.stderr)

    if manifest.startup.type == "none":
        hc_results = [
            HealthCheckResult(label=hc.label, url=hc.url, status="ok")
            for hc in manifest.health_checks
        ]
        return StartupResult(status="ok", health_checks=hc_results, skipped_startup=True)

    if quick_check(manifest.health_checks, timeout=3):
        print("Services already healthy — skipping startup.", file=sys.stderr)
        hc_results = [
            HealthCheckResult(label=hc.label, url=hc.url, status="ok")
            for hc in manifest.health_checks
        ]
        return StartupResult(status="ok", health_checks=hc_results, skipped_startup=True)

    print(f"Starting services (type: {manifest.startup.type})...", file=sys.stderr)
    returncode, stderr = execute_startup(manifest, cwd)

    if returncode != 0:
        finding = Finding(
            level="BLOCKER",
            message=f"Startup command falhou (exit {returncode})",
            detail=stderr[:2000] if stderr else "",
        )
        return StartupResult(status="blocker", findings=[finding])

    return wait_for_health(
        manifest.health_checks,
        manifest.startup.type,
        manifest.startup.ready_timeout,
        cwd,
    )


def _merge_results(results: list[StartupResult]) -> StartupResult:
    """Merge multiple StartupResult objects into one."""
    all_findings: list[Finding] = []
    all_hc: list[HealthCheckResult] = []
    all_env_missing: list[str] = []
    all_env_present: list[str] = []
    all_urls: list[URLResult] = []
    skipped = False

    for r in results:
        all_findings.extend(r.findings)
        all_hc.extend(r.health_checks)
        all_env_missing.extend(r.env_missing)
        all_env_present.extend(r.env_present)
        all_urls.extend(r.urls)
        if r.skipped_startup:
            skipped = True

    status = "ok"
    if any(f.level == "BLOCKER" for f in all_findings):
        status = "blocker"
    elif any(f.level == "WARN" for f in all_findings):
        status = "warn"

    return StartupResult(
        status=status,
        findings=all_findings,
        health_checks=all_hc,
        env_missing=all_env_missing,
        env_present=all_env_present,
        urls=all_urls,
        skipped_startup=skipped,
    )


def run_full(manifest: TestingManifest, cwd: Path) -> StartupResult:
    """Sequence: start → validate_env → validate_urls. Merge all results."""
    start_result = start_services(manifest, cwd)
    env_result = validate_env(manifest, cwd)
    url_result = validate_urls(manifest)
    return _merge_results([start_result, env_result, url_result])


def _result_to_dict(result: StartupResult) -> dict:
    """Serialize StartupResult to a JSON-serializable dict."""
    return {
        "status": result.status,
        "findings": [asdict(f) for f in result.findings],
        "health_checks": [asdict(hc) for hc in result.health_checks],
        "env_missing": result.env_missing,
        "env_present": result.env_present,
        "urls": [asdict(u) for u in result.urls],
        "skipped_startup": result.skipped_startup,
    }


def _print_result(result: StartupResult, use_json: bool) -> None:
    if use_json:
        print(json.dumps(_result_to_dict(result), indent=2))
    else:
        icon = {"ok": "✅", "warn": "⚠️", "blocker": "❌"}.get(result.status, "?")
        print(f"{icon} Status: {result.status.upper()}")
        for f in result.findings:
            level_icon = {"BLOCKER": "❌", "WARN": "⚠️", "INFO": "ℹ️"}.get(f.level, "")
            print(f"  {level_icon} [{f.level}] {f.message}")
            if f.detail:
                print(f"     {f.detail}")


def _detect_repo_root() -> Path:
    """Detect REPO_ROOT from env var or via script location (parents[2])."""
    env_root = os.environ.get("REPO_ROOT")
    if env_root:
        return Path(env_root)
    # .specify/scripts/qa_startup.py → parents[2] == repo root
    return Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="qa_startup.py",
        description="Runtime QA startup and validation for madruga.ai platforms",
    )
    parser.add_argument("--platform", required=True, help="Platform name (e.g., madruga-ai)")
    parser.add_argument("--cwd", default=None, help="Working directory for startup commands")
    parser.add_argument("--json", action="store_true", dest="use_json", help="Output JSON to stdout")

    ops = parser.add_mutually_exclusive_group(required=True)
    ops.add_argument("--parse-config", action="store_true", help="Parse and validate testing manifest")
    ops.add_argument("--start", action="store_true", help="Start services and wait for health checks")
    ops.add_argument("--validate-env", action="store_true", help="Validate required env vars")
    ops.add_argument("--validate-urls", action="store_true", help="Validate URL reachability")
    ops.add_argument("--full", action="store_true", help="Full sequence: start → env → urls")

    args = parser.parse_args(argv)

    repo_root = _detect_repo_root()
    cwd = Path(args.cwd).resolve() if args.cwd else Path.cwd()

    try:
        manifest = load_manifest(args.platform, repo_root)
    except Exception as exc:
        print(f"ERROR: Failed to load manifest: {exc}", file=sys.stderr)
        return 3

    if manifest is None:
        if args.use_json:
            print(json.dumps({"error": f"No testing: block found for platform '{args.platform}'"}))
        else:
            print(
                f"⚠️  No testing: block found for platform '{args.platform}' in platform.yaml.",
                file=sys.stderr,
            )
        return 2

    try:
        if args.parse_config:
            # Just validate and print the manifest
            if args.use_json:
                print(
                    json.dumps(
                        {
                            "status": "ok",
                            "startup": {
                                "type": manifest.startup.type,
                                "command": manifest.startup.command,
                                "ready_timeout": manifest.startup.ready_timeout,
                            },
                            "health_checks": len(manifest.health_checks),
                            "urls": len(manifest.urls),
                            "required_env": manifest.required_env,
                            "env_file": manifest.env_file,
                            "journeys_file": manifest.journeys_file,
                        },
                        indent=2,
                    )
                )
            else:
                print(f"✅ Testing manifest loaded for '{args.platform}'")
                print(f"  Startup type: {manifest.startup.type}")
                print(f"  Health checks: {len(manifest.health_checks)}")
                print(f"  URLs: {len(manifest.urls)}")
                print(f"  Required env: {manifest.required_env}")
            return 0

        elif args.start:
            result = start_services(manifest, cwd)

        elif args.validate_env:
            result = validate_env(manifest, cwd)

        elif args.validate_urls:
            result = validate_urls(manifest)

        elif args.full:
            result = run_full(manifest, cwd)

        else:
            print("ERROR: No operation specified", file=sys.stderr)
            return 2

    except Exception as exc:
        print(f"ERROR: Unexpected error: {exc}", file=sys.stderr)
        return 3

    _print_result(result, args.use_json)

    if result.status == "blocker":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
