# Workflow bootstrap evidence — 2026-11-03

Status: infrastructure implemented; independent review and QA results recorded below.
Scope: engineering workflow only. No production simulation or TUI changes, commits,
pushes, merges, or user-level configuration changes authorized for this delivery.

## Roles actually invoked

- Lead `/root`: environment/configuration inspection, implementation, gates and integration.
- Native `/root/scheduler_audit`: read-only simulation specialist; actual spawn,
  message and final result obtained. Audited public fleet APIs and seeded traces.
- Native `/root/architecture_docs`: inspected actual code and wrote only
  docs/ARCHITECTURE.md and docs/ROADMAP.md under explicit ownership.
- Native `/root/independent_review`: fresh-context actual-diff review; independently
  ran lint, format, types and all 142 tests. Identified the clean-CI wheel isolation
  issue; final rereview found no remaining blocking or nonblocking issues.
- `/root/scheduler_audit` also received a distinct QA follow-up against the completed
  infrastructure, without write ownership. QA independently passed Ruff lint/format,
  mypy, CLI help, TOML parsing and all 142 tests (12.98s).

This session's spawn schema does not select custom role types. These invocations
used bounded role instructions, not hot-loaded named TOML agents. The durable files
use the official native schema; new-session discovery remains a separate check.

## Demonstration findings

The specialist independently ran:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/test_provider.py tests/test_sensor.py tests/test_planning.py
```

Result: **48 passed in 0.53s**. It also executed public-API probes via Python stdin:

```python
import numpy as np
from nightjar.core.provider import GridWorldSimulation, OperationalMode
from nightjar.core.world import GridWorld, Direction

sim = GridWorldSimulation(GridWorld(width=6, height=4, obstacles=()),
                          drone_count=2, max_ticks=1)
sim.queue_manual_action("01", Direction.EAST)
sim.queue_manual_action("02", Direction.WEST)
print(sim.fleet_round().tick)  # observed 2: budget overrun

def trace():
    run = GridWorldSimulation(GridWorld(seed=43), drone_count=3)
    for drone in run.frame().drones:
        run.set_mode(drone.identifier, OperationalMode.AUTO)
    frames = [run.fleet_round() for _ in range(5)]
    return frames, run.observations, run.belief_map.probabilities

