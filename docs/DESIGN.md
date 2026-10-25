# Nightjar TUI design baseline

This design has been approved as the starting point for implementation.

- Primary UI: Textual TUI with Rich-rendered, colored terminal cells.
- Style: tactical terminal, near-black (#080f0c), forest green, restrained amber for high belief areas.
- Normal startup: compact mission configuration screen followed by a separate validation/preflight review; `Esc` returns without discarding entered values.
- Configuration selectors use in-layout `RadioSet` options rather than floating dropdowns. Focus is amber/forest green, selected values remain identifiable when blurred, and keyboard selection uses arrows plus Space.
- Drone count uses a focused, keyboard-accessible 1–10 slider (Left/Right to adjust; Home/End for limits) rather than typed numeric input. Configuration and preflight provide visible next, back, and launch buttons alongside their keyboard shortcuts.
- Main mission layout: header with operation identifier, configurable 16x12 / 32x16 / 40x20 map, right-hand drone telemetry and selected-drone status, bottom event log and mission status, keyboard footer.
- Heatmap layers: synthetic heatmap only in the scripted demo (H); neutral terrain (H), visited/coverage cells (C), and multi-drone path history (P) in GridWorld missions.
- Controls: Space play/pause scripted demo, N step, WASD move selected MANUAL drone, Tab cycle drones, 1/2/3 select RAVEN/GHOST/VIPER, M/I set selected drone MANUAL/IDLE, C coverage, P paths, R enter/exit demo replay, left/right seek during replay, Q quit.
- Map should reserve symbols for walls (▓▓) and agents (01/02/03), render map values via heat colors, never let the display determine simulation logic.
- Core Python state must be independent of Textual so real probability inference, algorithms, persistence and a possible FastAPI service can be added later.

## Scope boundaries

The normal startup configures a deterministic local GridWorld mission with an open or seeded obstacle field, supported map preset, 1–10 drones, MANUAL or IDLE initial state, mission tick budget, and seed. Preflight displays actual centralized validation results and blocks invalid launches. Drones use core-managed positions, collision checks, histories, and MANUAL/AUTO/IDLE state; only MANUAL movement is implemented. The original scripted demo remains available as a direct launch mode; its heatmap is generated from analytic peaks and its three agents follow fixed scripted routes and statuses. Neither mode has actual sensing, Bayesian inference, autonomous search, drone networking, or event-store replay. Demo replay recalculates frames rather than replaying a persistent event log.

## Roadmap

1. Add synthetic sensor simulation with deterministic readings and explicit separation from hidden world state.
2. Add Bayesian belief updates and test normalization.
3. Add a random and frontier search baseline, then expected-information-gain planning.
4. Add deterministic event records and real snapshot-based replay.
5. Introduce persistence / FastAPI only if cross-process ingestion or remote runs justify them.
