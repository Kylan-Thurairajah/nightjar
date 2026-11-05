# Nightjar architecture

This describes the local implementation. Product constraints and the approved terminal design remain in [AGENTS.md](../AGENTS.md) and [DESIGN.md](DESIGN.md). Planned work is in [ROADMAP.md](ROADMAP.md).

## Runtime and state

`src/nightjar/__main__.py` launches one Textual application. Normal startup uses configuration and preflight screens; explicit `demo` and `gridworld` modes bypass configuration. There are no service processes, databases, or hardware integrations.

| Module | Responsibility |
| --- | --- |
| `core/mission.py` | Frozen mission configuration, preset dimensions, centralized validation, world and simulation construction |
| `core/world.py` | Integer grid geometry, seeded obstacles, hidden stationary objective, cardinal movement and explicit blocking results |
| `core/provider.py` | Mission lifecycle, fleet state, control modes, action execution, observation collection, shared belief, typed public frames |
| `core/replay.py` | Immutable public events/snapshots, clamped timeline viewing and validated versioned JSON archives |
| `core/sensor.py` | Synthetic binary Manhattan-distance proximity sensor, immutable observation records and reliability presets |
| `core/belief.py` | Shared Bayesian posterior in log space, read-only probability snapshots, entropy and MAP statistics |
| `core/planning.py` | Public planner input contract, RANDOM, FRONTIER and INFORMATION GAIN policies |
| `core/demo.py` | Separate scripted three-agent demonstration and illustrative heatmap |
| `services/hybrid.py` | FIFO mission commands, background core execution, committed caches and replay/control lifecycle |
| `tui/` | Configuration/preflight, keyboard handling, telemetry and map rendering |
| `benchmark.py` | Offline adapter over public core APIs, deterministic metrics/reporting and a standalone CLI |

Core modules do not import Textual or Rich. `GridWorldSimulation` owns deterministic state transitions. `HybridMissionController` in `services/` owns TUI lifecycle and serialized command execution; the offline benchmark continues using core APIs directly. Each internal drone has its own world position, mode, path, visited cells and latest movement result. `GridWorldFrame` and `DroneFrame` expose public presentation state without objective coordinates. The explicit debug objective accessor is for tests and debugging only.

## Actions, scheduling and timing

The mission owns a global tick counter. An accepted movement attempt, including a blocked move, or a successful scan consumes one tick. Mode changes and UI selection do not. World-local movement ticks and UI timer callbacks are distinct from mission ticks.

`step()` accepts MANUAL movement and `autonomous_step()` executes one named AUTO action for direct callers. The hybrid TUI timer uses `fleet_round()` instead. MANUAL launch keeps the selected drone MANUAL and normalizes other non-IDLE drones to AUTO, paused; IDLE launch preserves parking. Space controls autonomous fleet run/pause, N pauses and steps one fleet round, and WASD/E are explicit selected-MANUAL actions between serial rounds.

The core `fleet_round()` API walks the stable drone roster once. At each entry it consumes that drone's queued manual movement, otherwise resolves an AUTO action; IDLE drones do not act. Modes interleave in roster order. Queuing another movement for the same drone replaces its previous pending movement. Mode changes clear that drone's queue and reservation. Movement checks current positions and reservations; successful movement records a destination reservation. These are serial actions, not simultaneous motion or a distributed coordination protocol.

The fleet round checks mission status before each drone action and stops immediately when an earlier action ends the mission. A partial round commits one snapshot. Planner STOP remains mission-wide exhaustion; independent per-drone exhaustion is not added. The TUI runs the AUTO fleet while allowing one MANUAL drone. `set_hybrid_control()` computes the complete requested modes first, preserves other IDLE drones, and applies changed modes in one capacity-checked zero-tick capture boundary. Rejected handoffs cannot partially change modes or controller selection.

## Hybrid command execution

