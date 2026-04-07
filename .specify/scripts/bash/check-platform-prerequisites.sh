#!/usr/bin/env bash

# Platform pipeline prerequisites checker
#
# Validates skill dependencies by reading platform.yaml pipeline nodes,
# checking file existence, and returning JSON/text status.
#
# Usage: ./check-platform-prerequisites.sh [OPTIONS]
#
# OPTIONS:
#   --platform <name>   Platform name (e.g., madruga-ai, prosauai) [REQUIRED]
#   --skill <id>        Check prerequisites for a specific pipeline node
#   --epic <slug>       Check epic cycle node prerequisites (e.g., 001-onboarding)
#   --status            Show full pipeline status (all nodes)
#   --json              Output in JSON format (default: text)
#   --help, -h          Show help message
#
# One of --skill, --status, or --epic is required.

set -e

# Parse command line arguments
PLATFORM=""
SKILL=""
EPIC=""
JSON_MODE=false
STATUS_MODE=false
USE_DB=false
CHECK_PLATFORM_ONLY=false

i=1
while [ $i -le $# ]; do
    arg="${!i}"
    case "$arg" in
        --json) JSON_MODE=true ;;
        --status) STATUS_MODE=true ;;
        --use-db) USE_DB=true ;;
        --check-platform-only) CHECK_PLATFORM_ONLY=true ;;
        --help|-h)
            cat << 'EOF'
Usage: check-platform-prerequisites.sh [OPTIONS]

Platform pipeline prerequisites checker.

OPTIONS:
  --platform <name>        Platform name (required)
  --skill <id>             Check prerequisites for a specific pipeline node
  --epic <slug>            Check epic cycle node prerequisites (e.g., 001-onboarding)
  --status                 Show full pipeline status (all nodes)
  --json                   Output in JSON format
  --use-db                 Query SQLite DB for enhanced status (hash, staleness)
  --check-platform-only    Only verify platform exists (for non-DAG skills)
  --help, -h               Show this help message

EXAMPLES:
  ./check-platform-prerequisites.sh --json --platform madruga-ai --skill domain-model
  ./check-platform-prerequisites.sh --json --platform madruga-ai --status
  ./check-platform-prerequisites.sh --json --platform madruga-ai --status --use-db
  ./check-platform-prerequisites.sh --json --platform madruga-ai --check-platform-only
  ./check-platform-prerequisites.sh --json --platform prosauai --epic 001-onboarding --status
  ./check-platform-prerequisites.sh --json --platform prosauai --epic 001-onboarding --skill discuss
EOF
            exit 0
            ;;
        --platform)
            i=$((i + 1))
            PLATFORM="${!i}" ;;
        --skill)
            i=$((i + 1))
            SKILL="${!i}" ;;
        --epic)
            i=$((i + 1))
            EPIC="${!i}" ;;
    esac
    i=$((i + 1))
done

# Source common functions
SCRIPT_DIR="$(CDPATH="" cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

REPO_ROOT=$(get_repo_root)

# Validate required arguments
if [ -z "$PLATFORM" ]; then
    if $JSON_MODE; then
        echo '{"error":"--platform is required","suggestion":"Provide platform name, e.g., --platform madruga-ai"}'
    else
        echo "ERROR: --platform is required" >&2
    fi
    exit 1
fi

if [ -z "$SKILL" ] && [ "$STATUS_MODE" != true ] && [ "$CHECK_PLATFORM_ONLY" != true ] && [ -z "$EPIC" ]; then
    if $JSON_MODE; then
        echo '{"error":"One of --skill, --status, --epic, or --check-platform-only is required"}'
    else
        echo "ERROR: One of --skill, --status, --epic, or --check-platform-only is required" >&2
    fi
    exit 1
fi

PLATFORM_DIR="$REPO_ROOT/platforms/$PLATFORM"
PLATFORM_YAML="$PLATFORM_DIR/platform.yaml"

