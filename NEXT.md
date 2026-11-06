# Next task: Coordinated Assignments and Verified Discovery

Field Awareness and Fleet Identity (015) is implemented and locally verified:
**349 tests passed** after the grid-safe unit marker refinement. Compact ASCII unit designators/numeric display, owner-lettered trails,
equipment/doorways, room-entry logs, room coverage and T milestones are available.
See [spec015](docs/specs/015-field-awareness.md),
[delivery evidence](docs/reports/015-field-awareness.md) and the manual guide.

Next implement [spec016](docs/specs/016-coordinated-discovery.md):

- Persistent reachable search assignments, distinct owner markers and visible task
  reasons; reallocate on manual takeover, parking, blocked/unreachable route,
  completed scan and promising contact. Room boundaries remain passable.
- SEARCHING / CONTACT / VERIFYING / CONFIRMED, with one verifier and other drones
  continuing reconnaissance. A noisy positive reading or high belief is not success.
- Explicit one-tick exact-cell synthetic verification, manual and AUTO; failed
  verification updates the posterior, confirmed presence changes mission/UI outcome.
- Typed operational snapshots and strict version-2 validation, preserving legacy
  baseline benchmarks/comparisons and version-1 archive behavior.
- Focused deterministic model/assignment/budget/verification/replay tests plus
  architecture, simulation, QA and independent review. Run required regression gates.

Reconcile the concrete016 spec with the final015 code before implementation.
This handoff does not start016 automatically. Demo/blog014 remains deferred by owner
preference. The owner authorized committing and pushing the current 012/013/015
changes on 2026-11-06. Future commits, pushes, merges, new dependencies and
publication require separate authorization. Owner manual acceptance of these
changes remains unreported.
