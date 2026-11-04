---
name: simulation-verification
description: Verify Nightjar sensing, Bayesian inference, search planning, and deterministic scheduling using mathematical checks and reproducible simulation traces.
---

Read the affected core code and existing tests. Select relevant checks rather than
running statistical experiments by default:

- Belief: finite nonnegative probabilities, sum near one with justified tolerance,
  zero obstacle mass, entropy between zero and log2(candidate count), hand-computed
  likelihood updates, impossible evidence rejected without mutation.
- Information gain: compare against an independent small binary-partition calculation;
  an uninformative sensor gives zero gain. The implementation clamps gains to zero,
  so checking nonnegativity alone cannot detect a broken expectation calculation.
- State boundaries: inspect PlannerState construction and imports for hidden target
  leakage, copied read-only beliefs, and core independence from Textual/Rich.
- Determinism: repeat identical configuration and ordered actions; compare frames,
  observations, modes, positions, histories, tick counts, and belief arrays. Include
  multiple drones, blocked moves, budget exhaustion mid-round, and terminal no-ops.
- Scheduling: inspect actual action order, shared sensor/planner RNG consumption,
  collisions and reservations, and whether one planner stopping ends the fleet.

Use tests/test_belief.py, test_sensor.py, test_planning.py, test_provider.py, and
test_world.py as starting points. Review tasks remain read-only; report missing tests
and minimal public-API reproductions. Implementation tasks may add regression tests
within assigned ownership. Do not silently fix semantics during verification.

For requested benchmarks, record configuration, seed set, algorithm, versions, metric,
sample count, and uncertainty; keep expensive experiments outside PR CI. Report exact
commands/results, file locations, verified facts, and unverified assumptions.
