# Nightjar

Nightjar is a Python-based, terminal-first autonomous search simulation platform. It is designed as a local research and portfolio project for exploring deterministic 2D worlds, synthetic sensing, probabilistic inference, search strategies, and reproducible evaluation through a restrained Textual interface.

The project is simulation-only: it does not control real drones or connect to physical sensors.

## Current status

The normal startup opens a mission configuration form followed by a separate preflight review. It validates an operation name, one of two environment presets, 1–10 drones, a supported map size, initial MANUAL or IDLE control, a positive tick budget, a nonnegative seed, and available spawn cells. Confirmed settings deterministically initialize the GridWorld and drone fleet.

The running GridWorld TUI displays each drone's position and operational mode. Drones have independent movement histories and visited cells; movement and obstacle, boundary, and drone collision rules are handled by the core simulation. MANUAL control is available; IDLE drones can be switched to MANUAL with `M`. AUTO is represented for future work but autonomous behavior is not implemented. Each mission has one hidden, stationary synthetic point of interest, and `E` records a proximity scan from the selected drone. A shared Bayesian belief map updates from observations and is displayed with `H`; the target is not included in ordinary simulation frames, the belief model, or the map.

Environment presets are **Open field** and **Obstacle field**; map sizes are **Compact** (16×12), **Standard** (32×16), and **Extended** (40×20). Sensor configuration offers **High reliability**, **Standard**, and **Degraded** presets. Mission execution stops when its configured tick budget is exhausted.

### Synthetic sensing and simulation ticks

The binary proximity sensor uses Manhattan distance with a fixed 3-cell detection radius. Inside that radius, a positive reading is drawn using the preset's sensitivity; outside it, the preset's false-positive probability is used. Negative readings are the complementary outcomes. The presets are High reliability (98% sensitivity / 2% false-positive probability), Standard (90% / 5%), and Degraded (75% / 15%). These are synthetic model parameters, not hardware performance claims; sensing does not model walls or physical through-wall detection.

The sensor has a dedicated pseudorandom stream seeded from the mission seed, separate from obstacle generation. Repeating the same configuration and action sequence reproduces the same readings, observation IDs, and ordering. Every valid scan and every accepted movement attempt consumes one simulation tick, including a movement blocked by a wall, boundary, or drone; movement requests denied because a drone is IDLE do not. Scans are rejected once the mission tick budget is exhausted. Observation records contain the drone's scan position and sensor configuration, but not the hidden target location. No observations are persisted between runs.

The belief starts uniformly over the world's valid objective cells and applies each scan once using that observation's recorded sensor settings. Readings are treated as conditionally independent given the objective location and their recorded sensor configurations. Entropy is shown in bits; the displayed entropy change is current entropy minus initial entropy (negative values indicate lower entropy, not guaranteed correctness), while each scan event reports the change since the preceding observation. The MAP coordinate marks the highest-probability cell, not a confirmed discovery. Belief updates use log probabilities to remain stable over long observation sequences. Exact-zero likelihoods stay impossible; evidence incompatible with all remaining hypotheses is rejected rather than resetting the distribution. No Bayesian computations use ground-truth coordinates.

The original scripted three-agent demonstration remains available with `--mode demo`. Its synthetic heatmap is illustrative, not Bayesian inference; agent routes and statuses are scripted.

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
| `Space` | Play or pause the scripted demo |
| `N` | Advance one demo tick, or a predefined move for the selected drone |
| `W` / `A` / `S` / `D` | Move the selected MANUAL drone one cell |
| `E` | Scan for the hidden objective with the selected drone |
| `Tab` | Cycle to the next drone |
| `1` / `2` / `3` | Select RAVEN / GHOST / VIPER |
| `M` / `I` | Set selected drone to MANUAL / IDLE |
| `H` | Toggle the mission belief heatmap / terrain, or show the demo heatmap |
| `C` | Show visited-cell coverage |
| `P` | Show movement paths |
| `R` | Enter or exit scripted demo replay |
| `Left` / `Right` | Seek in demo replay |
| `Q` | Quit |

## Tests

Run the complete test suite from the repository root:

```powershell
python -m pytest -q
```

If the project is not installed in the active Python environment, install it with the commands above first.

## Roadmap

1. **Milestone 6: Autonomous Search and Information-Gain Planning** — compare random/frontier exploration policies with belief-driven information-gain planning using deterministic simulations and reproducible metrics; keep planners independent of hidden ground truth.
2. Add deterministic event records and snapshot-based replay.
3. Consider persistence only if a concrete requirement justifies it.

Persistence or remote services will be considered only if a concrete requirement justifies them.
