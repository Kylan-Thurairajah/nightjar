# Next task: Persistent Search Assignments

The manual verified-discovery slice of milestone 016 is implemented locally:
candidate contacts, exact-cell verification, rejected-candidate belief updates,
confirmed mission status, map marking and replay-safe debrief. See the
[implementation note](docs/reports/016-verified-discovery.md).

Continue the remaining coordination work in [spec016](docs/specs/016-coordinated-discovery.md):

- Persistent reachable search assignments, distinct owner markers and visible task
  reasons; reallocate on manual takeover, parking, blocked/unreachable route,
  completed scan and promising contact. Room boundaries remain passable.
- Route one AUTO verifier to a candidate while the rest of the fleet continues
  reconnaissance; add bounded wait/yield behavior and mission-wide terminal rules.
- Public typed assignment snapshots and strict archive validation for operational
  task transitions, while retaining version-1 and baseline comparison behavior.
- Focused assignment, replay, capacity and hidden-state tests plus architecture,
  simulation, QA and full-regression checks.

Reconcile the concrete016 spec with the final015 code before implementation.
The approved 016 direction is in progress; this handoff lists only the remaining
assignment scope. Demo/blog014 remains deferred by owner preference. Future commits,
pushes, merges, new dependencies and publication require separate authorization.
