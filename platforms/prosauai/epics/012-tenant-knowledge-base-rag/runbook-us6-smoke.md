# US6 Smoke Runbook — RAG Feature-Flag Hot-Reload (T077)

**Epic**: 012-tenant-knowledge-base-rag
**Task**: T077 (Smoke Step 12 do `quickstart.md`)
**Owner**: Pace ops (single operator; dev pair optional)
**Estimate**: 15-25 min wall-clock (setup + 2 reload windows + cleanup)
**Status**: pending — requires staging API + Ariel tenant in `tenants.yaml`

## Why this exists

T077 is the human-driven smoke that closes the US6 loop end-to-end:
YAML edit → :class:`prosauai.config_poller.TenantConfigPoller` tick
(<= 60 s) → in-memory `app.state.tenant_store` swap → admin endpoint
behaviour change (upload alternates 403 ⇄ 201). The backend tests
(T073) and the admin endpoint tests (T076) cover the wire contracts;
the e2e Playwright spec (T074) covers the UI/HTTP integration; this
runbook is the hand-driven check that the **kill-switch RTO ≤60 s
contract** (FR-046, SC-007) holds in a real environment.

Skipping this runbook is acceptable when the staging environment is
unavailable, but flag it in the PR description so reviewers know the
end-to-end RTO path is unverified.

## Pre-requisites

* Staging API + admin UI running with epic 012 PR-A + PR-B branches
  deployed. PR-C UI is *not* required — this smoke drives the API
  directly via curl so the loop is testable before the UI lands.
* Tenant `pace-internal` (Ariel) present in `tenants.yaml` and reachable
  by the API. Verify via:
  ```bash
  curl -sf "https://staging-api.prosauai.com/admin/config/tenants/ariel/rag" \
    -H "Authorization: Bearer $ADMIN_TOKEN" | jq .enabled
  # → true OR false (any value proves the endpoint resolves the tenant).
  ```
* `ADMIN_TOKEN` env var with a valid admin JWT (login flow once via
  `/admin/auth/login` and copy the cookie).
* `TENANTS_YAML` env var pointing at the live YAML the poller reads
  (`apps/api/config/tenants.yaml` for Compose; the path provided by
  ops for k8s ConfigMaps).
* `TENANT_ID` env var with the tenant UUID (used as the upload query
  param). Defaults to Ariel's seeded UUID:
  ```bash
  export TENANT_ID="00000000-0000-4000-a000-000000000001"
  ```
* A throwaway 1-line MD file:
  ```bash
  printf "# FAQ smoke probe\n" > /tmp/reload-probe.md
  ```

## Steps

### 1. Snapshot the YAML

```bash
cp "$TENANTS_YAML" "$TENANTS_YAML.bak.$(date +%s)"
```

The runbook restores from the snapshot at the end. If you crash mid-
runbook, manually `cp <bak> <yaml>` to recover.

### 2. Force `rag.enabled: false` for Ariel

Edit `$TENANTS_YAML` (in-place; e.g. `vim`, `yq -i`, etc.) so the
Ariel block has:

```yaml
- id: pace-internal
  ...
  rag:
    enabled: false
```

Save. Note the wall-clock time `t0`.

### 3. Wait for the poller tick (<= 60 s)

Watch the API logs in another terminal:

```bash
docker-compose logs -f api 2>&1 | grep -E "tenant_config_reload_(applied|unchanged|failed)|tenants_yaml_rag_block_invalid"
```

You should see, within ≤60 s of `t0`:

```
event=config_poller_reload_applied tenant_count=N
event=metric metric_name=tenant_config_reload_total outcome=applied
```

If you see `event=tenants_yaml_rag_block_invalid` instead, the YAML is
malformed — the poller kept the previous good store live (FR-045
fail-safe). Roll back via the `.bak` snapshot and fix the YAML.

### 4. Verify the live snapshot via the debug endpoint (T076)

```bash
curl -sf "https://staging-api.prosauai.com/admin/config/tenants/ariel/rag" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq .enabled
# → false
```

This MUST return `false` before proceeding. If it still returns `true`,
the poller has not ticked yet — keep waiting (you have up to 60 s
budget).

### 5. Confirm upload returns 403

```bash
curl -i -X POST \
  "https://staging-api.prosauai.com/admin/knowledge/documents?tenant_id=$TENANT_ID" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -F "file=@/tmp/reload-probe.md"
```

Expected: `HTTP/1.1 403 Forbidden` with body containing
`{"error":"rag_not_enabled_for_tenant", ...}`.

Record the wall-clock `t1`. The interval `t1 - t0` MUST be ≤ 90 s
(60 s SLA + 30 s slack for the tick + curl overhead). If it exceeds
60 s in steady state, file an SC-007 regression alert.

