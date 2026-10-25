# The next single task

Connect the deterministic `GridWorld` to a single-agent simulation provider that the TUI can consume, while leaving the existing scripted multi-agent demo available and clearly labeled.

Done when:

- A typed frame from the provider exposes the agent position, grid obstacles, and simulation tick without exposing hidden data.
- A TUI single-step action advances the world through `GridWorld.step` and never moves the agent into a wall or outside the grid.
- The existing scripted demo and its tests continue to work unchanged.
- Core simulation modules remain independent of Textual and Rich.

Keep the synthetic belief field labeled as a demo; do not add inference, planning, persistence, or networking.
