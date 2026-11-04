# Nightjar | Repository Instructions for Coding Agents

This file is the persistent source of truth for Codex and other coding agents working in this repository. **Read it before any task**, together with `NEXT.md` and `docs/DESIGN.md`. Keep it accurate when implementation decisions change. Do not rewrite it wholesale or silently expand scope.

## 1. Product goal
Nightjar is a **local-first, Python-only, simulation-only** research/portfolio application. Users run small, hypothetical 2D autonomous search scenarios through a restrained, military-inspired terminal interface. The technical substance is deterministic simulation, uncertain synthetic sensing, probabilistic inference, planning, benchmarking, and later reliable replay.

**Never** add real drone control, surveillance feeds, person tracking, actual through-wall detection, or integrations with physical sensing equipment. All points of interest and observations are synthetic.

## 2. Approved product design (preserve)
- Primary and final interface: **Textual + Rich TUI**, not React/web.
- Visual style: near-black background, dark forest-green grids and panels, subdued green foreground, restrained amber for higher probability or noteworthy observations. Minimal effects; clear typography, no unnecessary animation.
- Default world: approximately **32x16 cells**; small fixed-size maps, no zoom/pan or advanced navigation.
- Main screen: top mission/status header; central colored block-character map; right agent telemetry and belief-state panel; bottom event log and replay area; discoverable keyboard shortcut footer.
- Existing key map: Space play/pause; N single step; H heatmap; C coverage; P paths; Tab select agent; R replay; Left/Right seek when replaying; Q quit. A `?` shortcut help overlay may be added later if it improves discoverability.
- Prefer effectiveness and legibility to decorative polish. Always test narrow terminal widths without sacrificing normal desktop terminal layout.
- `docs/DESIGN.md` contains additional design details. Treat approved design as a constraint; ask before major aesthetic or workflow changes.

## 3. Scope and architecture
- **One Python application, one easy launch command**: `nightjar` after editable install, or `python -m nightjar`.
- Dependencies for MVP: Python 3.11+, Textual, Rich (transitive through Textual), NumPy, pytest. Prefer the existing package manager/build system in `pyproject.toml`.
- No FastAPI, React, TypeScript, PostgreSQL, Docker, Mesa, LangGraph, or microservices for MVP. Only suggest additions when a **specific implemented requirement** needs them and document the tradeoff before adding.
- `src/nightjar/core/`: deterministic world, sensing, inference, planning and state transitions. **Must not import Textual/Rich or depend on TUI widgets.**
- `src/nightjar/tui/`: rendering, shortcuts, screens and controls. Reads typed snapshots / invokes application services, not internal hidden simulation ground truth.
- `src/nightjar/services/` (when necessary): mission lifecycle and orchestration between core and TUI.
- `src/nightjar/storage/` (later, when needed): events/snapshots/replay. Start with simple local files if suitable; choose a database only with measured justification.
- Prefer small, explicit modules and pure functions. Avoid generic architecture/framework scaffolding before it is needed.

## 4. Modeling and correctness invariants
- Fixed random seeds must yield reproducible simulation results. Never depend on wall-clock scheduling for simulation outcomes.
- Keep hidden world/point-of-interest state separate from observations and agent beliefs. Planners must **never** receive hidden ground truth.
- Walls and bounds prevent invalid movement; the behavior for invalid actions must be explicit and tested.
- Belief arrays represent valid, normalized probability distributions; distinguish real Bayesian posterior calculations from synthetic display heatmaps.
- Separate **simulation ticks** from wall-clock/UI frame timing.
- Real benchmark claims require reproducible experiments. Never fabricate accuracy, speedups, search efficiency, or reliability numbers.
- State records should be designed for deterministic replay, but do not introduce event sourcing/storage until its milestone.
- Keep terminal UI responsive; don't run expensive computation on the UI event loop.

