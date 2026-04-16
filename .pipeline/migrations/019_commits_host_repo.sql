-- 019_commits_host_repo.sql — Cross-repo commit attribution
-- Adds host_repo column to track WHERE a commit physically lives, separate
-- from platform_id (which means "owns the work / epic"). Solves the case
-- where prosauai work is committed inside the madruga.ai checkout.
--
-- Format: '<org>/<name>' (e.g. 'paceautomations/madruga.ai').
-- Nullable so legacy rows are not lost; backfill heuristic below.
--
-- ALTER TABLE ADD COLUMN with NULL default is constant-time in SQLite
-- (no table rewrite). Pattern preferred over CREATE+COPY when CHECK
-- constraints are not affected.

ALTER TABLE commits ADD COLUMN host_repo TEXT;

-- Backfill: hook + backfill sources fired in the madruga.ai checkout.
-- external-fetch sources read from the bound repo of the platform_id at
-- ingest time — heuristic: madruga-ai/fulano fetches were against madruga.ai;
-- everything else assumes paceautomations/<platform_id>. If no platform.yaml
-- match exists at audit time, the audit script can refine these.
UPDATE commits SET host_repo = 'paceautomations/madruga.ai'
  WHERE host_repo IS NULL AND source IN ('hook', 'backfill', 'manual', 'reseed');

UPDATE commits SET host_repo = 'paceautomations/madruga.ai'
  WHERE host_repo IS NULL AND source = 'external-fetch'
    AND platform_id IN ('madruga-ai', 'fulano');

UPDATE commits SET host_repo = 'paceautomations/prosauai'
  WHERE host_repo IS NULL AND source = 'external-fetch' AND platform_id = 'prosauai';

CREATE INDEX IF NOT EXISTS idx_commits_host_repo ON commits(host_repo);
