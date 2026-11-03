# Nightjar TUI design baseline

This design has been approved as the starting point for implementation.

- Primary UI: Textual TUI with Rich-rendered, colored terminal cells.
- Style: tactical terminal, near-black (#080f0c), forest green, restrained amber for high belief areas.
- Normal startup: compact mission configuration screen followed by a separate validation/preflight review; `Esc` returns without discarding entered values.
- Configuration selectors use in-layout `RadioSet` options rather than floating dropdowns. Focus is amber/forest green, selected values remain identifiable when blurred, and keyboard selection uses arrows plus Space.
- Drone count uses a focused, keyboard-accessible 1–10 slider (Left/Right to adjust; Home/End for limits) rather than typed numeric input. Configuration and preflight provide visible next, back, and launch buttons alongside their keyboard shortcuts.
- Main mission layout: header with operation identifier, configurable 16x12 / 32x16 / 40x20 map, right-hand drone telemetry and selected-drone status, bottom event log and mission status, keyboard footer.
- Heatmap layers: real Bayesian belief heatmap toggled with H in GridWorld missions (obstacles and drone markers remain above it); H toggles back to neutral terrain. Visited/coverage cells (C) and multi-drone path history (P) remain separate overlays. The scripted demo retains its illustrative synthetic heatmap.
- Controls: Space play/pause scripted demo or run/pause the selected AUTO drone, N step, WASD move selected MANUAL drone, E scan with the selected MANUAL drone, Tab cycle drones, 1/2/3 select RAVEN/GHOST/VIPER, M toggle selected drone MANUAL/AUTO (IDLE returns to MANUAL), I set selected drone IDLE, C coverage, P paths, R enter/exit demo replay, left/right seek during replay, Q quit.
- Map should reserve symbols for walls (▓▓) and agents (01/02/03), render map values via heat colors, never let the display determine simulation logic.
- Core Python state must be independent of Textual so real probability inference, algorithms, persistence and a possible FastAPI service can be added later.

## Scope boundaries

The normal startup configures a deterministic local GridWorld mission with an open or seeded obstacle field, supported map preset, 1–10 drones, MANUAL or IDLE initial state, synthetic sensor reliability preset, search planner, mission tick budget, and seed. Preflight displays actual centralized validation results and blocks invalid launches. Drones use core-managed positions, collision checks, histories, and MANUAL/AUTO/IDLE state; MANUAL movement remains available, and the selected AUTO drone executes at most one action per planner call; multi-drone autonomous coordination is not implemented. GridWorld missions collect deterministic synthetic proximity observations and update one shared Bayesian belief distribution. The H overlay uses posterior probability relative to the uniform prior; zero-probability cells remain subdued, the MAP cell is amber after evidence changes the prior, and drone markers and obstacles render above the heatmap. The telemetry panel reports entropy in bits, current-minus-initial entropy change, MAP cell and probability, and remaining nonzero candidates. Scan-event ΔH is current entropy minus the previous entropy. RANDOM, FRONTIER, and INFORMATION GAIN planners are framework-independent and receive public geometry, selected-drone state, sensor configuration, remaining budget, and a read-only belief snapshot, never hidden objective state. Information gain is expected prior entropy minus expected posterior entropy; candidate utility subtracts a fixed 0.01 bits per movement/scan tick, and each planner scans a position at most once. Planner exhaustion and the tick budget terminate autonomous execution; positive readings do not confirm discovery. Drone networking and event-store replay are not implemented. The original scripted demo remains available as a direct launch mode; its heatmap is generated from analytic peaks and its three agents follow fixed scripted routes and statuses. Demo replay recalculates frames rather than replaying a persistent event log.

## Roadmap

1. [x] Add synthetic sensor simulation with deterministic readings and explicit separation from hidden world state.
2. [x] Add Bayesian belief updates and test normalization.
3. [x] Add deterministic random, frontier, and information-gain autonomous planners.
4. Coordinate multiple autonomous drones safely through serial actions and a shared belief.
5. Add deterministic event records and real snapshot-based replay only after coordination.