first, second = trace(), trace()
assert first[0] == second[0] and first[1] == second[1]
np.testing.assert_array_equal(first[2], second[2])
```

Findings confirmed by the architecture agent and lead inspection:

- **Scheduler prerequisite**: `provider.py:353,363,521` checks active status before
  the round but queued manual dispatch bypasses the public guard; two queued moves
  overrun a one-tick budget. Existing tests do not cover this boundary.
- **Semantics decision**: `provider.py:351,356` claims manual-first but actually
  interleaves MANUAL/AUTO by roster order. AUTO 01 acted at tick 1 before queued
  MANUAL 02 at tick 2 in the specialist's ordering probe.
- `provider.py:494` makes one planner STOP terminal for the whole mission; fleet
  intent needs review. TUI `app.py:156,393` still advances selected AUTO only.
- Repeated seed-43 three-AUTO five-round traces yielded equal frames, observations,
  and bitwise-equal belief arrays. This bounded evidence is not universal correctness.

No disagreements on these facts. No simulation corrections were made; the M8 spec
requires explicit prerequisite analysis and approval for material semantics choices.

## Gate scope and tooling decisions

Ruff and mypy are development-only dependencies pinned to the versions evaluated.
Ruff checks E4/E7/E9/F across src/tests, with two file-level F401 exemptions for
existing unused `math.exp` and `pytest` imports. These exemptions also mask future
unused imports in those files; remove them when those imports are cleaned up.

Initial Ruff formatter audit found 14 unformatted files (8 already formatted).
CI checks four already-clean substantive files: sensor.py, test_world.py,
test_sensor.py and test_demo.py. Full-repo formatting is deferred to a separately
reviewable cleanup; new/changed Python files should be formatted by their owner.

Initial mypy audit of all eight core modules found one provider.py:263 tuple
assignment error. CI checks world, sensor, belief and planning with silent import
following. Provider, mission, demo and TUI are outside this gate; it is not full type
coverage. Expand the gate after addressing baseline debt, without global ignores.

Hypothesis is deferred: existing seeded/parameterized tests already exercise the
important current invariants. Adopt it when a concrete generation/shrinking need
justifies another dependency. Existing Textual pilots supply headless integration
coverage. No expensive Monte Carlo checks were added to PR CI.

## Environment and failures

System `python -m pytest -q` previously failed collection because Nightjar was not
installed in that interpreter. Use the project `.venv` interpreter. Restricted pip
could not find packages; the approved network retry installed Ruff 0.17.3/mypy 2.4.1.
Codex help/config checks emit temporary PATH cleanup/access warnings but exit zero.
Git feature-branch creation required sandbox escalation; no source was discarded.

Initial wheel build failed on restricted temporary-file access, then the approved
retry exposed missing setuptools in the virtual environment. Installed setuptools,
wheel and PyYAML locally for build/skill validation (not application dependencies).
Skill validation initially failed for missing PyYAML in both Python environments.
The reviewer independently identified that a fresh CI install would also lack the
backend for `--no-build-isolation`. CI now retains default build isolation; the
local no-isolation build passed after installing its backend. No simulation edits
were needed. This correction was agreed rather than an unresolved disagreement.

## Executed final verification

Commands below used `.\.venv\Scripts\python.exe` as Python:

| Command | Result |
| --- | --- |
| `-m pytest -q -p no:cacheprovider` | 142 passed in 11.27s (includes headless TUI) |
| `-m ruff check src tests` | Passed |
| `-m ruff format --check src/nightjar/core/sensor.py tests/test_world.py tests/test_sensor.py tests/test_demo.py` | 4 files already formatted |
| `-m mypy` | Success, 4 source files |
| `-m pip wheel . --no-deps --no-build-isolation --wheel-dir dist` | Built nightjar_sim-0.1.0-py3-none-any.whl after backend install |
| `-m nightjar --help` | Passed; imports/CLI available |
| `C:/Users/kylan/.codex/skills/.system/skill-creator/scripts/quick_validate.py .agents/skills/feature-delivery` | Skill is valid |
| Same validator with `.agents/skills/simulation-verification` | Skill is valid |
| Python `tomllib` parse of config and all five agent files | Passed |
| `codex --strict-config app-server --print-startup-config` | Exit 0, CLI version confirmed; does not prove named-agent discovery |
| `git diff --check` | Passed (line-ending warnings only) |

QA's exact variants were `-m ruff check --no-cache src tests`,
`-m ruff format --check --no-cache` with the same four paths above,
`-m mypy --cache-dir=nul`, `-m pytest -q -p no:cacheprovider`, and
`-m nightjar --help`. It parsed pyproject plus the six Codex TOML files.
The independent reviewer ran the full suite with normal caching: 142 passed with
one sandbox-related cache warning. Its packaging attempt was blocked by temporary
directory permissions; the lead's approved local build succeeded as recorded above.

GitHub-hosted CI and a visible interactive terminal were not executed here.
Headless Textual execution is verified. Application/demo behavior is unchanged;
scripted demo heatmaps/replay remain illustrative and real mission replay is absent.
No new tests were necessary for unchanged production behavior; existing tests and
native skill/config validators cover this infrastructure's executable boundaries.

Acceptance: repository-local context, five durable roles, two skills, incremental
gates, spec convention, M8 preparation, and actual delegation/review are delivered.
Named-agent discovery in a fresh client and hosted CI remain environmental checks.
Human integration approval is pending; changes are uncommitted on
`chore/native-agent-workflow`. No product architecture decision was taken; M8 open
semantics require later human decisions as specified in its prepared spec.

## Changed-file inventory

- `.codex/config.toml`: concurrency cap, inherited model/permissions.
- `.codex/agents/{architecture,implementation,simulation,reviewer,qa}.toml`: five
  bounded native roles; lead remains the primary session.
- `.agents/skills/{feature-delivery,simulation-verification}/SKILL.md`: reusable
  delivery lifecycle and mathematical/deterministic verification procedures.
- `AGENTS.md`: replace stale first-milestone instructions with durable navigation,
  delegation, ownership and approval rules; dated decision entry.
- `NEXT.md`: concise active-spec pointer and single-request entry point.
- `README.md`: workflow entry point and roadmap link.
- `docs/ARCHITECTURE.md`: actual state, modules, RNGs and known fleet limitations.
- `docs/ROADMAP.md`: implemented versus planned milestones.
- `docs/WORKFLOW.md`: setup, orchestration, handoffs, permission limits and reports.
- `docs/specs/TEMPLATE.md`: lightweight spec convention.
- `docs/specs/008-mission-replay.md`: prepared M8 acceptance/tests/open decisions.
- `docs/reports/workflow-bootstrap.md`: this reproducible delivery evidence.
- `pyproject.toml`: dev tooling and scoped lint/type configurations.
- `.github/workflows/test.yml`: extend existing job with lint/format/type/package
  and CLI import checks alongside pytest; no duplicate workflow.

No ADR was created: no new product architecture was decided. Future material M8
semantics decisions should receive a concise ADR after human approval.
