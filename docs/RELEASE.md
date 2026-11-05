# Local release preparation

This is a local-first, Python-only synthetic research application. A verified build
is not a published release. Nothing in this checklist authorizes committing, pushing,
merging, uploading packages or creating remote releases.

## Local validation

From the repository root in PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check src tests
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m pip wheel . --no-deps --wheel-dir dist
.\.venv\Scripts\python.exe -m nightjar --help
.\.venv\Scripts\python.exe -m nightjar.benchmark --help
.\.venv\Scripts\python.exe -m nightjar
```

Use the formatter paths in `.github/workflows/test.yml`. Exercise configuration,
preflight, manual control with background AUTO, handoff/IDLE, overlays, replay and quit at
normal and compact terminal sizes. Include shared-coverage/soft-target fleet tests
from [the manual guide](MANUAL_TESTING.md). Repeat the documented small benchmark and compare
its non-timing output. Build in a fresh environment with declared dependencies for
release; install the resulting wheel into a separate environment and check package
imports, benchmark entry point and packaged Textual styles.

CI should run small deterministic tests and packaging/import checks, not long
experiments. Record interpreter/dependency versions, commands, actual results, source
fingerprint and unresolved findings in the delivery report. Keep benchmark artifacts
and release claims tied to the code that produced them.

## Owner decisions before public release

- Review and approve the complete accumulated diff before merging. Feature-branch
  delivery does not itself authorize a merge or public release.
- Choose and approve a license. No repository license file was found; this task does
  not choose one or claim license clearance for publication.
- Review the hybrid fleet workflow with actual manual input, parking and handoff.
  The benchmark all-AUTO protocol does not validate human-driven UI interaction.
- Review versions, changelog, supported Python/terminal environments, known limitations
  and measured benchmark scope. Local checks do not establish cross-platform support.
- Explicitly approve any commit, push, merge, tag, package upload or remote release.
  Choose the publication destination and credentials only when that action is approved.

No external account connection is needed for local preparation. Hosted CI status and
publication outcomes must be checked when those external actions are authorized.

## Known product boundaries

All environments, objectives and observations are synthetic. The demo is scripted.
No physical drones/sensors, surveillance feeds, networking service or database exists.
Belief certainty is not discovery. One planner STOP is mission-wide. Hybrid TUI
handoff is supported; automatic sector assignment remains absent. Replay supports in-memory historical viewing
and a validated JSON API, not a save/load UI or historical resumption. Full retained
snapshots consume memory; history capacity can stop new mutations before tick budget
when many zero-tick changes occur. Benchmarks expose these existing rules rather than
changing them for better scores.
