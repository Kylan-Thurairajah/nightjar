# Nightjar | Repository Instructions for Coding Agents

This file is the persistent source of truth for Codex and other coding agents working in this repository. **Read it before any task**, together with `NEXT.md` and `docs/DESIGN.md`. Keep it accurate when implementation decisions change. Do not rewrite it wholesale or silently expand scope.

## 1. Product goal
Nightjar is a **local-first, Python-only, simulation-only** research/portfolio application. Users run small, hypothetical 2D autonomous search scenarios through a restrained, military-inspired terminal interface. The technical substance is deterministic simulation, uncertain synthetic sensing, probabilistic inference, planning, benchmarking, and later reliable replay.

**Never** add real drone control, surveillance feeds, person tracking, actual through-wall detection, or integrations with physical sensing equipment. All points of interest and observations are synthetic.

## 2. Approved product design (preserve)
- Primary and final interface: **Textual + Rich TUI**, not React/web.
- Visual style: near-black background, dark forest-green grids and panels, subdued green foreground, restrained amber for higher probability or noteworthy observations. Minimal effects; clear typography, no unnecessary animation.
- Default world: approximately **32x16 cells**; small fixed-size maps, no zoom/pan or advanced navigation.
- Main screen: top mission/status header; central colored block-character map; right agent telemetry and belief-state panel; bottom event log and replay area; discoverable keyboard shortcut footer.
- Existing key map: Space play/pause; N single step; H heatmap; C coverage; P paths; Tab select agent; R replay; Left/Right seek when replaying; Q quit. A `?` shortcut help overlay may be added later if it improves discoverability.
- Prefer effectiveness and legibility to decorative polish. Always test narrow terminal widths without sacrificing normal desktop terminal layout.
- `docs/DESIGN.md` contains additional design details. Treat approved design as a constraint; ask before major aesthetic or workflow changes.

## 3. Scope and architecture
- **One Python application, one easy launch command**: `nightjar` after editable install, or `python -m nightjar`.
- Dependencies for MVP: Python 3.11+, Textual, Rich (transitive through Textual), NumPy, pytest. Prefer the existing package manager/build system in `pyproject.toml`.
- No FastAPI, React, TypeScript, PostgreSQL, Docker, Mesa, LangGraph, or microservices for MVP. Only suggest additions when a **specific implemented requirement** needs them and document the tradeoff before adding.
- `src/nightjar/core/`: deterministic world, sensing, inference, planning and state transitions. **Must not import Textual/Rich or depend on TUI widgets.**
- `src/nightjar/tui/`: rendering, shortcuts, screens and controls. Reads typed snapshots / invokes application services, not internal hidden simulation ground truth.
- `src/nightjar/services/` (when necessary): mission lifecycle and orchestration between core and TUI.
- `src/nightjar/storage/` (later, when needed): events/snapshots/replay. Start with simple local files if suitable; choose a database only with measured justification.
- Prefer small, explicit modules and pure functions. Avoid generic architecture/framework scaffolding before it is needed.

## 4. Modeling and correctness invariants
- Fixed random seeds must yield reproducible simulation results. Never depend on wall-clock scheduling for simulation outcomes.
- Keep hidden world/point-of-interest state separate from observations and agent beliefs. Planners must **never** receive hidden ground truth.
- Walls and bounds prevent invalid movement; the behavior for invalid actions must be explicit and tested.
- Belief arrays represent valid, normalized probability distributions; distinguish real Bayesian posterior calculations from synthetic display heatmaps.
- Separate **simulation ticks** from wall-clock/UI frame timing.
- Real benchmark claims require reproducible experiments. Never fabricate accuracy, speedups, search efficiency, or reliability numbers.
- State records should be designed for deterministic replay, but do not introduce event sourcing/storage until its milestone.
- Keep terminal UI responsive; don't run expensive computation on the UI event loop.

## 5. Agent working method (every task)
1. Read `AGENTS.md`, `NEXT.md`, `docs/DESIGN.md`, `README.md`, and relevant code/tests before modifying files.
2. Write a brief implementation plan listing the **smallest files** to touch. Respect the current milestone.
3. Implement one vertical slice, favoring the simplest correct code. Do not refactor unrelated code.
4. Add/extend tests for new logic and deterministic edge cases.
5. Run `python -m pytest -q` and any appropriate package/import/smoke checks. Launch the Textual app if the environment supports a terminal. Report explicitly if UI execution cannot be verified.
6. Summarize changed files, tests executed, what remains mock/demo, and any known limitations.
7. Update `NEXT.md` with **one actionable next milestone** and acceptance criteria when the current milestone is complete. Update `README.md` / `docs/DESIGN.md` only if actual behavior or decisions changed.
8. Update `AGENTS.md` **only when durable architectural, workflow, design or scope rules change**. Preserve user-approved constraints. Add a short dated entry to the Decision Log rather than rewriting the file repeatedly. If there is a conflict with a new user instruction, follow the user and update this file accordingly.

## 6. First milestone for the supplied starter
Follow `NEXT.md`: implement `src/nightjar/core/world.py` with a small deterministic `GridWorld`, obstacles, one virtual agent, and a `step(direction)` API. Test legal movement, out-of-bounds/wall blocking, and reproducibility. Integrate with the existing TUI only if it is a small, safe extension after core tests pass; otherwise retain the clearly labeled scripted demo. **Do not** implement Bayesian inference, multi-agent planning, FastAPI, databases, or a full project rewrite in this first task.

## 7. Definition of done
- The project installs and starts with documented commands where dependencies are available.
- New behavior has tests; regressions are not introduced.
- Real features and mock/demo features are clearly distinguished.
- `NEXT.md` accurately describes what Codex should do next.
- The military-style TUI design and Python-only architecture are preserved.

## Decision Log
- 2026-10-24: Approved a small-scale, local-first Python/Textual terminal product with understated military styling. No web frontend, zoom/pan, advanced map navigation, separate FastAPI server, or unnecessary infrastructure for MVP. Keep potential systems expansion optional and evidence-driven.
