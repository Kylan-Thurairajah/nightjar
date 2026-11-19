# Beacon search demo

I’ve been playing a lot of Rainbow Six Siege lately, and the recon drones gave me
the idea for this little search sim. The demo is a fictional intel-gathering
mission, not a recreation of the game or its maps.

The goal is simple: find the hidden beacon and check the likely spot. R1 (RAVEN),
G2 (GHOST), and V3 (VIPER) are virtual drones. The colored trails show where each
one has searched; a `?` marks a candidate and `◎` marks a verified beacon. A scan
is a clue, not a confirmation.

The README clip opens after deployment and follows live search through beacon
verification, with the mission-control screen updating continuously. It uses the
Textual UI at **132 columns × 55 rows** so the map, telemetry, controls, and event
log fit without scrolling. It ends on the verification result.

## Launch and configure

From the repository root, run:

```bash
.venv/bin/python -m nightjar
```

Use these settings in mission configuration:

| Setting | Value |
| --- | --- |
| Operation name | `NIGHTJAR BEACON SEARCH` |
| Environment | Training Facility |
| Map | Standard (32 × 16) |
| Drones | 3 |
| Initial control | Manual |
| Search policy | Frontier |
| Sensor | High reliability (98% / 2%) |
| Tick budget | 1200 |
| Seed | 6 |

Review the preflight screen and launch.

## Refresh the README recording

On macOS, run the capture script from the repository root:

```bash
.venv/bin/python scripts/record_demo.py
```

The script drives the Textual app with real search, rescan, movement, and
verification actions in a roughly 28-second H.264 video. It records the deployed
mission in two-tick increments and enforces a 30-second maximum. It replaces the
README MP4 and preview image only after a successful verification. The README
preview opens the playable video. It captures no setup screens or debrief. For
this compact repeatable walkthrough, it uses the
high-reliability 98% / 2% proximity model at exact-cell range; the ordinary
mission preset keeps its wider search radius. The target remains hidden from
route logic.

## Play the walkthrough

1. Press `B` to read the brief, then `Esc` to return to the mission.
2. Press `M` to let R1 join G2 and V3 in autonomous search. Press `N` to advance
   one fleet round at a time; the colored paths make each drone’s coverage easier
   to follow.
3. When the UI shows a candidate, press `3` to hand control to V3 and `H` to show
   the belief map. Move V3 to the `?` cell with `WASD`.
4. Press `F` to check the exact cell. A match ends the mission as **BEACON
   VERIFIED**.
5. Press `B` for the debrief. It reports elapsed ticks, scan readings and positive
   intel, candidate checks, the verifying drone, and a short timeline. Press `R`
   to review the recorded mission.

All readings and verification happen in the simulation. No real aircraft or
physical sensors are modeled.

## What the clip shows

- The mission-focus panel sets the goal: find the hidden beacon.
- R1, G2, and V3 search different parts of the facility; their colors and trails
  show who covered what.
- A likely cell becomes a candidate, then V3 moves there and checks it.
- The verified result appears in the live mission-control banner.

## Deeper engineering

For the implementation behind the walkthrough, see [architecture](ARCHITECTURE.md),
[measured search-policy comparisons](BENCHMARKS.md), and [known limitations](ROADMAP.md).
