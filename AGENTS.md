# Rakathon 2026 — shared instructions

Purpose: a 24-hour oncology/healthcare hackathon, October 16, 2026 12:00 to
October 17, 2026 12:00 CEST. Current phase: workspace preparation; challenge,
stack, architecture, and application commands are TBD. Do not invent them or
scaffold an application before a challenge is selected.

- Read only what the task needs. Start with Git status and targeted paths/search
  (`rg --files`, `rg -n PATTERN path`); exclude generated files and private data.
  Do not dump the repository or load every document on startup.
- Before writing, confirm task owner, branch/worktree, file scope, and acceptance
  criteria. Each independent writer normally gets a `task/<slug>` branch and its
  own worktree. Never run autonomous writers concurrently in one working tree.
  Coordinate shared files/interfaces with the human integrator.
- Follow existing conventions. Record the chosen stack and runnable commands in
  `docs/architecture.md` when decided; keep meaningful tradeoffs in
  `docs/decisions.md`. Prefer the smallest change that meets acceptance criteria.
- No speculative dependencies, orchestration frameworks, services, containers,
  CI, or background agents. No automatic agent conversations, recursive
  delegation, or review loops. Humans assign parallel work explicitly.
- Keep prompts, plans, output, and handoffs short. Use one agent per task by
  default; escalate reasoning/model only when needed. Consult
  `docs/usage-playbook.md` for usage questions, not on every task. Never infer
  remaining subscription quota from local token counts. Do not configure API
  keys, paid overages, billing, or global CLI settings.
- Run checks appropriate to the change before reporting completion. For Bash:
  `bash -n scripts/doctor.sh && bash -n scripts/status.sh`, and
  `shellcheck scripts/*.sh` if available. Use temporary
  repositories for destructive Git test cases. Never invent passing tests,
  requirements, data provenance, or clinical facts. State unrun checks explicitly.
  Workspace shortcuts: `uv run ./rak --help`; use `uv run ./rak check` when changing
  workspace tooling. Python/uv here serve only tooling, not a chosen app stack.
- On failure, inspect the error and narrow the cause. Avoid repeated blind retries.
  Report blockers with the failing command, relevant error, and next concrete
  action; continue independent authorized work when possible.
- Preserve others' changes. No destructive reset/clean, forced removal, force
  push, or automatic integration. Commit/push only when explicitly requested;
  use small commits named `docs: ...`, `chore: ...`, `feat: ...`, or `fix: ...`.
  Human integrator reviews diffs, merges, and tests the combined result.
- Finish with changed paths, actual checks/results, open risks, and next step.
  Use `docs/handoff-template.md` only when transferring work. Update the task
  row when ownership or status changes; do not maintain duplicate task logs.
- Develop/test with synthetic or explicitly approved datasets. Never send actual
  patient information to external AI providers without explicit authorization
  and an appropriate data-processing basis. Keep credentials, tokens, records,
  and identifying logs out of Git, prompts, screenshots, and handoffs. Ignoring a
  file does not make it safe to upload. Treat LLM output as unverified; record
  sources and require qualified human validation for consequential medical
  functionality. Do not claim regulatory certification or clinical validity.
