# Milestone 8 delivery evidence — 2026-11-04

Status: implemented and verified locally on `feature/mission-replay`; human integration
approval pending. All acceptance criteria and definition of done are satisfied.
Scope: [Mission Replay and Event Reliability](../specs/008-mission-replay.md).
Existing uncommitted workflow infrastructure is preserved. No commit, push or merge
is authorized. Milestone 9 will remain a handoff only.

## Plan and definition of done

1. Core: `core/provider.py`, new `core/replay.py`, `test_replay.py` and targeted
   provider regressions. Record typed ordered events and immutable public snapshots;
   validate versioned JSON; guard mid-round tick exhaustion.
2. TUI: `tui/app.py`, new `test_tui_replay.py`. Render a coherent historical snapshot,
   pause on replay entry/exit, clamp seeks, reject live mutations, preserve demo/layout.
3. Verify deterministic traces and archive rejection, run required gates, obtain
   simulation/QA/independent review, correct blocking findings and revalidate.
4. Update specification, architecture, design, README, roadmap and NEXT to verified
   status. Stop after reporting; do not execute the next milestone.

Done means every active spec acceptance criterion has concrete evidence, blocking
reviews are resolved, documentation matches implementation, and remaining risks and
approval actions are reported. No dependencies or unrelated architecture changes.

## Architecture decisions

Named `architecture` agent `/root/m8_architecture` inspected actual code read-only.
It found no significant architectural change requiring new approval with these
scope-preserving choices:

- Keep stable roster-order dispatch, selected-AUTO TUI execution, and mission-wide
  planner exhaustion. Fix the misleading manual-first docstring, not scheduling.
- Break a fleet round when an action ends the mission, fixing the spec's tick-budget
  overrun prerequisite. A partial round is a committed history boundary.
- Add a core replay module alongside existing provider/frame types. No storage,
  service, framework, RNG-state checkpointing or historical resume.
- Capture initial state, effective mode changes, direct action boundaries, and one
  snapshot per committed fleet round, suppressing nested captures.
- Expose read-only timelines. Reconstruct a new validated timeline from versioned
  JSON; never load historical state into the live provider.
- Use explicit capacity with pre-mutation rejection instead of silent record loss.
  Minimum 2048 snapshots, increasing with configured tick budget; open-budget runs
  use the minimum. Document cumulative histories' memory cost.

## Actual agent contributions

- `/root/m8_architecture` (`architecture`): requirements, actual interfaces,
  scheduler prerequisites and ownership design; no edits or tests.
- `/root/m8_core` (`implementation`): assigned provider/replay and core test files.
- `/root/m8_tui` (`implementation`): assigned app and isolated replay UI tests.
- `/root/m8_qa` (`qa`): read-only acceptance analysis followed by final verification.
- `/root/m8_simulation` (`simulation`): independent math, RNG, deterministic trace
  and malformed archive review; exact STOP finding and revalidation.
- `/root/m8_review` (`reviewer`, fresh context): inspected actual diff/additions,
  independently ran full tests, and found the signed-seed roundtrip and contradictory
  planner-metadata cases for correction.

Native named-role invocation is available in this session and was actually used.
These subagents inherit the parent permissions; their review scope is instruction-only.
A final dedicated read-only CLI review will provide enforced filesystem isolation.

## Verification

Before implementation: `.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider`
— **142 passed in 12.72s**. Initial integrated QA: **183 passed in 19.67s**.
After STOP regressions, independent reviewer: **187 passed in 17.35s**.
Final results after all corrections: **190 passed in 17.21s** (48 cases added over
the baseline). Enforced read-only CLI reviewer independently passed all 190 in 16.92s.

## Findings and corrections

- QA found three narrow typing issues in the provider/event decoder. Core ownership
  corrected them; the entire core now passes mypy (9 modules), replacing the earlier
  four-module gate. CI formatting now includes all touched/new Python files in M8.
- Simulation review reproduced a malformed STOP archive missing its terminal event.
  The loader now requires matching terminal cause/order; four regressions cover
  missing terminal, wrong status, intervening action and false planner exhaustion
  after budget consumption. Simulation review independently confirmed the exact
  malformed archive rejects while the valid archive loads.
- Independent review found that core `GridWorld` accepts signed integer seeds while
  the archive decoder originally rejected negative seeds. The decoder/test correction
  preserves the existing core domain (mission configuration still requires nonnegative
  seeds). It also found contradictory planner metadata loading on an AUTO scan;
  a scoped transition check and regressions now reject it and prevent changes across
  manual/mode boundaries. Legitimate direct scans of AUTO drones retain the previous
  planner decision because they do not invoke the planner. The independent reviewer
  rechecked both defects and reported no remaining blocking or nonblocking findings.
- Narrow layout analysis found the replay panel originally below the viewport at
  80x24. Minimal compact sizing moved the timeline from `(43,25,34,8)` to
  `(45,14,34,8)`; at 110x42 it stays `(75,32,34,8)`. Tests check actual regions and
  the control hint, including resize while configuration is open.

No design disagreements remain: roster order, global STOP, selected-AUTO UI behavior
and viewing-only replay were preserved. No dependency or significant product
architecture change required human approval in this implementation.

## Independent experiments and UI execution

- QA: 288 mixed-mode archive roundtrips (12 seeds x 3 policies x 8 rounds), plus
  duplicate-key/type rejection and immutable array probes; all passed.