## 5. Agent working method (every task)
1. Read `AGENTS.md`, `NEXT.md`, `docs/DESIGN.md`, `README.md`, and relevant code/tests before modifying files.
2. Write a brief implementation plan listing the **smallest files** to touch, explicit acceptance criteria and definition of done. A short checklist is enough for a small task. Respect the current milestone.
3. Implement one vertical slice, favoring the simplest correct code. Do not refactor unrelated code.
4. Add/extend tests for new logic and deterministic edge cases.
5. Run `python -m pytest -q` and any appropriate package/import/smoke checks. Launch the Textual app if the environment supports a terminal. Report explicitly if UI execution cannot be verified.
6. Summarize changed files, tests executed, what remains mock/demo, and any known limitations.
7. Update `NEXT.md` with **one actionable next milestone** and acceptance criteria when the current milestone is complete; this is a handoff, not authorization to execute it. Never automatically start the next milestone. Update `README.md` / `docs/DESIGN.md` only if actual behavior or decisions changed.
8. Update `AGENTS.md` **only when durable architectural, workflow, design or scope rules change**. Preserve user-approved constraints. Add a short dated entry to the Decision Log rather than rewriting the file repeatedly. If there is a conflict with a new user instruction, follow the user and update this file accordingly.

## 6. Repository workflow and delegation
- `NEXT.md` points to the active spec; `docs/ROADMAP.md` records milestone status. Inspect local code rather than assuming milestone labels prove behavior.
- `docs/ARCHITECTURE.md` describes current modules; `docs/DESIGN.md` owns UI decisions; `docs/WORKFLOW.md` owns setup, gates, handoffs and reporting.
- Follow existing typed dataclasses, enums, explicit imports and small pure functions. Keep `[y, x]` arrays distinct from `(x, y)` coordinates.
- Use native subagents for bounded specialist work when useful. Small edits stay with the lead. Normal features need independent actual-diff review; high-risk math, scheduling, events and architecture need architecture analysis, simulation review and QA.
- Read-only reviewers must not edit implementation. Assign file ownership to writers; avoid concurrent shared-file edits. Limit concurrency to three specialists or the client's lower limit. Only the lead delegates.
- Use `.agents/skills/feature-delivery/` for substantial delivery and `simulation-verification/` for numerical/deterministic checks. Roles live in `.codex/agents/`.
- Use feature branches for substantial changes. Preserve existing work. Obtain human approval for material architecture/product/semantics decisions and before commits, pushes or merges; no automatic destructive Git operations.
- Record substantial delivery evidence in a PR or concise `docs/reports/` report, including actual agent invocations, findings, corrections, commands/results and unresolved criteria.
- Routine repository edits, tests, documentation and bounded independent analysis/review are authorized within the task; do not ask repeatedly for those operations or each delegation. Approval already granted for a specific action persists within its scope.
- Ask before adding dependencies, significant architecture changes, destructive operations or external writes, as well as the Git integration actions above. Sandbox/automatic-review approval alone is not human authorization for these actions.
- Iterate on implementation, tests and blocking findings within approved scope. Stop and report when acceptance criteria and definition of done are met, a blocker needs human intervention, or the next change would exceed scope. Do not broaden scope to fix unrelated findings.
- Read-only provisional planning of the next milestone may run during implementation. Label it provisional, keep it out of the active implementation, and reconcile it with final integrated code before execution; execution still needs a new task authorization.

## 7. Definition of done
- The project installs and starts with documented commands where dependencies are available.
- New behavior has tests; regressions are not introduced.
- Real features and mock/demo features are clearly distinguished.
- `NEXT.md` accurately describes what Codex should do next.
- The military-style TUI design and Python-only architecture are preserved.

## Decision Log
- 2026-11-03: Clarified task-scoped autonomy, explicit acceptance/stopping criteria, approval for dependencies and consequential actions, and provisional planning without automatic milestone execution. Use a read-only parent session for enforced filesystem review; native subagents inherit permissions.
- 2026-11-03: Adopted repository-local native Codex specialists, delivery/verification skills, specifications and incremental CI gates. Human approval is required before commit, push or merge. Milestone instructions now live in NEXT/specs rather than global rules.
- 2026-10-24: Approved a small-scale, local-first Python/Textual terminal product with understated military styling. No web frontend, zoom/pan, advanced map navigation, separate FastAPI server, or unnecessary infrastructure for MVP. Keep potential systems expansion optional and evidence-driven.
