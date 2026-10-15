# AI usage playbook — 24 hours

Official docs checked **2026-10-15**; entitlements and commands can change.
Verify the account's live interface before the event. No scripts here query
providers, read credentials, enforce budgets, or estimate remaining quotas.

## Verified facts and where to look

| Provider / intended login | Check actual available usage | What the numbers mean |
| --- | --- | --- |
| Codex / ChatGPT Plus | Interactive `/status`; [Codex usage dashboard](https://chatgpt.com/codex/settings/usage) | Plan limits/reset information, when available; context/token statistics alone are not remaining quota |
| Claude Code / Claude Pro | Interactive `/usage`; [Claude Settings → Usage](https://claude.ai/settings/usage) | Subscription usage bars and resets; local session dollar/token estimates are not a Pro bill or a complete account quota |
| Antigravity (`agy`) / personal Google account with AI Plus | Interactive `/usage` (alias `/quota`); [quota panel documentation](https://antigravity.google/docs/cli/commands/usage/) | Refreshes model quota information from the service; `/context` measures context consumption, not subscription capacity |

Codex is included with Plus. Model, context, reasoning, tools, and caching affect
usage; included limits cannot be derived from a published API price or a fixed
number of messages. Use the live dashboard, not old promotional limits.
([OpenAI pricing and limits](https://learn.chatgpt.com/docs/pricing))

Claude Pro includes subscription usage. `/usage` distinguishes plan usage from
local cost estimates; values can be stale or unavailable. Claude web activity and
other sessions also matter; check the account view and its displayed resets.
Extra usage/usage credits are separate spending options, not a free fallback.
([Claude usage documentation](https://code.claude.com/docs/en/costs),
[subscription usage](https://support.claude.com/en/articles/9797557-usage-limit-best-practices))

**Antigravity is a different service from Gemini CLI.** Its current plans place
Google AI Plus in the weekly baseline group, without Pro/Ultra's five-hour refresh
benefit. Usage varies with agent work and available capacity; do not apply Gemini
CLI daily request numbers or Google AI Pro entitlements to this account.
Keep Antigravity's quota view separate from Claude Code's, even when selecting a
Claude model in Antigravity. Verify the actual model buckets and reset times.
([Antigravity plans](https://antigravity.google/docs/plans/))

No single token/message counter predicts all subscription windows, model buckets,
tool activity, context effects, or server-side accounting. A fresh session does
not reset plan limits. Missing quota information means **unknown**, not unlimited.

## Model choices — recommended heuristics

Choose among models actually offered by the authenticated CLI. No pinned model
configuration is installed. These are starting points, not guaranteed access or
quota-saving ratios; escalate once when a scoped attempt exposes a real gap.

| Work | First choice | Escalation / stopping rule |
| --- | --- | --- |
| Simple edits, extraction, small tests | Codex Luna (`gpt-6-luna`), Claude Haiku if offered, or Antigravity's available Gemini Flash | Prefer shell/editor for deterministic work; use one available tool |
| Substantial implementation/debugging | Codex `gpt-6.1-sol` if offered, otherwise the available Sol; Claude Sonnet | Increase reasoning for the hard part; reserve Astra/Opus for a specific unresolved problem |
| Research | One available tool with source retrieval; Flash/Luna for source summaries, Sol/Sonnet for synthesis | Give exact questions and primary sources; verify citations and do not infer clinical validity |
| Independent review | A fresh Sol/Sonnet session, optionally another provider | Review a bounded diff against acceptance criteria; stronger model only for consequential uncertainty |

The provider docs describe [Sol/Luna/Astra roles](https://learn.chatgpt.com/docs/models),
[Claude aliases](https://code.claude.com/docs/en/model-config), and
[Antigravity model access](https://antigravity.google/docs/models/).
For Antigravity AI Plus, start with the offered Gemini Flash; reserve any available
Claude model for a specific harder task or independent review. Check the live
selector: the published model table includes time-limited access to older models.
Our routing above is a team heuristic. Use standard/default speed and ordinary
reasoning first; avoid expensive maximum/ultra modes that may delegate work.
Model selection is never permission to enable API billing or extra credits.

## Suggested event rhythm (CEST; capacity guidance, not enforced budgets)

| Time | Focus / usage discipline |
| --- | --- |
| Fri 12:00–14:00 | Human selects challenge, verifies data permission, defines one demo flow and interfaces. One focused planning session; avoid three parallel architecture proposals |
| Fri 14:00–22:00 | Small owned tasks, separate worktrees. Integrate working slices early. Check account usage after substantial tasks or roughly every two hours |
| Fri 22:00–Sat 06:00 | Reduce scope; integrate and debug. At each check, retain roughly a third of currently visible capacity for the remaining event; this is a target, not a quota forecast |
| Sat 06:00–10:00 | Protect the strongest remaining provider for integration and the hardest defects. Validate demo, failure paths, evidence and data handling |
| Sat 10:00–12:00 | Freeze features; bounded final review, demo rehearsal, submission and fallback recording. Keep one usable session/provider available where possible |

At start, before large tasks, and before the final stretch, a human checks the
official usage views and reset times. There is no need to maintain token ledgers.
Do not assume midnight resets or that a short-window reset restores weekly quota.
If availability falls faster than expected, cut task scope and concurrency early.

## Context and review discipline

- Retain a session while solving the same component with useful active context.
  Start fresh for an unrelated task, a role change to independent review, or a
  noisy/stale history. Hand over branch, paths, acceptance, exact checks, and blocker
  using the [handoff template](handoff-template.md); omit the transcript.
- Search targeted paths; read relevant snippets, not every document. Filter long
  test logs locally and include the failing portion. Never attach datasets,
  credentials, patient records, dependency trees, or generated bundles as context.
- One owner implements and runs meaningful checks. Request one independent review
  for shared interfaces, authentication/data handling, subtle algorithms, or the
  final demo path. Give the reviewer the diff, requirements and test evidence;
  keep review read-only. Human clinical validation remains separate.
- Skip a second model for obvious formatting or small changes already covered by
  meaningful checks. Triage findings once and verify fixes; reopen review only
  for unresolved risk or a new substantial change. Recursive agent review loops
  repeat context, consume scarce capacity, and often amplify speculative concerns.
- Humans may assign concurrent independent tasks explicitly; never auto-launch
  all three providers, agent teams, background research, or recursive delegation.
  Exit completed sessions and stop active runs; do not leave polling/retry loops.

## Rate limits and avoiding charges

1. Stop the affected run; note the provider's reset/retry time and preserve a short
   handoff plus local changes. Do not repeatedly retry a limit error.
2. Check the official account view. If another provider has capacity, explicitly
   transfer one bounded task to its own worktree or stop the old writer before
   reusing that checkout. Otherwise work manually, test, simplify, and wait.
3. Never switch to API keys, Vertex/Bedrock/other billable providers, purchased
   credits, or extra usage to bypass a limit. Decline automatic credit fallbacks.
   For Antigravity, avoid `/boost` and credit purchase flows; inspect the account's
   AI Credit Overages setting if offered and have the human keep it at Never.
   Do not change global authentication, subscription, or billing settings here.
4. Confirm the active sign-in mode manually before work. Existing environment or
   global config may select API billing; do not print credential values into logs.
   If the mode is uncertain, stop model calls until the human verifies it.

No subscriptions guarantee 24 hours of continuous agent work. Preserve time for
manual recovery and a smaller working submission. Do not share account credentials.

## Command reference

Run from the assigned worktree root, one writer at a time. These commands do not
enforce usage caps; interactive requests use the currently authenticated account.

| CLI | Shell commands | Inside the interactive CLI |
| --- | --- | --- |
| Codex | `codex --version`, `codex --help`, `codex`, `codex resume` | `/model`, `/status`; use command menu for available commands |
| Claude | `claude --version`, `claude --help`, `claude`, `claude --continue`, `claude --resume` | `/help`, `/model`, `/usage`, `/memory`; `/clear` for a fresh task, `/compact` for continuing context |
| Antigravity | `agy --version`, `agy --help`, `agy`, `agy --continue`, `agy --conversation ID` | `/help` or `?`, `/usage` (or `/quota`), `/context`, `/rules`, `/clear`, `/resume`; launch `agy --model MODEL` only with a model actually offered |

Codex, Claude and Antigravity version/help flags were checked locally; **no model
sessions or subscription quota calls were run**. Antigravity is version 1.3.5.
Slash commands and instruction discovery are documentation verified; check the
installed help and loaded rules at runtime. Account/model access remains unverified.

Codex discovers [AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md).
Claude's [import](https://code.claude.com/docs/en/memory) loads it through `CLAUDE.md`.
Antigravity [reads AGENTS.md directly](https://antigravity.google/docs/rules/), so no
`GEMINI.md` or additional rule copy is required. Inspect Claude `/memory` and
Antigravity `/context` and `/rules`; restart after instruction changes. Global
rules/plugins can also load context. Do not start remote-control daemons, scheduled
tasks, or `/teamwork-preview` for this workflow.
CLI references: [Codex](https://learn.chatgpt.com/docs/developer-commands?surface=cli),
[Claude](https://code.claude.com/docs/en/cli-reference),
[Antigravity](https://antigravity.google/docs/cli/reference/).
