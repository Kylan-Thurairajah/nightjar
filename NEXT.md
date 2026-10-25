# The next single task

Implement Milestone 3B: Multiple Drone Support and Selection.

Done when:

- Add support for a small, fixed number of independently positioned virtual drones in the GridWorld simulation without adding autonomous planning.
- Each drone's position, movement result, visited cells, and path are represented in simulation state independent of Textual.
- The TUI displays each drone clearly and uses the existing `Tab` control to select the active drone for manual WASD movement.
- Movement and collision results remain routed through `GridWorld.step()` semantics, with tests for selection, independent movement, collisions, and reproducibility.
- Existing demo mode remains functional.

Do not add sensors, Bayesian inference, networking, persistence, or new frameworks.
