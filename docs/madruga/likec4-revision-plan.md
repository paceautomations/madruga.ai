# LikeC4 Revision Plan

Audit results and action plan for fixing all LikeC4 model issues across platforms.

---

## Audit Summary

| Metric | Fulano | Madruga-AI |
|--------|--------|-----------|
| Files | 8 | 8 |
| Elements defined | 28 | 32 |
| Relationships | ~50 | ~45 |
| Views (structural) | 3 | 3 |
| Views (scoped) | 4 | 4 |
| Views (dynamic) | 1 | 1 |
| `navigateTo` links | **0** | **0** |
| Export errors | 0 | 0 |
| LikeC4 version | 1.51.0 (1.53.0 available) | same |

---

## Issues Found

### BLOCKER: Navigation Completely Broken

**Problem:** ALL `navigateTo` arrays are empty in both platforms' exported JSON.
Clicking any element in any diagram does nothing — no drill-down, no view switching.

**Root Cause:** Views use plain `include element` without `with { navigateTo ... }` clauses.
LikeC4 requires explicit `navigateTo` declarations to enable click-to-navigate.

**Impact:** The portal's `onNavigateTo` handler in `LikeC4Diagram.tsx` receives no events.
The `buildViewPaths()` mapping in `platforms.mjs` is correct but never used.

**Fix:** Add `navigateTo` to every element inclusion where a detail view exists.

### WARNING: Duplicate Relationship (madruga-ai)

**File:** `platforms/madruga-ai/model/relationships.likec4`
**Lines:** 138-140 and 143-145

```likec4
// Line 138 — first occurrence
execution.dagExecutor -[acl]-> integration.claudeClient 'ACL' {
    description 'DAG Executor usa ACL para isolar detalhes do Claude API...'
}

// Line 143 — duplicate with slightly different description
execution.dagExecutor -[acl]-> integration.claudeClient 'ACL (dispatch)' {
    description 'DAG Executor usa ACL para isolar detalhes do Claude API...'
}
```

**Fix:** Remove the duplicate (lines 143-145).

### WARNING: Duplicate Pub-Sub Relationship (madruga-ai)

**File:** `platforms/madruga-ai/model/relationships.likec4`
**Lines:** 165-166

```likec4
execution.dagExecutor -[pubSub]-> observability.metricsCollector 'Pub-Sub (executor)'
execution.dagExecutor -[pubSub]-> observability.metricsCollector 'Pub-Sub'
```

**Fix:** Merge into single relationship.

### NIT: LikeC4 Version Outdated

**Current:** 1.51.0
**Available:** 1.53.0

**Fix:** `npm i -g likec4@latest`

### NIT: No Deployment Views

Neither platform has deployment diagrams (Arc42 section 7).
Infrastructure.likec4 defines elements but no deployment topology views.

---

## Fix Plan

### Phase 1: Fix Navigation (BLOCKER) — Both Platforms

#### Fulano — views.likec4

```likec4
// index view: clicking fulano → containers
view index {
  include agent, admin
  include fulano with {
    navigateTo containers
  }
  include evolutionApi, claudeSonnet, claudeHaiku
  include redis, supabaseFulano
}

// containers view: clicking bounded contexts → detail views
view containers of fulano {
  include *
  include agent, admin
  include redis, supabaseFulano, bifrost, langfuse, infisical
  include evolutionApi, supabaseResenhai, claudeSonnet, claudeHaiku
}

// contextMap view: clicking bounded contexts → detail views
view contextMap {
  include channel with { navigateTo channelDetail }
  include channel.*
  include conversation with { navigateTo conversationDetail }
  include conversation.*
  include safety with { navigateTo safetyDetail }
  include safety.*
  include operations with { navigateTo operationsDetail }
  include operations.*
  include observability
  include observability.*
  include agent, admin
  include evolutionApi, bifrost, claudeSonnet, claudeHaiku
  include redis, supabaseFulano, supabaseResenhai, langfuse
}

// businessFlow: navigateTo on key steps (dynamic views can link to other dynamic views)
```

#### Madruga-AI — views.likec4

```likec4
// index view: clicking madrugaAi → containers
view index {
  include architect, daemon
  include madrugaAi with {
    navigateTo containers
  }
  include claudeApi, telegramBot, githubApi, likec4Cli, sentryCloud
  include sqliteDb, gitFs
}

// contextMap view: clicking bounded contexts → detail views
view contextMap {
  include documentation with { navigateTo documentationDetail }
  include documentation.*
  include specDomain with { navigateTo specificationDetail }
  include specDomain.*
  include execution with { navigateTo executionDetail }
  include execution.*
  include intelligence with { navigateTo intelligenceDetail }
  include intelligence.*
  include integration, integration.*
  include observability, observability.*
  include architect, daemon
  include claudeApi, telegramBot, githubApi, likec4Cli, sentryCloud
  include sqliteDb, gitFs
}
```

### Phase 2: Remove Duplicates (madruga-ai)

In `platforms/madruga-ai/model/relationships.likec4`:

1. **Remove lines 143-145** (duplicate ACL relationship)
2. **Remove line 166** (duplicate Pub-Sub relationship)

### Phase 3: Update LikeC4

```bash
npm i -g likec4@latest
```

### Phase 4: Validate

```bash
# Export both models and verify navigateTo is populated
cd platforms/fulano/model && likec4 export json -o /tmp/fulano.json
cd platforms/madruga-ai/model && likec4 export json -o /tmp/madruga.json

# Check navigateTo
python3 -c "
import json
for name in ['fulano', 'madruga']:
    with open(f'/tmp/{name}.json') as f:
        data = json.load(f)
    for proj in data:
        views = proj.get('views', {})
        for vid, v in views.items():
            nav = v.get('navigateTo', [])
            if nav:
                print(f'{name}/{vid}: navigateTo={nav}')
"

# Serve locally to test navigation
cd platforms/fulano/model && likec4 serve
```

### Phase 5: Portal Build Verification

```bash
cd portal && npm run build
```

Verify that the `viewPaths` mapping in `buildViewPaths()` covers all view IDs
that have `navigateTo` targets.

---

## View Navigation Map (Target State)

### Fulano

```
index
  └─ fulano → containers
       └─ (elements shown, externals linked)

contextMap
  ├─ channel → channelDetail
  ├─ conversation → conversationDetail
  ├─ safety → safetyDetail
  └─ operations → operationsDetail

businessFlow (standalone dynamic view)
```

### Madruga-AI

```
index
  └─ madrugaAi → containers
       └─ (elements shown, externals linked)

contextMap
  ├─ documentation → documentationDetail
  ├─ specDomain → specificationDetail
  ├─ execution → executionDetail
  └─ intelligence → intelligenceDetail

businessFlow (standalone dynamic view)
```

---

## Estimated Effort

| Phase | Effort | Risk |
|-------|--------|------|
| 1. Fix navigation | ~30 min | Low — additive changes only |
| 2. Remove duplicates | ~5 min | Low — removing redundancy |
| 3. Update LikeC4 | ~5 min | Low — minor version bump |
| 4. Validate | ~15 min | Low — export + inspect |
| 5. Portal build | ~10 min | Medium — Vite plugin may need rebuild |
