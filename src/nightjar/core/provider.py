"""State provider for deterministic, manually controlled GridWorld drones."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from nightjar.core.world import BlockReason, Direction, GridWorld, Position, StepResult


DRONE_CALLSIGNS = (
    "RAVEN",
    "GHOST",
    "VIPER",
    "FALCON",
    "SPECTER",
    "WRAITH",
    "HAWK",
    "PHANTOM",
    "TALON",
    "SHADE",
)


class OperationalMode(str, Enum):
    MANUAL = "MANUAL"
    AUTO = "AUTO"
    IDLE = "IDLE"


class MissionStatus(str, Enum):
    ACTIVE = "ACTIVE"
    BUDGET_EXHAUSTED = "BUDGET EXHAUSTED"


@dataclass(frozen=True)
class DroneFrame:
    identifier: str
    callsign: str
    position: Position
    visited: frozenset[Position]
    path: tuple[Position, ...]
    mode: OperationalMode
    tick: int
    last_direction: Direction | None
    last_result: StepResult | None

    @property
    def moves(self) -> int:
        return len(self.path) - 1


@dataclass(frozen=True)
class GridWorldFrame:
    width: int
    height: int
    obstacles: frozenset[Position]
    drones: tuple[DroneFrame, ...]
    tick: int
    events: tuple[str, ...]
    operation_name: str
    mission_id: str
    scenario: str
    seed: int
    max_ticks: int | None
    status: MissionStatus

    @property
    def position(self) -> Position:
        """Compatibility view of the first drone's position."""
        return self.drones[0].position

    @property
    def visited(self) -> frozenset[Position]:
        """Compatibility view of the first drone's visited cells."""
        return self.drones[0].visited

    @property
    def path(self) -> tuple[Position, ...]:
        """Compatibility view of the first drone's path."""
        return self.drones[0].path

    @property
    def last_direction(self) -> Direction | None:
        return self.drones[0].last_direction

    @property
    def last_result(self) -> StepResult | None:
        return self.drones[0].last_result

    def drone(self, identifier: str) -> DroneFrame:
        for drone in self.drones:
            if drone.identifier == identifier:
                return drone
        raise KeyError(f"unknown drone: {identifier}")


@dataclass
class _Drone:
    identifier: str
    callsign: str
    world: GridWorld
    visited: set[Position]
    path: list[Position]
    mode: OperationalMode = OperationalMode.MANUAL
    last_direction: Direction | None = None
    last_result: StepResult | None = None

    def frame(self) -> DroneFrame:
        return DroneFrame(
            identifier=self.identifier,
            callsign=self.callsign,
            position=self.world.position,
            visited=frozenset(self.visited),
            path=tuple(self.path),
            mode=self.mode,
            tick=self.world.tick,
            last_direction=self.last_direction,
            last_result=self.last_result,
        )


