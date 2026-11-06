# Mission presentation and debrief

Owner approved the presentation roadmap and immediate implementation, with focused
checks and no routine approval pauses. This is the first delivery slice: make the
mission understandable and visually engaging without changing inference/planners.

## Scope and plan

- Original Training Facility scenario with named rooms and door-connected walls for
  supported map sizes. Existing presets/defaults stay stable. Public room metadata
  derives from scenario/geometry; never from hidden objective or live config in replay.
- Configuration/preflight becomes a mission brief: fleet, action budget, one hidden
  synthetic objective, uncertain readings, Space to begin. Preserve launch/back flow.
- Map shows room identifiers, latest scan footprint and latest fleet planner target.
  Drone/wall priority preserved. Footprint is the current synthetic Manhattan model,
  not a physical visibility model. Brief readable observation explanation; negative
  readings decrease relative belief inside footprint for existing informative sensors,
  not proof of emptiness. Use restrained green/amber; no continuous decorative motion.
- Per-drone mode/room/activity summaries plus explicitly labelled latest FLEET intent.
  Existing snapshots lack per-drone decision ownership; never misattribute a target.
- Public-state mission summary/debrief with unique visited coverage, ticks, scans,
  uncertainty/entropy change, MAP confidence and actual stopping reason. Accessible
  via B (Brief / Debrief), terminal state prompts visibly to open it. No unexpected
  automatic modal stealing input. Modal pauses future AUTO scheduling, queues behind
  accepted work, and closes back to paused mission/replay. Q/Esc/Enter close it.
- Summary uses current viewed snapshot during replay and correct initial history
  entropy, no live-state leakage or provider thread reads. No target-found banner.

## File ownership

1. Scenario implementation: core/scenarios.py, core/mission.py,
   tui/mission_screens.py, focused tests/test_facility.py.
2. Map implementation: tui/map_widget.py, focused tests/test_map_presentation.py.
   Signature adds optional last_observation and planner_decision only; pure scenario
   room metadata import, no app access. Existing positional calls remain supported.
3. UI implementation: tui/app.py, tui/presentation.py, tui/nightjar.tcss,
   focused tests/test_presentation.py. Integrate map keywords and summary lifecycle.
4. Lead: roadmap/NEXT/design/README/architecture, CI gate/source provenance/report.

## Acceptance and definition of done

- Facility deterministic, all supported sizes connected/traversable with valid
  1-10 spawns/objective placement. Existing seeds/defaults unchanged.
- Brief/mission visuals/debrief work at normal and80x24; actual stats not fabricated.
- Latest scan/target tied only to displayed snapshot; walls/drones remain legible;
  historical target/footprint/summary never use future evidence.
- B modal uses safe pause/queued barrier, dismisses to same view, no simulation ticks
  from rendering; existing manual/AUTO/replay/demo controls remain intact.
- Focused new tests, full regression suite once, existing lint/types/format gates and
  bounded independent diff review. Correct blockers and rerun affected tests only.
  Existing numerical algorithms unchanged, so no redundant simulation sweeps.
- Docs reflect actual implementation and future comparison/demo/objective milestones.
  Done at locally verified delivery. No new dependency, commit/push/merge/publication.

Future stages are described in ROADMAP; they are not silently bundled into this UI
slice. Objective confirmation requires explicit semantics, kept separate from belief.
Status: implemented and locally verified; owner manual review pending.
See [delivery evidence](../reports/012-mission-presentation.md).
