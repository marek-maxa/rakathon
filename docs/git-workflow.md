# Worktrees: one writer per checkout

Human integrator owns `main` and the task board. A worker owns `task/<slug>` and
its worktree. Worktrees share Git history/refs, not live files or staged changes.
Pause writers before checkout, update, integration, or removal. Never run Git
mutations concurrently in the same checkout. Do not commit/push unless requested.

## Create and inspect

Run from the primary repository root. With no `HEAD`, stop and have a human review
and make the first commit using [README](../README.md#1-před-začátkem-rakathonu).
Uncommitted setup files are not copied into new worktrees.

Shortcut from a clean primary checkout on `main`:
`uv run ./rak task example --open`. It creates the branch/worktree below and
optionally opens VS Code. It refuses missing commits, dirty primary checkouts,
existing paths/branches, and nested task creation; it never resets or removes work.
Use `uv run ./rak status` to inspect and `uv run ./rak agent codex` (or `claude`,
`agy`) inside a task checkout to launch one writer. Updates, merges and removal
remain the explicit native Git operations below. Each checkout gets its own
ignored `.venv`; no environment activation is needed.

```bash
git rev-parse --verify HEAD
git status --short --branch
git worktree list
mkdir -p .worktrees
git worktree add -b task/example .worktrees/example main
git -C .worktrees/example status --short --branch
code --new-window .worktrees/example
```

Use a unique real slug per task. `.worktrees/` is ignored; verify with
`git check-ignore .worktrees/example`. Commands fail on existing branch/path
instead of replacing it. To reopen an existing branch use
`git worktree add .worktrees/example task/example` if not already checked out.
An external sibling path is also valid when filesystem permissions allow it.
Do not nest further worktrees inside a task worktree.

## Update a task branch

Run inside its worktree with the writer paused. Inspect `git status --short` and
stop if it has changes; commit authorized work or preserve it before proceeding.
Do not stash someone else's work or discard changes to make commands succeed.

```bash
git status --short --branch
git merge main
```

This brings in the integrator's local `main`. If needed, the integrator first
fetches the agreed remote explicitly (`git fetch origin`) and updates a clean
`main` using `git merge --ff-only origin/main`. No remote/default branch was
verified at setup: local `main` is unborn and its `origin/main` upstream is gone.
Do not pull blindly or assume a remote branch exists. A different team's default
branch must be substituted explicitly throughout these examples.

For conflicts: inspect `git status`, resolve only owned files with the integrator,
stage specific resolved files, run checks, then `git merge --continue` when
authorized. To abandon the merge started above, use `git merge --abort`; starting
with a clean tree protects preexisting work. Stop/report if recovery fails.

## Review and integrate (human controlled)

Worker first checks `git diff --check`, runs the acceptance checks, and reviews
`git diff` plus `git diff --cached`. When authorized, stage explicit paths and
commit, e.g. `git commit -m "feat: implement selected task"`. Handoff includes
actual results and uncommitted/untracked files. Those files do not merge.

In the primary checkout, with workers paused and **both checkouts clean**:

```bash
git switch main
git status --short --branch
git -C .worktrees/example status --short --branch
git log --oneline main..task/example
git diff --stat main...task/example
git diff main...task/example
# Human reviews and chooses to integrate:
git merge --no-ff --no-commit task/example
git diff --cached --check
git diff --cached
# Run the actual combined checks from docs/architecture.md, then:
git commit -m "chore: integrate example task"
```

The merge deliberately stops before a commit (unless already up to date). A human
resolves conflicts, checks the result, and commits, or uses `git merge --abort`.
Never auto-merge into main, force-push, or push without instruction. Review scope
and interfaces early; isolation does not prevent integration conflicts.

## Remove only after preserving and integrating work

Run from primary root, with the task writer stopped. Inspect tracked, untracked,
**and ignored** files (datasets/notes can be lost even on a seemingly clean tree):

```bash
git -C .worktrees/example status --short --untracked-files=all --ignored
git log --oneline main..task/example
git merge-base --is-ancestor task/example main
```

Stop on any files to preserve, unmerged commits, or nonzero ancestry result.
Move needed local files to a safe location first. Only then run:

```bash
git worktree remove .worktrees/example
git branch -d task/example
git worktree list
```

`git worktree remove` refuses ordinary dirty trees but can remove ignored files;
the explicit inspection above is essential. `git branch -d` protects unmerged
branches, but the ancestry check against `main` also verifies the intended target.
No `--force`, `-D`, `reset --hard`, `clean`, or filesystem deletion to bypass safety.
If a directory is missing unexpectedly, inspect `git worktree prune --dry-run`
and recover any needed files before deciding whether to prune stale metadata.
