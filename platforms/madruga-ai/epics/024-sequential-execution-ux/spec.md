# Feature Specification: Sequential Execution UX

**Feature Branch**: `epic/madruga-ai/024-sequential-execution-ux` (deferred — planning runs on `epic/prosauai/004-router-mece` per auto-sabotage guardrails)
**Created**: 2026-04-11
**Status**: Draft
**Input**: Epic 024 — Sequential Execution UX. Abrir o repo de uma plataforma externa e ver a branch ativa sendo construída em tempo real. Enfileirar 2–3 epics com um comando e deixá-los executar em sequência sem intervenção humana entre eles.

## Clarifications

### Session 2026-04-11

Autonomous resolution pass (no user prompts). Each residual ambiguity was resolved by the best answer grounded in `pitch.md`, `decisions.md`, and the auto-sabotage guardrails. Rationale for the answer is included inline.

- **Q**: What is the concrete upper bound on the delay between a running epic reaching terminal state and the next queued epic starting? **A**: **60 seconds** (wall-clock). Chosen because: (1) the existing daemon poll cycle is already short, (2) 60s gives operational headroom without constraining implementation, (3) it is observably testable end-to-end without a stopwatch precision requirement. Applied to **SC-002** and **SC-007**.
- **Q**: What is the total upper bound on the retry window for a transient promotion failure (FR-011)? **A**: **≤ 10 seconds** total retry budget across all attempts. Chosen because it matches the pitch's captured decision #7 (1s + 2s + 4s ≈ 7s backoff sequence plus one attempt) and keeps the operator feedback loop tight. Applied to **FR-011**.
- **Q**: When FR-009 says "oldest queued epic (FIFO)", what timestamp defines "oldest"? **A**: **The time the epic most recently transitioned INTO the `queued` status.** If an epic is dequeued (back to `drafted`) and re-queued, the re-queue time resets ordering. Chosen because it matches operator intuition — re-queuing is an explicit intentional act that should place the epic at the end of the line. Applied to **FR-009**.
- **Q**: What happens in FR-005 (cascade base) if the prior epic's local branch has been deleted (e.g., the clone was cleaned up after merge)? **A**: **Fall back to the platform's configured base branch** (e.g., `origin/develop`) after fetching. This is consistent with the pitch's Resolved Gray Area #2 and captured decision #5. Applied to **FR-005**.
- **Q**: In FR-015 (artifact migration), what happens if the base-branch version of pitch/decisions has drifted between draft creation and promotion time? **A**: **The base-branch version at the moment of promotion is authoritative.** The operator is expected to run delta review (via `/madruga:epic-context`) before queuing if they want the draft re-validated; post-queue drift is inherited as-is. Chosen because it preserves a single source of truth (main) and avoids three-way merge semantics, which are out of scope for this epic. Applied to **FR-015** and as a new entry under **Assumptions**.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Live visibility into the active epic branch (Priority: P1)

As a developer working on an external platform (e.g., `prosauai`), I want to open the platform's main clone in my editor and immediately see the exact branch of the epic currently being implemented, without manually navigating to a worktree directory whose path changes every epic.

**Why this priority**: Visibility during execution is the foundation for human oversight. Without it, the developer cannot inspect progress, intervene when needed, or review diffs in real time. This is the single biggest operational friction reported in the pitch (Atrito 1).

**Independent Test**: Can be fully tested in isolation by (a) opting a platform into the new isolation mode, (b) starting an epic through the normal pipeline, and (c) opening the platform clone in an editor. Test passes if the active branch is visible at the canonical clone path — no worktree navigation required.

**Acceptance Scenarios**:

1. **Given** a platform opted into the new isolation mode and the platform has no running epic, **When** the developer opens the platform clone in their editor, **Then** they see the platform's default base branch (e.g., `develop`).
2. **Given** a platform opted into the new isolation mode and an epic is actively running, **When** the developer opens the platform clone in their editor, **Then** they see the epic branch checked out with the code changes produced so far visible in the working tree.
3. **Given** a platform NOT opted into the new isolation mode, **When** an epic runs, **Then** the existing worktree behavior is preserved unchanged (backwards compatible).