# Check platform exists
if [ ! -d "$PLATFORM_DIR" ]; then
    if $JSON_MODE; then
        printf '{"error":"Platform '\''%s'\'' not found","suggestion":"Run platform_cli.py list to see available platforms"}\n' "$PLATFORM"
    else
        echo "ERROR: Platform '$PLATFORM' not found at $PLATFORM_DIR" >&2
    fi
    exit 1
fi

if [ ! -f "$PLATFORM_YAML" ]; then
    if $JSON_MODE; then
        printf '{"error":"platform.yaml not found for %s","suggestion":"Run copier update or create platform.yaml"}\n' "$PLATFORM"
    else
        echo "ERROR: platform.yaml not found at $PLATFORM_YAML" >&2
    fi
    exit 1
fi

# --check-platform-only: just verify platform exists and is valid, then exit
if [ "$CHECK_PLATFORM_ONLY" = true ]; then
    if $JSON_MODE; then
        printf '{"platform":"%s","valid":true,"platform_dir":"%s"}\n' "$PLATFORM" "$PLATFORM_DIR"
    else
        echo "Platform '$PLATFORM' is valid at $PLATFORM_DIR"
    fi
    exit 0
fi

# --epic mode: check epic cycle node prerequisites
if [ -n "$EPIC" ]; then
    python3 -c "
import json, sys, os, glob, yaml

platform_dir = sys.argv[1]
platform_name = sys.argv[2]
epic_slug = sys.argv[3]
json_mode = sys.argv[4] == 'true'
skill_id = sys.argv[5] if len(sys.argv) > 5 else ''
status_mode = sys.argv[6] == 'true'
use_db = sys.argv[7] == 'true'

# Load epic_cycle from platform.yaml
with open(os.path.join(platform_dir, 'platform.yaml')) as f:
    manifest = yaml.safe_load(f)

epic_cycle = manifest.get('pipeline', {}).get('epic_cycle', {})
nodes = epic_cycle.get('nodes', [])
if not nodes:
    print(json.dumps({'error': 'No epic_cycle section in platform.yaml'}))
    sys.exit(1)

epic_dir = os.path.join(platform_dir, 'epics', epic_slug)

def check_outputs(node):
    outputs = node.get('outputs', [])
    for o in outputs:
        path = o.replace('{epic}', os.path.join('epics', epic_slug))
        if not os.path.exists(os.path.join(platform_dir, path)):
            return False
    return len(outputs) > 0

if use_db:
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(platform_dir), '..', '.specify', 'scripts'))
        from db import get_conn, get_epic_nodes, get_epic_status
        conn = get_conn()
        db_nodes = get_epic_nodes(conn, platform_name, epic_slug)
        db_status = get_epic_status(conn, platform_name, epic_slug)
        db_map = {n['node_id']: n for n in db_nodes}
        conn.close()
    except Exception:
        db_map = {}
        db_status = {}
else:
    db_map = {}
    db_status = {}

node_map = {n['id']: n for n in nodes}
results = []
for node in nodes:
    nid = node['id']
    optional = node.get('optional', False)
    gate = node.get('gate', 'human')
    outputs_exist = check_outputs(node)

    # Check DB status if available
    db_node = db_map.get(nid)
    if db_node and db_node.get('status') == 'done':
        status = 'done'
    elif outputs_exist:
        status = 'done'
    else:
        deps = node.get('depends', [])
        missing_deps = []
        for dep_id in deps:
            dep_node = node_map.get(dep_id)
            if not dep_node:
                continue
            if dep_node.get('optional', False):
                continue
            if not check_outputs(dep_node):
                dep_db = db_map.get(dep_id)
                if not (dep_db and dep_db.get('status') == 'done'):
                    missing_deps.append(dep_id)
        if missing_deps:
            status = 'blocked'
        elif optional:
            status = 'skipped'
        else:
            status = 'ready'

    entry = {'id': nid, 'status': status, 'gate': gate}
    if optional:
        entry['optional'] = True
    results.append(entry)

