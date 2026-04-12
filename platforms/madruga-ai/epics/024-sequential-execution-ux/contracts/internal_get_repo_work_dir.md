# Internal Contract: `get_repo_work_dir()`

**Phase**: P4
**File**: `.specify/scripts/ensure_repo.py`
**Type**: New public function
**Spec reference**: FR-001, FR-002, FR-003

## Purpose

Single entry point for the pipeline to ask: "Given this platform and this epic, where should the L2 cycle read from and write to?" Returns a `Path` pointing to either the platform's main clone (new `branch` isolation mode) or a dedicated worktree (existing `worktree` isolation mode, default).

Replaces the existing direct call to `create_worktree()` in `implement_remote.py` (which P5 does as a call-site swap).

## Signature

```python
def get_repo_work_dir(platform_name: str, epic_slug: str) -> Path:
    """
    Resolve the working directory for an epic's L2 cycle.

    Dispatches based on `repo.isolation` in platform.yaml:
      - "worktree" (default, preserves current behavior): returns a new or existing worktree path.
      - "branch":                                          returns the platform's main clone path
                                                           after checking out the epic branch.

    Self-ref platforms (repo.name == own repo) short-circuit to REPO_ROOT regardless
    of the isolation setting, preserving the current self-ref behavior.

    Args:
        platform_name: Platform as registered in platform.yaml.
        epic_slug:     Epic identifier (e.g., '004-channel-webhook').

    Returns:
        Absolute Path to the working directory. Caller should `cwd=str(result)` when
        invoking subprocess / claude -p.

    Raises:
        FileNotFoundError:     platform.yaml does not exist.
        KeyError:              platform.yaml missing required fields (repo.name, repo.base_branch).
        DirtyTreeError:        isolation=branch AND the main clone has uncommitted changes.
        subprocess.CalledProcessError: git operation failed (caller should handle + retry).
    """
```

## Pseudo-implementation

```python
def get_repo_work_dir(platform_name: str, epic_slug: str) -> Path:
    binding = _load_repo_binding(platform_name)  # existing helper
    if _is_self_ref(binding["name"]):            # existing helper
        return REPO_ROOT

    isolation = binding.get("isolation", "worktree")
    if isolation == "branch":
        repo_path = ensure_repo(platform_name)           # existing helper
        _checkout_epic_branch(repo_path, platform_name, epic_slug, binding)
        return repo_path
    elif isolation == "worktree":
        from worktree import create_worktree             # existing function
        return create_worktree(platform_name, epic_slug)
    else:
        raise ValueError(f"Unknown isolation mode: {isolation!r} for platform {platform_name}")
```

## Dependencies

- `_load_repo_binding(platform_name)` — already exists in `ensure_repo.py`. Returns the `repo` dict from `platform.yaml`.
- `_is_self_ref(repo_name)` — already exists. Checks if repo.name matches the current repo.
- `ensure_repo(platform_name)` — already exists. Returns the Path to the platform's main clone, cloning if needed.
- `create_worktree(platform_name, epic_slug)` — already exists in `worktree.py`. Unchanged.
- `_checkout_epic_branch(...)` — **NEW helper** in `ensure_repo.py`, documented separately in `internal_checkout_epic_branch.md`.

## Behavior for self-ref platforms

`_is_self_ref` returns True → function returns `REPO_ROOT` immediately, **without** reading the isolation setting. Rationale: self-ref platforms cannot use worktree OR branch isolation — they run in the current repo regardless (pipeline-dag-knowledge.md §8 parallel epics constraint).

This means `repo.isolation: branch` in a self-ref platform's `platform.yaml` is effectively ignored. The plan explicitly does NOT migrate `madruga-ai` to the new isolation mode (spec.md Assumptions).

## Test cases (P4)

| Test | Given | When | Then |
|------|-------|------|------|
| self-ref short-circuit | platform is madruga-ai (self-ref) | get_repo_work_dir | returns REPO_ROOT, no git ops |
| worktree mode (default) | platform.yaml has no isolation key | get_repo_work_dir | delegates to create_worktree |
| worktree mode (explicit) | isolation: worktree | get_repo_work_dir | delegates to create_worktree |
| branch mode happy path | isolation: branch, clean tree, branch doesn't exist | get_repo_work_dir | creates branch, returns clone path |
| branch mode existing branch | isolation: branch, branch already checked out | get_repo_work_dir | no-op checkout, returns clone path |
| branch mode dirty tree | isolation: branch, dirty tree | get_repo_work_dir | raises DirtyTreeError |
| unknown isolation value | isolation: foo | get_repo_work_dir | raises ValueError |
| missing platform.yaml | no file | get_repo_work_dir | raises FileNotFoundError |
