# Fleet coordination: reduce overlapping AUTO searches

## Authorization and objective

Owner selected fleet coordination as the next development milestone after reporting
all supplied hybrid manual tests passed. Reduce duplicate exploration using public
fleet knowledge, preserving the existing Python/Textual simulation architecture.

## Behavior and bounded design

- Planners receive visited cells as the union of all drones' public visited histories,
  including MANUAL and IDLE histories. Rendering keeps individual drone histories.
- FRONTIER and INFORMATION GAIN prefer targets not already selected by an earlier
  AUTO drone in the same serial fleet round. Claims are soft preferences, not walls:
  routes may cross, sensing footprints may overlap, and when all otherwise eligible
  targets are claimed the original candidate set is used. Claims never cause STOP.
- Use a default-empty immutable `reserved_targets` field on PlannerState. Candidate
  filtering is before ordinary deterministic scoring; existing ties and IG likelihoods/
  utility remain unchanged. FRONTIER retains frontier-first then unvisited fallback.
- Round claims are local to fleet_round, accumulated from successful AUTO MOVE
  decisions, reset each round, and never retained across pause, handoff or replay.
  Direct autonomous_step uses shared coverage and no cross-call target claims.
- RANDOM remains a seeded baseline; fleet-global scan de-duplication already applies
  to every policy. Single-drone traces must remain unchanged.
- Preserve stable roster order, one action per eligible drone, current global tick
  budget/collisions, shared belief/RNG and mission-wide planner STOP. No WAIT action,
  per-drone exhaustion, sector partitions, persistent assignments or new dependency.
- Existing snapshots/actions suffice for replay; no archive schema or historical
  resume change. Targets remain existing public PlannerDecision metadata.
- Keep current UI controls and committed-state background execution unchanged.

## Plan and ownership

1. Implementation agent: planning.py/provider.py plus focused new coordination tests.
   Extend immutable planner input, shared coverage and round-local preferences only.
2. Lead: docs/spec/report/NEXT, benchmark metadata/fingerprint reconciliation and CI
   formatter allowlist. Preserve all preceding uncommitted hybrid work.
3. Simulation, QA and independent reviewer inspect actual code and run bounded checks;
   lead fixes blockers within scope and runs full gates/package/TUI smoke.

## Acceptance criteria

- Fixture tests prove shared manual/AUTO coverage reaches planners while per-drone
  histories remain intact, and FRONTIER avoids another drone's already-covered cells.
- Both purposeful policies choose an unclaimed eligible target when one exists;
  fallback preserves action/STOP semantics when all candidates are claimed.
- Serial multi-AUTO tests prove distinct target choices on a deliberately overlapping
  fixture and round-local reset, with manual/IDLE exclusion and no extra ticks.
- Repeated seeds/ordered commands reproduce events/snapshots/observations/belief.
  Narrow corridors, inaccessible regions, collisions, budget cutoff, terminal no-ops,
  capacity rejection and replay viewing/JSON reload preserve invariants.
- RANDOM and single-drone baseline traces remain unchanged. No hidden objective input.
- Provide a reproducible focused overlap example; do not claim general efficiency,
  entropy improvement or sensing-footprint separation from a small fixture.
- Run full pytest, Ruff/check/CI format, mypy, wheel/import/CLI and relevant normal/
  narrow headless TUI checks. Obtain architecture/simulation/QA/independent review.
- Document limitations, measured evidence, manual test commands and one next handoff.

## Definition of done

All criteria have actual test/review evidence and blockers are resolved; documentation
matches implemented behavior. Stop at local verification. No commit/push/merge or
next feature execution without owner authorization. Status: implemented and locally verified; coordination manual acceptance pending.
See [evidence](../reports/011-fleet-coordination.md).
