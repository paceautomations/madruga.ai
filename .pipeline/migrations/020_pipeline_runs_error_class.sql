-- 020_pipeline_runs_error_class.sql — Persist same-error CB classification
-- Pre-fix, the circuit breaker counted infra failures (zombies, watchdog
-- timeouts, "circuit breaker OPEN" echoes) as task failures, seeding the CB
-- with false positives after each daemon restart.  _classify_error()
-- already labelled errors as deterministic/transient/unknown but the label
-- was thrown away.  This column persists the label so _seed_from_db can
-- ignore transient/infra failures when reconstructing the breaker state.

ALTER TABLE pipeline_runs ADD COLUMN error_class TEXT;
