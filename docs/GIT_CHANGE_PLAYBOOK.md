# Git Change Playbook

Use this file as the default workflow whenever you want to change code.

## Default Rule

- Create a branch for every code change.
- Keep `development` and `main` clean and releasable.
- Open a PR, merge, then delete the branch.

## Quick Start Checklist

1. Sync your base branch.
2. Create a short-lived branch for one task.
3. Make small, focused commits.
4. Run tests/lint relevant to your change.
5. Push branch and open PR.
6. Merge after review/CI passes.
7. Delete local and remote branch.

## Step-by-Step Commands

### 1) Sync base branch

```bash
git checkout development
git pull origin development
```

### 2) Create branch

Use one branch per task:

```bash
git checkout -b feature/<short-description>
```

Examples:
- `feature/update-extraction-timeout`
- `fix/sortstar-docx-placeholder`
- `chore/refactor-processing-service`

### 3) Make and commit changes

```bash
git status
git add <files>
git commit -m "feat: short description"
```

Commit message prefixes:
- `feat:` new behavior
- `fix:` bug fix
- `refactor:` internal cleanup, same behavior
- `test:` tests only
- `docs:` documentation only
- `chore:` tooling/maintenance

### 4) Validate before push

Run only what applies to your change:

```bash
python -m pytest tests/test_llm/test_extraction_v2.py
python scripts/check_secrets.py --staged
```

If frontend changed:

```bash
cd frontend
npm run lint
```

### 5) Push and open PR

```bash
git push -u origin feature/<short-description>
```

PR checklist:
- Scope is small and focused.
- Tests added/updated for behavior changes.
- No secrets or local-only files included.
- Clear summary and rollback plan.

### 6) Merge and clean up

After PR merge:

```bash
git checkout development
git pull origin development
git branch -d feature/<short-description>
git push origin --delete feature/<short-description>
```

## When You Can Skip a Branch

Only for very small local-only edits in a personal repo with no review/CI needs.
If unsure, create a branch.

## Safety Rules

- Do not commit `.env` or credentials.
- Do not mix unrelated changes in one branch.
- Avoid long-lived branches; rebase/merge from `development` frequently.
- If branch history gets messy, open a fresh branch and cherry-pick clean commits.

## Branch Naming Convention

- `feature/<topic>`
- `fix/<topic>`
- `chore/<topic>`
- `docs/<topic>`

Use lowercase and hyphens.
