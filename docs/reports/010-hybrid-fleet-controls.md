# Hybrid fleet control delivery — 2026-11-04

Status: implemented and locally verified on `feature/hybrid-fleet-controls`.
Spec: [010-hybrid-fleet-controls](../specs/010-hybrid-fleet-controls.md).

Plan: atomic provider mode helper; framework-independent serialized async controller;
cached-state TUI integration; deterministic concurrency/replay/UI tests; simulation,
QA and independent review; docs and one NEXT handoff. Stop at verified local changes,
without commit, push, merge, publication or a new product task.

Architecture analysis `/root/hybrid_architecture` inspected actual code read-only.
It recommended preserving core/benchmark rules, existing MANUAL/IDLE launch options,
global Space/N behavior, explicit IDLE reactivation, and replay selection restoration.
Multi-drone planning can be expensive, so the optional services layer is used for one
small serialized controller and off-event-loop core calls, not a generic framework.
The user explicitly authorized the intended hybrid control workflow in NEXT.

Acceptance and definition of done are the active spec's checklist. Commands, agent
contributions, corrections and final evidence will be recorded here.

## Baseline and implementation ownership

- Baseline `.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider` with
  approved temporary-file access: **216 passed in 23.40s**. Restricted overlap had
  two known pytest temp-directory setup errors and one transient empty preflight
  render assertion; the approved full baseline passed. No baseline failure is
  represented as a passing check.
- `/root/hybrid_core` (`implementation`): provider helper, new service/controller
  package and `tests/test_hybrid.py` only.
- `/root/hybrid_tui` (`implementation`): app integration and existing/new TUI tests.
- `/root/hybrid_qa` (`qa`): read-only acceptance/concurrency analysis and final checks.
- Executor Future + shielding was selected over a shielded `to_thread` Task so loop
  shutdown/task cancellation cannot release the lock while a real thread still runs.
  This is a routine implementation refinement of the approved off-loop controller.

## Early findings and corrections

- QA found expected manual denials on parked/AUTO drones would pause healthy
  background drones under a generic ValueError handler. Added specific
  `ControlDeniedError`; the TUI reports it without stopping other AUTO drones.
- Review of queued replay transitions identified that cached early guards could
  drop input after a pending replay exit, and drop arrows after pending entry.
  UI intents are now ordered and the controller checks replay at execution time;
  seek/selection requests queue behind the replay barrier.
- Existing tests assumed N moved MANUAL implicitly and selection changed no modes.
  Those expectations are updated to the requested fleet semantics; WASD collision,
  budget, sensor, history and scripted demo checks remain.
- Provisional QA: 11 core/controller tests passed in 0.48s, 12-module types passed,
  and an independent delayed-planner probe passed eight repeated owner cancellations,
  three cancelled waiters, surviving select/scan FIFO, stable pre-commit caches and
  valid archive reload. Capacity-full initialization and parked denials remained atomic.

## Final specialist verification

- `/root/hybrid_final_review` (`reviewer`), instruction-only read-only: actual diff
  reviewed; no blockers found. Controller/hybrid TUI suite: **19 passed in 3.37s**.
- `/root/hybrid_final_simulation` (`simulation`), instruction-only read-only:
  **130 passed in 0.71s** across hybrid/belief/sensor/planning/world/replay tests.
  An independent public-API probe ran 18 repeated trace pairs (three policies,
  budgets 1/2/3/4/7/20), checking identical JSON, valid normalized belief, obstacle
  mass, collision avoidance, budget caps, archive reload and replay isolation.
- `/root/hybrid_final_qa` (`qa`), instruction-only read-only: all three TUI suites
  **39 passed in 22.36s**. Normal 110x42 and narrow 80x24 behavior, delayed-planner
  responsiveness, timer coalescing, queued input, parking, replay and demo covered.
  Independent 80x24 MANUAL/IDLE preflight rendering probe passed.
- Enforced read-only CLI review ran with `codex --sandbox read-only
  --ask-for-approval never --disable apps --disable plugins review --uncommitted`.
  It found a P2 queued Space/R/Space replay-exit resume regression. Assigned
  `/root/hybrid_queue_fix` (`implementation`) only app.py/test_tui_hybrid.py for
  correction and regression coverage. Its restricted full test run had 233 passes
  and two temp-directory setup errors; this is not a passing full-suite result.
  Optional GitHub MCP startup lacked GITHUB_PAT_TOKEN; local review still completed.

