# Milestone 9: Reproducible Benchmarking and Release Preparation

## Objective

Compare the existing synthetic search policies through one offline command and
prepare honest release documentation. Produce reviewable local artifacts, not an
automatic public release.

## Current implementation context

The [architecture](../ARCHITECTURE.md) describes a deterministic simulation with
public frames, shared beliefs, seeded sensor/planner streams and retained replay.
`fleet_round()` dispatches in roster order with a global tick budget and mission-wide
planner exhaustion. The TUI still executes selected AUTO only; the user's intended
manual-one/other-drones-AUTO handoff is an explicit remaining gap, not benchmark work.
At task start there was no benchmark command or measured comparison. Version remains
0.1.0; no repository license file was found during inspection.

## Functional requirements

1. Add `python -m nightjar.benchmark`, with no Textual import or new dependency.
   Default: Compact, Open field, one drone, Standard sensor, seeds 0/1/2 and 50 ticks.
   Compare RANDOM, FRONTIER and INFORMATION GAIN in fixed order for each seed.
2. Allow existing map/scenario/sensor presets, 1–10 drones, 1–32 distinct nonnegative
   seeds and 1–1000 ticks per run. Every policy receives identical settings except
   strategy. Reject invalid inputs before starting the matrix.
3. For each run, set all drones AUTO in roster order and call the existing fleet
   round API until actual terminal status. A global budget is shared, not per drone;
   early planner exhaustion is valid. Detect ACTIVE/no-progress rather than hang.
   Keep replay capture unchanged and release each simulation after extracting metrics.
4. Record budget, actual ticks, terminal reason, rounds, scans, movement attempts,
   successful moves, blocked attempts, unique visited/traversable cells, coverage,
   initial/final entropy and signed entropy reduction (initial minus final). Coverage
   includes spawn cells and all non-obstacle cells, including unreachable cells.
5. Emit versioned, stable JSON with raw rows and clearly defined descriptive means
   and sample counts. Include full configuration/protocol, Python/NumPy/app versions
   and deterministic source fingerprint. No timing, timestamp, machine path or hidden
   objective-derived scoring. Identical sources/environment/arguments reproduce JSON.
6. Default stdout; optional `--output PATH` exclusively creates a local report and
   refuses an existing file. CLI failures are clear and nonzero. Do not overwrite user
   data or introduce network calls.
7. Run a bounded real example matrix and retain its raw JSON alongside methods,
   commands, results and limitations. No claims of significance, discovery, optimality
   or hardware performance from a small synthetic example.
8. Prepare a changelog and release checklist: local packaging/install/TUI checks,
   known gaps, owner decisions (including license) and approval before publication.

## Architectural constraints

Follow ../../AGENTS.md and ../DESIGN.md. The benchmark is an adapter around public
core APIs, not a new simulator or planner. No TUI/core semantics changes, replay
disabling, frameworks, new dependencies, CI Monte Carlo job or external publication.

## Acceptance criteria and required tests

- Deterministic JSON and stable row ordering across repeated runs; equal configuration
  and budgets for every strategy/seed; meaningful multiple-drone and early-STOP cases.
- Independently calculated metric fixtures and actual public state agree; ticks equal
  movement attempts plus scans and remain within budget.
- Duplicate/invalid/excessive inputs fail; active/no-progress fails instead of hanging.
- CLI help, stdout and exclusive output work; prior file bytes remain unchanged;
  benchmark execution does not import Textual/Rich or inspect the hidden objective.
- Small CI tests, full pytest, lint/format/type gates, wheel/import/install and TUI
  smoke checks pass. Independent math/protocol review, QA and actual-diff review
  findings are resolved, with exact commands/evidence in the delivery report.
- Methods and measured example match the final code; release readiness is accurately
  described as local preparation with public release pending owner decisions/approval.

## Definition of done and stopping conditions

All criteria verified, blocking findings resolved, docs and NEXT reconciled with final
code, limitations/approval actions reported. Stop after local delivery; do not commit,
push, merge, publish, choose a license or implement the fleet-control follow-up.

## Non-goals

Hybrid fleet UI handoff, sector assignment, new sensing/discovery mechanics, success
scoring, planner optimization, statistically powered performance claims, disk replay
UI, package-index hosting, websites or actual drone integrations.

## Completion status

Implemented and verified locally; publication is not performed. Architecture review
found no significant architecture decision requiring approval for this scoped adapter.
The measured nine-run artifact reproduces exactly, the full suite and local gates
pass, and independent review found no blocking implementation issues. See
[delivery evidence](../reports/009-benchmarking-release.md) for exact commands, findings,
environment limitations and owner approvals still required.
