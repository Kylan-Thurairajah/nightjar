# Autonomy and lifecycle policy — 2026-11-03

Scope: refine the existing uncommitted workflow infrastructure. No product milestone,
production code, dependency, user-level setting, commit, push or merge changes.

## Acceptance and definition of done

- Inspect current user/project configuration before edits; preserve user settings.
- Set only supported repository-local permission defaults; document host overrides.
- Define autonomous edits/checks/delegation, consequential-action approvals, bounded
  correction loops, explicit acceptance/done criteria and stopping conditions.
- Permit provisional next-milestone analysis without authorizing execution.
- Provide a real filesystem-enforced read-only review route; distinguish native
  inherited-permission reviewers from isolated review sessions.
- Validate changed configuration and skill, run existing tests, obtain independent
  review, and report remaining risks and approval actions. Stop after these criteria.

## Inspection and decisions

User config already trusts Nightjar and selects the unelevated Windows sandbox.
It contained no explicit sandbox mode or approval policy. Project config initially
only capped concurrency. No user-level changes are needed or proposed.

Minimal project changes: `sandbox_mode = "workspace-write"`,
`approval_policy = "on-request"`, `approvals_reviewer = "user"`. These are defaults
for future trusted project sessions; managed policies and session overrides win.
This chat's host-managed `auto_review` routing remains in force. Instructions require
actual human authorization for consequential actions even if a command rule or
automatic approval would otherwise allow execution.

The installed native role schema cannot override parent permissions. Therefore no
fictional per-role `sandbox_mode` keys were added. WORKFLOW supplies a dedicated
CLI parent-session read-only launch, disabling apps/plugins and escalation. Other
MCP tools are not covered by filesystem sandboxing and must not be used for external
writes during local review. Native reviewers remain instruction-only when launched
from a writable parent.

## Changed files for this follow-up

- `.codex/config.toml`: project-local permission and human-review defaults.
- `AGENTS.md`: task acceptance/done, autonomy, approvals, stopping/provisional rules
  and dated decision entry.
- `.agents/skills/feature-delivery/SKILL.md`: bounded automatic correction loop and
  explicit stop/approval behavior.
- `.codex/agents/implementation.toml`: require acceptance/done in handoffs and return
  blockers rather than expanding scope.
- `docs/WORKFLOW.md`: supported read-only launch, permission limitations, action
  matrix, lifecycle and provisional-planning rules.
- `docs/specs/TEMPLATE.md`: explicit definition of done/stopping conditions.
- `docs/reports/autonomy-policy.md`: this concise evidence record.

Earlier bootstrap changes remain preserved in the working tree; they are inventoried
separately in workflow-bootstrap.md. No production or tests files were edited.

## Verification and independent review

All Python commands use `.\.venv\Scripts\python.exe`.

- `codex --strict-config app-server --print-startup-config`: exit 0; harmless runtime
  temporary-directory warnings. Does not prove named-role discovery.
- Python `tomllib` parsing: config plus five role files passed (6 files).
- Skill creator `quick_validate.py .agents/skills/feature-delivery`: valid.
- `git diff --check`: passed; existing CRLF conversion warnings only.
- `-m pytest -q -p no:cacheprovider`: **142 passed in 11.89s**, including headless
  Textual tests. No visible terminal launch was performed for this config/docs task.
- Enforced review launched using
  `codex --sandbox read-only --ask-for-approval never --disable apps --disable plugins review --uncommitted`.
  Restricted launch failed because Codex could not initialize its user runtime
  database. Approved retry started CLI session
  `01a1a496-608a-7a63-9f2f-9c4ada02d9d9`; its runtime banner confirmed
  `approval: never`, `sandbox: read-only`. Runtime state writes are distinct from
  repository edits; user configuration was not edited.
- Independent CLI reviewer completed with no actionable defects in tracked or
  untracked changes. It reported passing Ruff lint, scoped formatter, mypy and all
  142 tests. Its default pytest capture failed because read-only mode blocked temp
  files; `-B -m pytest -q -p no:cacheprovider --capture=sys` then passed in 11.47s.
  No sandbox bypass was needed for its checks. Hosted CI and named-agent discovery
  remain unverified; standalone read-only review execution is now demonstrated.

No blocking review corrections were requested. All task acceptance criteria and
definition of done above are satisfied; this task stops here with a reviewable diff.

## Remaining limits and approval actions

The current host cannot be reconfigured by repository TOML; verify effective settings
in a new trusted project session. Native per-role read-only sandboxes are unsupported.
The standalone CLI review used enforced filesystem restrictions and completed.
No milestone was started or advanced. Human approval is required before consequential
actions, including dependencies, material architecture changes, destructive/external
writes, commits, pushes or merges. No user-level settings change is needed.
