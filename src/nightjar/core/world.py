"""Deterministic, single-agent grid world used by simulation code."""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum
from typing import Iterable

Position = tuple[int, int]


class Direction(str, Enum):
    NORTH = "north"
    EAST = "east"
    SOUTH = "south"
    WEST = "west"


class BlockReason(str, Enum):
    BOUNDARY = "boundary"
    OBSTACLE = "obstacle"
    DRONE = "drone"


@dataclass(frozen=True)
class StepResult:
    position: Position
    moved: bool
    blocked_by: BlockReason | None
    tick: int


class GridWorld:
    """A rectangular grid with seeded obstacles and a hidden synthetic objective."""

    _DELTAS = {
        Direction.NORTH: (0, -1),
        Direction.EAST: (1, 0),
        Direction.SOUTH: (0, 1),
        Direction.WEST: (-1, 0),
    }
    _OBJECTIVE_SEED_SALT = 0x4E494748

    def __init__(
        self,
        width: int = 32,
        height: int = 16,
        seed: int = 0,
        *,
        obstacle_count: int | None = None,
        obstacles: Iterable[Position] | None = None,
        start_position: Position = (0, 0),
        reserved_positions: Iterable[Position] = (),
        include_hidden_objective: bool = True,
    ) -> None:
        if type(width) is not int or width < 1:
            raise ValueError("width must be a positive integer")
        if type(height) is not int or height < 1:
            raise ValueError("height must be a positive integer")
        if type(seed) is not int:
            raise ValueError("seed must be an integer")
        if (
            not isinstance(start_position, tuple)
            or len(start_position) != 2
            or any(type(coordinate) is not int for coordinate in start_position)
        ):
            raise ValueError("start_position must be an integer (x, y) coordinate tuple")
        if not (0 <= start_position[0] < width and 0 <= start_position[1] < height):
            raise ValueError(f"start position {start_position!r} is outside the grid")
        if obstacle_count is not None and (
            type(obstacle_count) is not int or obstacle_count < 0
        ):
            raise ValueError("obstacle_count must be a non-negative integer")
        if type(include_hidden_objective) is not bool:
            raise ValueError("include_hidden_objective must be a boolean")
        if obstacles is not None and obstacle_count is not None:
            raise ValueError("provide either obstacles or obstacle_count, not both")

        self._width = width
        self._height = height
        self._seed = seed
        self._position = start_position
        self._tick = 0

        available = [
            (x, y)
            for y in range(height)
            for x in range(width)
            if (x, y) != start_position
        ]
        if obstacles is not None:
            selected = set(obstacles)
            for position in selected:
                if (
                    not isinstance(position, tuple)
                    or len(position) != 2
                    or any(type(coordinate) is not int for coordinate in position)
                ):
                    raise ValueError("obstacles must be integer (x, y) coordinate tuples")
                x, y = position
                if not (0 <= x < width and 0 <= y < height):
                    raise ValueError(f"obstacle position {position!r} is outside the grid")
                if position == start_position:
                    raise ValueError("the starting position cannot be an obstacle")
        else:
            if obstacle_count is None:
                obstacle_count = min(len(available), width * height // 12)
            if obstacle_count > len(available):
                raise ValueError("obstacle_count cannot exceed the number of non-start cells")
            selected = set(random.Random(seed).sample(available, obstacle_count))

        self._obstacles = frozenset(selected)
        reserved = frozenset(reserved_positions)
        for position in reserved:
            if (
                not isinstance(position, tuple)
                or len(position) != 2
                or any(type(coordinate) is not int for coordinate in position)
            ):
                raise ValueError("reserved_positions must contain integer (x, y) tuples")
            x, y = position
            if not (0 <= x < width and 0 <= y < height):
                raise ValueError(f"reserved position {position!r} is outside the grid")
            if position in self._obstacles:
                raise ValueError("reserved positions cannot be obstacles")
        objective_candidates = [
            point
            for point in available
            if point not in self._obstacles
            and point not in reserved
            and point not in {
                (0, 0),
                (width - 1, 0),
                (0, height - 1),
                (width - 1, height - 1),
            }
        ]
        if not objective_candidates:
            objective_candidates = [
                point
                for point in available
                if point not in self._obstacles and point not in reserved
            ]
        if include_hidden_objective and not objective_candidates:
            raise ValueError("not enough free cells for a hidden objective")
        self._objective_candidates = tuple(objective_candidates)
        self._objective_position = (
            random.Random(seed ^ self._OBJECTIVE_SEED_SALT).choice(
                self._objective_candidates
            )
            if include_hidden_objective
            else None
        )

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    @property
    def seed(self) -> int:
        return self._seed

    @property
    def obstacles(self) -> frozenset[Position]:
        return self._obstacles

    @property
    def position(self) -> Position:
        return self._position

    @property
    def tick(self) -> int:
        return self._tick

    @property
    def objective_candidates(self) -> tuple[Position, ...]:
        """Return valid objective hypotheses without exposing sampled ground truth."""
        return self._objective_candidates

    def debug_objective_position(self) -> Position:
        """Return hidden ground truth for explicit tests and debugging only."""
        if self._objective_position is None:
            raise RuntimeError("this GridWorld does not contain a hidden objective")
        return self._objective_position

    def step(
        self,
        direction: Direction | str,
        *,
        occupied_positions: Iterable[Position] = (),
    ) -> StepResult:
        """Attempt one cardinal move, optionally blocking cells occupied by other drones."""
        try:
            action = Direction(direction)
        except (TypeError, ValueError) as error:
            raise ValueError(f"unsupported direction: {direction!r}") from error

        dx, dy = self._DELTAS[action]
        occupied = frozenset(occupied_positions)
        x, y = self._position
        destination = (x + dx, y + dy)
        reason: BlockReason | None = None
        if not (0 <= destination[0] < self._width and 0 <= destination[1] < self._height):
            reason = BlockReason.BOUNDARY
        elif destination in self._obstacles:
            reason = BlockReason.OBSTACLE
        elif destination in occupied:
            reason = BlockReason.DRONE
        else:
            self._position = destination

        self._tick += 1
        return StepResult(
            position=self._position,
            moved=reason is None,
            blocked_by=reason,
            tick=self._tick,
        )
