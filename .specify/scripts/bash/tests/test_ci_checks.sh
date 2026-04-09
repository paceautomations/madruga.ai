#!/usr/bin/env bash
# Tests for ci-checks.sh — structural/smoke tests only.
# Validates argument parsing and output format, not whether lint/tests pass.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/test_helpers.sh"
CI_CHECKS="$SCRIPT_DIR/../ci-checks.sh"

# Unset recursion guard so we can test ci-checks.sh from within bash-tests
unset CI_CHECKS_RUNNING

echo "=== Test: ci-checks.sh ==="

# T001: --help exits 0
echo ""
echo "T001: --help exits 0 and shows usage"
OUTPUT=$(bash "$CI_CHECKS" --help 2>&1)
RC=$?
assert_eq "T001: exit code 0" "0" "$RC"
assert_contains "T001: shows Usage" "Usage" "$OUTPUT"

# T002: --suite invalid exits 2
echo ""
echo "T002: --suite with invalid name exits 2"
OUTPUT=$(bash "$CI_CHECKS" --suite nonexistent 2>&1) && RC=0 || RC=$?
assert_eq "T002: exit code 2" "2" "$RC"
assert_contains "T002: error mentions unknown suite" "Unknown suite" "$OUTPUT"

# T003: unknown argument exits 2
echo ""
echo "T003: unknown argument exits 2"
OUTPUT=$(bash "$CI_CHECKS" --foobar 2>&1) && RC=0 || RC=$?
assert_eq "T003: exit code 2" "2" "$RC"
assert_contains "T003: error mentions unknown argument" "Unknown argument" "$OUTPUT"

# T004: --json --suite lint produces valid JSON with expected keys
echo ""
echo "T004: --json output is valid JSON with expected keys"
OUTPUT=$(bash "$CI_CHECKS" --suite lint --json 2>&1) && RC=0 || RC=$?
# RC may be 0 or 1 depending on lint status — we only check output format
assert_contains "T004: JSON has passed key" '"passed"' "$OUTPUT"
assert_contains "T004: JSON has suites key" '"suites"' "$OUTPUT"
assert_contains "T004: JSON has total_duration_s" '"total_duration_s"' "$OUTPUT"
# Validate JSON is well-formed
if echo "$OUTPUT" | python3 -m json.tool > /dev/null 2>&1; then
    PASS=$((PASS + 1))
    echo "  [PASS] T004: output is valid JSON"
else
    FAIL=$((FAIL + 1))
    ERRORS="$ERRORS\n  [FAIL] T004: output is not valid JSON"
    echo "  [FAIL] T004: output is not valid JSON"
fi

# T005: --fast flag is accepted and produces valid JSON
# Note: we test with --suite to avoid recursion (--fast includes bash-tests which re-enters)
echo ""
echo "T005: --fast --suite lint produces valid JSON"
OUTPUT=$(bash "$CI_CHECKS" --fast --suite lint --json 2>&1) && RC=0 || RC=$?
assert_contains "T005: JSON has passed key" '"passed"' "$OUTPUT"

test_summary
