# Engineering workflow

Start with: **Use $feature-delivery to implement the active specification in NEXT.md.**
The primary session is the lead; it owns scope, sequencing, integration, and reporting.
Product direction and significant architecture decisions remain with the human.

## Task size and handoffs

| Work | Execution |
| --- | --- |
| Small isolated fix/docs | Lead inspects, edits, runs relevant checks, summarizes. |
| Normal feature | Spec, focused plan, implementation, tests, independent reviewer, corrections. |
| Inference/planner/scheduler/events/architecture | Architecture analysis, approval for material design changes, implementation, simulation review, QA, independent reviewer, corrections and revalidation, human integration approval. |

Delegate through native subagents using the role names below. A handoff includes the
spec path, bounded question, owned files (or read-only scope), acceptance criteria,
required evidence, and dependencies. Use fresh context for independent review: supply
the spec, baseline, diff, and repository paths, without implementation conclusions.
Inspect untracked additions as well as `git diff`. The lead reconciles disagreements
against code/tests and records unresolved issues rather than voting among agents.

| Agent | Invoke when | Write scope |
| --- | --- | --- |
| architecture | Requirements affect interfaces or high-risk behavior | Read-only instructions |
| implementation | A bounded approved slice benefits from delegation | Assigned files and tests |
| simulation | Math, RNG, scheduling, planning, or event semantics change | Read-only instructions |
| reviewer | Substantial diff is ready for independent inspection | Read-only instructions |
| qa | Acceptance needs independent executed verification | Generated check artifacts only |

Example request: “Have architecture inspect the replay spec and qa audit existing
coverage in parallel; then implement the agreed slice and have simulation and reviewer
inspect the actual diff.” Do not spawn every role for every task. Limit to three
specialists concurrently, lower when the client imposes a smaller limit. Only the
lead delegates. Avoid concurrent edits to shared files; use isolated worktrees when
independent implementations materially benefit. Integration belongs to the lead.

## Native setup and limitations

Project agents live in `.codex/agents/*.toml`; skills live in
`.agents/skills/<name>/SKILL.md`. The project config caps spawned threads at three
and inherits model/reasoning settings. Project defaults are `sandbox_mode =
"workspace-write"`, `approval_policy = "on-request"`, and `approvals_reviewer =
"user"`. No user config changes
are needed. Trust this repository through Codex's normal project trust flow and start
a new session after adding these files. Ask Codex to use a named role; these names
are not shell commands. Skills can be requested as `$feature-delivery` and
`$simulation-verification`.

Observed on 2026-11-03: CLI `0.164.0-alpha.11.1`, VS Code extension
`openai.chatgpt-26.1021.22027-win32-x64`, `multi_agent` enabled, `multi_agent_v2`
disabled. This session exposes native spawn/follow-up/message tools and successfully
delegated the audit in the linked report. No CLI update is required for this session.
The bootstrap chat initially could not select project custom-agent types. On
2026-11-04 the Milestone 8 session exposed and invoked the configured `architecture`,
`implementation` and `qa` roles through native `agent_type` selection. This verifies
named-role discovery in that session; it does not establish support in every client
version. See the milestone delivery report for actual invocation evidence.

Check setup with `codex --version`, `codex features list`, and
`codex --strict-config app-server --print-startup-config`. If native delegation is
disabled, inspect that installed version's help and enable its supported multi-agent
feature in the session (`codex --enable multi_agent` for the observed CLI). Do not
invent a wrapper or silently alter user settings. Report a missing capability.

Native agents inherit the parent's permissions; a role file cannot override its
sandbox or approval policy. For filesystem-enforced analysis/review, use a separate
read-only Codex parent session rather than relying only on role instructions:

```powershell
codex --sandbox read-only --ask-for-approval never --disable apps --disable plugins review --uncommitted
```

This supported installed CLI command reviews staged, unstaged and untracked changes.
For architecture/simulation analysis use the same parent flags with `exec --ephemeral`
and a bounded prompt referencing the spec and role instructions. Run it when the CLI
and authentication are available. These are native Codex sessions, not custom agent
frameworks. Read-only filesystem sandboxing blocks repository writes and `never`
prevents escalation; disabling apps/plugins removes those tool surfaces. It does not
prove arbitrary inherited MCP connectors are read-only; avoid them for local review.
Do not bypass sandboxing if checks need writes: return a finding or have QA execute
them separately. Record actual launch/settings and results, or the environment blocker.

