# The next single task

Fleet coordination is implemented and locally verified: **270 tests passed**, with
architecture, implementation, simulation, QA and independent review. See
[spec011](docs/specs/011-fleet-coordination.md) and [evidence](docs/reports/011-fleet-coordination.md).

AUTO planners now share fleet visited coverage. FRONTIER and INFORMATION GAIN prefer
unclaimed eligible targets within each serial round, falling back when needed.
Routes/sensing areas may overlap; there are no fixed sectors or persistent claims.
Hybrid controls and global stopping/budget rules remain unchanged.

## Next: coordination manual acceptance and integration review

Use [the manual guide's milestone011 section](docs/MANUAL_TESTING.md#fleet-coordination-follow-up-milestone-011).
Owner acceptance of the earlier hybrid controls is recorded; the coordination change
has not yet been manually accepted by the owner.

Acceptance criteria:

- Run three drones with FRONTIER then INFORMATION GAIN. Move/scan selected MANUAL,
  run other AUTO drones, check paths/coverage, handoff and parking. Shared transit
  paths are valid; exact target avoidance has seeded automated evidence.
- Verify N/pause, normal/compact layout and replay selection/exit preserve live state
  and control. Record actual owner results and fix any reproducible blockers.
- Review diff/report before integration; obtain explicit approval for commit, push
  or merge. Existing uncommitted hybrid work must remain preserved.
- Stop at acceptance/integration review. New features, license and public release
  need separate authorization; do not automatically begin another product milestone.