### 6. Force `rag.enabled: true` for Ariel

Edit `$TENANTS_YAML` again — flip the value back to `true`:

```yaml
rag:
  enabled: true
```

Save. Note the wall-clock time `t2`.

### 7. Wait for the next poller tick + verify enabled

Same procedure as step 3-4. After `≤ 60 s`:

```bash
curl -sf "https://staging-api.prosauai.com/admin/config/tenants/ariel/rag" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq .enabled
# → true
```

### 8. Confirm upload returns 201

```bash
curl -i -X POST \
  "https://staging-api.prosauai.com/admin/knowledge/documents?tenant_id=$TENANT_ID" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -F "file=@/tmp/reload-probe.md"
```

Expected: `HTTP/1.1 201 Created` with a JSON body matching
`DocumentUploadResponse` (T009): `document_id`, `chunks_created ≥ 1`,
`total_tokens ≥ 1`, `cost_usd ≥ 0`, `embedding_model="text-embedding-3-small"`.

Record the wall-clock `t3`. The interval `t3 - t2` MUST be ≤ 90 s.

### 9. Verify metric increments

The structured log pipeline emits one `tenant_config_reload_total`
metric per tick. In the same logs window you opened in step 3, count
the `outcome=applied` events between `t0` and `t3` — at minimum two
(once for each YAML edit). Operators with a Prometheus dashboard
should also see:

* `rate(tenant_config_reload_total{outcome="applied"}[5m]) > 0` during
  the smoke window.
* `tenant_config_reload_failed_total` — **no increase** (no validation
  errors).
* `rag_uploads_rejected_total{reason="rag_not_enabled_for_tenant"}` —
  exactly **one** increment (from step 5).

### 10. Cleanup — restore the snapshot

```bash
cp "$TENANTS_YAML.bak.<timestamp>" "$TENANTS_YAML"
```

Wait one final tick. The endpoint snapshot returns to whatever value
was live before the smoke. Delete the probe file:

```bash
rm -f /tmp/reload-probe.md
```

### 11. Optional — delete the probe document

If step 8's upload created a real document on Ariel, delete it via:

```bash
curl -i -X DELETE \
  "https://staging-api.prosauai.com/admin/knowledge/documents/<document_id>?tenant_id=$TENANT_ID" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
# → 204 No Content
```

The cascade removes the chunks + Storage object (FR-009).

## Validation checklist

For T077 to be considered green:

- [ ] Step 3: `tenant_config_reload_applied` log + paired metric
      observed within ≤60 s of YAML edit
- [ ] Step 4: debug endpoint returns the new `enabled` value
- [ ] Step 5: upload returns 403 `rag_not_enabled_for_tenant` with
      `t1 - t0 ≤ 90 s`
- [ ] Step 7: debug endpoint returns the re-enabled value
- [ ] Step 8: upload returns 201 with a valid `DocumentUploadResponse`
      and `t3 - t2 ≤ 90 s`
- [ ] Step 9: `tenant_config_reload_total{outcome=applied}` ≥ 2 during
      window; `tenant_config_reload_failed_total` no increase
- [ ] Step 10: YAML restored, no orphan probe document on Ariel

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Step 3 log not appearing | Poller stuck or interval > 60 s | Check `prosauai.config_poller_iteration_failed`; restart api as last resort |
| Step 4 returns old value | YAML edit not flushed | Verify file mtime updated; some k8s ConfigMap mounts have ≥60 s sync lag |
| Step 5 returns 200 instead of 403 | Old in-memory store still live | Wait additional 30 s — total budget is 90 s before SLA breach |
| `tenants_yaml_rag_block_invalid` in logs | YAML syntax error / wrong type | Restore snapshot; fix the offending field; the previous good store stays live during the failure |
| Step 8 returns 503 `embeddings_provider_down` | Bifrost down or OpenAI rate-limited | Re-run after Bifrost recovers; this is a Bifrost smoke not a US6 regression |

## Reverse procedure (kill-switch in production incident)

If you need to disable RAG for *every* tenant in production
(e.g. embedder cost runaway):

1. Edit `tenants.yaml` and set `rag.enabled: false` on every tenant.
2. Commit + push to the live branch.
3. Wait ≤60 s for the poller. The debug endpoint
   (`/admin/config/tenants/<slug>/rag`) confirms the snapshot.
4. All uploads start returning 403; the `search_knowledge` tool is
   filtered out of every agent's pipeline schema (T046, defense-in-depth).
5. Reverse via the same procedure with `enabled: true` once the
   incident is resolved. Documents and chunks already persisted are
   **NOT** deleted (FR-046 — re-enable just flips the master switch).

This procedure is the documented kill-switch for SC-007 and the
RTO target on the operational runbook.
