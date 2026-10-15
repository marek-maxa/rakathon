#!/usr/bin/env bash
# Local diagnostics only: no model calls, authentication, installs, or Git writes.
set -euo pipefail

failures=0
report() {
    printf '%-10s %s\n' "$1" "$2"
    if [[ $1 == FAILURE ]]; then failures=$((failures + 1)); fi
}

for tool in bash git uv python3 codex claude agy code; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        level=WARNING
        if [[ $tool == bash || $tool == git || $tool == python3 ]]; then level=FAILURE; fi
        report "$level" "$tool not installed/on PATH"
        continue
    fi
    if version=$("$tool" --version 2>&1); then
        # Some CLIs emit warnings before their version; preserve those as warnings.
        if [[ $version == *WARNING* ]]; then
            report WARNING "$tool version output: $version"
        else
            report PASS "$tool: ${version%%$'\n'*}"
        fi
    else
        report WARNING "$tool found but --version failed (not a subscription check)"
    fi
done

if command -v python3 >/dev/null 2>&1; then
    if python3 -c 'import sys; raise SystemExit(sys.version_info < (3, 11))'; then
        report PASS 'Python >= 3.11 for workspace utilities'
    else
        report FAILURE 'Workspace utilities require Python >= 3.11'
    fi
fi
command -v git >/dev/null 2>&1 || exit 1
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
if ! root=$(git -C "$script_dir" rev-parse --show-toplevel 2>/dev/null); then
    report FAILURE 'Scripts must be inside a Git working tree'
    exit 1
fi
cd -- "$root"
report PASS "Repository: $root"
if git rev-parse --verify HEAD >/dev/null 2>&1; then
    report PASS 'Initial commit exists'
else
    report WARNING 'No initial commit; a human must review/commit before creating task worktrees'
fi
if branch=$(git symbolic-ref --short -q HEAD); then
    report PASS "Branch: $branch"
else
    report WARNING 'Detached HEAD; select a task branch before writing'
fi
if git worktree list --porcelain >/dev/null; then
    report PASS 'Native Git worktree support available'
else
    report FAILURE 'git worktree list failed'
fi
if ! state=$(git --no-optional-locks status --porcelain=v1 --untracked-files=normal); then
    report FAILURE 'Cannot inspect Git working tree'
elif [[ -n $state ]]; then
    report WARNING 'Uncommitted/untracked changes; inspect uv run ./rak status (or bash scripts/status.sh)'
else
    report PASS 'Working tree clean'
fi

for file in AGENTS.md CLAUDE.md .gitignore .gitattributes README.md \
    pyproject.toml uv.lock rak tests/test_workspace.py \
    .vscode/settings.json scripts/doctor.sh scripts/status.sh \
    docs/challenge.md docs/architecture.md docs/decisions.md docs/tasks.md \
    docs/handoff-template.md docs/usage-playbook.md docs/git-workflow.md; do
    if [[ -s $file ]]; then report PASS "$file"; else report FAILURE "Missing/empty: $file"; fi
done
if [[ -f CLAUDE.md && $(<CLAUDE.md) == '@AGENTS.md' ]]; then
    report PASS 'CLAUDE.md imports shared instructions only'
else
    report FAILURE 'CLAUDE.md must contain only @AGENTS.md'
fi
report UNVERIFIED 'Antigravity loads AGENTS.md directly per official docs; inspect /context and /rules at runtime'
if git check-ignore -q --no-index .worktrees/probe; then
    report PASS '.worktrees/ ignored'
else
    report FAILURE '.worktrees/ must be ignored before using nested worktrees'
fi
for script in scripts/doctor.sh scripts/status.sh; do
    if bash -n "$script"; then report PASS "$script syntax"; else report FAILURE "$script syntax"; fi
done
if command -v shellcheck >/dev/null 2>&1; then
    if shellcheck scripts/doctor.sh scripts/status.sh; then
        report PASS 'ShellCheck'
    else
        report FAILURE 'ShellCheck findings'
    fi
else
    report UNVERIFIED 'ShellCheck unavailable (optional); Bash syntax checked separately'
fi
report UNVERIFIED 'Sign-in modes, account eligibility, live quotas, and runtime instruction loading: verify interactively'
report UNVERIFIED 'Application checks TBD until challenge/stack selection; see docs/architecture.md'
if [[ -x .venv/bin/python ]]; then
    report PASS 'Local .venv present (uv manages it; no activation needed)'
else
    report UNVERIFIED 'Local .venv not created yet; run uv sync --offline'
fi
printf '\nFailures: %d (warnings/unverified do not fail this check)\n' "$failures"
if (( failures > 0 )); then exit 1; fi
