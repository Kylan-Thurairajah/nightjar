"""Public, immutable mission viewing history and versioned JSON archives.

These records are not resumable checkpoints: hidden objectives and RNG state are
deliberately absent. Loading creates a separate timeline, never a live simulation.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, fields, is_dataclass, replace
from enum import Enum
from typing import Any

import numpy as np

from nightjar.core.belief import BeliefMap, BeliefSnapshot, BeliefStats
from nightjar.core.planning import (
    PlannerAction,
    PlannerActionType,
    PlannerDecision,
    SearchStrategy,
)
from nightjar.core.provider import (
    DroneFrame,
    GridWorldFrame,
    MissionStatus,
    OperationalMode,
)
from nightjar.core.sensor import Observation, SensorConfig, SensorPreset, SensorType
from nightjar.core.world import BlockReason, Direction, Position, StepResult


class HistoryCapacityError(ValueError):
    """A new commit would exceed the explicit retained-history capacity."""


@dataclass(frozen=True)
class MissionEvent:
    sequence: int
    tick: int
    boundary: int
    kind: str
    drone_id: str | None = None
    details: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class MissionSnapshot:
    index: int
    event_sequence: int
    frame: GridWorldFrame
    observations: tuple[Observation, ...]
    belief: BeliefSnapshot
    sensor_config: SensorConfig
    search_strategy: SearchStrategy
    last_planner_decision: PlannerDecision | None

    def __post_init__(self) -> None:
        # Immutable bytes backing prevents callers re-enabling NumPy writes.
        values = np.asarray(self.belief.probabilities, dtype=np.float64)
        probabilities = np.frombuffer(values.tobytes(), dtype=np.float64).reshape(
            values.shape
        )
        object.__setattr__(
            self, "belief", replace(self.belief, probabilities=probabilities)
        )


@dataclass(frozen=True)
class ReplayTimeline:
    snapshots: tuple[MissionSnapshot, ...]
    events: tuple[MissionEvent, ...]

    def snapshot(self, index: int) -> MissionSnapshot:
        if type(index) is not int:
            raise ValueError("replay index must be an integer")
        if not self.snapshots:
            raise ValueError("replay requires an initial snapshot")
        return self.snapshots[max(0, min(len(self.snapshots) - 1, index))]

    def to_json(self) -> str:
        return json.dumps(
            {
                "version": 1,
                "snapshots": _encode(self.snapshots),
                "events": _encode(self.events),
            },
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

    @classmethod
    def from_json(cls, value: str) -> ReplayTimeline:
        """Validate a complete archive before returning a new immutable timeline."""
        try:
            data = json.loads(value, object_pairs_hook=_unique_object)
            data = _object(data, {"version", "snapshots", "events"})
            if type(data["version"]) is not int or data["version"] != 1:
                raise ValueError("unsupported replay version")
            snapshots = tuple(_snapshot(item) for item in _list(data["snapshots"]))
            events = tuple(_event(item) for item in _list(data["events"]))
            timeline = cls(snapshots, events)
            _validate(timeline)
            return timeline
        except (KeyError, TypeError, OverflowError, IndexError, AttributeError) as exc:
            raise ValueError("malformed replay archive") from exc


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate replay field: {key}")
        result[key] = value
    return result


def _encode(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, np.ndarray):
        return value.tolist()
    if is_dataclass(value):
        return {
            field.name: _encode(getattr(value, field.name)) for field in fields(value)
        }
    if isinstance(value, frozenset):
        return [_encode(item) for item in sorted(value)]
    if isinstance(value, tuple):
        return [_encode(item) for item in value]
    return value


def _object(value: Any, names: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != names:
        raise ValueError("invalid replay object fields")
    return value


def _list(value: Any) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError("expected replay list")
    return value


def _int(value: Any, minimum: int | None = 0) -> int:
    if type(value) is not int or minimum is not None and value < minimum:
        raise ValueError("invalid replay integer")
    return value


def _number(value: Any) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("invalid replay number")
    return float(value)


def _text(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("invalid replay text")
    return value


def _position(value: Any) -> Position:
    value = _list(value)
    if len(value) != 2:
        raise ValueError("invalid replay coordinate")
    return (_int(value[0]), _int(value[1]))


def _positions(value: Any, *, unique: bool = False) -> tuple[Position, ...]:
    positions = tuple(_position(item) for item in _list(value))
    if unique and len(set(positions)) != len(positions):
        raise ValueError("duplicate replay coordinate")
    return positions


def _sensor(value: Any) -> SensorConfig:
    data = _object(value, {field.name for field in fields(SensorConfig)})
    return SensorConfig(
        detection_radius=_int(data["detection_radius"]),
        sensitivity=_number(data["sensitivity"]),
        false_positive_probability=_number(data["false_positive_probability"]),
        preset=SensorPreset(_text(data["preset"])),
    )


def _observation(value: Any) -> Observation:
    data = _object(value, {field.name for field in fields(Observation)})
    if type(data["positive"]) is not bool:
        raise ValueError("invalid replay sensor reading")
    return Observation(
        mission_id=_text(data["mission_id"]),
        observation_id=_text(data["observation_id"]),
        drone_id=_text(data["drone_id"]),
        tick=_int(data["tick"], 1),
        position=_position(data["position"]),
        sensor_type=SensorType(_text(data["sensor_type"])),
        positive=data["positive"],
        sensor_config=_sensor(data["sensor_config"]),
        sequence_number=_int(data["sequence_number"], 1),
    )


def _drone(value: Any) -> DroneFrame:
    data = _object(value, {field.name for field in fields(DroneFrame)})
    result = data["last_result"]
    if result is not None:
        result = _object(result, {field.name for field in fields(StepResult)})
        if type(result["moved"]) is not bool:
            raise ValueError("invalid replay movement result")
        result = StepResult(
            position=_position(result["position"]),
            moved=result["moved"],
            blocked_by=(
                None
                if result["blocked_by"] is None
                else BlockReason(_text(result["blocked_by"]))
            ),
            tick=_int(result["tick"], 1),
        )
        if result.moved == (result.blocked_by is not None):
            raise ValueError("inconsistent replay movement result")
    return DroneFrame(
        identifier=_text(data["identifier"]),
        callsign=_text(data["callsign"]),
        position=_position(data["position"]),
        visited=frozenset(_positions(data["visited"], unique=True)),
        path=_positions(data["path"]),
        mode=OperationalMode(_text(data["mode"])),
        tick=_int(data["tick"]),
        last_direction=(
            None
            if data["last_direction"] is None
            else Direction(_text(data["last_direction"]))
        ),
        last_result=result,
    )


def _frame(value: Any) -> GridWorldFrame:
    data = _object(value, {field.name for field in fields(GridWorldFrame)})
    return GridWorldFrame(
        width=_int(data["width"], 1),
        height=_int(data["height"], 1),
        obstacles=frozenset(_positions(data["obstacles"], unique=True)),
        drones=tuple(_drone(item) for item in _list(data["drones"])),
        tick=_int(data["tick"]),
        events=tuple(_text(item) for item in _list(data["events"])),
        operation_name=_text(data["operation_name"]),
        mission_id=_text(data["mission_id"]),
        scenario=_text(data["scenario"]),
        seed=_int(data["seed"], None),
        max_ticks=(None if data["max_ticks"] is None else _int(data["max_ticks"], 1)),
        status=MissionStatus(_text(data["status"])),
    )


def _decision(value: Any) -> PlannerDecision | None:
    if value is None:
        return None
    data = _object(value, {field.name for field in fields(PlannerDecision)})
    action = _object(data["action"], {"type", "direction"})
    return PlannerDecision(
        strategy=SearchStrategy(_text(data["strategy"])),
        action=PlannerAction(
            PlannerActionType(_text(action["type"])),
            None
            if action["direction"] is None
            else Direction(_text(action["direction"])),
        ),
        reason=_text(data["reason"]),
        target=None if data["target"] is None else _position(data["target"]),
        expected_information_gain_bits=(
            None
            if data["expected_information_gain_bits"] is None
            else _number(data["expected_information_gain_bits"])
        ),
        travel_cost=None if data["travel_cost"] is None else _int(data["travel_cost"]),
    )


def _snapshot(value: Any) -> MissionSnapshot:
    data = _object(value, {field.name for field in fields(MissionSnapshot)})
    belief = _object(data["belief"], {field.name for field in fields(BeliefSnapshot)})
    stats = _object(belief["stats"], {field.name for field in fields(BeliefStats)})
    rows = _list(belief["probabilities"])
    probabilities = np.array(
        [[_number(cell) for cell in _list(row)] for row in rows], dtype=np.float64
    )
    return MissionSnapshot(
        index=_int(data["index"]),
        event_sequence=_int(data["event_sequence"]),
        frame=_frame(data["frame"]),
        observations=tuple(_observation(item) for item in _list(data["observations"])),
        belief=BeliefSnapshot(
            probabilities=probabilities,
            prior_cell_probability=_number(belief["prior_cell_probability"]),
            candidate_positions=_positions(belief["candidate_positions"], unique=True),
            stats=BeliefStats(
                initial_entropy_bits=_number(stats["initial_entropy_bits"]),
                entropy_bits=_number(stats["entropy_bits"]),
                entropy_change_bits=_number(stats["entropy_change_bits"]),
                map_position=_position(stats["map_position"]),
                map_probability=_number(stats["map_probability"]),
                candidate_count=_int(stats["candidate_count"], 1),
            ),
            observation_count=_int(belief["observation_count"]),
        ),
        sensor_config=_sensor(data["sensor_config"]),
        search_strategy=SearchStrategy(_text(data["search_strategy"])),
        last_planner_decision=_decision(data["last_planner_decision"]),
    )


def _event(value: Any) -> MissionEvent:
    data = _object(value, {field.name for field in fields(MissionEvent)})
    kind = _text(data["kind"])
    if kind not in {"move", "blocked", "scan", "mode", "stop", "terminal"}:
        raise ValueError("unsupported replay event kind")
    pairs: list[tuple[str, str]] = []
    for pair in _list(data["details"]):
        values = _list(pair)
        if len(values) != 2:
            raise ValueError("invalid replay event details")
        pairs.append((_text(values[0]), _text(values[1])))
    details = tuple(pairs)
    if len(dict(details)) != len(details):
        raise ValueError("invalid replay event details")
    return MissionEvent(
        sequence=_int(data["sequence"], 1),
        tick=_int(data["tick"]),
        boundary=_int(data["boundary"], 1),
        kind=kind,
        drone_id=None if data["drone_id"] is None else _text(data["drone_id"]),
        details=details,
    )


def _validate(timeline: ReplayTimeline) -> None:
    if not timeline.snapshots:
        raise ValueError("replay requires an initial snapshot")
    initial = timeline.snapshots[0]
    if (
        initial.index != 0
        or initial.event_sequence != 0
        or initial.frame.tick != 0
        or initial.observations
    ):
        raise ValueError("invalid initial replay snapshot")
    geometry = initial.frame
    if (
        geometry.status is not MissionStatus.ACTIVE
        or initial.last_planner_decision is not None
    ):
        raise ValueError("invalid initial replay mission state")
    if any(
        drone.tick != 0
        or drone.path != (drone.position,)
        or drone.visited != frozenset({drone.position})
        or drone.last_result is not None
        or drone.last_direction is not None
        or drone.mode is OperationalMode.AUTO
        for drone in geometry.drones
    ):
        raise ValueError("invalid initial replay drone state")
    starts = {drone.position for drone in geometry.drones}
    corners = {
        (0, 0),
        (geometry.width - 1, 0),
        (0, geometry.height - 1),
        (geometry.width - 1, geometry.height - 1),
    }
    available = tuple(
        (x, y)
        for y in range(geometry.height)
        for x in range(geometry.width)
        if (x, y) not in starts and (x, y) not in geometry.obstacles
    )
    candidates = (
        tuple(point for point in available if point not in corners) or available
    )
    if initial.belief.candidate_positions != candidates:
        raise ValueError("replay candidates do not match public mission geometry")
    belief = BeliefMap(
        geometry.width,
        geometry.height,
        geometry.obstacles,
        initial.belief.candidate_positions,
        geometry.mission_id,
    )
    previous = initial
    event_offset = 0
    sequences: dict[str, int] = {}
    observation_ids: set[str] = set()
    observation_tick = 0
    for index, snapshot in enumerate(timeline.snapshots):
        frame = snapshot.frame
        if (
            snapshot.index != index
            or not event_offset <= snapshot.event_sequence <= len(timeline.events)
        ):
            raise ValueError("invalid replay snapshot ordering")
        if (
            frame.width,
            frame.height,
            frame.obstacles,
            frame.operation_name,
            frame.mission_id,
            frame.scenario,
            frame.seed,
            frame.max_ticks,
        ) != (
            geometry.width,
            geometry.height,
            geometry.obstacles,
            geometry.operation_name,
            geometry.mission_id,
            geometry.scenario,
            geometry.seed,
            geometry.max_ticks,
        ):
            raise ValueError("replay mission geometry/identity changed")
        if (
            snapshot.sensor_config != initial.sensor_config
            or snapshot.search_strategy != initial.search_strategy
        ):
            raise ValueError("replay mission configuration changed")
        decision = snapshot.last_planner_decision
        if decision is not None and (
            decision.strategy is not snapshot.search_strategy
            or decision.target is not None
            and not _valid_position(frame, decision.target)
            or decision.expected_information_gain_bits is not None
            and decision.expected_information_gain_bits < 0
        ):
            raise ValueError("invalid replay planner metadata")
        if not 1 <= len(frame.drones) <= 10 or len(
            {drone.identifier for drone in frame.drones}
        ) != len(frame.drones):
            raise ValueError("invalid replay drone identities")
        if [(d.identifier, d.callsign) for d in frame.drones] != [
            (d.identifier, d.callsign) for d in geometry.drones
        ]:
            raise ValueError("replay drone roster changed")
        if len({d.position for d in frame.drones}) != len(frame.drones):
            raise ValueError("replay drone collision")
        for point in frame.obstacles:
            if not (0 <= point[0] < frame.width and 0 <= point[1] < frame.height):
                raise ValueError("replay obstacle outside bounds")
        for drone in frame.drones:
            for point in (*drone.path, *drone.visited, drone.position):
                if not _valid_position(frame, point):
                    raise ValueError("invalid replay drone position")
            if (
                not drone.path
                or drone.path[-1] != drone.position
                or frozenset(drone.path) != drone.visited
            ):
                raise ValueError("inconsistent replay movement history")
            if any(
                abs(a[0] - b[0]) + abs(a[1] - b[1]) != 1
                for a, b in zip(drone.path, drone.path[1:])
            ):
                raise ValueError("noncardinal replay movement")
            if drone.tick > frame.tick or (drone.last_result is None) != (
                drone.last_direction is None
            ):
                raise ValueError("inconsistent replay drone tick/result")
            if drone.last_result is not None and (
                drone.last_result.position != drone.position
                or drone.last_result.tick != drone.tick
            ):
                raise ValueError("inconsistent replay movement result")
        if frame.max_ticks is not None and frame.tick > frame.max_ticks:
            raise ValueError("replay exceeds mission budget")
        if (
            frame.status is MissionStatus.BUDGET_EXHAUSTED
            and frame.tick != frame.max_ticks
        ):
            raise ValueError("inconsistent replay budget status")
        if (
            frame.status is MissionStatus.ACTIVE
            and frame.max_ticks is not None
            and frame.tick >= frame.max_ticks
        ):
            raise ValueError("active replay exhausted its budget")
        if snapshot.belief.candidate_positions != initial.belief.candidate_positions:
            raise ValueError("replay candidates changed")
        if snapshot.observations[: len(previous.observations)] != previous.observations:
            raise ValueError("replay observations are not append-only")
        for observation in snapshot.observations[len(previous.observations) :]:
            if (
                observation.observation_id in observation_ids
                or observation.tick <= observation_tick
                or observation.tick > frame.tick
                or observation.mission_id != frame.mission_id
                or observation.drone_id not in {d.identifier for d in frame.drones}
                or not _valid_position(frame, observation.position)
                or observation.sensor_config != snapshot.sensor_config
            ):
                raise ValueError("invalid replay observation identity/order")
            sequences[observation.drone_id] = sequences.get(observation.drone_id, 0) + 1
            if observation.sequence_number != sequences[observation.drone_id]:
                raise ValueError("invalid replay drone observation sequence")
            observation_ids.add(observation.observation_id)
            observation_tick = observation.tick
            belief.update(observation)
        probabilities = snapshot.belief.probabilities
        if (
            probabilities.shape != (frame.height, frame.width)
            or np.any(probabilities < 0)
            or not np.isfinite(probabilities).all()
            or not np.isclose(probabilities.sum(), 1, rtol=0, atol=1e-12)
            or not np.allclose(probabilities, belief.probabilities, rtol=1e-12, atol=0)
            or snapshot.belief.observation_count != len(snapshot.observations)
            or not math.isclose(
                snapshot.belief.prior_cell_probability,
                belief.prior_cell_probability,
                rel_tol=1e-12,
            )
        ):
            raise ValueError("invalid replay belief")
        actual_stats, expected_stats = snapshot.belief.stats, belief.stats
        if (
            actual_stats.map_position != expected_stats.map_position
            or actual_stats.candidate_count != expected_stats.candidate_count
            or any(
                not math.isclose(
                    getattr(actual_stats, name),
                    getattr(expected_stats, name),
                    rel_tol=1e-10,
                    abs_tol=1e-12,
                )
                for name in (
                    "initial_entropy_bits",
                    "entropy_bits",
                    "entropy_change_bits",
                    "map_probability",
                )
            )
        ):
            raise ValueError("invalid replay belief statistics")
        boundary_events = timeline.events[event_offset : snapshot.event_sequence]
        if index:
            if not boundary_events or previous.frame.status is not MissionStatus.ACTIVE:
                raise ValueError("empty or post-terminal replay boundary")
            _validate_boundary(previous, snapshot, boundary_events, event_offset)
        elif boundary_events:
            raise ValueError("initial replay snapshot has events")
        event_offset = snapshot.event_sequence
        previous = snapshot
    if event_offset != len(timeline.events):
        raise ValueError("uncommitted replay events")


def _valid_position(frame: GridWorldFrame, point: Position) -> bool:
    return (
        0 <= point[0] < frame.width
        and 0 <= point[1] < frame.height
        and point not in frame.obstacles
    )


def _validate_boundary(
    previous: MissionSnapshot,
    snapshot: MissionSnapshot,
    events: tuple[MissionEvent, ...],
    offset: int,
) -> None:
    tick = previous.frame.tick
    drones = {drone.identifier: drone for drone in previous.frame.drones}
    observation_index = len(previous.observations)
    status = previous.frame.status
    auto_actions: list[MissionEvent] = []
    certain_planner_action = False
    deltas = {
        Direction.NORTH: (0, -1),
        Direction.EAST: (1, 0),
        Direction.SOUTH: (0, 1),
        Direction.WEST: (-1, 0),
    }
    for sequence, event in enumerate(events, offset + 1):
        if event.sequence != sequence or event.boundary != snapshot.index:
            raise ValueError("invalid replay event sequence/boundary")
        if status is not MissionStatus.ACTIVE:
            raise ValueError("replay actions after terminal event")
        details = dict(event.details)
        if event.kind in {"move", "blocked", "scan"}:
            tick += 1
        if event.tick != tick:
            raise ValueError("invalid replay event tick")
        if event.kind == "terminal":
            if event.drone_id is not None or set(details) != {"status"}:
                raise ValueError("invalid replay terminal event")
            status = MissionStatus(details["status"])
            if status is MissionStatus.ACTIVE:
                raise ValueError("invalid replay terminal status")
            if (
                status is MissionStatus.BUDGET_EXHAUSTED
                and (
                    tick != snapshot.frame.max_ticks
                    or sequence == offset + 1
                    or events[sequence - offset - 2].kind
                    not in {"move", "blocked", "scan"}
                )
                or status is MissionStatus.PLANNER_EXHAUSTED
                and (
                    sequence == offset + 1
                    or events[sequence - offset - 2].kind != "stop"
                )
            ):
                raise ValueError("replay terminal event lacks its cause")
            continue
        if event.drone_id not in drones:
            raise ValueError("unknown replay event drone")
        drone = drones[event.drone_id]
        if drone.mode is OperationalMode.AUTO and event.kind in {
            "move",
            "blocked",
            "scan",
            "stop",
        }:
            auto_actions.append(event)
            # Public scan() deliberately accepts an AUTO drone without invoking
            # its planner. A scan alone need not update the previous decision.
            if event.kind != "scan":
                certain_planner_action = True
        if event.kind == "mode":
            if set(details) != {"mode"}:
                raise ValueError("invalid replay mode event")
            mode = OperationalMode(details["mode"])
            if mode is drone.mode:
                raise ValueError("redundant replay mode event")
            drones[drone.identifier] = replace(drone, mode=mode)
        elif event.kind in {"move", "blocked"}:
            if (
                set(details) != {"direction", "control", "result"}
                or details["control"] != drone.mode.value
            ):
                raise ValueError("invalid replay move event")
            if drone.mode not in {OperationalMode.MANUAL, OperationalMode.AUTO}:
                raise ValueError("idle replay movement")
            direction = Direction(details["direction"])
            dx, dy = deltas[direction]
            destination = drone.position[0] + dx, drone.position[1] + dy
            moved = event.kind == "move"
            reason = None if moved else BlockReason(details["result"])
            if moved and (
                details["result"] != "moved"
                or not _valid_position(snapshot.frame, destination)
                or destination
                in {d.position for key, d in drones.items() if key != drone.identifier}
            ):
                raise ValueError("illegal replay move")
            if not moved:
                outside = not (
                    0 <= destination[0] < snapshot.frame.width
                    and 0 <= destination[1] < snapshot.frame.height
                )
                expected = (
                    BlockReason.BOUNDARY
                    if outside
                    else BlockReason.OBSTACLE
                    if destination in snapshot.frame.obstacles
                    else BlockReason.DRONE
                    if destination
                    in {
                        d.position
                        for key, d in drones.items()
                        if key != drone.identifier
                    }
                    else None
                )
                if reason is not expected:
                    raise ValueError("invalid replay blocked reason")
            point = destination if moved else drone.position
            drones[drone.identifier] = replace(
                drone,
                position=point,
                visited=drone.visited | {point},
                path=drone.path + (point,) if moved else drone.path,
                tick=drone.tick + 1,
                last_direction=direction,
                last_result=StepResult(point, moved, reason, drone.tick + 1),
            )
        elif event.kind == "scan":
            if set(details) != {"observation_id"} or observation_index >= len(
                snapshot.observations
            ):
                raise ValueError("invalid replay scan event")
            observation = snapshot.observations[observation_index]
            if (
                observation.observation_id != details["observation_id"]
                or observation.drone_id != drone.identifier
                or observation.tick != tick
                or observation.position != drone.position
            ):
                raise ValueError("replay scan does not match observation")
            observation_index += 1
        elif event.kind == "stop":
            if details or drone.mode is not OperationalMode.AUTO:
                raise ValueError("invalid replay planner stop")
            if sequence != offset + len(events) - 1 or events[-1].kind != "terminal":
                raise ValueError("replay planner stop must terminate its boundary")
    if (
        tick != snapshot.frame.tick
        or tuple(drones.values()) != snapshot.frame.drones
        or status is not snapshot.frame.status
        or observation_index != len(snapshot.observations)
    ):
        raise ValueError("replay snapshot does not match committed events")
    decision = snapshot.last_planner_decision
    changed = decision != previous.last_planner_decision
    if changed or certain_planner_action:
        if not auto_actions or decision is None:
            raise ValueError("replay planner metadata changed without an AUTO action")
        action_event = auto_actions[-1]
        expected_action = {
            "move": PlannerActionType.MOVE,
            "blocked": PlannerActionType.MOVE,
            "scan": PlannerActionType.SCAN,
            "stop": PlannerActionType.STOP,
        }[action_event.kind]
        if decision.action.type is not expected_action or (
            expected_action is PlannerActionType.MOVE
            and decision.action.direction
            is not Direction(dict(action_event.details)["direction"])
        ):
            raise ValueError("replay planner metadata contradicts its AUTO action")
    if (
        decision is not None
        and decision.action.type is PlannerActionType.STOP
        and (
            snapshot.frame.status is not MissionStatus.PLANNER_EXHAUSTED
            or not any(event.kind == "stop" for event in events)
        )
    ):
        raise ValueError("replay STOP decision lacks a terminal planner stop")
