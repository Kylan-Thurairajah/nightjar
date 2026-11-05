# Hybrid Fleet TUI Control and Manual Handoff

## Objective and current context

Give the user one MANUAL drone while other active drones continue AUTO reconnaissance.
The core already has deterministic roster-order fleet rounds, collisions, a shared
belief and replay. The current TUI invokes only selected-drone AUTO calls. This task
connects the fleet to the interface without new planners, sensor/discovery mechanics,
networking or benchmark protocol changes.

## Behavior

- MANUAL mission launch starts paused with drone 01 MANUAL and other non-IDLE drones
  AUTO. IDLE launch remains all parked. No mission starts running without Space.
- Space toggles fleet run/pause independent of selected mode; no AUTO drones means
  no autoplay. N pauses autoplay and advances one fleet round, not an implicit manual
  movement. WASD/E explicitly move/scan selected MANUAL without pausing background work.
- Tab/1–3 selection of an active drone hands it MANUAL and returns previous MANUAL
  control to AUTO. Selecting IDLE preserves parking and releases previous MANUAL to
  AUTO. M toggles selected MANUAL/AUTO or explicitly reactivates IDLE as MANUAL; I
  parks selected. Other IDLE drones remain parked. All-AUTO operation is allowed.
- Selection/mode changes do not pause remaining AUTO drones. Global pause affects
  autonomous scheduling; direct manual moves/scans remain available while paused.
- Keep global tick budgets, stable roster dispatch, shared planner/sensor streams,
  collisions and mission-wide planner exhaustion unchanged. Stop autoplay at terminal
  state, capacity failure or when no AUTO drone remains. At most one round is in flight;
  no timer backlog or concurrent provider mutation is allowed.
- Mode handoff is one atomic, zero-tick replay boundary, or a no-op. Rejections/full
  capacity must not partially change modes, owner selection, queues or RNG state.
- Replay entry pauses scheduling and waits for already accepted commands to finish
  before freezing history. Replay selections/seek/overlays are viewing-only; mutations
  are rejected. Exit restores saved live selection and unchanged live state, paused.

## Architecture and implementation plan

1. `core/provider.py`: add `set_hybrid_control(selected_id, mode=None)`. Validate and
   compute desired modes before using one existing capture boundary; retain current
   direct APIs so benchmarks and non-TUI callers behave exactly as before.
2. `services/hybrid.py`: one small framework-independent controller owns serialized
   async commands and cached public live/view snapshots/history. Core operations run
   in a thread executor under a FIFO lock; publication/selection updates occur only
   after completion. Cancellation must retain serialization until the actual executor
   future finishes. No Textual/Rich imports. Replay lifecycle belongs here.
3. `tui/app.py`: submit controller commands through Textual workers; timer requests
   are skipped while explicit/in-flight work exists and recheck run/pause state before
   execution. Render only cached committed state, never mutable mid-round provider
   reads. Keep existing layout/demo and expose fleet state/shortcuts clearly.
4. Extend focused core/controller and normal/narrow headless UI tests. Update obsolete
   selected-only/N-scripted-step assertions to the explicit behavior above while
   retaining their collision, budget, telemetry and demo checks.

This uses the already-approved optional services layer for necessary lifecycle
orchestration. It does not add a framework, new dependency or significant product
architecture beyond the user's requested control workflow.

## Acceptance criteria and tests

- MANUAL/IDLE launch, single/multiple drones and handoffs maintain at most one MANUAL,
  preserve parked drones and use exactly one zero-tick mode boundary where needed.
- Other AUTO drones take actions while a selected MANUAL drone waits, moves or scans;
  switching control does not stop remaining reconnaissance. N advances fleet only.
- Seeded mixed-command sequences reproduce snapshots/events/belief; ticks/collisions,
  partial terminal rounds and capacity failures obey existing core rules.
- Deliberately delayed planner work leaves the event loop responsive; timer work is
  coalesced, accepted explicit input serialized, cached frames never show partial
  rounds, and pause/replay requests cannot leak later autonomous work.
- Replay is byte-identical live-state isolation, including view-only selection and
  restoring the original live controlled drone on exit. Terminal/control errors fail
  safely. Tests cover queued commands and failures, not just idle worker states.
- Normal and 80x24 keyboard workflows/telemetry/replay hints pass; scripted demo stays
  unchanged. Full pytest, lint/format/types, wheel/import/CLI and terminal smoke pass.
- Architecture, implementation, simulation, QA and independent review evidence is
  recorded; blocking findings resolved; docs/NEXT reflect verified behavior.

## Definition of done, non-goals and status

Done when these criteria have executed evidence and remaining limitations are
reported. No sector assignment, independent drone exhaustion, target discovery,
planner optimization, new infrastructure or following product task. No commit, push,
merge or publication. Status: implemented and locally verified; owner manual acceptance/integration pending.
See [delivery evidence](../reports/010-hybrid-fleet-controls.md).
