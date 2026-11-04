# The next single task

Implement Milestone 8: Deterministic Replay and Mission Timeline.

Done when:

- Capture a reproducible serialized mission snapshot for each committed fleet round, including drone positions, modes, observations, and belief state.
- Rebuild a replay timeline from those snapshots without introducing networked services or external persistence.
- Expose replay controls for stepping backward/forward across deterministic mission history while preserving the current compact Textual layout.
- Add seed-based tests covering snapshot determinism and replay ordering across multiple drones.
- Keep core simulation logic independent from Textual, and leave the demo path unchanged unless it is needed for the replay workflow.
