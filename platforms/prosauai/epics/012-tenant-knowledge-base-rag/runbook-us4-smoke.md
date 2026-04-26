# US4 Smoke Runbook — Per-Agent RAG Toggle (T069)

**Epic**: 012-tenant-knowledge-base-rag
**Task**: T069
**Owner**: Pace ops + dev pair (Ariel)
**Estimate**: 30-45 min wall-clock (setup + verify + cleanup)
**Status**: pending — requires staging environment with ResenhAI tenant + 2 agents

## Why this exists

T069 is the human-driven smoke that closes the US4 loop end-to-end:
backend PATCH (T066) → admin UI Switch (T067/T068) → runtime
pipeline filter (T046) → Trace Explorer (epic 008). The backend +
frontend tests (T064, T065) cover the wire contract; this runbook
proves the toggle actually flips the agent's runtime behaviour in a
real conversation.

Skipping this runbook is acceptable when the staging environment is
unavailable, but flag it in the PR description so reviewers know the
end-to-end path is unverified.

## Pre-requisites

* Staging API + admin UI running with epic 012 PR-A + PR-B + PR-C
  branches deployed.
* Tenant `resenhai` configured in `tenants.yaml` with:
  ```yaml
  rag:
    enabled: true
    top_k: 5
    max_upload_mb: 10
  ```
* At least 1 document already uploaded to ResenhAI's KB (use the
  `quickstart.md` flow if needed).
* 2 agents seeded for ResenhAI (typical setup: `agent-aulas` +
  `agent-comercial`). Verify via:
  ```bash
  curl -sb cookies.txt 'https://staging-admin.prosauai.com/admin/agents?tenant=resenhai' | jq '.items | length'
  # → 2 (or more)
  ```
* Pace admin login credentials available.

## Steps

### 1. Toggle ON for agent A (`agent-aulas`)

1. Open `https://staging-admin.prosauai.com/admin/agents?tenant=resenhai`.
2. Locate `agent-aulas` row. The RAG toggle should be visible
   between the name and the model line (interactive — `rag.enabled=true`).
3. Click the toggle. Confirmation prompt appears: *"Adicionar
   search_knowledge aos tools_enabled?"*
4. Click **Confirmar**.
5. Toggle flips to `data-state="checked"` (filled colour).
6. Verify via API:
   ```bash
   curl -sb cookies.txt 'https://staging-admin.prosauai.com/admin/agents?tenant=resenhai' \
     | jq '.items[] | select(.name == "agent-aulas") | .tools'
   # → ["search_knowledge"]
   ```
7. Verify in DB (optional, requires SSH):
   ```sql
   SELECT a.name, p.tools_enabled
   FROM agents a JOIN prompts p ON p.id = a.active_prompt_id
   WHERE a.name IN ('agent-aulas', 'agent-comercial');
   -- agent-aulas should have ["search_knowledge"]; agent-comercial should not.
   ```

### 2. Toggle OFF for agent B (`agent-comercial`)

1. Same Agentes tab. Locate `agent-comercial` row.
2. If its toggle is already OFF, skip. Otherwise click + confirm
   *"Remover search_knowledge dos tools_enabled?"*.
3. Toggle flips to `data-state="unchecked"`.

### 3. Reload + verify persistence

1. Reload the page (`Cmd+R`).
2. Both toggles should reflect their new state (checked for
   `agent-aulas`, unchecked for `agent-comercial`).

### 4. Send test message → verify Trace Explorer

#### 4a. Message routed to `agent-aulas`

1. Use the WhatsApp simulator (epic 008) or send a real test message
   that the router will route to `agent-aulas`.
2. Wait for the agent to reply (~3-5 s).
3. Open Trace Explorer (`/admin/traces`) and filter by tenant
   `resenhai` + the simulator phone.
4. Open the most recent trace. Drill into the `agent.generate` step
   and assert:
   * Subspan `tool_call.search_knowledge` is **present**.
   * Subspan `rag.search` shows `chunks_returned >= 1` and
     `distance_top1 < 0.4`.
   * The agent's response cites or uses the retrieved chunk content.

#### 4b. Message routed to `agent-comercial`

1. Send a similar message that the router will route to
   `agent-comercial`.
2. Open the resulting trace.
3. Assert:
   * Subspan `tool_call.search_knowledge` is **absent**.
   * The agent responded purely from the system prompt.

### 5. Defense-in-depth check (optional)

Confirm that even if `tools_enabled` somehow contained
`search_knowledge` for an agent on a tenant with `rag.enabled=false`,
the runtime would silently drop the tool. This is already covered by
T046 unit tests; the smoke version is:

1. Edit `tenants.yaml` for `resenhai` → `rag.enabled: false`.
2. Wait ≤60 s (config_poller hot-reload — epic 010).
3. Send a message that would normally trigger
   `search_knowledge`. Trace should show NO `tool_call.search_knowledge`
   subspan even for `agent-aulas` (which still has the tool whitelisted).
4. Restore `rag.enabled: true` afterwards.

## Cleanup

* Restore agents to their pre-smoke state via the same toggles.
* No DB rows need manual cleanup (toggle is idempotent).

## Success criteria

- [ ] Toggle ON persisted for `agent-aulas` (DB + admin GET both reflect).
- [ ] Toggle OFF persisted for `agent-comercial`.
- [ ] Trace for `agent-aulas` message contains `tool_call.search_knowledge`.
- [ ] Trace for `agent-comercial` message does NOT contain
      `tool_call.search_knowledge`.
- [ ] Optional: defense-in-depth flag check passes.

## Failure modes & mitigations

| Symptom | Likely cause | Mitigation |
|--|--|--|
| Toggle is greyed-out | `rag.enabled=false` for the tenant | Edit `tenants.yaml`, wait ≤60 s |
| PATCH returns 403 | Tenant flag mismatch with config_poller cache | Check API logs for `agent_tools_patch_rejected_rag_disabled` |
| PATCH returns 422 | Unknown tool name in payload | UI bug — open issue, payload should only ever send registered tool names |
| `search_knowledge` span missing for `agent-aulas` | Pipeline filter hasn't reloaded tenant config | Wait for config_poller refresh or restart API replicas |
| Agent uses outdated chunks | KB upload concurrent with toggle | Re-run smoke after upload completes |

## References

* spec.md — US4 + FR-048..FR-050
* tasks.md — T064, T065, T066, T067, T068, T069
* runbook origin: T069 in tasks.md
