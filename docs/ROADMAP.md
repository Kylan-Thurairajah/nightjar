# Product roadmap

The active task is linked from [NEXT.md](../NEXT.md). This roadmap records product milestones; engineering workflow changes do not advance simulation features.

| Milestone | Status | Scope |
| --- | --- | --- |
| 1–6 | Implemented | Deterministic GridWorld, mission configuration, synthetic sensing, shared Bayesian belief and autonomous search policies |
| 7: Hybrid Multi-Agent Autonomous Operations | Core implemented; hybrid TUI follow-up open | Core serial fleet-round API, queued manual movement, AUTO/MANUAL/IDLE modes and shared belief |
| 8: Mission Replay and Event Reliability | Implemented; verified locally, integration pending | Typed ordered events, immutable snapshots, validated versioned JSON viewing archives and mission replay controls |
| 9: Reproducible Benchmarking and Public Release | Local implementation/verification complete; publication pending | Offline policy comparisons, measured raw example, methods and release checklist |

The TUI still steps only the selected AUTO drone. Milestone 8 preserves core roster ordering and mission-wide planner exhaustion, fixes mid-round budget overrun, and tests these explicit policies. This does not introduce fleet-wide UI autoplay or per-drone exhaustion. See [ARCHITECTURE.md](ARCHITECTURE.md).

Milestone 8 preserves the compact interface and covers both direct calls and fleet rounds. Replay is historical viewing, not simulation resume. See its [specification](specs/008-mission-replay.md) and [verification report](reports/008-mission-replay.md). Feature-branch delivery is authorized; merging and next-milestone execution are not automatic.

Milestone 9 records seeds, configuration, protocol/software/source versions, raw metrics and stopping rules in deterministic JSON. See [methods/results](BENCHMARKS.md), [specification](specs/009-benchmarking-release.md) and [release checklist](RELEASE.md). The measured nine-run example is descriptive, not a general policy ranking or real-world claim. Expensive experiments remain outside CI. Owner license/integration/publication decisions remain open.

The next product task is the hybrid TUI follow-up described in [NEXT.md](../NEXT.md): one manually controlled drone while the others continue AUTO reconnaissance. No automatic transition to that work or public release is authorized by completion here.
