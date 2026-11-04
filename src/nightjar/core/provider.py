"""State provider for deterministic, manually controlled GridWorld drones."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Iterable, Iterator

if TYPE_CHECKING:
    from nightjar.core.replay import MissionSnapshot, ReplayTimeline

from nightjar.core.belief import BeliefMap, BeliefSnapshot, BeliefStats
from nightjar.core.planning import (
    PlannerActionType,
    PlannerDecision,
    PlannerState,
    SearchStrategy,
    create_planner,
)
from nightjar.core.sensor import (
    Observation,
    ProximitySensor,
    SensorConfig,
    SensorType,
)
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
    PLANNER_EXHAUSTED = "PLANNER EXHAUSTED"


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
        sensor_config: SensorConfig | None = None,
        search_strategy: SearchStrategy = SearchStrategy.INFORMATION_GAIN,
        history_capacity: int | None = None,
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
        if not isinstance(search_strategy, SearchStrategy):
            raise ValueError("search_strategy must be a supported SearchStrategy")
        self._directions = tuple(Direction(direction) for direction in directions)
        if not self._directions:
            raise ValueError("directions must contain at least one movement")

        base_world = world if world is not None else GridWorld(seed=0)
        self._width = base_world.width
        self._height = base_world.height
        self._obstacles = base_world.obstacles
        starts = self._initial_positions(
            base_world.position,
            drone_count,
        )
        mission_world = GridWorld(
            width=self._width,
            height=self._height,
            seed=base_world.seed,
            obstacles=self._obstacles,
            start_position=base_world.position,
            reserved_positions=starts,
        )
        self._objective_position = mission_world.debug_objective_position()
        self._drones: list[_Drone] = []
        for index, position in enumerate(starts):
            drone_world = (
                mission_world
                if index == 0
                else GridWorld(
                    width=self._width,
                    height=self._height,
                    seed=base_world.seed,
                    obstacles=self._obstacles,
                    start_position=position,
                    include_hidden_objective=False,
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
        self._search_strategy = search_strategy
        self._planner = create_planner(search_strategy, base_world.seed ^ 0x504C414E)
        self._last_planner_decision: PlannerDecision | None = None
        self._belief_map = BeliefMap(
            self._width,
            self._height,
            self._obstacles,
            mission_world.objective_candidates,
            self._mission_id,
        )
        if sensor_config is not None and not isinstance(sensor_config, SensorConfig):
            raise ValueError("sensor_config must be a SensorConfig")
        self._sensor_config = (
            sensor_config if sensor_config is not None else SensorConfig()
        )
        self._sensor = ProximitySensor(self._sensor_config, base_world.seed)
        self._observations: list[Observation] = []
        self._observation_sequences = {drone.identifier: 0 for drone in self._drones}
        self._manual_requests: dict[str, Direction] = {}
        self._reservations: dict[str, Position] = {}
        from nightjar.core.replay import MissionEvent

        capacity = max(2048, 2 * (max_ticks or 0) + 1)
        if history_capacity is not None:
            if type(history_capacity) is not int or history_capacity < 1:
                raise ValueError("history_capacity must be a positive integer")
            capacity = history_capacity
        self._history_capacity = capacity
        self._recorded_events: list[MissionEvent] = []
        self._snapshots: list[MissionSnapshot] = []
        self._capture_depth = 0
        self._boundary_start = 0
        self._snapshots.append(self.snapshot())

    @property
    def history(self) -> ReplayTimeline:
        """Immutable committed history; queue preparation is not a committed action."""
        from nightjar.core.replay import ReplayTimeline

        return ReplayTimeline(tuple(self._snapshots), tuple(self._recorded_events))

    def snapshot(self) -> MissionSnapshot:
        """Copy public viewing state without exposing RNGs or hidden objectives."""
        from nightjar.core.replay import MissionSnapshot

        return MissionSnapshot(
            index=max(0, len(self._snapshots) - (self._capture_depth == 0)),
            event_sequence=len(self._recorded_events),
            frame=self.frame(),
            observations=self.observations,
            belief=self.belief_map,
            sensor_config=self.sensor_config,
            search_strategy=self.search_strategy,
            last_planner_decision=self.last_planner_decision,
        )

    @contextmanager
    def _boundary(self) -> Iterator[None]:
        self._begin_boundary()
        try:
            yield
        finally:
            self._end_boundary()

    def _begin_boundary(self) -> None:
        from nightjar.core.replay import HistoryCapacityError

        if self._capture_depth == 0:
            if len(self._snapshots) >= self._history_capacity:
                raise HistoryCapacityError(
                    "Mission history is full; replay/export the recorded mission "
                    "or start a new mission before another action."
                )
            self._boundary_start = len(self._recorded_events)
        self._capture_depth += 1

    def _end_boundary(self) -> None:
        self._capture_depth -= 1
        if (
            self._capture_depth == 0
            and len(self._recorded_events) > self._boundary_start
        ):
            from dataclasses import replace

            self._snapshots.append(replace(self.snapshot(), index=len(self._snapshots)))

    def _record(self, kind: str, drone_id: str | None = None, **details: str) -> None:
        from nightjar.core.replay import MissionEvent

        self._recorded_events.append(
            MissionEvent(
                sequence=len(self._recorded_events) + 1,
                tick=self._tick,
                boundary=len(self._snapshots),
                kind=kind,
                drone_id=drone_id,
                details=tuple(sorted(details.items())),
            )
        )

    def _initial_positions(
        self,
        first_position: Position,
        count: int,
    ) -> tuple[Position, ...]:
        corners = (
            (0, 0),
            (self._width - 1, self._height - 1),
            (self._width - 1, 0),
            (0, self._height - 1),
        )
        candidates: tuple[Position, ...] = (first_position, *corners)
        candidates += tuple(
            (x, y) for y in range(self._height) for x in range(self._width)
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

    @property
    def sensor_config(self) -> SensorConfig:
        return self._sensor_config

    @property
    def search_strategy(self) -> SearchStrategy:
        return self._search_strategy

    @property
    def last_planner_decision(self) -> PlannerDecision | None:
        return self._last_planner_decision

    @property
    def observations(self) -> tuple[Observation, ...]:
        return tuple(self._observations)

    @property
    def belief_map(self) -> BeliefSnapshot:
        return self._belief_map.snapshot()

    @property
    def belief_stats(self) -> BeliefStats:
        return self._belief_map.stats

    def debug_objective_position(self) -> Position:
        """Return hidden ground truth for explicit tests and debugging only."""
        return self._objective_position

    @property
    def reservations(self) -> frozenset[Position]:
        return frozenset(self._reservations.values())

    def queue_manual_action(
        self, drone_id: str, direction: Direction | str
    ) -> Direction:
        """Queue one explicit movement for the next serial fleet round."""
        if self._status is not MissionStatus.ACTIVE:
            raise ValueError("cannot queue movement after the mission has ended")
        drone = self._get_drone(drone_id)
        if drone.mode is not OperationalMode.MANUAL:
            raise ValueError(f"drone {drone.identifier} is not in MANUAL mode")
        requested = Direction(direction)
        self._manual_requests[drone.identifier] = requested
        self._events.append(
            f"[{self._tick:04d}]  {drone.identifier} {drone.callsign} QUEUED MOVE {requested.value.upper()}"
        )
        # Queue replacement is uncommitted preparation, so do not retain an
        # unbounded string log while no simulation ticks are advancing.
        self._events[:] = self._events[-8:]
        return requested

    def clear_manual_action(self, drone_id: str) -> None:
        self._manual_requests.pop(drone_id, None)

    def set_mode(self, drone_id: str, mode: OperationalMode | str) -> None:
        drone = self._get_drone(drone_id)
        requested = OperationalMode(mode)
        if self._status is not MissionStatus.ACTIVE or requested is drone.mode:
            return
        with self._boundary():
            drone.mode = requested
            self._reservations.pop(drone.identifier, None)
            self._manual_requests.pop(drone.identifier, None)
            self._events.append(
                f"[{self._tick:04d}]  {drone.identifier} {drone.callsign} MODE {drone.mode.value}"
            )
            self._record("mode", drone.identifier, mode=drone.mode.value)

    def fleet_round(self) -> GridWorldFrame:
        """Process each drone once in stable roster order, interleaving its mode."""
        if self._status is not MissionStatus.ACTIVE:
            return self.frame()

        if not self._manual_requests and not any(
            drone.mode is OperationalMode.AUTO for drone in self._drones
        ):
            return self.frame()
        with self._boundary():
            ordered_ids = [drone.identifier for drone in self._drones]
            for drone_id in ordered_ids:
                if self._status is not MissionStatus.ACTIVE:
                    break
                drone = self._get_drone(drone_id)
                queued = self._manual_requests.pop(drone_id, None)
                if queued is not None:
                    if drone.mode is not OperationalMode.MANUAL:
                        continue
                    self._move_drone(drone, queued, autonomous=False)
                    continue
                if drone.mode is OperationalMode.AUTO:
                    self._resolve_autonomous_action(drone)
            return self.frame()

    def step_fleet(self) -> GridWorldFrame:
        return self.fleet_round()

    def run_fleet_round(self) -> GridWorldFrame:
        return self.fleet_round()

    def advance_fleet(self) -> GridWorldFrame:
        return self.fleet_round()

    def scan(self, drone_id: str) -> Observation:
        """Collect one synthetic reading and consume one mission tick."""
        if self._status is not MissionStatus.ACTIVE:
            raise ValueError("cannot scan after the mission has ended")
        drone = self._get_drone(drone_id)
        with self._boundary():
            positive = self._sensor.scan(drone.world.position, self._objective_position)
            self._tick += 1
            self._observation_sequences[drone.identifier] += 1
            observation = Observation(
                mission_id=self._mission_id,
                observation_id=f"{self._mission_id}-OBS-{len(self._observations) + 1:06d}",
                drone_id=drone.identifier,
                tick=self._tick,
                position=drone.world.position,
                sensor_type=SensorType.PROXIMITY,
                positive=positive,
                sensor_config=self._sensor_config,
                sequence_number=self._observation_sequences[drone.identifier],
            )
            previous_entropy = self._belief_map.stats.entropy_bits
            belief_stats = self._belief_map.update(observation)
            self._observations.append(observation)
            reading = "POSITIVE" if positive else "NEGATIVE"
            auto_label = " AUTO" if drone.mode is OperationalMode.AUTO else ""
            self._events.append(
                f"[{self._tick:04d}]  {drone.callsign}{auto_label} SENSOR SCAN INITIATED"
            )
            self._events.append(
                f"[{self._tick:04d}]  {drone.callsign} PROXIMITY: {reading} "
                f"| ΔH {belief_stats.entropy_bits - previous_entropy:+.2f} bits"
            )
            self._record(
                "scan", drone.identifier, observation_id=observation.observation_id
            )
            if self._max_ticks is not None and self._tick >= self._max_ticks:
                self._status = MissionStatus.BUDGET_EXHAUSTED
                self._events.append(
                    f"[{self._tick:04d}]  MISSION COMPLETE / TICK BUDGET EXHAUSTED"
                )
                self._record("terminal", status=self._status.value)
            return observation

    def step(
        self,
        direction: Direction | str | None = None,
        *,
        drone_id: str | None = None,
    ) -> GridWorldFrame:
        if self._status is not MissionStatus.ACTIVE:
            return self.frame()
        identifier = self._drones[0].identifier if drone_id is None else drone_id
        drone = self._get_drone(identifier)
        if drone.mode is not OperationalMode.MANUAL:
            raise ValueError(f"drone {drone.identifier} is not in MANUAL mode")
        if direction is None:
            direction = self._directions[self._steps % len(self._directions)]
        else:
            direction = Direction(direction)

        with self._boundary():
            self._move_drone(drone, direction, autonomous=False)
            return self.frame()

    def _resolve_autonomous_action(self, drone: _Drone) -> GridWorldFrame:
        """Execute the planner-selected action for a single AUTO drone."""
        if self._status is not MissionStatus.ACTIVE:
            return self.frame()
        if drone.mode is not OperationalMode.AUTO:
            raise ValueError(f"drone {drone.identifier} is not in AUTO mode")

        occupied = frozenset(
            other.world.position for other in self._drones if other is not drone
        ) | frozenset(self._reservations.values())
        permitted_moves: list[Direction] = []
        x, y = drone.world.position
        deltas = {
            Direction.NORTH: (0, -1),
            Direction.EAST: (1, 0),
            Direction.SOUTH: (0, 1),
            Direction.WEST: (-1, 0),
        }
        for direction in deltas:
            dx, dy = deltas[direction]
            destination = (x + dx, y + dy)
            if (
                0 <= destination[0] < self._width
                and 0 <= destination[1] < self._height
                and destination not in self._obstacles
                and destination not in occupied
            ):
                permitted_moves.append(direction)

        scanned_positions = frozenset(
            observation.position for observation in self._observations
        )
        state = PlannerState(
            width=self._width,
            height=self._height,
            obstacles=self._obstacles,
            position=drone.world.position,
            traversable=frozenset(
                (cell_x, cell_y)
                for cell_y in range(self._height)
                for cell_x in range(self._width)
                if (cell_x, cell_y) not in self._obstacles
            ),
            visited=frozenset(drone.visited),
            movement_history=tuple(drone.path),
            scanned_positions=scanned_positions,
            occupied_positions=occupied,
            permitted_moves=tuple(permitted_moves),
            scan_permitted=drone.world.position not in scanned_positions,
            belief=self._belief_map.snapshot(),
            sensor_config=self._sensor_config,
            remaining_budget=(
                None if self._max_ticks is None else self._max_ticks - self._tick
            ),
        )
        decision = self._planner.decide(state)
        self._last_planner_decision = decision
        action = decision.action
        if action.type is PlannerActionType.STOP:
            self._status = MissionStatus.PLANNER_EXHAUSTED
            self._events.append(
                f"[{self._tick:04d}]  {self._search_strategy.label} PLANNER EXHAUSTED"
            )
            self._record("stop", drone.identifier)
            self._record("terminal", status=self._status.value)
        elif action.type is PlannerActionType.SCAN:
            if not state.scan_permitted:
                raise RuntimeError(
                    "planner returned a scan at an already scanned position"
                )
            self.scan(drone.identifier)
        elif action.type is PlannerActionType.MOVE:
            if (
                action.direction is None
                or action.direction not in state.permitted_moves
            ):
                raise RuntimeError("planner returned a movement that is not permitted")
            self._move_drone(drone, action.direction, autonomous=True)
        else:
            raise RuntimeError(f"planner returned unsupported action: {action.type!r}")
        return self.frame()

    def autonomous_step(self, drone_id: str) -> GridWorldFrame:
        """Execute at most one planner-selected movement or scan action."""
        if self._status is not MissionStatus.ACTIVE:
            return self.frame()
        drone = self._get_drone(drone_id)
        if drone.mode is not OperationalMode.AUTO:
            raise ValueError(f"drone {drone.identifier} is not in AUTO mode")
        with self._boundary():
            frame = self._resolve_autonomous_action(drone)
            return frame

    def _move_drone(
        self,
        drone: _Drone,
        direction: Direction,
        *,
        autonomous: bool,
    ) -> None:
        occupied = {
            other.world.position for other in self._drones if other is not drone
        }
        reserved = self._reservations.copy()
        for drone_id, destination in reserved.items():
            if drone_id != drone.identifier:
                occupied.add(destination)
        if drone.identifier in self._reservations:
            self._reservations[drone.identifier] = (
                drone.world.position[0],
                drone.world.position[1],
            )
        result = drone.world.step(direction, occupied_positions=occupied)
        drone.last_direction = direction
        drone.last_result = result
        drone.visited.add(result.position)
        if result.moved:
            event_result = "moved"
            drone.path.append(result.position)
            self._reservations[drone.identifier] = result.position
            description = (
                f"{drone.identifier} {drone.callsign} MOVED {direction.value.upper()} TO "
                f"({result.position[0]:02d},{result.position[1]:02d})"
            )
        else:
            self._reservations.pop(drone.identifier, None)
            reason = result.blocked_by
            if reason is None:
                raise RuntimeError("blocked GridWorld step did not include a reason")
            event_result = reason.value
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
        if autonomous:
            description = (
                f"{drone.callsign} AUTO MOVE {direction.value.upper()}"
                if result.moved
                else f"{drone.callsign} AUTO BLOCKED {direction.value.upper()}"
            )
        self._events.append(f"[{self._tick:04d}]  {description}")
        self._record(
            "move" if result.moved else "blocked",
            drone.identifier,
            direction=direction.value,
            control="AUTO" if autonomous else "MANUAL",
            result=event_result,
        )
        if self._max_ticks is not None and self._tick >= self._max_ticks:
            self._status = MissionStatus.BUDGET_EXHAUSTED
            self._events.append(
                f"[{self._tick:04d}]  MISSION COMPLETE / TICK BUDGET EXHAUSTED"
            )
            self._record("terminal", status=self._status.value)

    def _get_drone(self, drone_id: str) -> _Drone:
        for drone in self._drones:
            if drone.identifier == drone_id:
                return drone
        raise KeyError(f"unknown drone: {drone_id}")


def _mission_identifier(operation_name: str) -> str:
    return "-".join(operation_name.strip().upper().replace("_", " ").split())
