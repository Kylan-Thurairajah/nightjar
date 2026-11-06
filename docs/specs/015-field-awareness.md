# Field awareness and fleet identity

Owner requested user-facing operation features ahead of demo/blog/replay polish:
animal identities for three drones, richer fields, room entry logs, coverage,
mission milestones, persistent assignments and a real discovery sequence.
This first implementation slice delivers field awareness; the next operational
slice (016) implements persistent task allocation and verified discovery together.
No temporary target is presented as a permanent assignment or confirmed objective.

## Behavior and ownership

- Keep01RAVEN/02GHOST/03VIPER identities. Animal text glyphs (bird/owl/snake) and
  muted matching colors on live map/telemetry; G toggles numeric fallback. Text
  presentation requested, but actual glyph rendering depends on terminal fonts.
  IDs4-10 keep numeric fallback. No raster assets/dependencies or renamed archiveIDs.
- Color per-drone paths, mark shared routes distinctly, and color the latest AUTO
  destination only when owner can be derived from public recorded action. It remains
  latest fleet intent, not three fabricated persistent assignments.
- Facility has legible doorways and small equipment islands as actual obstacles,
  preserving connected walkable space, valid spawns and room labels at all sizes.
  Core/scenarios.py gains public SiteFeature(name,position,kind), layout.features.
  Wall/fixture geometry only; synthetic sensing still has no wall occlusion.
- Room entry notifications derive from successful recorded movement, not blocked
  attempts; doors do not spam fake room entries. Show relevant new entries in log.
- Coverage stays physical visitation, with selected-room visited percentage and
  detailed per-room counts; never label uncertain rooms CLEARED.
- T opens read-only mission milestones/room coverage; B includes concise field
  summary if useful. Deployed, firstscan, firstpositive(signal, notconfirmedcontact),
  room entries, coverage25/50/75 and actualstop derive from displayed public event
  prefix. No future records leak into historical view. No extra permanent panel.

Writer1: core/scenarios.py + tests/test_site_features.py.
Writer2: tui/map_widget.py, new tui/drone_identity.py, tests/test_drone_identity.py
and tests/test_map_presentation.py only.
Writer3: tui/app.py, tui/presentation.py, new tui/awareness.py, nightjar.tcss,
tests/test_field_awareness.py plus necessary existing test_tui/test_tui_replay
presentation assertion updates only. No concurrent shared edits.
Lead: docs/CI/source provenance/examples and integration/review.

## Acceptance and done

- Correct two-terminal-cell icons, numericfallback, three recognizable identities,
  matching path colors, real movement/geometry priority and no fixture/door deception.
- Connected facility at all supported sizes; true obstacle/island movement rules,
  valid1-10spawns; Open/Obstacle defaults and numerical models unchanged.
- Roomlogs/milestones only from acceptedmove/scans/eventprefix; no blockedentry,
  repeat-renderduplication or futurehistory. Physical roomcoveragecounts exclude
  walls/equipment. T/B pause behind acceptedwork and restore identical viewedstate.
- Normal/80x24 usablemap/coverage/log/footer/modal; demo/comparison not broken.
- Focused meaningful tests, one fullregression, existing gates and bounded independent
  actualdiff review; no repeated broad numerical sweeps. Correct affected blockers.
- Update README/design/architecture/roadmap/NEXT honestly. Record actual checks and
  distinguish completed015 from planned016. No new dependencies, commit/push/merge.
Status: implemented and locally verified on2026-11-06; owner manual review pending.
See [delivery evidence](../reports/015-field-awareness.md).
