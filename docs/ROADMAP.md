# Product roadmap

The active task is linked from [NEXT.md](../NEXT.md). This roadmap records product milestones; engineering workflow changes do not advance simulation features.

| Milestone | Status | Scope |
| --- | --- | --- |
| 1–6 | Implemented | Deterministic GridWorld, mission configuration, synthetic sensing, shared Bayesian belief and autonomous search policies |
| 7: Hybrid Multi-Agent Autonomous Operations | Implemented; owner manual acceptance passed; integration pending | Serial fleet rounds, hybrid manual/AUTO TUI, atomic handoff, explicit IDLE parking and shared belief |
| 8: Mission Replay and Event Reliability | Implemented; verified locally, integration pending | Typed ordered events, immutable snapshots, validated versioned JSON viewing archives and mission replay controls |
| 9: Reproducible Benchmarking and Public Release | Local implementation/verification complete; publication pending | Offline policy comparisons, measured raw example, methods and release checklist |
| Fleet coordination follow-up | Implemented; coordination manual acceptance/integration pending | Shared visited coverage and soft round-local target preferences, no fixed sectors |

The TUI now runs all AUTO drones through the existing serial fleet scheduler while
one selected drone can remain MANUAL. Atomic handoff preserves IDLE parking;
background planning runs off the UI loop and replay reads committed snapshots.
Global roster ordering, tick budgets and mission-wide planner exhaustion remain.
There is no sector assignment or independent per-drone exhaustion. See
[ARCHITECTURE.md](ARCHITECTURE.md) and [hybrid verification](reports/010-hybrid-fleet-controls.md).

Milestone 8 preserves the compact interface and covers both direct calls and fleet rounds. Replay is historical viewing, not simulation resume. See its [specification](specs/008-mission-replay.md) and [verification report](reports/008-mission-replay.md). Feature-branch delivery is authorized; merging and next-milestone execution are not automatic.

Milestone 9 records seeds, configuration, protocol/software/source versions, raw metrics and stopping rules in deterministic JSON. See [methods/results](BENCHMARKS.md), [specification](specs/009-benchmarking-release.md) and [release checklist](RELEASE.md). The measured nine-run example is descriptive, not a general policy ranking or real-world claim. Expensive experiments remain outside CI. Owner license/integration/publication decisions remain open.

Owner reports the supplied hybrid manual tests passed. The selected fleet
coordination follow-up is now implemented and locally verified: 270 tests passed.
See [spec011](specs/011-fleet-coordination.md) and [evidence](reports/011-fleet-coordination.md).
The next task is coordination manual acceptance in [NEXT.md](../NEXT.md).
Commits, pushes, merges and publication remain separate approval actions.

## Approved presentation roadmap (2026-11-05)

Owner approved these directions and immediate delivery of the first scoped slice.
Implementation proceeds one reviewable slice at a time, without repeated routine
approvals. Preserve current core mathematics and honest presentation of uncertainty.

| Stage | Status | Acceptance |
| --- | --- | --- |
| 012 Mission presentation and debrief | Implemented locally; manual review pending | Named-room original facility, clear brief, scan footprint/evidence, latest fleet intent and accurate debrief; readable at80x24, replay-safe |
| 013 Matched policy comparison | Implemented locally; manual review pending | Compare real FRONTIER/IG runs under same map/seed/fleet/tick ceiling; show coverage/uncertainty traces and actual stopping reasons; no assumed winner or misleading fair-outcome claim |
| 014 Repeatable demo and engineering story | Deferred by owner: product first | Deterministic recorded walkthrough, concise captions/storyboard, screenshots/README, reproducible experiment and actual multi-agent development findings; distinguish simulated drones from coding agents; no automatic social publishing |
| 015 Field awareness and fleet identity | Implemented locally; 338 tests passed | Animal identities, owner-colored paths, richer facility, room logs/coverage, honest milestones |
| 016 Coordinated assignments and verified discovery | Next implementation slice | Durable reachable search/verify tasks, reallocation triggers, explicit verification, unmistakable confirmed outcome; public state and replay validation |

The original floor plan is inspired by tactical games without copying game maps or
assets. No real surveillance/physical sensing is introduced. Recording tools remain
optional external tooling; no application dependency is added for video capture.

## Product priority update

Owner prioritizes what an observer can understand: distinct drones, purposeful
coverage, field awareness and a visible search/contact/verification outcome.
Replay remains a reliability tool rather than a headline. No restart-button milestone.
Keep the aesthetic restrained and operational; no real hardware/feeds, combat or
physical sensing claims. Detailed accepted scopes are spec015 and spec016.
