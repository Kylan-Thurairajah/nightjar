# Nightjar

Nightjar is a Python-based, terminal-first autonomous search simulation platform. It is designed as a local research and portfolio project for exploring deterministic 2D worlds, synthetic sensing, probabilistic inference, search strategies, and reproducible evaluation through a restrained Textual interface.

The project is simulation-only: it does not control real drones or connect to physical sensors.

## Current status

The normal startup opens a mission configuration form followed by a separate preflight review. It validates an operation name, one of two environment presets, 1–10 drones, a supported map size, initial MANUAL or IDLE control, a positive tick budget, a nonnegative seed, and available spawn cells. Confirmed settings deterministically initialize the GridWorld and drone fleet.

The running GridWorld TUI displays each drone's position and operational mode. Drones have independent movement histories and visited cells; movement and obstacle, boundary, and drone collision rules are handled by the core simulation. `M` toggles the selected drone between MANUAL and AUTO; `I` sets it to IDLE. The configured planner policy is separate from this per-drone control mode. MANUAL launch assigns the first drone to the user and other active drones to AUTO, initially paused. The TUI runs the serial fleet scheduler independently of selection; selecting an active drone hands manual control to it and returns the previous controlled drone to AUTO. Explicit IDLE parking is preserved. Each mission has one hidden, stationary synthetic point of interest, and `E` records a manual proximity scan. A shared Bayesian belief map updates from observations and is displayed with `H`; planner inputs exclude the target's actual location.

Environment presets are **Open field** and **Obstacle field**; map sizes are **Compact** (16×12), **Standard** (32×16), and **Extended** (40×20). Sensor configuration offers **High reliability**, **Standard**, and **Degraded** presets. Mission execution stops when its configured tick budget is exhausted or the active autonomous planner has no eligible action.

### Synthetic sensing and simulation ticks

The binary proximity sensor uses Manhattan distance with a fixed 3-cell detection radius. Inside that radius, a positive reading is drawn using the preset's sensitivity; outside it, the preset's false-positive probability is used. Negative readings are the complementary outcomes. The presets are High reliability (98% sensitivity / 2% false-positive probability), Standard (90% / 5%), and Degraded (75% / 15%). These are synthetic model parameters, not hardware performance claims; sensing does not model walls or physical through-wall detection.

The sensor has a dedicated pseudorandom stream seeded from the mission seed, separate from obstacle generation. Repeating the same configuration and action sequence reproduces the same readings, observation IDs, and ordering. Every valid scan and every accepted movement attempt consumes one simulation tick, including a movement blocked by a wall, boundary, or drone; movement requests denied because a drone is IDLE do not. Scans are rejected once the mission tick budget is exhausted. Observation records contain the drone's scan position and sensor configuration, but not the hidden target location. No observations are persisted between runs.

The belief starts uniformly over the world's valid objective cells and applies each scan once using that observation's recorded sensor settings. For each candidate, a positive reading has likelihood equal to sensitivity inside the sensor's Manhattan radius and false-positive probability outside it; a negative reading uses the corresponding complements. Bayes' rule multiplies those likelihoods by the prior/posterior and normalizes across candidates. Readings are treated as conditionally independent given the objective location and their recorded sensor configurations. Entropy is shown in bits; the displayed entropy change is current entropy minus initial entropy (negative values indicate lower entropy, not guaranteed correctness), while each scan event reports the change since the preceding observation. The MAP coordinate marks the highest-probability cell, not a confirmed discovery. Belief updates use log probabilities to remain stable over long observation sequences. Exact-zero likelihoods stay impossible; evidence incompatible with all remaining hypotheses is rejected rather than resetting the distribution. No Bayesian computations use ground-truth coordinates.

The GridWorld heatmap labels its colors **relative intensity**: uniformly likely cells use a subdued green baseline, and cells above the uniform prior are shaded by their logarithmic probability gain relative to the prior, with the MAP cell highlighted in amber. Zero-probability cells remain distinct from low-probability cells, and the colors are not absolute probability bands. The `H` shortcut toggles this Bayesian heatmap against neutral terrain; coverage (`C`) and path (`P`) remain separate overlays.

### Autonomous search policies