- Simulation reviewer: 30 paired strategy/seed configurations with three drones and
  47-tick budgets; exact serialized equality and roundtrips, normalized finite
  nonnegative obstacle-free beliefs, bounded entropy passed.
- Independent binary mutual-information calculation: expected
  0.5461407082172529 bits versus 0.5461407082172531 from the existing implementation
  (difference 2.22e-16). This is a correctness probe, not a performance benchmark.
- Lead PTY smoke: `.\.venv\Scripts\python.exe -m nightjar --mode gridworld` launched
  at 80x24, accepted step/scan/replay inputs (`n`, `e`, `r`), visibly emitted
  `REPLAY 3/3 / READ ONLY` and arrow/R hints, and quit with code 0 after seek,
  blocked-step, live-return and quit inputs. Headless tests provide the state
  assertions; the PTY output verifies terminal startup/input/clean exit.

## Final commands and results

Python below is `.\.venv\Scripts\python.exe`:

| Command | Actual result |
| --- | --- |
| `-m pytest -q -p no:cacheprovider` | 190 passed in 17.21s |
| `-m ruff check src tests` | Passed |
| `-m ruff format --check` with the nine paths in CI | 9 files already formatted |
| `-m mypy` | Success, all 9 core source files |
| `-m pip wheel . --no-deps --no-build-isolation --wheel-dir dist` | Built nightjar_sim-0.1.0-py3-none-any.whl, 47,338 bytes |
| `-m nightjar --help` | Passed |
| Isolated wheel import/archive/CSS probe (`-I -c`) | Imported replay/provider from built wheel, round-tripped initial history and verified CSS member |
| `git diff --check` | Passed, CRLF conversion warnings only |

The final formatter paths are `src/nightjar/core/{sensor,provider,replay}.py`,
`src/nightjar/tui/app.py`, and `tests/{test_world,test_sensor,test_demo,test_replay,test_tui_replay}.py`.
CI uses an isolated wheel build; local validation used the installed build backend.
The restricted wheel attempt hit temp-directory permissions; the approved retry
passed. No new dependency was introduced by this milestone.

Dedicated enforced filesystem review:

```powershell
codex --sandbox read-only --ask-for-approval never --disable apps --disable plugins review --uncommitted
```

The restricted launch could not initialize Codex's runtime database; the approved
retry launched session `01a1a6e8-b8c8-7193-98eb-5a585df76a22`, whose runtime banner
confirmed read-only sandbox and no escalation. It inspected tracked/untracked changes,
ran `-B -m pytest -q -s -p no:cacheprovider` (190 passed in 16.92s), Ruff checks and
`-B -m mypy --no-incremental --cache-dir=nul`; all passed. Its final report found no
actionable defects. An optional GitHub MCP credential warning did not affect local
review; no connector writes were used. User-level settings were not changed.

## Changed files for Milestone 8

- `src/nightjar/core/replay.py` (new): immutable records, deterministic JSON,
  validation and clamped viewing.
- `src/nightjar/core/provider.py`: committed capture, capacity preflight, typed
  actions and budget guard; preserve scheduler/planner policy.
- `src/nightjar/tui/app.py`: coherent historical rendering, replay controls and
  mutation guards, capacity feedback, compact screen-class updates.
- `src/nightjar/tui/nightjar.tcss`: minimal compact sizing while preserving desktop.
- `tests/test_replay.py` (new): core determinism, capacity, state/JSON/terminal/seed
  regressions and archive immutability.
- `tests/test_tui_replay.py` (new): keyboard/telemetry/state isolation, seek limits,
  history feedback and actual viewport/resize coverage.
- `pyproject.toml`: expand the type gate to the complete core.
- `.github/workflows/test.yml`: expand incremental formatter coverage to M8 files.
- `README.md`: replay controls/API/capacity/limits and current status.
- `docs/DESIGN.md`: real mission replay and compact-terminal behavior.
- `docs/ARCHITECTURE.md`: actual event/snapshot contracts, loader and memory bounds.
- `docs/ROADMAP.md`: locally verified M8, M9 next and unstarted.
- `docs/WORKFLOW.md`: actual named-role discovery/invocation evidence.
- `docs/specs/008-mission-replay.md`: resolved design and verified completion.
- `NEXT.md`: M9 handoff criteria, without execution authorization.
- `docs/reports/008-mission-replay.md` (new): this evidence and limitation record.

Earlier uncommitted workflow files/settings/tests were preserved; their inventory is
in the bootstrap/autonomy reports. No unrelated production module was refactored.

## Remaining limitations and approval state

Replay is in-memory public viewing state, not a resumable checkpoint or automatic
file persistence feature. Full snapshots/cumulative histories trade simplicity for
memory/JSON size; capacity can stop mutations before the tick budget when many
zero-tick changes occur. The TUI still executes only selected AUTO drones; one planner
STOP still ends the mission. Demo heatmaps/routes/replay remain scripted and separate.
Planner telemetry is checked against recorded actions but does not prove optimal
planning or recompute random decisions. No benchmark claims are made.

Hosted GitHub Actions and clean-machine installation were not run; local packaging,
CLI/PTY launch, headless UI tests and all configured gates passed. Native reviewers
inherit writable parent permissions unless separately launched read-only as above.
No unresolved blocking findings remain. No dependencies or significant design changes
need approval for this delivery. Commits, pushes, merges or publication still require
human authorization. M9 was not started. This task stops at the verified result.