When this host only exposes inherited-permission subagents, native review remains
instruction-only: label it honestly and use the separate CLI route where supported.
Named agents inherit models rather than pinning unavailable ones.

Managed/client policy, explicit session flags, and existing command rules can affect
effective permissions. Repository TOML does not reconfigure an already-running chat
or revoke saved command approvals. In particular this chat uses host-managed automatic
approval review; project `approvals_reviewer = "user"` is a future-session default,
not proof of a human approval prompt here. Confirm effective permissions on startup.
Human authorization below remains required even if a tool could execute without a
prompt. Do not modify user settings or remove saved rules without explicit approval.

Supported syntax references: [custom agents](https://learn.chatgpt.com/docs/agent-configuration/subagents),
[configuration](https://learn.chatgpt.com/docs/config-file/config-reference), and
[skills](https://learn.chatgpt.com/docs/build-skills). Check installed help and current
official docs before changing configuration; native agent schemas evolve.

## Verification and integration

Use an editable install with `python -m pip install -e ".[dev]"`. Activate `.venv`
or use its Python explicitly. The CI workflow is the executable source for gates.
Existing pytest tests cover core invariants, deterministic runs, integration, and
Textual `run_test` pilots including an 80x24 configuration layout. Report visible
terminal verification separately from headless tests.

Incremental gate scope and baseline debt are recorded in
[the bootstrap report](reports/workflow-bootstrap.md). Format new/changed Python
files with Ruff; expand CI's formatter allowlist as legacy files are cleaned up.

Use a feature branch for substantial work (`git switch -c <feature-name>`), preserving
existing changes; use a worktree only when justified. Obtain explicit approval before
committing, pushing, or merging; earlier unrelated push requests do not authorize
future deliveries. No destructive Git operations or overwriting unrelated work.
Ask about material architecture/TUI/semantics changes before their implementation,
with concrete alternatives. Routine reversible work within the spec proceeds.

## Autonomy and task lifecycle

Before implementation, state acceptance criteria, definition of done and owned files
in the spec or a short task checklist. The active request defines scope; NEXT is
context, not permission to start its milestone.

| Proceed within the authorized task | Human approval before action |
| --- | --- |
| Repository file edits, documentation, existing tests and checks | New dependencies, including development tooling |
| Bounded architecture analysis, simulation verification, independent review | Significant architecture, product or simulation-semantics changes |
| Corrections for blocking findings within acceptance criteria | Destructive operations or writes outside the authorized workspace |
| Local reversible preparation and verification | External writes, commits, pushes and merges |

Approval must cover the concrete action; an explicit request may supply it. Do not
ask again for ordinary safe work or delegation already authorized. Installing the
already-approved declared dependencies is distinct from adding a new dependency;
network/sandbox escalation may still apply. Never treat automatic sandbox approval
as the user's authorization for a consequential action.

The lead automatically cycles implementation, relevant tests, independent review,
blocking corrections and affected revalidation. It stops and reports when all criteria
and definition of done are satisfied, a blocker requires human input/access, or the
next change would exceed approved scope. On a blocker, finish independent authorized
work first; report the exact failing evidence and smallest intervention required.
Do not endlessly retry unchanged failures or add unrelated improvements after done.

Read-only provisional planning for the next milestone may run while implementation
continues. Mark its assumptions and provisional status. Reconcile it against the
final integrated code and verification findings before execution. Updating NEXT or
finishing a milestone never authorizes executing the next one; wait for a new task.

Substantial specs use docs/specs/TEMPLATE.md; architecture decisions with enduring
tradeoffs get a concise numbered record under docs/adr/. Do not write an ADR for
routine implementation choices. Update NEXT only when its active milestone completes.

## Delivery evidence

Record in the PR or `docs/reports/<task>.md`: objective/spec and completion status;
changed files and purpose; agent role/task identifiers and contributions; findings
with locations/severity; disagreements and corrections; exact commands/results and
environment failures; acceptance criteria satisfied or pending; mock/demo boundaries;
risks and human decisions/approval state. Do not create reports for trivial edits.
Never imply that independent review or a passing suite proves untested behavior.