Choose **RANDOM**, **FRONTIER**, or **INFORMATION GAIN** in mission configuration. The policy controls actual planner decisions; the initial control setting still independently determines whether drones start MANUAL or IDLE.

- **RANDOM** uses a private pseudorandom stream seeded from the mission seed and chooses among legal cardinal moves and a scan at the current position if that position has not been scanned.
- **FRONTIER** scans each position once, then follows a shortest-path BFS route to a reachable unvisited cell bordering visited territory. When no such frontier remains, it routes to the nearest other reachable unvisited cell, then stops when coverage is complete.
- **INFORMATION GAIN** computes expected entropy reduction for the sensor's positive and negative outcomes at each reachable, unscanned sensing location. It chooses the best `expected information gain - 0.01 bits × (movement ticks + scan tick)` utility and moves toward it one cell per action. Ties are resolved by travel cost, then row and column. The fixed cost coefficient is a simple, interpretable tradeoff, not a measured performance optimum. A position is scanned at most once by this policy; after all positive-utility unscanned positions are exhausted, it stops.

AUTO planners share the fleet's visited coverage, including cells explored manually.
Within each serial round, FRONTIER and INFORMATION GAIN prefer targets not already
chosen by an earlier AUTO drone. These are soft preferences: routes and sensing
areas can overlap, and planners reuse a claimed target when no eligible alternative
exists. Claims reset each round; there are no fixed sectors or persistent assignments.
RANDOM remains the seeded baseline. Single-drone policy behavior is preserved.

The information-gain expectation uses the same Manhattan-radius sensitivity/false-positive likelihoods and Bayesian posterior as mission scans. Hypothetical calculations do not mutate the mission belief. Movement and scans remain separate one-tick actions, routed through the existing world and observation pipeline. A noisy positive reading is not a confirmed discovery. Autonomous missions end on tick-budget exhaustion or when the chosen planner has no eligible action; no ground-truth search-success score is awarded. Random and frontier exploration are baselines, not claims of optimal search.

In GridWorld mode, `Space` runs/pauses the whole AUTO fleet while the selected MANUAL drone stays under your control. `N` pauses autoplay and advances one fleet round; it never moves a MANUAL drone implicitly. Use `W`/`A`/`S`/`D` and `E` for explicit selected-MANUAL movement/scans, including while other drones run. Tab/1?3 hands control to an active drone. `M` toggles selected MANUAL/AUTO or explicitly reactivates IDLE as MANUAL; `I` parks selected without pausing other AUTO drones. Selecting IDLE does not wake it. IDLE launch keeps all drones parked, and Space does not start when no AUTO drone is available. A single drone can be released to AUTO with M. Planner policy and current mode appear in telemetry; the timeline shows fleet run/pause and the latest shared planner decision.

### Mission replay

GridWorld missions retain an initial public snapshot and ordered typed events for
committed actions. Press `R` to pause and view the latest recorded snapshot, then
`Left` / `Right` to seek with clamped endpoints. Snapshot numbers are separate from
ticks: mode changes and planner exhaustion can commit history without advancing time.
The map, telemetry, belief, observations, events and planner decision all come from
the selected historical snapshot. Movement, scans, mode changes, stepping and autoplay
are disabled while viewing replay; drone selection and overlays remain available.
Press `R` again to return to the unchanged live mission and its saved selected drone, still paused. Replay selection never hands off live control. Entry waits for an already accepted operation to finish; pausing prevents later autonomous rounds but does not cancel a round already in flight.

Core callers can use `simulation.history.to_json()` and
`ReplayTimeline.from_json(text)` from `nightjar.core.replay` to serialize and validate
a separate, read-only timeline. Archives contain no hidden objective or RNG state;
they support viewing rather than resuming simulation. There is no save/load file
dialog or automatic disk persistence.

History retains at least 2048 snapshots by default, or `2 * max_ticks + 1` when larger.
If capacity is reached, the next committed mutation is rejected before state or RNG
changes; the TUI reports `HISTORY FULL`. Core callers can set `history_capacity`
explicitly. Full snapshots include cumulative observation/path references and belief
grids, so memory and archive size grow with mission length; serialization is an
explicit API operation, not part of the UI timer.

