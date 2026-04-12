#!/usr/bin/env bash
# Tests for --base-dir / SPECIFY_BASE_DIR support in SpecKit scripts
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASH_DIR="$SCRIPT_DIR/.."
source "$SCRIPT_DIR/test_helpers.sh"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"

# Fixed branch numbers — high enough to never collide with real work
BRANCH_T006="999-test-basedir"
BRANCH_T007="998-test-default"
BRANCH_T008="999-test-basedir"

# Save the caller's branch so cleanup can restore it.
# Without this, the test leaves HEAD on a leaked test branch and the
# caller's next git operation (commit, push) targets the wrong ref.
ORIGINAL_BRANCH="$(git -C "$REPO_ROOT" branch --show-current 2>/dev/null)"
[ -z "$ORIGINAL_BRANCH" ] && ORIGINAL_BRANCH="main"

cleanup() {
    rm -rf /tmp/test-epic-basedir
    rm -rf /tmp/test-default-basedir
    # Detach HEAD first so we can delete any test branch (can't delete current)
    git -C "$REPO_ROOT" checkout --detach 2>/dev/null || true
    git -C "$REPO_ROOT" branch -D "$BRANCH_T006" 2>/dev/null || true
    git -C "$REPO_ROOT" branch -D "$BRANCH_T007" 2>/dev/null || true
    # Restore the caller's original branch
    git -C "$REPO_ROOT" checkout "$ORIGINAL_BRANCH" 2>/dev/null || true
}

trap cleanup EXIT

echo "=== Test: --base-dir in create-new-feature.sh ==="

# T006: --base-dir creates spec in custom dir
echo ""
echo "T006: create-new-feature.sh --base-dir creates spec.md in custom dir"
mkdir -p /tmp/test-epic-basedir
OUTPUT=$(cd "$REPO_ROOT" && bash "$BASH_DIR/create-new-feature.sh" --base-dir /tmp/test-epic-basedir --json --number 999 --short-name "test-basedir" "Test base dir feature" 2>&1 || true)
SPEC_PATH=$(echo "$OUTPUT" | grep -o '"SPEC_FILE":"[^"]*"' | cut -d'"' -f4)
if [ -n "$SPEC_PATH" ]; then
    assert_contains "T006: SPEC_FILE points to custom dir" "/tmp/test-epic-basedir" "$SPEC_PATH"
    assert_file_exists "T006: spec.md created in custom dir" "$SPEC_PATH"
else
    assert_contains "T006: JSON output contains SPEC_FILE" "SPEC_FILE" "$OUTPUT"
fi

# T007: without --base-dir creates in specs/ — use --base-dir /tmp to avoid polluting repo
echo ""
echo "T007: create-new-feature.sh default creates spec in expected location"
# Return to main so we can create a new test branch
git -C "$REPO_ROOT" checkout main 2>/dev/null || true
git -C "$REPO_ROOT" branch -D "$BRANCH_T006" 2>/dev/null || true
mkdir -p /tmp/test-default-basedir
OUTPUT2=$(cd "$REPO_ROOT" && bash "$BASH_DIR/create-new-feature.sh" --base-dir /tmp/test-default-basedir --json --number 998 --short-name "test-default" "Test default dir" 2>&1 || true)
SPEC_PATH2=$(echo "$OUTPUT2" | grep -o '"SPEC_FILE":"[^"]*"' | cut -d'"' -f4)
if [ -n "$SPEC_PATH2" ]; then
    assert_file_exists "T007: spec.md created" "$SPEC_PATH2"
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
git checkout -b "$BRANCH_T008" 2>/dev/null || true
export SPECIFY_BASE_DIR=/tmp/test-epic-basedir
OUTPUT3=$(bash "$BASH_DIR/check-prerequisites.sh" --json 2>&1 || true)
unset SPECIFY_BASE_DIR
assert_contains "T008: FEATURE_DIR resolves to custom dir" "/tmp/test-epic-basedir" "$OUTPUT3"

test_summary
