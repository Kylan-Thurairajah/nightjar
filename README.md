# Nightjar

Nightjar is a Python-based, terminal-first autonomous search simulation platform. It is designed as a local research and portfolio project for exploring deterministic 2D worlds, synthetic sensing, probabilistic inference, search strategies, and reproducible evaluation through a restrained Textual interface.

The project is simulation-only: it does not control real drones or connect to physical sensors.

## Current status

The normal startup opens a mission configuration form followed by a separate preflight review. It validates an operation name, one of two environment presets, 1–10 drones, a supported map size, initial MANUAL or IDLE control, a positive tick budget, a nonnegative seed, and available spawn cells. Confirmed settings deterministically initialize the GridWorld and drone fleet.

The running GridWorld TUI displays each drone's position and operational mode on a neutral map. Drones have independent movement histories and visited cells; movement and obstacle, boundary, and drone collision rules are handled by the core simulation. MANUAL control is available; IDLE drones can be switched to MANUAL with `M`. AUTO is represented for future work but autonomous behavior is not implemented.

Environment presets are **Open field** and **Obstacle field**; map sizes are **Compact** (16×12), **Standard** (32×16), and **Extended** (40×20). Mission execution stops when its configured tick budget is exhausted.

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
| `Tab` | Cycle to the next drone |
| `1` / `2` / `3` | Select RAVEN / GHOST / VIPER |
| `M` / `I` | Set selected drone to MANUAL / IDLE |
| `H` | Show the demo heatmap or neutral mission terrain |
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

1. Add synthetic sensor simulation and test deterministic readings separated from hidden world state.
2. Add and evaluate simple search baselines before considering information-gain planning.
3. Add deterministic event records and snapshot-based replay.

Persistence or remote services will be considered only if a concrete requirement justifies them.
