# Mission presentation delivery - 2026-11-05

Status: implemented and locally verified on `feature/mission-presentation`.
Spec: [012](../specs/012-mission-presentation.md).

Owner approved all proposed presentation directions, future planning updates and
immediate development. Requested faster UI delivery, focused checking and no
routine approval pauses. Lead updated NEXT/ROADMAP/DESIGN and scoped the first
presentation slice before implementation. No new dependency or simulation math.

## Plan and agents

- `/root/presentation_architecture` (`architecture`, read-only instructions): bounded
  interface analysis; public frame scenario/geometry and snapshot evidence suffice;
  latest decision has no owner, so label fleet intent honestly; no archive schema
  change. No edits or tests.
- `/root/presentation_scenario` (`implementation`): core/scenarios.py, core/mission.py,
  mission_screens.py and facility tests only.
- `/root/presentation_map` (`implementation`): map_widget.py and map rendering tests.
- `/root/presentation_app` (`implementation`): app.py, presentation.py, nightjar.tcss
  and focused headless summary/presentation tests.
- Lead: specs, roadmap/design/NEXT/docs, CI formatter and benchmark source provenance.

Three writers have disjoint ownership. Native read-only specialists inherit session
permissions and are instruction-only; separate read-only review is recorded honestly.

## Verification approach

Prior delivery baseline:270 tests passed. Do not rerun unchanged numerical sweeps.
Run targeted new checks, one full suite, existing lint/format/types and a bounded
actual-diff review. New scenario connectivity/spawns and historical presentation
must be tested; pause/control/replay regressions remain unacceptable.

## Results and handoff

Pending implementation. Roadmap13 comparison and14 demo/story are planned; objective
confirmation rules remain separate from current belief display. No invented user
manual acceptance, new dependency, commit/push/merge/publication.

## Initial verification and corrections

- Scenario/mission targeted tests:38passed2.87s. Map presentation:8passed0.39s.
  App presentation:4passed2.82s, including110x42/80x24 and replay/terminal summary.
- Full suite once after integration: **294 passed in33.29s** using
  `.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider` with temp access.
- Ruffcheck passed; incremental formatter27files passed; mypy13core/service/benchmark
  sourcefiles passed. Existing nine-run raw benchmark metrics/protocol unchanged;
  source fingerprint regenerated to include core/scenarios.py.
- Lead corrected new-string encoding corruption in progress bars via implementation
  follow-up; filled/empty glyphs now differ and no accidental '?' placeholders remain.
- Bounded independent review used installed Codex CLI with enforced read-only sandbox,
  approvalnever, apps/pluginsdisabled, exec--ephemeral and a code-only prompt (no
  duplicate test sweep). Found P2 legend secondline clipped due inherited top padding.
  Actual80x24 terminal smoke also exposed focusline wrapping/map compression. App
  agent assigned focused responsive sizing/copy correction and affected tests only.
- Actual PTY facility Compact mission launched; E scan/B summary and Q close/Q quit
  worked and exited0. Summary showed actual public statistics and no confirmation.
  Fullscreen rendered SVG previews at build/presentation-preview/{mission,summary}.svg;
  generated artifacts are ignored, not production dependencies or committed assets.

Final responsive correction verification completed. Optional GitHub MCP in CLI had
missing GITHUB_PAT_TOKEN; local review completed without external writes.

## Responsive correction and completion

The correction uses shorter non-wrapping focus/legend text and GridWorld-only CSS:
two real legend rows without top padding, compact title/panel sizing and no wasted
map padding. Scripted demo sizing remains unchanged. A new viewport test inspects
actual rendered lines rather than unbounded Static text; at80x24 it verifies visible
coverage bar, both legend rows, at least five map content rows, PLAN/COST/terminal
status and replay hint. Measured fixture: six map rows and seven timeline rows.
Lead reviewed the actual corrected diff and reran Ruff/types/whitespace successfully.

### Changed files

Scenario metadata/construction and config/preflight; map renderer; app summaries,
new presentation.py and TUI CSS; three new focused test files. README, design,
architecture, AGENTS decision log, manual guide, roadmap, NEXT and spec/report012
record the implementation. Planned spec013 makes comparison acceptance concrete.
Existing formatter gate expanded to27files; source fingerprint now includes scenarios.
No new dependency or inference/planner/sensor/replay schema change.

### Remaining boundaries

Scan tint is static latest evidence, not continuous radar. Target marker is latest
fleet intent, not persistent per-drone assignment. Walls constrain movement but do
not occlude the synthetic sensor. Room labels appear only on neutral terrain and
matching facility geometry. Compact screens scroll some content. Debrief reports
uncertainty/confidence, not accuracy or confirmed discovery. Objective confirmation,
comparison workflow and demo/story package remain later planned stages.

Owner manual acceptance remains pending. No commit, push, merge or publication.

Final affected UI regression command:
`python -m pytest -q -p no:cacheprovider tests/test_presentation.py tests/test_tui.py
tests/test_tui_hybrid.py tests/test_tui_replay.py tests/test_tui_coordination.py`
**50 passed in30.41s** after correction, including the additional viewport case.
Ruff/check/format passed. The earlier full294-test result predates that one new
regression case; no second full sweep was run, per focused verification approach.
No blocking findings remain; local acceptance/definition of done are satisfied.