---

### User Story 2 — Queue two or three epics for sequential autonomous execution (Priority: P1)

As a developer, I want to mark two or three epics as "next in line" with a single command and walk away, expecting the pipeline to execute them one after another in the declared order without me having to manually start each one.

**Why this priority**: This is the second foundational friction (Atrito 2). Without it, the operator must remain present between every epic to manually invoke the next one, which breaks the promise of autonomous execution and creates dead time in the pipeline. Equal priority to Story 1 because both are called out as the core value of the epic.

**Independent Test**: Can be fully tested by (a) queuing two drafted epics with the new queue command, (b) starting the first one, (c) letting it complete without manual intervention, and (d) verifying the second starts automatically within one poll cycle of the first finishing. Test passes if the developer's intervention is exactly zero between epic completion and next epic start.

**Acceptance Scenarios**:

1. **Given** a platform with at least one drafted epic, **When** the developer runs the queue command for that epic, **Then** the epic's status transitions from `drafted` to `queued` and the pitch remains visible on the platform's base branch.
2. **Given** a platform with one epic currently running and one epic in `queued` status, **When** the running epic reaches the `shipped` or terminal state, **Then** the queued epic is automatically promoted to `in_progress`, its branch is created (or reused), and its implementation begins within one background poll cycle.
3. **Given** two epics are queued and the first is running, **When** the first completes, **Then** the second is promoted automatically; when the second completes, no further promotion occurs (nothing else queued).
4. **Given** an epic in `drafted` status (not queued), **When** a running epic completes, **Then** the drafted epic is NOT auto-promoted — it waits for explicit manual promotion.

---

### User Story 3 — Safe failure and recovery during automatic promotion (Priority: P1)

As a developer, I want any failure during automatic promotion (dirty working tree, branch checkout conflict, database write failure) to pause the pipeline loudly and safely — never leave the system in an inconsistent state and never silently skip a queued epic.

**Why this priority**: Auto-promotion without failure handling is worse than manual promotion — silent drops lose work, and inconsistent state corrupts the pipeline. This story is equally critical because it underwrites the trust needed to use Stories 1 and 2 at all.

**Independent Test**: Can be fully tested by (a) creating a dirty working tree in the platform clone, (b) queuing an epic, (c) triggering promotion, and (d) verifying the epic transitions to `blocked` with a user-visible alert (not a silent failure). Separately, verify database writes are atomic: on retry exhaustion, the epic status reflects `blocked` rather than a half-committed intermediate state.

**Acceptance Scenarios**:

1. **Given** a queued epic and a dirty working tree in the platform clone, **When** promotion is triggered, **Then** the promotion is aborted, the epic's status becomes `blocked`, and the developer receives a notification explaining the dirty tree (including the output of the tree-status check).
2. **Given** a queued epic and a transient git operation failure, **When** promotion is triggered, **Then** the system retries up to 3 times with backoff before giving up.
3. **Given** a queued epic and a permanent git failure after retries, **When** the retry budget is exhausted, **Then** the epic's status becomes `blocked`, a notification is sent, and the database reflects a consistent state (no half-applied branch metadata).
4. **Given** the running epic set becomes empty after an epic ships, **When** the promotion hook executes, **Then** it is idempotent: running it twice does not duplicate branches, status transitions, or notifications.

---

### User Story 4 — Runtime kill-switch for the new promotion behavior (Priority: P2)

As an operator rolling out this feature, I want to merge the code into `main` without immediately activating the automatic promotion behavior, so I can observe the change in production gradually and roll back instantly if something surprises me.

