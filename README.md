# Nightjar

**Find the hidden beacon.**

One pilot. Two autonomous searchers. A shared search.

Nightjar is a local drone-search simulation. Fly one virtual drone by hand while
two teammates search a four-room training facility. Every scan adds a clue to the
shared map. Replay the mission to see how the search unfolded.

![Nightjar's full-screen beacon-search demo: a pilot and autonomous drones search a training facility, then a positive synthetic scan updates the evidence map.](docs/demo/media/beacon-search.gif)

The beacon and sensors are synthetic. A positive scan is a clue, not a confirmed
discovery; this version does not control real drones or model target confirmation.

## Try the mission

Requires Python 3.11 or newer. From the repository root:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m nightjar
```

Use any installed Python 3.11+ executable; change `python3.12` if needed.

<details>
<summary>Windows PowerShell</summary>

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m nightjar
```

</details>

In the setup screen, choose **Training Facility**, **Standard**, **3 drones**,
**Manual**, **Frontier**, **High reliability**, and **seed 6**. Use a full-size
terminal for the complete map and mission panels.

`WASD` moves your drone · `E` scans · `N` advances the fleet · `Space` runs or
pauses it · `R` replays the mission · `B` opens the brief.

For the exact walkthrough and screenshots, see the [demo guide](docs/DEMO.md).

## Why I built it

- Keep a human pilot in control while autonomous teammates work alongside them.
- Make uncertain sensor evidence visible as the search changes.
- Keep each mission inspectable, not just playable, with room coverage and replay.

## Under the hood

If you're curious about the engineering behind the console:

- [Architecture and simulation boundaries](docs/ARCHITECTURE.md)
- [Search policies, metrics, and measured comparisons](docs/BENCHMARKS.md)
- [Design decisions](docs/DESIGN.md)
- [Roadmap and known limitations](docs/ROADMAP.md)
- [Development setup and tests](docs/WORKFLOW.md)