class GridWorldSimulation:
    """Own drone state and route every movement attempt through GridWorld.step."""

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
        *,
        drone_count: int = 3,
        initial_mode: OperationalMode | str = OperationalMode.MANUAL,
        max_ticks: int | None = None,
        operation_name: str = "GRIDWORLD",
        scenario: str = "obstacle_field",
    ) -> None:
        if type(drone_count) is not int or not 1 <= drone_count <= len(DRONE_CALLSIGNS):
            raise ValueError(
                f"drone_count must be between 1 and {len(DRONE_CALLSIGNS)}"
            )
        if max_ticks is not None and (type(max_ticks) is not int or max_ticks < 1):
            raise ValueError("max_ticks must be a positive integer")
        initial_mode = OperationalMode(initial_mode)
        if initial_mode is OperationalMode.AUTO:
            raise ValueError("initial_mode supports MANUAL or IDLE, not AUTO")
        if not operation_name.strip():
            raise ValueError("operation_name must not be empty")
        self._directions = tuple(Direction(direction) for direction in directions)
        if not self._directions:
            raise ValueError("directions must contain at least one movement")

        base_world = world if world is not None else GridWorld(seed=0)
        self._width = base_world.width
        self._height = base_world.height
        self._obstacles = base_world.obstacles
        starts = self._initial_positions(base_world.position, drone_count)
        self._drones: list[_Drone] = []
        for index, position in enumerate(starts):
            drone_world = (
                base_world
                if index == 0
                else GridWorld(
                    width=self._width,
                    height=self._height,
                    seed=base_world.seed,
                    obstacles=self._obstacles,
                    start_position=position,
                )
            )
            identifier = f"{index + 1:02d}"
            callsign = DRONE_CALLSIGNS[index]
            self._drones.append(
                _Drone(
                    identifier=identifier,
                    callsign=callsign,
                    world=drone_world,
                    visited={position},
                    path=[position],
                    mode=initial_mode,
                )
            )

        self._tick = 0
        self._events = ["[0000] GRIDWORLD READY / USE WASD TO MOVE"]
        self._steps = 0
        self._operation_name = operation_name
        self._mission_id = _mission_identifier(operation_name)
        self._scenario = scenario
        self._seed = base_world.seed
        self._max_ticks = max_ticks
        self._status = MissionStatus.ACTIVE

    def _initial_positions(self, first_position: Position, count: int) -> tuple[Position, ...]:
        corners = (
            (0, 0),
            (self._width - 1, self._height - 1),
            (self._width - 1, 0),
            (0, self._height - 1),
        )
        candidates = (first_position, *corners)
        candidates += tuple(
            (x, y)
            for y in range(self._height)
            for x in range(self._width)
        )
        positions: list[Position] = []
        for point in candidates:
            if point not in self._obstacles and point not in positions:
                positions.append(point)
                if len(positions) == count:
                    return tuple(positions)
        raise ValueError("the grid does not contain enough free cells for all drones")

    def frame(self) -> GridWorldFrame:
        return GridWorldFrame(
            width=self._width,
            height=self._height,
            obstacles=self._obstacles,
            drones=tuple(drone.frame() for drone in self._drones),
            tick=self._tick,
            events=tuple(self._events[-8:]),
            operation_name=self._operation_name,
            mission_id=self._mission_id,
            scenario=self._scenario,
            seed=self._seed,
            max_ticks=self._max_ticks,
            status=self._status,
        )

    def set_mode(self, drone_id: str, mode: OperationalMode | str) -> None:
        drone = self._get_drone(drone_id)
        drone.mode = OperationalMode(mode)
        self._events.append(
            f"[{self._tick:04d}]  {drone.identifier} {drone.callsign} MODE {drone.mode.value}"
        )

    def step(
        self,
        direction: Direction | str | None = None,
        *,
        drone_id: str | None = None,
    ) -> GridWorldFrame:
        if self._status is MissionStatus.BUDGET_EXHAUSTED:
            return self.frame()
        identifier = self._drones[0].identifier if drone_id is None else drone_id
        drone = self._get_drone(identifier)
        if drone.mode is not OperationalMode.MANUAL:
            raise ValueError(f"drone {drone.identifier} is not in MANUAL mode")
        if direction is None:
            direction = self._directions[self._steps % len(self._directions)]
        else:
            direction = Direction(direction)

        occupied = {
            other.world.position
            for other in self._drones
            if other is not drone
        }
        result = drone.world.step(direction, occupied_positions=occupied)
        drone.last_direction = direction
        drone.last_result = result
        drone.visited.add(result.position)
        if result.moved:
            drone.path.append(result.position)
            description = (
                f"{drone.identifier} {drone.callsign} MOVED {direction.value.upper()} TO "
                f"({result.position[0]:02d},{result.position[1]:02d})"
            )
        else:
            reason = result.blocked_by
            if reason is None:
                raise RuntimeError("blocked GridWorld step did not include a reason")
            reason_label = {
                BlockReason.OBSTACLE: "WALL",
                BlockReason.BOUNDARY: "BOUNDARY",
                BlockReason.DRONE: "DRONE COLLISION",
            }[reason]
            description = (
                f"{drone.identifier} {drone.callsign} BLOCKED BY {reason_label} "
                f"MOVING {direction.value.upper()}"
            )
        self._tick += 1
        self._steps += 1
        self._events.append(f"[{self._tick:04d}]  {description}")
        if self._max_ticks is not None and self._tick >= self._max_ticks:
            self._status = MissionStatus.BUDGET_EXHAUSTED
            self._events.append(
                f"[{self._tick:04d}]  MISSION COMPLETE / TICK BUDGET EXHAUSTED"
            )
        return self.frame()

    def _get_drone(self, drone_id: str) -> _Drone:
        for drone in self._drones:
            if drone.identifier == drone_id:
                return drone
        raise KeyError(f"unknown drone: {drone_id}")


def _mission_identifier(operation_name: str) -> str:
    return "-".join(operation_name.strip().upper().replace("_", " ").split())