**Why this priority**: Secondary to the core feature stories because it is a rollout safety mechanism, not user-facing functionality. But it is mandatory per the auto-sabotage guardrails (Camada 4) and matches the precedent set by existing flags (`MADRUGA_BARE_LITE`, `MADRUGA_KILL_IMPLEMENT_CONTEXT`, etc.).

**Independent Test**: After the code is merged and deployed, verify that automatic promotion does NOT occur by default. Then, explicitly enable the feature via the documented runtime mechanism and verify promotion resumes. Both states must be reachable without code changes or redeploy.

**Acceptance Scenarios**:

1. **Given** the code is deployed with the feature flag at its default state, **When** a queued epic exists and a running epic completes, **Then** automatic promotion does NOT occur — the queued epic remains in `queued` status indefinitely.
2. **Given** the feature flag is explicitly enabled, **When** a queued epic exists and a running epic completes, **Then** automatic promotion occurs within one background poll cycle (matches Story 2 scenario 2).
3. **Given** the feature flag is explicitly disabled at runtime, **When** the daemon restarts, **Then** the flag state is preserved and promotion remains disabled.

---

### Edge Cases

- **Concurrent epic attempt**: What happens if someone manually starts an epic while a queued epic is mid-promotion? → Promotion respects the sequential invariant (only one epic at a time per platform). If a manual start beats the hook to the lock, the queued epic waits for the next slot.
- **Queue crosses platform boundaries**: What if platform A has a queued epic and platform B has a running epic? → Queue is per-platform. Platform A's queue does not wait on platform B.
- **Branch already exists locally in the clone**: If the queued epic's target branch name already exists in the clone from a previous aborted attempt, the promotion reuses it (checkout existing) rather than creating a new branch.
- **Base cascade for second queued epic**: When epic N+1 is promoted while epic N is still unmerged to the platform's base branch, the new branch is created from N's current HEAD — not from the stale base branch. This preserves the logical sequence without requiring manual rebase.
- **Stale queue entries**: If an epic has been in `queued` status for an unusually long period (operator abandoned the queue), the system takes no automatic action — status remains `queued` until manually addressed. No timeouts, no auto-cancellation.
- **Feature flag toggled mid-execution**: If the flag is disabled while a promotion is in progress, the in-progress promotion completes; only the next decision point observes the new flag value.
- **Draft promoted directly to running (bypassing queue)**: A drafted epic can still be started manually through the normal path; the queue mechanism is additive, not a replacement.
- **Dirty tree notification missed**: If the notification channel is unavailable, the status transition to `blocked` still persists in the database so the state is recoverable even if the operator never sees the alert.

## Requirements *(mandatory)*

### Functional Requirements

**Isolation mode (Story 1):**

- **FR-001**: The platform configuration MUST support an opt-in isolation mode that, when selected, causes epic work to happen directly in the platform's main clone instead of in a separate worktree.
- **FR-002**: When the new isolation mode is selected, the pipeline MUST check out the epic branch at the main clone path so the developer sees it in their editor without path changes.
- **FR-003**: When the new isolation mode is NOT selected, the existing worktree-based behavior MUST continue unchanged for backwards compatibility.
- **FR-004**: Before checking out an epic branch in the main clone, the system MUST verify the working tree is clean and MUST refuse to proceed if it is not, recording the blocking state visibly.
- **FR-005**: When a second or later epic is promoted while a prior epic's branch has not yet been merged to the base branch, the new branch MUST be created from the prior epic's current tip (cascade), not from the stale base branch. If the prior epic's local branch no longer exists (e.g., cleaned up after merge), the system MUST fall back to the platform's configured base branch after fetching from origin.

**Queue and auto-promotion (Stories 2, 3):**