if status_mode or not skill_id:
    next_nodes = [r['id'] for r in results if r['status'] == 'ready']
    done_count = sum(1 for r in results if r['status'] == 'done')
    total = len(results)
    output = {
        'platform': platform_name,
        'epic': epic_slug,
        'source': 'db' if use_db and db_map else 'filesystem',
        'nodes': results,
        'next': next_nodes,
        'progress': {
            'done': done_count,
            'ready': sum(1 for r in results if r['status'] == 'ready'),
            'blocked': sum(1 for r in results if r['status'] == 'blocked'),
            'skipped': sum(1 for r in results if r['status'] == 'skipped'),
            'total': total
        }
    }
    if db_status:
        output['db_status'] = db_status
    print(json.dumps(output, indent=2))
else:
    # Skill mode for epic cycle
    target = node_map.get(skill_id)
    if not target:
        print(json.dumps({'error': f\"Node '{skill_id}' not found in epic_cycle\", 'available_nodes': [n['id'] for n in nodes]}))
        sys.exit(1)
    deps = target.get('depends', [])
    missing = []
    for dep_id in deps:
        dep_r = next((r for r in results if r['id'] == dep_id), None)
        if dep_r and dep_r['status'] != 'done':
            if not node_map.get(dep_id, {}).get('optional', False):
                missing.append(dep_id)
    ready = len(missing) == 0
    result = {
        'platform': platform_name,
        'epic': epic_slug,
        'skill': skill_id,
        'ready': ready,
        'missing': missing,
        'depends_on': deps
    }
    print(json.dumps(result, indent=2))
    if not ready:
        sys.exit(2)
" "$PLATFORM_DIR" "$PLATFORM" "$EPIC" "$JSON_MODE" "$SKILL" "$STATUS_MODE" "$USE_DB"
    exit $?
fi

# --use-db: query SQLite for enhanced status (with hashes, staleness)
if [ "$USE_DB" = true ]; then
    DB_PATH="$REPO_ROOT/.pipeline/madruga.db"
    if [ ! -f "$DB_PATH" ]; then
        echo '{"warning":"DB not found at .pipeline/madruga.db, falling back to filesystem"}' >&2
        USE_DB=false
    else
        # Query DB via Python for full status with hashes and staleness
        DB_RESULT=$(python3 -c "
import sys, json
sys.path.insert(0, sys.argv[1] + '/.specify/scripts')
from db import get_conn, get_pipeline_nodes, get_stale_nodes, get_platform_status, get_epics
import yaml

conn = get_conn()
status = get_platform_status(conn, sys.argv[2])
nodes = get_pipeline_nodes(conn, sys.argv[2])
epics = get_epics(conn, sys.argv[2])

# Parse DAG edges for staleness
with open(sys.argv[3]) as f:
    manifest = yaml.safe_load(f)
dag_edges = {}
for n in manifest.get('pipeline', {}).get('nodes', []):
    dag_edges[n['id']] = n.get('depends', [])

stale = get_stale_nodes(conn, sys.argv[2], dag_edges)
stale_ids = {s['node_id'] for s in stale}

# Enhance nodes with stale flag
for node in nodes:
    node['stale'] = node['node_id'] in stale_ids

result = {
    'platform': sys.argv[2],
    'source': 'db',
    'status': status,
    'nodes': nodes,
    'stale_nodes': stale,
    'epics_count': len(epics)
}
print(json.dumps(result, indent=2))
conn.close()
" "$REPO_ROOT" "$PLATFORM" "$PLATFORM_YAML" 2>&1)
        echo "$DB_RESULT"
        exit 0
    fi
fi

# Check python3 availability
if ! command -v python3 >/dev/null 2>&1; then
    if $JSON_MODE; then
        echo '{"error":"python3 required for YAML parsing"}'
    else
        echo "ERROR: python3 required for YAML parsing" >&2
    fi
    exit 1
fi

# Parse pipeline nodes from platform.yaml using python3
PIPELINE_JSON=$(python3 -c "
import yaml, json, sys

with open(sys.argv[1]) as f:
    data = yaml.safe_load(f)

pipeline = data.get('pipeline')
if not pipeline:
    json.dump({'error': 'No pipeline section in platform.yaml', 'suggestion': 'Run copier update or add pipeline: section manually'}, sys.stdout)
    sys.exit(0)

nodes = pipeline.get('nodes', [])
json.dump(nodes, sys.stdout)
" "$PLATFORM_YAML" 2>/dev/null)

# Check if pipeline section exists
if echo "$PIPELINE_JSON" | python3 -c "import json,sys; d=json.load(sys.stdin); sys.exit(0 if 'error' not in d else 1)" 2>/dev/null; then
    : # No error
else
    if $JSON_MODE; then
        echo "$PIPELINE_JSON"
    else
        echo "ERROR: No pipeline section in platform.yaml" >&2
        echo "Suggestion: Run copier update or add pipeline: section manually" >&2
    fi
    exit 1
fi

# Use python3 for all DAG logic (more reliable than bash for JSON manipulation)
if [ "$STATUS_MODE" = true ]; then
    # Status mode: check all nodes
    python3 -c "
import json, sys, os, glob

platform_dir = sys.argv[1]
platform_name = sys.argv[2]
json_mode = sys.argv[3] == 'true'
nodes = json.loads(sys.argv[4])

def check_outputs(node):
    \"\"\"Check if a node's outputs exist.\"\"\"
    pattern = node.get('output_pattern')
    if pattern:
        matches = glob.glob(os.path.join(platform_dir, pattern))
        return len(matches) > 0
    outputs = node.get('outputs', [])
    if not outputs:
        return os.path.exists(os.path.join(platform_dir, 'platform.yaml'))
    return all(os.path.exists(os.path.join(platform_dir, o)) for o in outputs)

# Build node map
node_map = {n['id']: n for n in nodes}

# Determine status for each node
results = []
for node in nodes:
    nid = node['id']
    optional = node.get('optional', False)
    gate = node.get('gate', 'human')
    layer = node.get('layer', '')

    outputs_exist = check_outputs(node)

    if outputs_exist:
        status = 'done'
        missing_deps = []
    else:
        # Check dependencies
        deps = node.get('depends', [])
        missing_deps = []
        for dep_id in deps:
            dep_node = node_map.get(dep_id)
            if not dep_node:
                continue
            if dep_node.get('optional', False):
                continue  # Skip optional deps
            if not check_outputs(dep_node):
                missing_deps.append(dep_id)

        if missing_deps:
            status = 'blocked'
        elif optional and not outputs_exist:
            status = 'skipped'
        else:
            status = 'ready'

    entry = {'id': nid, 'status': status, 'layer': layer, 'gate': gate}
    if optional:
        entry['optional'] = True
    if missing_deps:
        entry['missing_deps'] = missing_deps
    results.append(entry)

next_nodes = [r['id'] for r in results if r['status'] == 'ready']
done_count = sum(1 for r in results if r['status'] == 'done')
ready_count = sum(1 for r in results if r['status'] == 'ready')
blocked_count = sum(1 for r in results if r['status'] == 'blocked')
skipped_count = sum(1 for r in results if r['status'] == 'skipped')
total = len(results)

if json_mode:
    output = {
        'platform': platform_name,
        'nodes': results,
        'next': next_nodes,
        'progress': {
            'done': done_count,
            'ready': ready_count,
            'blocked': blocked_count,
            'skipped': skipped_count,
            'total': total
        }
    }
    print(json.dumps(output, indent=2))
else:
    pct = int(done_count / total * 100) if total > 0 else 0
    print(f'Pipeline Status: {platform_name}')
    print(f'Progress: {done_count}/{total} nodes done ({pct}%)')
    print()
    print(f'{\"Layer\":<12} {\"Skill\":<22} {\"Status\":<10} {\"Gate\":<14} {\"Missing\"}')
    print('-' * 75)
    for r in results:
        missing = ', '.join(r.get('missing_deps', [])) or '-'
        opt = ' (optional)' if r.get('optional') else ''
        print(f'{r[\"layer\"]:<12} {r[\"id\"]:<22} {r[\"status\"]:<8} {r[\"gate\"]:<14} {missing}{opt}')
    print()
    if next_nodes:
        print(f'Next available: /{next_nodes[0]} {platform_name}')
    elif done_count == total:
        print('Pipeline complete!')
    else:
        print('Pipeline blocked. Check missing dependencies above.')
" "$PLATFORM_DIR" "$PLATFORM" "$JSON_MODE" "$PIPELINE_JSON"
else
    # Skill mode: check specific node
    python3 -c "
import json, sys, os, glob

platform_dir = sys.argv[1]
platform_name = sys.argv[2]
skill_id = sys.argv[3]
json_mode = sys.argv[4] == 'true'
nodes = json.loads(sys.argv[5])

def check_outputs(node):
    pattern = node.get('output_pattern')
    if pattern:
        matches = glob.glob(os.path.join(platform_dir, pattern))
        return len(matches) > 0
    outputs = node.get('outputs', [])
    if not outputs:
        return os.path.exists(os.path.join(platform_dir, 'platform.yaml'))
    return all(os.path.exists(os.path.join(platform_dir, o)) for o in outputs)

# Build node map
node_map = {n['id']: n for n in nodes}

# Find target node
target = node_map.get(skill_id)
if not target:
    available = [n['id'] for n in nodes]
    if json_mode:
        print(json.dumps({'error': f\"Node '{skill_id}' not found in pipeline\", 'available_nodes': available}))
    else:
        print(f\"ERROR: Node '{skill_id}' not found in pipeline\", file=sys.stderr)
        print(f'Available nodes: {', '.join(available)}', file=sys.stderr)
    sys.exit(1)

# Resolve dependencies
deps = target.get('depends', [])
missing = []
available = []

for dep_id in deps:
    dep_node = node_map.get(dep_id)
    if not dep_node:
        missing.append(dep_id)
        continue
    if dep_node.get('optional', False):
        # Optional dep: check but do not block
        if check_outputs(dep_node):
            for o in dep_node.get('outputs', []):
                available.append(o)
        continue
    # Check dep outputs
    dep_outputs = dep_node.get('outputs', [])
    dep_pattern = dep_node.get('output_pattern')
    if dep_pattern:
        matches = glob.glob(os.path.join(platform_dir, dep_pattern))
        if matches:
            for m in matches:
                available.append(os.path.relpath(m, platform_dir))
        else:
            missing.append(dep_id)
    else:
        all_exist = True
        for o in dep_outputs:
            if os.path.exists(os.path.join(platform_dir, o)):
                available.append(o)
            else:
                all_exist = False
        if not all_exist:
            missing.append(dep_id)

ready = len(missing) == 0
outputs = target.get('outputs', [])
if target.get('output_pattern'):
    outputs = [target['output_pattern']]

if json_mode:
    result = {
        'platform': platform_name,
        'platform_dir': platform_dir,
        'skill': skill_id,
        'ready': ready,
        'missing': missing,
        'available': sorted(set(available)),
        'depends_on': deps,
        'outputs': outputs
    }
    print(json.dumps(result, indent=2))
else:
    status = 'READY' if ready else 'BLOCKED'
    print(f'Platform: {platform_name}')
    print(f'Skill: {skill_id}')
    print(f'Status: {status}')
    print()
    print('Dependencies:')
    for dep_id in deps:
        dep_node = node_map.get(dep_id, {})
        dep_outputs = dep_node.get('outputs', [dep_node.get('output_pattern', '?')])
        exists = dep_id not in missing
        marker = '[ok]' if exists else '[missing]'
        opt = ' (optional)' if dep_node.get('optional') else ''
        print(f'  {marker} {dep_id} -> {', '.join(dep_outputs)}{opt}')
    print()
    print('Outputs (will generate):')
    for o in outputs:
        print(f'  {o}')

if not ready:
    sys.exit(2)
" "$PLATFORM_DIR" "$PLATFORM" "$SKILL" "$JSON_MODE" "$PIPELINE_JSON"
fi
