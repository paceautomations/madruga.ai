#!/usr/bin/env bash
# ci-checks.sh — Single source of truth for CI validation suites.
#
# Used by: .github/workflows/ci.yml (per-suite), Makefile (make ci), /ship skill.
# Excluded suites (CI-only): smoke-test (starts Easter server), portal-build (needs npm).
#
# Usage: ./ci-checks.sh [OPTIONS]
#
# OPTIONS:
#   --suite <name>   Run one suite: lint, db-tests, bash-tests, template-tests
#   --fast           Fast mode: lint + bash-tests only (~2s). Used by /ship.
#   --json           Machine-readable JSON output
#   --help, -h       Show help

set -euo pipefail

# Recursion guard: bash-tests runs test_ci_checks.sh which may call ci-checks.sh again
if [[ "${CI_CHECKS_RUNNING:-}" == "1" ]]; then
    echo '{"passed":true,"suites":[],"total_duration_s":0,"failed_suites":[]}'
    exit 0
fi
export CI_CHECKS_RUNNING=1

SCRIPT_DIR="$(CDPATH="" cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"
REPO_ROOT="$(get_repo_root)"
SCRIPT_START=$SECONDS

SUITE=""
JSON_MODE=false
FAST_MODE=false
VALID_SUITES=("lint" "db-tests" "bash-tests" "template-tests")
FAST_SUITES=("lint" "bash-tests")

# --- Argument parsing ---
i=1
while [ $i -le $# ]; do
    arg="${!i}"
    case "$arg" in
        --json) JSON_MODE=true ;;
        --fast) FAST_MODE=true ;;
        --suite)
            i=$((i + 1))
            SUITE="${!i}" ;;
        --help|-h)
            cat << 'EOF'
Usage: ci-checks.sh [OPTIONS]

Single source of truth for CI validation suites.

OPTIONS:
  --suite <name>   Run one suite: lint, db-tests, bash-tests, template-tests
                   Without --suite, runs all 4 suites sequentially.
  --fast           Run only fast suites (lint + bash-tests, ~2s). For /ship.
  --json           Machine-readable JSON output
  --help, -h       Show this help message

EXAMPLES:
  ./ci-checks.sh                        # Run all suites
  ./ci-checks.sh --suite lint           # Run lint only
  ./ci-checks.sh --suite db-tests --json  # Run tests with JSON output
  ./ci-checks.sh --json                 # All suites, JSON output
EOF
            exit 0
            ;;
        *)
            echo "ERROR: Unknown argument: $arg" >&2
            echo "Run with --help for usage." >&2
            exit 2
            ;;
    esac
    i=$((i + 1))
done

# Validate suite name
if [[ -n "$SUITE" ]]; then
    valid=false
    for s in "${VALID_SUITES[@]}"; do
        [[ "$s" == "$SUITE" ]] && valid=true && break
    done
    if ! $valid; then
        echo "ERROR: Unknown suite '$SUITE'. Valid: ${VALID_SUITES[*]}" >&2
        exit 2
    fi
fi

# --- Suite runners ---
# Each returns 0 on success, non-zero on failure. Output goes to stdout/stderr.

run_lint() {
    python3 "$REPO_ROOT/.specify/scripts/platform_cli.py" lint --all
    python3 -m ruff check "$REPO_ROOT/.specify/scripts/"
    python3 -m ruff format --check "$REPO_ROOT/.specify/scripts/"
}

run_db_tests() {
    python3 -m pytest "$REPO_ROOT/.specify/scripts/tests/" -v --tb=short --timeout=60 --timeout-method=thread --cov --cov-report=term-missing
}

run_bash_tests() {
    local test_dir="$REPO_ROOT/.specify/scripts/bash/tests"
    for f in "$test_dir"/test_*.sh; do
        [ -f "$f" ] || continue
        bash "$f"
    done
}

run_template_tests() {
    python3 -m pytest "$REPO_ROOT/.specify/templates/platform/tests/" -v --tb=short
}

# --- Execution engine ---

RESULTS_NAMES=()
RESULTS_PASSED=()
RESULTS_DURATION=()
RESULTS_OUTPUT=()
TOTAL_PASS=true

run_suite() {
    local name="$1"
    local start_time=$SECONDS
    local output
    local passed=true

    if ! $JSON_MODE; then
        printf "[ci-checks] %-16s ... " "$name"
    fi

    # Capture output and exit code without disabling -e globally
    local rc=0
    output=$(
        case "$name" in
            lint)           run_lint 2>&1 ;;
            db-tests)       run_db_tests 2>&1 ;;
            bash-tests)     run_bash_tests 2>&1 ;;
            template-tests) run_template_tests 2>&1 ;;
        esac
    ) || rc=$?

    local duration=$(( SECONDS - start_time ))
    [[ "$rc" -ne 0 ]] && passed=false && TOTAL_PASS=false

    RESULTS_NAMES+=("$name")
    RESULTS_PASSED+=("$passed")
    RESULTS_DURATION+=("$duration")
    RESULTS_OUTPUT+=("$output")

    if ! $JSON_MODE; then
        if $passed; then
            echo "PASS (${duration}s)"
        else
            echo "FAIL (${duration}s)"
            echo "$output" | tail -20
        fi
    fi
}

# --- Determine which suites to run ---
if [[ -n "$SUITE" ]]; then
    suites_to_run=("$SUITE")
elif $FAST_MODE; then
    suites_to_run=("${FAST_SUITES[@]}")
else
    suites_to_run=("${VALID_SUITES[@]}")
fi

if ! $JSON_MODE; then
    echo "=== CI Checks (${#suites_to_run[@]} suites) ==="
    echo ""
fi

for s in "${suites_to_run[@]}"; do
    run_suite "$s"
done

# --- Output ---

if $JSON_MODE; then
    # Build JSON output
    total_duration=$(( SECONDS - SCRIPT_START ))
    suites_json="["
    failed_json="["
    first=true
    first_failed=true
    for idx in "${!RESULTS_NAMES[@]}"; do
        escaped_output="$(json_escape "${RESULTS_OUTPUT[$idx]}")"
        entry="{\"name\":\"${RESULTS_NAMES[$idx]}\",\"passed\":${RESULTS_PASSED[$idx]},\"duration_s\":${RESULTS_DURATION[$idx]},\"output\":\"${escaped_output}\"}"
        if $first; then first=false; else suites_json+=","; fi
        suites_json+="$entry"
        if [[ "${RESULTS_PASSED[$idx]}" == "false" ]]; then
            if $first_failed; then first_failed=false; else failed_json+=","; fi
            failed_json+="\"${RESULTS_NAMES[$idx]}\""
        fi
    done
    suites_json+="]"
    failed_json+="]"
    echo "{\"passed\":${TOTAL_PASS},\"suites\":${suites_json},\"total_duration_s\":${total_duration},\"failed_suites\":${failed_json}}"
else
    echo ""
    if $TOTAL_PASS; then
        echo "=== All checks passed ==="
    else
        failed_list=""
        for idx in "${!RESULTS_NAMES[@]}"; do
            [[ "${RESULTS_PASSED[$idx]}" == "false" ]] && failed_list+=" ${RESULTS_NAMES[$idx]}"
        done
        echo "=== FAILED:${failed_list} ==="
    fi
fi

$TOTAL_PASS && exit 0 || exit 1
