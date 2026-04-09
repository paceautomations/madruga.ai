#!/usr/bin/env bash
# Shared test assertion functions for bash test suites.
# Source this file in test scripts: source "$SCRIPT_DIR/test_helpers.sh"

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

test_summary() {
    echo ""
    echo "=== Results ==="
    echo "PASS: $PASS"
    echo "FAIL: $FAIL"
    if [ $FAIL -gt 0 ]; then
        echo -e "\nFailed tests:$ERRORS"
        exit 1
    fi
    echo "All tests passed!"
}
