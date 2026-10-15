# Architecture — TBD

No application or stack selected. Fill only what the chosen challenge needs.
The existing Python/uv environment is solely for workspace utilities, not an
application decision. It has no external dependencies or installed package.
Supported workflow: Linux; Windows users should follow the WSL2/Ubuntu setup in
README. Native PowerShell/CMD is unsupported; WSL2 has not been tested here.

- Language/runtime, versions, dependency tool: TBD
- Components and owned paths: TBD
- Interfaces/contracts between concurrent tasks: TBD
- Data flow, trust boundaries, approved storage/processing: TBD
- External services and permitted authentication/cost basis: TBD
- Clinical output provenance, limitations, human validation point: TBD

| Action | Exact command / prerequisites |
| --- | --- |
| Setup application | TBD |
| Run demo | TBD |
| Test | TBD |
| Lint/build | TBD |
| Submit/demo fallback | TBD |

Workspace setup: `uv sync --offline` (Python >= 3.11 already installed).
Workspace CLI: `uv run ./rak --help`; tests: `uv run ./rak check`.
Direct diagnostics remain available: `bash scripts/doctor.sh`, `bash scripts/status.sh`,
`bash -n scripts/doctor.sh && bash -n scripts/status.sh`, and
`shellcheck scripts/*.sh` (optional installed tool).
These validate infrastructure, not an application. Never report TBD checks as passed.
