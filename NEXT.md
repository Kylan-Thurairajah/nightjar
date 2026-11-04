# The next single task

Milestone 9's offline benchmarking and local release preparation are implemented:
**216 tests passed**, with reproducible raw results, lint/format/types, wheel/install
checks and independent review. See [the completed spec](docs/specs/009-benchmarking-release.md)
and [delivery evidence](docs/reports/009-benchmarking-release.md). Feature-branch
delivery is authorized; license selection, merging and public release require owner approval.

The next product task is **Hybrid Fleet TUI Control and Manual Handoff**.
Do not start it automatically. On an explicit request, use [the delivery workflow](docs/WORKFLOW.md)
and write a focused specification after inspecting the current provider, TUI and replay.
This closes the remaining Milestone 7 integration gap, rather than adding new planners.

Acceptance criteria for that next milestone:

- Support one user-controlled MANUAL drone while other active drones perform AUTO
  reconnaissance through the existing serial fleet scheduler.
- Define and test selection handoff: previous controlled drone returns to AUTO,
  newly controlled drone becomes MANUAL, and explicit IDLE parking remains respected.
  Resolve launch/Space/pause and configuration interactions in the spec before code;
  obtain approval for material workflow choices not covered by the user's stated goal.
- Preserve deterministic global tick budgets, collision rules, shared belief, planner
  ground-truth isolation and exactly-once action/replay capture across mixed rounds.
- Keep manual movement/scanning responsive and prevent replay from mutating live state.
  Preserve demo behavior, compact layout and discoverable shortcut semantics.
- Add seeded multi-drone and headless normal/narrow-terminal tests for handoff,
  continuing background AUTO activity, IDLE, terminal conditions and replay isolation.
- Obtain architecture/simulation/QA/independent review, run required gates and update
  docs with actual behavior. Stop at verification; commits, pushes, merges and release
  still require human approval.
