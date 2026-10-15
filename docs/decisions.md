# Decisions

One short row per consequential choice; skip routine implementation details.

| Date | Decision | Reason / tradeoff |
| --- | --- | --- |
| 2026-10-15 | AGENTS.md is shared; Codex/Antigravity read directly, Claude imports | Small automatic context; no duplicated policy |
| 2026-10-15 | Antigravity (`agy`) replaces Gemini CLI | Use Antigravity commands, model access and quota views; no Gemini adapter needed |
| 2026-10-15 | Native Git worktrees; task branches; human integration | Isolates writers without a custom Git framework |
| 2026-10-15 | Stack and application deferred | Challenge not yet selected |
| 2026-10-15 | Dependency-free Python/uv workspace CLI (`uv run ./rak`) | Short manual commands; reuse Bash diagnostics and native Git; no packaging backend or agent orchestration |
| 2026-10-15 | Windows setup uses WSL2/Ubuntu; keep direct `./rak` launcher | Reuse Linux/Bash workflow without another package/backend; native Windows is unsupported and WSL2 remains untested here |

New entry: date, choice, one-line reason; link relevant evidence only when useful.