## Executed lead checks

- Full pytest before final queued-input correction: **235 passed in 24.30s** using
  `.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider` with temporary-file
  access. Restricted run had 233 passes and two WinError 5 temp fixture errors.
- `python -m ruff check src tests`: passed. CI formatter allowlist: **16 files
  already formatted**. `python -m mypy`: **12 source files**, no issues.
- `python -m pip wheel . --no-deps --no-build-isolation --wheel-dir dist`: passed.
  Installed that wheel into `build/hybrid-wheel-check` with `--no-deps --no-compile`;
  verified controller and TUI imports from that installed location. Restricted pip
  temp access failed first; approved retry passed. Existing declared dependencies
  were reused; this is not a fresh-machine or cross-platform install guarantee.
- Both `python -m nightjar --help` and `python -m nightjar.benchmark --help`: passed.
- Actual PTY `python -m nightjar --mode gridworld` launched at 80x24, displayed
  MANUAL 01 while GHOST/VIPER AUTO actions advanced ticks, accepted pause/selection/
  movement/replay/quit inputs and exited 0. Detailed state assertions come from
  headless tests; PTY smoke is not owner manual acceptance.
- Regenerated the committed small benchmark through the public benchmark API.
  Asserted every field unchanged except `software.source_sha256`; raw runs,
  summaries, configuration, protocol and software versions are identical.

## Changed files and limitations

- `core/provider.py`: opt-in atomic control policy; direct simulation APIs unchanged.
- New `services/__init__.py` and `services/hybrid.py`: serialized background execution,
  immutable committed caches, control ownership and replay barriers.
- `tui/app.py`, `tui/mission_screens.py`: fleet controls/queued intent integration and
  configuration/preflight copy; no layout redesign.
- New `tests/test_hybrid.py`, `tests/test_tui_hybrid.py`; existing `test_tui.py` and
  `test_tui_replay.py`: deterministic, concurrency and UI coverage.
- `pyproject.toml`, `.github/workflows/test.yml`: include service types and new tests
  in existing gates; no dependency additions.
- README, CHANGELOG, architecture/design/benchmark/release/roadmap docs, NEXT, this
  report/spec and the raw benchmark fingerprint reflect the implemented behavior.

All sensing/objectives remain synthetic; the separate demo remains scripted.
No sector assignment, per-drone exhaustion, target confirmation, historical resume,
file save/load UI or new dependency was added. A planner STOP remains mission-wide.
Pause permits an in-flight round to finish. Reproducibility requires the same ordered
commands; wall-clock human input determines that order. Snapshot history has bounded
capacity and increasing memory cost. Owner manual acceptance remains pending.
No commit, push, merge, user-level configuration change or publication performed.

## Final correction and completion

`/root/hybrid_queue_fix` added a monotonic Space/N/R request revision so stale
callbacks cannot clear newer intent, and preserved queued intent across replay timer
callbacks. Two regression tests cover Space/R/Space after replay entry and an older
no-AUTO request followed by activation/new resume. Affected TUI suite: **41 passed
in 20.99s**. Ruff and formatter passed. The independent reviewer inspected the actual
correction and found no new blocker.

Final lead full suite after the correction: **237 passed in 23.57s**.
Final Ruff passed, formatter **16 files unchanged**, mypy **12 files passed** and
`git diff --check` passed. Rebuilt the final wheel successfully after this correction.
The earlier 235-test result predates the two added regression cases.

Acceptance criteria and local definition of done are satisfied. NEXT now hands off
owner manual acceptance/integration review; that task was not started automatically.
Human approval remains required for commit, push, merge, licensing and publication.

Final independent correction validation by `/root/hybrid_final_review`: **29 passed
in 10.81s** (controller/hybrid TUI/replay). No blockers. The enforced CLI finding
was corrected and independently rechecked natively; a second enforced CLI run was
not claimed. Final wheel installed in `build/hybrid-final-wheel-check`; imported
its controller/corrected TUI and verified packaged Textual styles successfully.

## Owner manual acceptance

2026-11-05: Owner reported running the supplied manual tests and that all looked
good. Manual acceptance is passed by owner report; no blocking issue was reported.
The owner requested the next development milestone. Existing roadmap has no further
specified feature, so NEXT records a product-direction selection before new code.
Integration approval remains separate; no commit, push or merge was performed.
