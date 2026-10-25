# Nightjar TUI design baseline

This design has been approved as the starting point for implementation.

- Primary UI: Textual TUI with Rich-rendered, colored terminal cells.
- Style: tactical terminal, near-black (#080f0c), forest green, restrained amber for high belief areas.
- Main layout: header, 32x16 map, right-hand 3-agent telemetry and belief-state panel, bottom event log and mission replay, keyboard footer.
- Heatmap layers: synthetic belief demo (H), visited/coverage cells (C), path history (P).
- Controls: Space play/pause, N step, Tab select agent, R enter/exit replay, left/right seek during replay, Q quit.
- Map should reserve symbols for walls (▓▓) and agents (01/02/03), render map values via heat colors, never let the display determine simulation logic.
- Core Python state must be independent of Textual so real probability inference, algorithms, persistence and a possible FastAPI service can be added later.

## Scope boundaries

Currently, the heatmap is generated from analytic peaks purely for demonstration. The drones follow fixed routes. Their 'status' is scripted. No actual sensing, Bayesian inference, search planning, drone networking, or event-store replay exists yet. The bottom replay strip displays a tick that may be scrubbed by recalculating frames, not replaying a persistent event log.

## Roadmap

1. Replace demo routes with seeded GridWorld.step actions and collision checking.
2. Add synthetic proximity sensor likelihoods, test normalization of a true Bayesian belief map.
3. Add a random and frontier search baseline, then expected-information-gain planning.
4. Add deterministic event records and real snapshot-based replay.
5. Introduce persistence / FastAPI only if cross-process ingestion or remote runs justify them.
