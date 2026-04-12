# Internal Contract: `_checkout_epic_branch()`

**Phase**: P4
**File**: `.specify/scripts/ensure_repo.py`
**Type**: New private helper
**Spec reference**: FR-002, FR-004, FR-005

## Purpose

Check out the epic branch inside the platform's main clone, handling three cases:

1. **Branch already exists locally** → plain `git checkout`
2. **Branch does not exist AND a prior epic branch is active** → cascade from prior epic's tip
3. **Branch does not exist AND no prior epic branch (or prior is merged)** → branch from `origin/<base_branch>`

All paths are preceded by a dirty-tree guard that raises `DirtyTreeError` if the working tree has uncommitted changes.

## Signature

```python
def _checkout_epic_branch(
    repo_path: Path,
    platform_name: str,
    epic_slug: str,
    binding: dict,
) -> None:
    """
    Ensure the epic branch is checked out in `repo_path`.

    Args:
        repo_path:     Absolute path to the platform's main clone.
        platform_name: Platform name (for error messages).
        epic_slug:     Epic identifier.
        binding:       The `repo` dict from platform.yaml. Must contain:
                         - epic_branch_prefix (e.g., "epic/prosauai/")
                         - base_branch (e.g., "develop")

    Raises:
        DirtyTreeError:                Uncommitted changes in repo_path.
        subprocess.CalledProcessError: git operation failed after retries.
    """
```

## Algorithm

```python
def _checkout_epic_branch(repo_path, platform_name, epic_slug, binding):
    branch_name = f"{binding['epic_branch_prefix']}{epic_slug}"

    # 1. Dirty-tree guard (MUST be first — any git state change after this is safe)
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(repo_path),
        capture_output=True, text=True, check=True
    )
    if status.stdout.strip():
        raise DirtyTreeError(
            f"{repo_path} has uncommitted changes. Commit or stash before running epic {epic_slug}.\n"
            f"Dirty files:\n{status.stdout}"
        )

    # 2. If the branch already exists locally, just check it out.
    local = subprocess.run(
        ["git", "branch", "--list", branch_name],
        cwd=str(repo_path),
        capture_output=True, text=True, check=True
    ).stdout.strip()
    if local:
        subprocess.run(
            ["git", "checkout", branch_name],
            cwd=str(repo_path), check=True
        )
        return

    # 3. Branch is new. Fetch origin first so we have up-to-date refs.
    subprocess.run(
        ["git", "fetch", "origin", binding["base_branch"]],
        cwd=str(repo_path), check=True
    )

    # 4. Determine the cascade base.
    cascade_base = _get_cascade_base(repo_path, binding)

    # 5. Create the new branch from the cascade base.
    subprocess.run(
        ["git", "checkout", "-b", branch_name, cascade_base],
        cwd=str(repo_path), check=True
    )


def _get_cascade_base(repo_path: Path, binding: dict) -> str:
    """
    Return the ref to use as the starting point for a new epic branch.
    If a prior epic branch is locally present AND has commits not yet on
    origin/<base_branch>, cascade from its tip.
    Otherwise, return origin/<base_branch>.
    """
    base_ref = f"origin/{binding['base_branch']}"
    prefix = binding["epic_branch_prefix"].rstrip("/")

    # List epic branches locally, sorted by most recent committer date.
    result = subprocess.run(
        ["git", "for-each-ref", "--sort=-committerdate",
         f"refs/heads/{prefix}/*", "--format=%(refname:short)"],
        cwd=str(repo_path),
        capture_output=True, text=True, check=True
    )
    candidates = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    for candidate in candidates:
        # Check if candidate has commits not yet in base.
        ahead = subprocess.run(
            ["git", "rev-list", "--count", f"{base_ref}..{candidate}"],
            cwd=str(repo_path),
            capture_output=True, text=True, check=True
        )
        if int(ahead.stdout.strip()) > 0:
            return candidate  # Cascade from this prior epic.

    return base_ref  # Fallback: branch from base.
```

## Error semantics

- `DirtyTreeError` is a new exception class in `ensure_repo.py`. Caller (`promote_queued_epic`) catches it and transitions the epic to `blocked` with a notification.
- `subprocess.CalledProcessError` propagates up. Caller retries per the retry budget (3 attempts, 1/2/4s backoff, ≤10s total).

## Idempotency

- `git status --porcelain` is read-only.
- `git branch --list` is read-only.
- If the branch already exists, the function is a plain `git checkout` — idempotent.
- If the branch does not exist, the function creates it once. Running twice from a clean state would fail on the second call (`branch already exists`), which the caller should treat as a successful check-out via case 2.

## Test cases (P4)

Covered in `internal_get_repo_work_dir.md` — same test file, shared fixtures.
