"""State provider for the deterministic single-agent GridWorld simulation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from nightjar.core.world import Direction, GridWorld, Position, StepResult


@dataclass(frozen=True)
class GridWorldFrame:
    width: int
    height: int
    position: Position
    obstacles: frozenset[Position]
    visited: frozenset[Position]
    path: tuple[Position, ...]
    tick: int
    events: tuple[str, ...]
    last_direction: Direction | None
    last_result: StepResult | None


class GridWorldSimulation:
    """Expose renderable GridWorld state and a deterministic sequence of moves."""

    _DEFAULT_DIRECTIONS = (
        Direction.EAST,
        Direction.SOUTH,
        Direction.WEST,
        Direction.NORTH,
    )

    def __init__(
        self,
        world: GridWorld | None = None,
        directions: Iterable[Direction | str] = _DEFAULT_DIRECTIONS,
    ) -> None:
        self._world = world if world is not None else GridWorld(seed=0)
        self._directions = tuple(Direction(direction) for direction in directions)
        if not self._directions:
            raise ValueError("directions must contain at least one movement")
        self._steps = 0
        self._visited: set[Position] = {self._world.position}
        self._path: list[Position] = [self._world.position]
        self._events: list[str] = ["[0000] GRIDWORLD READY / USE WASD TO MOVE"]
        self._last_direction: Direction | None = None
        self._last_result: StepResult | None = None

    def frame(self) -> GridWorldFrame:
        return GridWorldFrame(
            width=self._world.width,
            height=self._world.height,
            position=self._world.position,
            obstacles=self._world.obstacles,
            visited=frozenset(self._visited),
            path=tuple(self._path),
            tick=self._world.tick,
            events=tuple(self._events[-8:]),
            last_direction=self._last_direction,
            last_result=self._last_result,
        )

    def step(self, direction: Direction | str | None = None) -> GridWorldFrame:
        if direction is None:
            direction = self._directions[self._steps % len(self._directions)]
        else:
            direction = Direction(direction)
        self._last_result = self._world.step(direction)
        self._last_direction = direction
        self._steps += 1
        self._visited.add(self._last_result.position)
        if self._last_result.moved:
            self._path.append(self._last_result.position)
            result = (
                f"MOVED {direction.value.upper()} TO "
                f"({self._last_result.position[0]:02d},{self._last_result.position[1]:02d})"
            )
        else:
            reason = self._last_result.blocked_by
            if reason is None:
                raise RuntimeError("blocked GridWorld step did not include a reason")
            reason_label = "WALL" if reason.value == "obstacle" else reason.value.upper()
            result = f"BLOCKED BY {reason_label} MOVING {direction.value.upper()}"
        self._events.append(f"[{self._last_result.tick:04d}]  {result}")
        return self.frame()
