# Fleet coordination delivery ? 2026-11-05

Status: implemented and locally verified on `feature/fleet-coordination`.
Spec: [011](../specs/011-fleet-coordination.md).

Owner explicitly selected reduced overlapping AUTO searches after confirming the
hybrid manual tests passed. Preserve all preceding uncommitted work; the new feature
branch carries it forward without committing/pushing/merging.

## Plan and acceptance

Use public fleet coverage and soft round-local target preferences, not sector
partitions or persistent allocation. Preserve tick/action/replay/control invariants.
Acceptance and definition of done are specified in the linked spec.

## Agent contributions

- `/root/coordination_architecture` (`architecture`, read-only instructions): inspected
  current planners/provider/replay/benchmarks. Scans were already shared; coverage
  was drone-local. Recommended union visited plus optional immutable target claims,
  candidate fallback, no archive schema change. No tests or edits performed.
- `/root/coordination_core` (`implementation`): owns planning.py/provider.py and new
  tests/test_coordination.py. No concurrent production writers.
- `/root/coordination_tui_tests` (`implementation`): owns only new
  tests/test_tui_coordination.py for normal/narrow real-policy integration.
- Lead owns spec/NEXT/docs, benchmark protocol metadata/tests and CI allowlist.

Native read-only specialists inherit session permissions; instruction-only review
is not described as sandbox isolation. Final CLI review uses enforced read-only
settings where supported. No user-level settings or dependencies changed.

## Baseline

`.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider` with temporary-file
access: **237 passed in 23.62s** before implementation. Lead saved four public-history
trace fixtures before changes (all three single-drone policies and three-drone
RANDOM, 8x6 Open seed17 budget35) for exact final comparison.

## Verification and independent contributions

- Core implementation: **29 new coordination cases**, **104 passed in 1.04s** across
  coordination/planning/provider/replay/hybrid; Ruff/check/format passed.
- TUI implementation: **4 passed in 5.80s**, real FRONTIER/INFORMATION GAIN at
  110x42 and 80x24, public-input recording without replacing planner actions.
- `/root/coordination_simulation` (`simulation`, read-only instructions): **168 passed
  in 1.15s** across coordination/planning/belief/sensor/provider/world/replay/hybrid.
  Independent 27 repeated trace pairs covered three policies, open/obstacle/corridor
  geometries, budgets1/5/21, three drones or ten in a corridor. Verified exact JSON,
  valid archive reload, finite normalized nonnegative belief, zero obstacle mass,
  entropy bounds, positions/collisions, budgets/progress/terminal no-ops. Mixed manual
  blocked movement/scanning, parked IDLE and history-full rejection probes passed.
  Hand-computed perfect binary sensor gain1bit and uninformative gain0 passed.
- `/root/coordination_review` (`reviewer`, fresh context, read-only instructions): no
  blocking or nonblocking correctness findings. Coordination/replay **69 passed**;
  planning/provider/TUI **28 passed**. Expanded benchmark attempt had **93 passes
  and two temp-directory setup errors** (not represented as a passing full gate).
- `/root/coordination_qa` (`qa`, fresh context, read-only instructions): **102 passed
  in 16.54s** for coordination/TUI coordination/hybrid TUI/replay/controller/core
  replay; one nonfatal pytest cache permission warning. Separate planning/provider/
  world/TUI check **64 passed in 12.07s** without warnings. No blockers.

## Final lead gates

- `.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider` with temp access:
  **270 passed in 31.09s**. This includes all 237 preceding tests plus 33 new cases.
- `python -m ruff check src tests`: passed. CI formatter check: **19 files already
  formatted**, expanded to planning and both new tests. `python -m mypy`: passed,
  **12 source files**. `git diff --check`: passed (Git line-ending notices only).
- Replayed all four lead-saved pre-change public-history traces: byte-identical.
  Core tests additionally pin four pre-change archive hashes for a separate small
  fixture (seed31,7x4,24ticks), preserving all single-drone policies and RANDOM3.
- Regenerated the one-drone benchmark artifact; asserted raw runs, summaries and
  configuration identical. Only explicit coordination protocol metadata and source
  fingerprint changed. The documented seed3/two-drone/seven-tick IG example still
  consumes seven movement ticks, zero scans, zero entropy reduction.
- `python -m pip wheel . --no-deps --no-build-isolation --wheel-dir dist`: passed.
  Installed with `--no-deps --no-compile --target build/coordination-wheel-check`;
  imported the installed coordinated core/TUI and verified packaged styles. Existing
  declared dependencies reused; not a fresh-machine/cross-platform guarantee.
- `python -m nightjar --help`: passed. Three-drone offline CLI smoke
  `python -m nightjar.benchmark --seeds 0 --ticks 5 --drones 3`: passed, including
  partial final rounds and explicit coordination metadata.
- Actual PTY `python -m nightjar --mode gridworld` at80x24 launched, displayed
  MANUAL01 plus AUTO02/03 actions, accepted run/pause/step/path/replay/quit input,
  and exited0. Detailed state assertions are from headless tests; this smoke does
  not substitute for owner manual acceptance of coordination.

## Reproducible focused evidence

`tests/test_coordination.py` runs 7x5 seeded maps with six obstacles and three AUTO
agents, recording actual planner inputs/decisions and comparing the same public
state without claims. FRONTIER seed1 at tick29 substitutes target(5,4) for already
claimed(5,3); INFORMATION GAIN seed0 at tick20 substitutes(4,1) for claimed(1,4).
Both keep an otherwise valid action. These examples establish target avoidance in
those fixtures, not improved coverage/entropy or general efficiency.

## Changed files for this milestone

- `core/planning.py`: immutable optional claims and eligible-candidate preference.
- `core/provider.py`: shared public visited input and local successful-MOVE claims.
- `benchmark.py`, `tests/test_benchmark.py`, raw benchmark example: protocol label
  and source provenance; no new scoring metric or performance claim.
- New `tests/test_coordination.py`, `tests/test_tui_coordination.py`: deterministic
  policy/controller/UI fixtures and invariant coverage.
- `.github/workflows/test.yml`: expanded existing format gate; no dependencies.
- README, CHANGELOG, architecture/design/benchmark/release/manual guides, roadmap,
  NEXT, spec011 and this report: actual behavior, evidence and manual handoff.
- All preceding hybrid uncommitted implementation/docs/tests remain preserved;
  they are not newly attributed to this milestone.

## Limitations and handoff

Claims reset each round, so there is no persistent allocation or fixed sectors.
Paths and sensor footprints may overlap; claimed targets can be reused on fallback.
Coverage means physical visitation, not sensor coverage. RANDOM is intentionally
uncoordinated beyond existing shared scans/collisions. A single planner STOP still
ends the mission. Replay remains viewing-only without file save/load or resume.
All sensing/objectives remain synthetic, and the separate demo remains scripted.

Local acceptance criteria/definition of done are met.
Owner manual coordination acceptance is pending; prior owner acceptance applies to
hybrid controls before this change. No commit/push/merge/publication performed.

## Enforced read-only final review

Executed `codex --sandbox read-only --ask-for-approval never --disable apps
--disable plugins review --uncommitted` successfully. The independent CLI reported
no actionable regressions. Its check ran **268 tests passing**, with two benchmark
tests blocked at setup by read-only temporary-file restrictions; those tests passed
in the lead's full270-test run with temporary-file access. The optional GitHub MCP
server lacked GITHUB_PAT_TOKEN, but local review completed; no external writes used.
This review covered the complete uncommitted diff, including preserved hybrid work.
No blocking findings remain. NEXT hands off coordination manual acceptance only.
