# Milestone 9 delivery evidence — 2026-11-04

Status: local implementation and verification complete on `feature/reproducible-benchmarks`;
owner integration/publication approval pending. No public release was performed.
Spec: [009-benchmarking-release](../specs/009-benchmarking-release.md).
Earlier uncommitted workflow and replay changes are preserved. No integration or
publication is authorized. The fleet UI handoff gap is explicitly outside this task.

## Plan and acceptance

- Add only `src/nightjar/benchmark.py` and `tests/test_benchmark.py` for executable
  behavior: an offline public-API adapter, typed config/metrics, stable JSON and CLI.
- Lead owns methods/measured artifact, release checklist/changelog, README and
  architecture/roadmap/NEXT/spec/report updates; CI covers only small benchmark tests.
- Verify spec criteria through implementation tests, simulation review, QA and fresh
  independent review, correcting blockers and revalidating affected checks.
- Definition of done is the active spec's acceptance/done checklist; stop at local
  release preparation, without publishing or automatically starting another task.

## Actual agent contributions

- `/root/m9_architecture` (`architecture`): read-only requirements/code review;
  recommended standalone CLI, equal-ceiling fleet protocol, bounded workload and
  honest metrics. No significant architecture approval needed; no edits/tests.
- `/root/m9_implementation` (`implementation`): owned benchmark module/tests;
  25 initial cases passed, lint/types passed. Changed output handling so failed runs
  do not leave empty report files; no simulator/TUI changes.
- `/root/m9_qa` (`qa`): prepared acceptance matrix before interruption; final results
  were not received. Lead executed the complete final QA checklist below instead.
- `/root/m9_simulation` (`simulation`): independently matched public-state fixtures
  and retained example, all means/sample counts, deterministic JSON and source hash;
  87 targeted cases passed after a temp-directory retry. It reported no blocking or
  nonblocking methodological defect. Its final message then hit a usage limit;
  the preceding concrete findings are preserved, not represented as a completed final turn.
- `/root/m9_final_review` (`reviewer`, fresh context after resumption): independently
  reviewed code/docs/raw results and lint/types; no blocking implementation finding.
  Flagged stale handoff docs and suggested a blocked/unreachable coverage fixture.

## Findings and corrections

- Reconciled NEXT, roadmap and spec with actual M9 completion instead of leaving
  them marked not started/in progress. Corrected Milestone 7's status to acknowledge
  the hybrid TUI gap, and made that one explicit next task without starting it.
- Added a hand-calculated metric regression: a 5x3 map split by three wall cells,
  one blocked attempt, one successful move and one scan. Expected ticks 3, attempts 2,
  successes/blocks/scans 1 each, visited 2, traversable 12, coverage 1/6 even though
  nine traversable cells are unreachable. This passed; benchmark suite is now 26 cases.
- Removed a duplicated empty architecture heading left by the interrupted docs edit.
- Kept single-drone defaults and documented that optional all-AUTO fleet benchmarking
  is not the missing hybrid TUI. No new sensing/planner/scheduler semantics were introduced.

## Initial evidence

Baseline `.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider`:
**190 passed in 24.52s**. Branch creation required the normal sandbox retry; no work
was discarded. User confirmed replay/manual testing matched currently implemented
behavior. This does not constitute acceptance of the missing fleet handoff feature.

## Final executed checks

Python commands use `.\.venv\Scripts\python.exe`:

| Command/check | Actual result |
| --- | --- |
| `-m pytest -q -p no:cacheprovider` | 216 passed in 22.57s after final regression |
| `-m ruff check src tests` | Passed |
| `-m ruff format --check` with the 11 paths in CI | 11 files already formatted before final fixture; touched test rechecked afterward |
| `-m mypy` | Success, 10 source files (core plus benchmark) |
| `-m nightjar.benchmark --help` | Passed |
| Regenerate default report in memory and compare retained JSON bytes | Exactly matched nine runs, software metadata and current source fingerprint |
| `-m pip wheel . --no-deps --no-build-isolation --wheel-dir dist` | Built nightjar_sim-0.1.0-py3-none-any.whl, 51,244 bytes |
| `-m pip install --no-deps --target build/release-check/site dist/nightjar_sim-0.1.0-py3-none-any.whl` | Passed after approved temp-directory retry |
| `-I -c` installed-wheel probe | Asserted import path is the isolated target; three-policy two-tick benchmark, source fingerprint and packaged CSS passed |
| `-m nightjar --mode gridworld` in PTY | Rendered 80x24 mission, accepted step/scan/replay/quit input, exit 0 |

