# Milestone 8: Mission Replay and Event Reliability

## Objective

Inspect committed synthetic mission history backward and forward without changing
the live mission or re-running stochastic sensing/planning.

## Current implementation context

See ../ARCHITECTURE.md. GridWorldSimulation exposes current frames, ordered
observations, and formatted event strings. The fleet API exists; the TUI advances
one selected AUTO drone. No serialized timeline or state reconstruction exists.
Demo replay recalculates scripted frames. See ../reports/workflow-bootstrap.md for
the scheduler audit; milestone numbering alone does not establish fleet correctness.

## Functional requirements

1. Define typed, ordered events with stable sequence numbers and simulation ticks;
   include accepted actions, blocked attempts, scans, mode changes, and terminal state.
   Define rejected actions and no-op behavior explicitly before implementation.
2. Capture an initial state and a reproducible serialized snapshot at each committed
   fleet-round boundary, including positions, modes, histories, observations, shared
   belief, mission status, and tick. Specify capture boundaries for existing direct
   manual/selected-AUTO calls so the TUI cannot bypass history.
3. Reconstruct a read-only timeline from snapshots and ordered records in memory;
   serialize using simple versioned local data structures with validation. No external
   persistence service is required. Retain enough precision for belief fidelity and
   keep hidden objectives out of public replay frames and planner inputs.
4. R enters/exits GridWorld replay; Left/Right seek with clamped endpoints. Pause live
   advancement during replay, reject mutation controls there, and return to the
   unchanged latest live state on exit. Preserve the compact layout and demo path.
5. Define sequence/tick/round relationships when a round ends early. Reject malformed,
   duplicate, out-of-order, or incompatible-version records without partial mutation.

## Architectural constraints

Follow ../../AGENTS.md and ../DESIGN.md. Core records/reconstruction cannot import
Textual/Rich. Replay viewing must consume recorded state, not sample RNGs. Resuming
simulation from historical snapshots is outside scope, so RNG-state restoration is
not required. Bound history according to the mission budget and document memory cost.

## Acceptance criteria

- Same configuration and ordered actions yield equal serialized events/snapshots.
- Reconstructed positions, modes, observations, belief and status match captured
  states at every boundary across multiple drones; seeking never changes live state.
- Every accepted committed action appears once in stable order; terminal and partial
  rounds have explicit behavior. Budget cannot be exceeded by queued actions.
- GridWorld replay controls work at normal and narrow terminal sizes; demo behavior
  remains covered. Invalid record loads fail atomically with a useful error.
- Complete repository gates, simulation review, independent review, and QA evidence.

## Required tests

Seeded multi-drone traces; empty history and initial state; blocked moves; multiple
scans/shared posterior; mode changes; mixed MANUAL/AUTO/IDLE; budget exhausted
mid-round; planner STOP; terminal no-ops; serialization round trips; ordering/version
validation; belief numerical fidelity; seek limits and live-state preservation;
headless Textual controls and compact layout; unchanged demo replay.

## Non-goals

Benchmarks (Milestone 9), databases, network services, historical branching/resume,
new planners, physical integrations, UI redesign, or fixing unrelated simulation bugs.

## Completion status

Implemented and verified locally; human integration approval pending. Architecture analysis resolved prerequisites by preserving
actual stable roster order and mission-wide planner exhaustion, correcting the
manual-first docstring, and fixing the specified budget guard. Capture covers both
direct actions and round boundaries. No new planner or scheduling policy is introduced.
All acceptance criteria have evidence in [the delivery report](../reports/008-mission-replay.md):
190 tests, deterministic experiments, simulation/QA/independent review, lint/format,
all-core types, wheel build and terminal smoke. Blockers were corrected and independently
rechecked. There is no disk save/load UI or historical resume; these remain non-goals.

## Definition of done

Acceptance criteria verified, required checks passed, blocking findings resolved,
documentation and NEXT reconciled with final code, and remaining limitations reported.
Met for this implementation. Stop here; commits, pushes, merges and Milestone 9 need
separate human authorization.