- **FR-006**: The system MUST support a new epic lifecycle status representing "next in line, execute when the platform slot becomes free" — distinct from `drafted` (planned but not ordered) and `in_progress` (actively running).
- **FR-007**: Users MUST be able to place a drafted epic into the new queued status with a single command that specifies platform and epic identifier.
- **FR-008**: The status transition machinery MUST NOT auto-promote an epic in the new queued status to `in_progress` through node-completion rules — only the explicit promotion mechanism may do so.
- **FR-009**: When the platform's **running slot** becomes free and at least one epic is queued, the system MUST automatically promote the oldest queued epic (FIFO, where "oldest" is defined as the time the epic most recently transitioned INTO the `queued` status) to `in_progress`, create its branch, and begin implementation within 60 seconds of the running slot becoming free.
- **FR-010**: The promotion mechanism MUST be idempotent: invoking it more than once for the same state transition MUST NOT create duplicate branches, duplicate status rows, or duplicate notifications.
- **FR-011**: If promotion fails for a transient reason (e.g., temporary git failure), the system MUST retry up to 3 times with exponential backoff, completing the full retry sequence in **no more than 10 seconds total** before declaring permanent failure.
- **FR-012**: If promotion fails permanently (retry budget exhausted, dirty tree, irrecoverable state), the epic MUST transition to a blocked status and a notification MUST be sent to the operator describing the failure reason.
- **FR-013**: On permanent promotion failure, the database MUST remain in a consistent state — no half-written branch metadata, no orphaned status rows.
- **FR-014**: The sequential invariant MUST be preserved: at most one epic per platform may be in `in_progress` at any time. The promotion mechanism MUST NOT violate this.

**Artifact handling (Story 2):**

- **FR-015**: When a queued epic is promoted, its planning artifacts (pitch, decisions, and any other draft-phase documents already committed to the base branch) MUST be brought onto the new epic branch using the base branch version at the moment of promotion as authoritative — no three-way merge, no conflict resolution. Drift between draft time and promotion time is inherited as-is; operators wanting a re-validated draft must run delta review before queuing.
- **FR-016**: The promotion mechanism MUST commit the artifact migration with a message that clearly identifies the cascade and the source of the inherited artifacts.

**Rollout safety (Story 4):**

- **FR-017**: The automatic promotion behavior MUST be gated by a runtime configuration mechanism that, in its default state, leaves promotion disabled — allowing the code to be merged without activating the behavior.
- **FR-018**: When the runtime flag is explicitly enabled, automatic promotion MUST occur per FR-009. When disabled, the promotion hook MUST be a no-op, leaving queued epics untouched.
- **FR-019**: The flag's current state MUST be observable by an operator without reading source code.

**Developer command surface:**

- **FR-020**: Users MUST be able to inspect the current queue for a platform (which epics are queued, in what order) through a user-facing command.
- **FR-021**: Users MUST be able to remove an epic from the queue (revert `queued` → `drafted`) through a user-facing command, without losing its pitch or decisions.

### Key Entities

- **Epic**: A unit of planned work for a platform. Has a status lifecycle that now includes a new queued state in addition to the existing states (proposed, drafted, in_progress, shipped, blocked, cancelled). Each epic belongs to exactly one platform, has a branch name once promoted, and carries its own pitch and decisions log.
- **Platform isolation mode**: A per-platform configuration value indicating whether epic work happens in the main clone (new mode) or in a dedicated worktree (existing mode). Default must remain the existing mode to avoid regression on unconfigured platforms.
- **Promotion event**: A transition from `queued` to `in_progress` for a single epic, triggered by the running slot becoming free. Either succeeds completely or fails completely — no partial states. Records timestamp and originating epic (which epic freed the slot).
- **Running slot**: A platform-level invariant representing "zero or one epic in progress". The slot is checked before promotion and respected by all other pipeline operations.
- **Runtime promotion flag**: A runtime configuration entry that gates whether the promotion hook takes effect. Independent of code deployment — the code can be present and inactive.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Developers working on an opted-in platform can see the active epic branch in their editor with **zero** navigation to alternative directories (no `cd` into worktree paths).
- **SC-002**: When two epics are queued and the first completes, the second starts automatically within **60 seconds** of the first reaching terminal state — the developer performs **zero** manual actions between completion of the first and start of the second.
- **SC-003**: The end-to-end "queue two epics, walk away, come back" workflow completes with the second epic in `shipped` status in **one attempt**, with no operator intervention required at any point during the queue run (assuming neither epic has a content-level defect).
- **SC-004**: Zero data-loss failure modes on dirty working tree: in **100%** of dirty-tree scenarios, the epic transitions to `blocked` with a notification and no files are modified in the clone.
- **SC-005**: The rollout is reversible in **under 30 seconds**: toggling the runtime flag disables the new behavior without requiring a redeploy or code change.
- **SC-006**: Backwards compatibility is exact: platforms not opted into the new isolation mode see **zero** behavior change in how their epics are executed — existing worktree paths, branch names, and timings are preserved.
- **SC-007**: Promotion failures are always observable: in **100%** of failure cases, the epic's status in the database reflects the failure (never stuck silently in `queued` or an intermediate state) within **60 seconds** of the failure.
- **SC-008**: The queue command is self-service: a developer can queue a previously-drafted epic with **one** command invocation and no manual database editing.