Installed-wheel check reused declared dependencies from the existing virtual environment;
it is not a clean-machine or fully fresh-dependency installation. The first restricted
import probe could not read the installed target and fell back to editable source;
the path assertion caught this. An approved retry explicitly verified the target path.

The restricted full test run had 213 passing cases and two `tmp_path` setup errors
from Windows temp-directory access; the approved retry passed all 215 then-existing
cases, and all 216 after the final fixture. The independent reviewer saw the same
setup restriction, not test assertion failures. Its nonstandard mypy cache override
failed; the documented normal mypy command passed. No tool failure is counted as a pass.

Final filesystem-enforced review used
`codex --sandbox read-only --ask-for-approval never --disable apps --disable plugins review --uncommitted`
(execution session 42331). It found no actionable correctness defects and passed all
11 formatter targets. Its test attempt had 214 passing cases and two temp-file setup
errors under read-only restrictions; the lead's approved full run passed all 216.
An optional GitHub MCP missing-token warning did not affect local review; no connector
writes or publication were used. Final `git diff --check` passed with CRLF warnings.

## Measured artifact

`docs/benchmarks/compact-open-3seeds.json` was generated by:

```powershell
.\.venv\Scripts\python.exe -m nightjar.benchmark --seeds 0 1 2 --ticks 50 --drones 1 --map compact --scenario open_field --sensor standard --output docs/benchmarks/compact-open-3seeds.json
```

Python 3.13.1, NumPy 2.5.4, Nightjar 0.1.0. The methods document records descriptive
means with n=3 per policy; no statistical significance or accuracy claim is made.
Simulation review matched an independent seed-3/two-drone/seven-tick public-state
fixture: all three policies obeyed the budget and action accounting. INFORMATION GAIN
used all seven ticks moving, with no scans and unchanged entropy; this limitation is
documented rather than hidden by a favorable ranking.

## Changed files in this milestone

- `src/nightjar/benchmark.py`, `tests/test_benchmark.py`: runner, metrics, CLI and
  deterministic/edge/file-preservation/import regressions.
- `docs/benchmarks/compact-open-3seeds.json`, `docs/BENCHMARKS.md`: actual raw data,
  definitions, commands, measured summary and limitations.
- `docs/RELEASE.md`, `CHANGELOG.md`: local release checks and pending owner decisions.
- `pyproject.toml`, `.github/workflows/test.yml`: benchmark type/format/CLI-help gates;
  expensive experiments stay out of CI.
- `README.md`, `docs/ARCHITECTURE.md`: user command and actual adapter boundaries.
- `docs/specs/009-benchmarking-release.md`, this report: acceptance, decisions/evidence.
- `docs/ROADMAP.md`, `NEXT.md`: verified local status and hybrid-control follow-up.

Earlier workflow/replay work is preserved and remains uncommitted. No runtime
dependency, license, user-level setting, simulator or TUI behavior changed in M9.

## Remaining limits and approval actions

No unresolved blocking implementation finding remains. Release preparation is local;
hosted CI, other operating systems and clean-machine installs are unverified. Public
release needs owner license choice, accumulated-diff acceptance and explicit approval
for integration/publication. Hybrid manual-one/others-AUTO TUI handoff remains missing
and is now NEXT's sole product follow-up. Current global STOP, shared total budget,
snapshot memory costs and synthetic sensing assumptions remain limitations of the
measured system. This task stops after verification and does not implement that follow-up.