The controller caches immutable live snapshots/history and a separate replay view.
Named async commands are serialized by a FIFO lock. Core transitions plus capture
run in a thread executor, and the completed snapshot/history/selection bundle is
published on the event loop. The TUI renders these caches, not a provider halfway
through a round. Its pending-command counter is reserved before worker scheduling;
timer ticks coalesce rather than accumulate behind explicit inputs.

Space pause takes effect immediately for future timer requests; an in-flight round
finishes. Manual movement, sensing and handoff requests remain ordered between
rounds. Expected `ControlDeniedError` feedback (for example WASD on IDLE) does not
stop other AUTO drones; terminal, capacity and unexpected core failures stop autoplay.
The actual executor future is shielded through cancellation so a cancelled caller
cannot release provider ownership while its Python thread is still mutating state.

Selecting an active live drone claims MANUAL and returns other active drones to
AUTO. IDLE remains parked until explicitly reclaimed with M; I parks selected
without stopping other AUTO drones. Replay entry waits behind accepted commands,
saves live selection and freezes committed history. Replay selection is view-only;
exit restores saved selection and returns paused, with no handoff or core mutation.
Terminal selection can inspect other drones without changing terminal modes.

## Sensing, inference and planning

One sensor stream serves the mission. Each observation records mission and observation IDs, drone ID, mission tick, scan position, sensor configuration, reading, and per-drone sequence number. Only sensor execution receives the hidden objective. Scans update one shared belief before appending the observation to public history.

The belief starts uniformly over valid objective candidate cells and keeps obstacle cells at zero probability. Updates use the recorded likelihood parameters, normalize in log space, and reject duplicate/out-of-order or globally impossible evidence. Public snapshots contain read-only probability arrays. Entropy change is current entropy minus initial entropy; a MAP cell or positive reading is not confirmed discovery.

`PlannerState` contains public geometry, selected-drone position/history, fleet-union visited coverage, globally scanned positions, occupied cells, legal moves, budget, sensor parameters and a copied read-only belief. It excludes the hidden objective. One planner instance is shared by the fleet. RANDOM uses legal actions and a private stream; FRONTIER uses deterministic BFS routing; INFORMATION GAIN evaluates binary sensor outcomes and subtracts 0.01 bits per movement/scan tick. Stable direction and tie ordering are part of reproducibility.

## Fleet search coordination

Before each AUTO decision, the provider unions public visited histories from all
MANUAL/AUTO/IDLE drones. Individual frame histories remain unchanged. Within a
fleet round, successful AUTO MOVE targets form a local set passed to later planners
as immutable `PlannerState.reserved_targets`. This is separate from movement
collision reservations. FRONTIER and INFORMATION GAIN prefer otherwise eligible
unclaimed targets, then fall back to the original eligible candidates when needed;
INFORMATION GAIN only considers positive-utility candidates before this preference.
RANDOM ignores target claims. Candidate scoring, sensing mathematics and tie breaks
remain unchanged. Claims never block routes or create planner exhaustion.

Claims reset on every round and have no persisted lifecycle or archive fields.
Direct `autonomous_step` shares coverage but has no cross-call claims. Replay records
executed actions and existing decision metadata without rerunning historical planners.
This reduces duplicate destinations on tested fixtures; it does not guarantee disjoint
paths/sensor footprints, globally optimal allocation or better entropy reduction.

## Randomness and history

Obstacle generation uses a local RNG seeded from the mission seed. Objective selection uses a separate salted seed. The proximity sensor owns another RNG initialized from the seed; the shared random planner uses `seed ^ 0x504C414E`. Reproduction requires the same configuration **and action order**, since sensor and planner streams are consumed serially.

The provider retains human-readable event strings for display and exposes the last eight in each frame. It also records typed immutable `MissionEvent` records with contiguous sequence numbers, simulation ticks and snapshot-boundary indices. Movement (including blocking), scans, effective mode changes, planner STOP and terminal transitions are committed events. Queue preparation/cancellation is not an executed action; its display text does not add a committed history boundary. Rejected requests and terminal/identical-mode no-ops add no records.