The fleet API preserves stable drone-roster ordering and mission-wide planner
exhaustion. Partial rounds stop at tick-budget exhaustion and commit once. Direct
manual/selected-AUTO calls also commit history, so the existing TUI cannot bypass it.
Queue preparation is not an executed action. Invalid actions and terminal no-ops do
not create committed records; repeated identical mode settings are no-ops.

The original scripted three-agent demonstration remains available with `--mode demo`. Its synthetic heatmap is illustrative, not Bayesian inference; agent routes and statuses are scripted. Its replay still recalculates demo frames.

## Requirements

- Python 3.11 or later
- pip
- A terminal that supports Textual (Windows Terminal is recommended on Windows)

## Install and run

### Windows PowerShell

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m nightjar
.\.venv\Scripts\python.exe -m nightjar --mode demo
.\.venv\Scripts\python.exe -m nightjar --mode gridworld
```

### macOS / Linux

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m nightjar
.venv/bin/python -m nightjar --mode demo
.venv/bin/python -m nightjar --mode gridworld
```

After installation, the `nightjar` command is also available in the environment.

Running without `--mode` opens mission configuration. Use `--mode demo` to launch the original scripted demo directly. `--mode gridworld` remains available for a direct GridWorld launch with default mission settings.

## Controls

### Configuration and preflight

Use `Tab` to move between fields. Adjust the 1–10 drone-count slider with `←` / `→`; `Home` and `End` select the minimum and maximum. Use the in-layout selection controls to choose presets. Select **NEXT: PREFLIGHT REVIEW** (or press `Enter`) to review the mission. On the preflight screen, select **BACK TO CONFIGURATION** or press `Esc` to edit settings; `Enter` launches the mission and `Q` returns to configuration. `Q` on the initial configuration form exits.

### Running mission

| Key | Action |
| --- | --- |
| `Space` | Play/pause demo; in GridWorld, run/pause all AUTO drones |
| `N` | Advance one demo tick; in GridWorld, pause and step one fleet round |
| `W` / `A` / `S` / `D` | Move the selected MANUAL drone one cell |
| `E` | Manually scan with the selected MANUAL drone |
| `Tab` | Hand control to the next active drone; parked IDLE stays parked |
| `1` / `2` / `3` | Select/handoff RAVEN / GHOST / VIPER; view-only during replay |
| `M` | Toggle selected GridWorld drone between MANUAL and AUTO |
| `I` | Park selected drone; remaining AUTO drones continue |
| `H` | Toggle the mission belief heatmap / terrain, or show the demo heatmap |
| `C` | Show visited-cell coverage |
| `P` | Show movement paths |
| `R` | Enter or exit recorded GridWorld replay or scripted demo replay |
| `Left` / `Right` | Seek one snapshot in GridWorld replay, or one demo tick |
| `Q` | Quit |

## Offline benchmarks

For an offline comparison of the existing search policies:

```powershell
.\.venv\Scripts\python.exe -m nightjar.benchmark --seeds 0 1 2 --ticks 50
```

This emits reproducible JSON with raw per-seed metrics, descriptive means, protocol,
software versions and source fingerprint. Add `--output benchmark-results.json` to
create a new local file; existing files are never silently overwritten. Optional
`--drones 3` uses the core all-AUTO fleet scheduler, not the TUI's
hybrid control: the benchmark has no manual user input. See [methods and measured example](docs/BENCHMARKS.md)
and the [release checklist](docs/RELEASE.md). No discovery or hardware-performance
claims are made. Public release still requires owner decisions and approval.

## Tests

Run the complete test suite from the repository root:

```powershell
python -m pytest -q
```

If the project is not installed in the active Python environment, install it with the commands above first.

## Roadmap

See [the maintained roadmap](docs/ROADMAP.md) for milestone status and verified limitations.

## Engineering workflow

Start substantial feature work with **Use $feature-delivery for the active spec in NEXT.md**.
See [workflow and Codex setup](docs/WORKFLOW.md), [actual architecture](docs/ARCHITECTURE.md),
and the [specifications](docs/specs/). Repository-local agents and skills support planning, implementation,
independent review and QA; integration requires human approval.

Persistence or remote services will be considered only if a concrete requirement justifies them.
