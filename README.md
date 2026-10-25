# Nightjar

Nightjar is a Python-based, terminal-first autonomous search simulation platform. It is designed as a local research and portfolio project for exploring deterministic 2D worlds, synthetic sensing, probabilistic inference, search strategies, and reproducible evaluation through a restrained Textual interface.

The project is simulation-only: it does not control real drones or connect to physical sensors.

## Current status

The default Textual TUI is a visual demo featuring a 32×16 grid, three virtual agents following scripted routes, obstacle symbols, telemetry, event log, timeline controls, and map overlays for a synthetic heatmap, visited cells, and paths. The heatmap is illustrative display data, not Bayesian inference; routes and statuses are scripted. Replay recalculates demo frames rather than reading a persistent event log.

The optional GridWorld TUI mode connects the deterministic single-agent `GridWorld` simulation to a neutral map and displays actual position, obstacles, tick, and movement results. `GridWorld` provides configurable dimensions, seeded obstacle placement, cardinal movement, and explicit boundary and obstacle collision results. Neither mode implements autonomous planning or real-world sensing.

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
.\.venv\Scripts\python.exe -m nightjar --mode gridworld
```

### macOS / Linux

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m nightjar
.venv/bin/python -m nightjar --mode gridworld
```

After installation, the `nightjar` command is also available in the environment.

## Controls

| Key | Action |
| --- | --- |
| `Space` | Play or pause (demo mode) |
| `N` | Advance one demo tick, or the next predefined GridWorld move |
| `W` / `A` / `S` / `D` | Move north / west / south / east one cell in GridWorld mode |
| `H` | Show the synthetic heatmap in demo mode; neutral terrain in GridWorld mode |
| `C` | Show visited cells |
| `P` | Show agent paths |
| `Tab` | Select the next agent (demo mode) |
| `R` | Enter or exit replay mode (demo mode) |
| `Left` / `Right` | Seek in replay mode (demo mode) |
| `Q` | Quit |

## Tests

Run the complete test suite from the repository root:

```powershell
python -m pytest -q
```

If the project is not installed in the active Python environment, install it with the commands above first.

## Roadmap

1. Add a synthetic proximity sensor and test a normalized Bayesian belief map, keeping observations separate from hidden world state.
2. Add and evaluate simple search baselines before considering information-gain planning.
3. Add deterministic event records and snapshot-based replay.

Persistence or remote services will be considered only if a concrete requirement justifies them.