`MissionSnapshot` stores public frame state, cumulative observations, an immutable belief grid and statistics, sensor configuration, strategy and latest planner decision. The initial snapshot is index zero. Each direct movement/scan/AUTO call and effective mode change captures a boundary; a fleet round suppresses nested captures and commits once. Zero-tick mode/STOP boundaries mean snapshot index is distinct from simulation tick. Exceptions unwind capture nesting so later calls can still capture correctly.

`simulation.history` returns an immutable `ReplayTimeline`; existing views do not grow when live execution continues. `snapshot(index)` clamps viewing endpoints. `to_json()` creates a deterministic version-1 archive with stable field/set ordering and full float precision; `from_json()` constructs a separate timeline only after schema, ordering, geometry, identities, event transitions, observation prefixes and reconstructed Bayesian belief/statistics validate. Duplicate JSON keys and nonfinite/invalid values are rejected. Historical arrays use immutable bytes backing, so NumPy write flags cannot be re-enabled. Loading neither changes the live simulation nor samples its RNGs.

History capacity defaults to `max(2048, 2 * max_ticks + 1)` snapshots (2048 with an open tick budget), with an explicit constructor override. Capacity includes the initial snapshot. A full archive raises `HistoryCapacityError` before a new committed operation mutates state or consumes planner/sensor randomness; no accepted history is silently evicted. Repeated zero-tick changes can fill history before the tick budget. Memory includes one belief grid per snapshot plus cumulative path/observation tuple references: O(S*(G+T)) reference/numeric storage in the worst case for S snapshots, G cells and T actions, with shared immutable observation objects. JSON repeats full viewing state and can be substantially larger. Serialization is explicit and is not performed on the UI timer.

GridWorld replay freezes a timeline for viewing; every historical rendering source comes from the selected snapshot. R enters/exits paused replay; arrows clamp, mutation shortcuts/timer are blocked, and selection/overlays remain UI-only. Compact sizing keeps timeline controls visible in 80x24 terminals without changing the normal desktop layout. There is no file save/load UI, disk persistence, historical resume or RNG checkpoint. Hidden objective coordinates and RNG state are absent from public archives. Demo replay continues to recompute scripted frames.

## Offline benchmarks

`python -m nightjar.benchmark` runs existing policies sequentially using a validated
bounded matrix. It creates the same mission settings per seed/strategy, sets every
drone AUTO and invokes the existing serial fleet API until terminal status. It does
not change planner, sensing, replay or TUI semantics. The default is one drone;
optional fleet experiments share a global budget and mission-wide STOP policy.
Completed timelines are not retained across runs. Public frames/observations provide
movement, scanning, visited coverage and belief metrics; hidden objectives are not
used for scoring. Versioned JSON records configuration, raw rows, descriptive means
and source/software provenance without timing or timestamps. See [methods](BENCHMARKS.md).

## Existing verification

`tests/test_world.py`, `test_provider.py` and `test_mission.py` cover geometry, state transitions and configuration. `test_sensor.py`, `test_belief.py` and `test_planning.py` cover seeded observations, Bayesian calculations, numerical stability, expected information gain and planner isolation. `test_replay.py` covers deterministic multi-drone archives, direct/fleet/partial boundaries, capacity isolation, malformed loads, immutable beliefs and terminal/no-op behavior. `test_tui.py` and `test_tui_replay.py` use Textual pilots, including historical telemetry, blocked mutation keys and actual viewport/resize checks. `test_demo.py` checks the separate scripted demonstration. `test_hybrid.py` and `test_tui_hybrid.py` additionally check atomic control, threaded serialization/cancellation, cached publication, FIFO input, continued background AUTO, parking and replay barriers. The type gate covers core, service and benchmark modules; formatter coverage is still incremental. `test_coordination.py` and
`test_tui_coordination.py` cover shared knowledge, soft claims/fallback and real-policy
normal/narrow hybrid/replay integration.
