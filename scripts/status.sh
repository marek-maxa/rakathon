#!/usr/bin/env bash
# Read-only snapshot; never polls providers or reads credential files.
set -euo pipefail

if ! command -v git >/dev/null 2>&1; then
    printf 'FAILURE: git is required\n' >&2
    exit 1
fi
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
if ! root=$(git -C "$script_dir" rev-parse --show-toplevel 2>/dev/null); then
    printf 'FAILURE: scripts must be inside a Git working tree\n' >&2
    exit 1
fi
cd -- "$root"
printf 'Repository: %s\n\n' "$root"
# Avoid even the optional index refresh performed by git status.
git --no-optional-locks status --short --branch --untracked-files=normal
printf '\nWorktrees (status above covers this worktree only):\n'
git worktree list
printf '\nTask board (this checkout; shared via commits, not live across worktrees):\n'
if [[ -f docs/tasks.md ]]; then
    while IFS= read -r line; do
        if [[ $line == \|* ]]; then printf '%s\n' "$line"; fi
    done < docs/tasks.md
else
    printf 'WARNING: docs/tasks.md missing\n'
fi
printf '\nCLI availability:\n'
for tool in codex claude agy; do
    if command -v "$tool" >/dev/null 2>&1; then
        printf 'PASS       %s installed\n' "$tool"
    else
        printf 'WARNING    %s missing\n' "$tool"
    fi
done
cat <<'USAGE'

Usage (open manually; no remaining quota is inferred here):
  Codex:  /status; https://chatgpt.com/codex/settings/usage
  Claude: /usage;  https://claude.ai/settings/usage
  Antigravity (agy): /usage (alias /quota); /context shows context consumption
  If a command/view is unavailable, use /help and the official docs below.
  Antigravity: Google AI Plus has the weekly baseline; verify live model quotas.
  Details and source links: docs/usage-playbook.md
USAGE
