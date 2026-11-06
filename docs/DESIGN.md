# Nightjar TUI design baseline

This design has been approved as the starting point for implementation.

- Primary UI: Textual TUI with Rich-rendered, colored terminal cells.
- Style: tactical terminal, near-black (#080f0c), forest green, restrained amber for high belief areas.
- Normal startup: compact mission configuration screen followed by a separate validation/preflight review; `Esc` returns without discarding entered values.
- Configuration selectors use in-layout `RadioSet` options rather than floating dropdowns. Focus is amber/forest green, selected values remain identifiable when blurred, and keyboard selection uses arrows plus Space.
- Drone count uses a focused, keyboard-accessible 1–10 slider (Left/Right to adjust; Home/End for limits) rather than typed numeric input. Configuration and preflight provide visible next, back, and launch buttons alongside their keyboard shortcuts.
- Main mission layout: header with operation identifier, configurable 16x12 / 32x16 / 40x20 map, right-hand drone telemetry and selected-drone status, bottom event log and mission status, keyboard footer.
- Heatmap layers: real Bayesian belief heatmap toggled with H in GridWorld missions (obstacles and drone markers remain above it); H toggles back to neutral terrain. Visited/coverage cells (C) and multi-drone path history (P) remain separate overlays. The scripted demo retains its illustrative synthetic heatmap.
- Controls: Space play/pause scripted demo or run/pause the AUTO fleet, N demo step or one paused fleet round, WASD move selected MANUAL drone, E scan with the selected MANUAL drone, Tab/1/2/3 hand off MANUAL control to active drones (view-only during replay; IDLE stays parked), M toggle selected drone MANUAL/AUTO (IDLE returns to MANUAL), I set selected drone IDLE, C coverage, P paths, R enter/exit recorded GridWorld or scripted demo replay, left/right seek during replay, Q quit.
- On terminals below 100 columns or 36 rows, compact sizing reduces header/workspace minimums and allows telemetry scrolling so replay controls remain visible. Normal desktop sizing stays unchanged.
- Map should reserve symbols for walls (▓▓) and agents (01/02/03), render map values via heat colors, never let the display determine simulation logic.
- Core Python state must be independent of Textual so real probability inference, algorithms, persistence and a possible FastAPI service can be added later.

## Scope boundaries

The normal startup configures a deterministic local GridWorld mission with an open field, seeded obstacle field or original named-room training facility, supported map preset, 1–10 drones, MANUAL or IDLE initial state, synthetic sensor reliability preset, search planner, mission tick budget, and seed. Preflight displays actual centralized validation results and blocks invalid launches. Drones use core-managed positions, collisions, histories and MANUAL/AUTO/IDLE state. MANUAL launch starts paused with drone 01 MANUAL and other active drones AUTO; IDLE launch keeps all parked. The timer advances existing serial fleet rounds independently of selection. N pauses and advances one fleet round without implicit MANUAL movement; WASD/E remain explicit selected-MANUAL inputs while background AUTO can continue. Selection transfers control among active drones, M toggles/reclaims it, and I preserves explicit parking without stopping the other AUTO drones. GridWorld missions collect deterministic synthetic proximity observations and update one shared Bayesian belief distribution. The H overlay uses posterior probability relative to the uniform prior; zero-probability cells remain subdued, the MAP cell is amber after evidence changes the prior, and drone markers and obstacles render above the heatmap. The telemetry panel reports entropy in bits, current-minus-initial entropy change, MAP cell and probability, and remaining nonzero candidates. Scan-event ΔH is current entropy minus the previous entropy. RANDOM, FRONTIER, and INFORMATION GAIN planners are framework-independent and receive public geometry, selected-drone state, sensor configuration, remaining budget, and a read-only belief snapshot, never hidden objective state. AUTO planners share fleet visited coverage; FRONTIER and INFORMATION GAIN prefer distinct eligible targets within each serial round, with soft fallback and no fixed sectors. Information gain is expected prior entropy minus expected posterior entropy; candidate utility subtracts a fixed 0.01 bits per movement/scan tick, and each planner scans a position at most once. Planner exhaustion and the tick budget terminate autonomous execution; positive readings do not confirm discovery. GridWorld replay records immutable public snapshots and typed ordered events in memory; entry pauses future scheduling and waits for accepted work, clamps seeking, and blocks live mutation. R returns to unchanged live state and saved control selection, paused. Core operations are serialized off the UI loop and the display reads only committed cached snapshots. There is no drone networking, disk persistence or historical resume. The original scripted demo remains available as a direct launch mode; its heatmap is generated from analytic peaks and its three agents follow fixed scripted routes and statuses. Demo replay recalculates frames rather than replaying a persistent event log.

## Roadmap

1. [x] Add synthetic sensor simulation with deterministic readings and explicit separation from hidden world state.
2. [x] Add Bayesian belief updates and test normalization.
3. [x] Add deterministic random, frontier, and information-gain autonomous planners.
4. [x] Connect hybrid manual/AUTO fleet control through serial actions, atomic handoffs and a shared belief.
5. [x] Add deterministic event records and recorded snapshot replay with validated JSON viewing archives.

## Approved presentation direction (2026-11-05)

Make the viewer understand mission, action, evidence and outcome within seconds.
Add an original named-room training facility, contextual scan/target overlays,
readable fleet intent and a public-statistics brief/debrief. Preserve near-black/
forest-green/amber styling, terminal-first layout, keyboard controls and compact
readability. Use short purposeful highlights rather than constant effects.

A latest fleet decision is not necessarily the selected drone's decision. Label it
honestly. Sensing footprint represents synthetic Manhattan radius without physical
wall occlusion. MAP confidence is not target confirmation. Later comparison screens
must show real measured traces, equal input ceilings and honest tradeoffs.

## Matched policy comparison (013)

V pauses the mission and opens an isolated comparison screen; explicit Run launches
fresh all-AUTO FRONTIER/INFORMATION GAIN experiments from configured starts. Same
map/seed/sensor/fleet/global tick ceiling, without copying current manual actions.
At sufficient width show both maps; otherwise toggle policy with Tab/1/2 while both
final summaries remain readable. Recorded comparison playback uses common ticks,
actual per-run snapshot ticks and clearly labelled coverage/entropy trace ranges.
An exhausted run freezes rather than inventing actions. No winner/discovery claim.
Close/cancel drains the isolated worker before returning to the same paused live or
historical view. Keyboard bindings apply to comparison only while it is open.

## Field awareness direction (owner-approved)

Keep callsigns/IDs but use bird, owl and snake emblems for the first three drones,
with a numeric display fallback. Colors/owner glyphs distinguish trails and future
assignments without relying on color alone. GHOST's owl is an emblem, not a rename.
Make facility doors/equipment recognizable and log actual room entry. Coverage
shows physical visits per room, never an uncertain CLEARED label. T exposes real
mission milestones without adding a permanent dashboard panel.

Next: persistent strategic assignments and SEARCHING/CONTACT/VERIFYING/CONFIRMED,
using a separate reliable exact-cell synthetic verification action. High belief alone
never reveals the objective or triggers success. Demo/blog polish remains deferred.

## Selection clarity revision (2026-11-06)

Original two-cell monochrome wing/optics/fang insignia replace animal emoji. All
three drones and their trails share neutral green; owner letters retain identity.
Amber on a drone marker or telemetry heading means selected, irrespective of mode.
Do not assign a permanent amber identity color to VIPER. G retains numeric fallback.
This supersedes the earlier per-drone palette/animal-glyph presentation choice.

## Grid-safe identity revision (2026-11-06)

Use plain ASCII unit designators R1/G2/V3, exactly two columns per cell. Remove
wing/optics/fang pictograms: terminal font shapes could look oversized. G switches
unit designators to numeric IDs. Keep neutral green for all identities and amber
only for selection, regardless of mode. Paths use R/G/V owner letters. Validate
actual terminal compositor cells and adjacent walls at normal/narrow sizes.
This replaces the earlier decorative insignia choice.
