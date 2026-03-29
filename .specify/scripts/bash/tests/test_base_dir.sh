#!/usr/bin/env bash
# Tests for --base-dir / SPECIFY_BASE_DIR support in SpecKit scripts
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
PASS=0
FAIL=0
ERRORS=""

assert_eq() {
    local desc="$1" expected="$2" actual="$3"
    if [ "$expected" = "$actual" ]; then
        PASS=$((PASS + 1))
        echo "  [PASS] $desc"
    else
        FAIL=$((FAIL + 1))
        ERRORS="$ERRORS\n  [FAIL] $desc: expected='$expected' actual='$actual'"
        echo "  [FAIL] $desc: expected='$expected' actual='$actual'"
    fi
}

assert_contains() {
    local desc="$1" needle="$2" haystack="$3"
    if echo "$haystack" | grep -q "$needle"; then
        PASS=$((PASS + 1))
        echo "  [PASS] $desc"
    else
        FAIL=$((FAIL + 1))
        ERRORS="$ERRORS\n  [FAIL] $desc: '$needle' not found in output"
        echo "  [FAIL] $desc: '$needle' not found in output"
    fi
}

assert_file_exists() {
    local desc="$1" path="$2"
    if [ -f "$path" ]; then
        PASS=$((PASS + 1))
        echo "  [PASS] $desc"
    else
        FAIL=$((FAIL + 1))
        ERRORS="$ERRORS\n  [FAIL] $desc: file not found at $path"
        echo "  [FAIL] $desc: file not found at $path"
    fi
}

cleanup() {
    rm -rf /tmp/test-epic-basedir
    rm -rf "$REPO_ROOT/specs/999-test-basedir"
    # Clean up git branch if created
    git -C "$REPO_ROOT" checkout - 2>/dev/null || true
    git -C "$REPO_ROOT" branch -D 999-test-basedir 2>/dev/null || true
    git -C "$REPO_ROOT" branch -D 998-test-default 2>/dev/null || true
}

trap cleanup EXIT

echo "=== Test: --base-dir in create-new-feature.sh ==="

# T006: --base-dir creates spec in custom dir
echo ""
echo "T006: create-new-feature.sh --base-dir creates spec.md in custom dir"
mkdir -p /tmp/test-epic-basedir
OUTPUT=$(cd "$REPO_ROOT" && bash "$SCRIPT_DIR/create-new-feature.sh" --base-dir /tmp/test-epic-basedir --json --short-name "test-basedir" "Test base dir feature" 2>&1 || true)
SPEC_PATH=$(echo "$OUTPUT" | grep -o '"SPEC_FILE":"[^"]*"' | cut -d'"' -f4)
if [ -n "$SPEC_PATH" ]; then
    assert_contains "T006: SPEC_FILE points to custom dir" "/tmp/test-epic-basedir" "$SPEC_PATH"
    assert_file_exists "T006: spec.md created in custom dir" "$SPEC_PATH"
else
    assert_contains "T006: JSON output contains SPEC_FILE" "SPEC_FILE" "$OUTPUT"
fi

# T007: without --base-dir still creates in specs/
echo ""
echo "T007: create-new-feature.sh without --base-dir creates in specs/"
cleanup 2>/dev/null || true
OUTPUT2=$(cd "$REPO_ROOT" && bash "$SCRIPT_DIR/create-new-feature.sh" --json --short-name "test-default" "Test default dir" 2>&1 || true)
SPEC_PATH2=$(echo "$OUTPUT2" | grep -o '"SPEC_FILE":"[^"]*"' | cut -d'"' -f4)
if [ -n "$SPEC_PATH2" ]; then
    assert_contains "T007: SPEC_FILE points to specs/" "/specs/" "$SPEC_PATH2"
else
    assert_contains "T007: JSON output contains SPEC_FILE" "SPEC_FILE" "$OUTPUT2"
fi

# T008: SPECIFY_BASE_DIR env var in check-prerequisites
echo ""
echo "T008: check-prerequisites.sh with SPECIFY_BASE_DIR"
# Create a minimal feature dir with required files
mkdir -p /tmp/test-epic-basedir
touch /tmp/test-epic-basedir/spec.md
touch /tmp/test-epic-basedir/plan.md
# We need to be on a feature branch for check-prerequisites
cd "$REPO_ROOT"
git checkout -b 999-test-basedir 2>/dev/null || true
export SPECIFY_BASE_DIR=/tmp/test-epic-basedir
OUTPUT3=$(bash "$SCRIPT_DIR/check-prerequisites.sh" --json 2>&1 || true)
unset SPECIFY_BASE_DIR
assert_contains "T008: FEATURE_DIR resolves to custom dir" "/tmp/test-epic-basedir" "$OUTPUT3"

# Summary
echo ""
echo "=== Results ==="
echo "PASS: $PASS"
echo "FAIL: $FAIL"
if [ $FAIL -gt 0 ]; then
    echo -e "\nFailed tests:$ERRORS"
    exit 1
fi
echo "All tests passed!"