## Assumptions

- The platforms this feature targets (e.g., `prosauai`) already have a documented main-clone path that is stable across epics — the pipeline does not need to synthesize a new path convention.
- Operators of the pipeline are comfortable reading operator notifications (existing notification channel) and acting on them when an epic transitions to `blocked`.
- Epics in the queue are independent: promoting epic N+1 does not require epic N's code to be merged to the base branch. Cascade from N's tip is acceptable and preserves logical sequence.
- Queue depth is small (2–3 epics at most). The system does not need to optimize for hundreds of queued epics or complex priority schemes — FIFO over a small queue is sufficient.
- Users who queue an epic accept the cascade semantics — they understand that if epic N introduces bugs, epic N+1 inherits them. This is equivalent to the current manual workflow where the developer runs `/madruga:epic-context` immediately after the previous epic.
- The new isolation mode is an opt-in; the default remains the existing worktree mode for platforms that have not been explicitly migrated. Existing pipeline behavior is the fallback on any configuration ambiguity.
- Automatic merge of pull requests is explicitly out of scope. All merges remain human-gated for code review. The queue mechanism drives work into `in_progress` but never into `merged` / `shipped` automatically.
- The `madruga-ai` self-reference platform is NOT a target of the new isolation mode in this epic. The mechanism must not break self-ref assumptions; migrating self-ref platforms is a future concern.
- Observability of queue state is sufficient through existing database inspection and pipeline status commands; this epic does not introduce a portal UI for queue management.
- Notification delivery channel availability is best-effort. If a notification cannot be delivered, the database state still accurately reflects the failure and is discoverable through the pipeline status surface.
- The base-branch state of draft artifacts at the moment of promotion is the authoritative version. If an operator wants to re-validate a draft against updated upstream context before promotion, they run delta review (`/madruga:epic-context` on the drafted epic) before queuing — the promotion mechanism itself does no drift reconciliation.

## Dependencies

- Existing SQLite migration precedent for modifying enum-like CHECK constraints (rec-table pattern).
- Existing platform configuration file (`platform.yaml`) as the opt-in surface for isolation mode.
- Existing background daemon poll loop as the insertion point for the promotion hook.
- Existing pipeline notification channel for dirty-tree and failure alerts.
- Existing pipeline status command surface for queue inspection.

## Out of Scope

- Automatic merge of pull requests after an epic ships.
- Queues deeper than 3 simultaneous epics or priority schemes beyond FIFO.
- Portal UI for queue management or visualization.
- Migration of the `madruga-ai` self-reference platform to the new isolation mode.
- Removal of worktree support (`worktree.py`) from the codebase — it stays as the default.
- Cross-platform queue coordination (each platform's queue is independent).
- Automatic recovery from `blocked` → `queued` or `blocked` → `in_progress`. Operator intervention is required to unblock.
