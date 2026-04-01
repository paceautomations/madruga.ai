# Decision Classifier — Knowledge

Instructions for detecting and classifying 1-way-door decisions during L2 skill execution.

---

## 1. What Is a 1-Way-Door Decision?

A decision that is **difficult or impossible to reverse** once implemented. Examples:
- Dropping a database column (data loss)
- Removing a public API endpoint (breaks consumers)
- Changing a public API contract (breaking change)
- Deleting production data

Contrast with 2-way-door decisions (easily reversible):
- Adding a new nullable column
- Renaming an internal variable
- Adding a new endpoint

---

## 2. Risk Score Calculation

```
score = Risk (1-5) × Reversibility (1-5)
```

| Factor | 1 | 2 | 3 | 4 | 5 |
|--------|---|---|---|---|---|
| **Risk** | No impact | Minor inconvenience | Service disruption | Data/revenue loss | Catastrophic/unrecoverable |
| **Reversibility** | Minutes (undo) | Hours (deploy) | Days (migration) | Weeks (complex) | Impossible |

### Threshold

- **score ≥ 15** → **1-way-door** → pause execution, notify via Telegram
- **score < 15** → **2-way-door** → proceed automatically

---

## 3. Risk Patterns Table

**Authoritative source**: `RISK_PATTERNS` in `.specify/scripts/decision_classifier.py`. The table below is a human-readable summary — if values diverge, the Python module is correct.

Patterns are matched case-insensitively against the decision description. Ordered by severity (highest first). First match wins.

| Category | Examples | Score | Result |
|----------|----------|-------|--------|
| Schema drop/delete | drop column, drop table, remove column | 25 | 1-way |
| Delete production data | delete data, truncate, purge | 25 | 1-way |
| Change API contract | change contract, breaking api | 25 | 1-way |
| Change auth/security | change auth, modify security | 20 | 1-way |
| Remove public endpoint | remove endpoint, deprecate endpoint | 15 | 1-way |
| Remove feature | remove feature, breaking change | 12 | 2-way |
| Add public endpoint | add endpoint, new route | 6 | 2-way |
| New dependency | add dependency, new library | 6 | 2-way |
| Schema add | add column, add index, create table | 2 | 2-way |
| Rename/refactor | rename, refactor, move file | 1 | 2-way |
| **Unknown** (no match) | — | 4 | 2-way |

**Threshold**: ≥15 = 1-way-door. Gap between 12 and 15 provides margin for edge cases. See `THRESHOLD` constant in `decision_classifier.py`.

---

## 4. Inline Detection During L2 Skills

When executing L2 skills (implement, etc.), watch for decisions that match patterns above. When a decision is encountered:

1. Calculate risk score using the patterns table.
2. If score < 15 → log as 2-way-door, proceed automatically.
3. If score ≥ 15 → **PAUSE execution**:
   a. Format the decision with context, score breakdown, and alternatives.
   b. Notify via Telegram using `notify_oneway_decision()`.
   c. Wait for approve/reject response.
   d. If approved → continue execution.
   e. If rejected → adjust approach or abort the decision.

### Fail Closed

If Telegram is unavailable when a 1-way-door decision needs notification:
- **Do NOT proceed** — the pipeline pauses and waits.
- Retry with exponential backoff (already built into telegram_adapter).
- A 1-way-door decision proceeding without human approval is worse than a paused pipeline.

---

## 5. Python Module Reference

The `decision_classifier.py` module at `.specify/scripts/decision_classifier.py` provides:

```python
from decision_classifier import classify_decision, RiskScore, THRESHOLD

result: RiskScore = classify_decision("drop column legacy_id from users table")
# result.score = 25, result.classification = "1-way-door"

if result.is_oneway():
    # pause and notify
    ...
```

Use this module for programmatic classification. The patterns table above is the human-readable reference; the module implements the same logic.
