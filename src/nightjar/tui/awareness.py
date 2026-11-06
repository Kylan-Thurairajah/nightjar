"""Field awareness derived only from the displayed public event prefix."""

from dataclasses import dataclass
from functools import lru_cache

from rich.text import Text

from nightjar.core.planning import PlannerActionType
from nightjar.core.provider import GridWorldFrame, OperationalMode
from nightjar.core.replay import MissionSnapshot, ReplayTimeline
from nightjar.core.scenarios import ScenarioLayout, facility_layout
from nightjar.core.world import Direction, Position


@dataclass(frozen=True)
class Milestone:
    tick: int
    label: str
    event_sequence: int
    drone_id: str | None = None

    @property
    def log_line(self) -> str:
        return f"[{self.tick:04d}]  {self.label}"


@dataclass(frozen=True)
class RoomCoverage:
    name: str
    visited: int
    total: int

    @property
    def fraction(self) -> float:
        return self.visited / self.total if self.total else 0.0


@dataclass(frozen=True)
class FieldAwareness:
    milestones: tuple[Milestone, ...]
    room_entries: tuple[Milestone, ...]
    room_coverage: tuple[RoomCoverage, ...]
    target_owner: str | None


@lru_cache(maxsize=6)
def _facility(width: int, height: int) -> ScenarioLayout | None:
    try:
        return facility_layout(width, height)
    except ValueError:
        return None


def _layout(frame: GridWorldFrame) -> ScenarioLayout | None:
    if frame.scenario != "training_facility":
        return None
    layout = _facility(frame.width, frame.height)
    return (
        layout if layout is not None and layout.obstacles == frame.obstacles else None
    )


def _room(layout: ScenarioLayout | None, point: Position) -> str | None:
    if layout is not None:
        return next((room.name for room in layout.rooms if point in room.cells), None)
    return None


def build_awareness(
    history: ReplayTimeline, snapshot: MissionSnapshot
) -> FieldAwareness:
    """Walk accepted events once; future records and hidden state are never read."""
    frame = snapshot.frame
    layout = _layout(frame)
    initial = history.snapshots[0].frame
    positions = {drone.identifier: drone.position for drone in initial.drones}
    modes = {drone.identifier: drone.mode for drone in initial.drones}
    callsigns = {drone.identifier: drone.callsign for drone in initial.drones}
    previous_rooms = {key: _room(layout, point) for key, point in positions.items()}
    visited = set(positions.values())
    traversable = frame.width * frame.height - len(frame.obstacles)
    milestones = [Milestone(0, "FLEET DEPLOYED", 0)]
    entries: list[Milestone] = []
    observations = {item.observation_id: item for item in snapshot.observations}
    first_scan = first_positive = False
    thresholds = [25, 50, 75]
    last_auto = None
    deltas = {
        Direction.NORTH.value: (0, -1),
        Direction.EAST.value: (1, 0),
        Direction.SOUTH.value: (0, 1),
        Direction.WEST.value: (-1, 0),
    }

    def coverage_marks(tick: int, sequence: int) -> None:
        while thresholds and len(visited) / traversable * 100 >= thresholds[0]:
            threshold = thresholds.pop(0)
            milestones.append(
                Milestone(tick, f"{threshold}% PHYSICALLY VISITED", sequence)
            )

    coverage_marks(0, 0)
    for event in history.events[: snapshot.event_sequence]:
        details = dict(event.details)
        identifier = event.drone_id
        if event.kind == "mode" and identifier is not None:
            modes[identifier] = OperationalMode(details["mode"])
        elif event.kind == "move" and identifier is not None:
            dx, dy = deltas[details["direction"]]
            x, y = positions[identifier]
            point = positions[identifier] = (x + dx, y + dy)
            visited.add(point)
            room = _room(layout, point)
            # Doorways retain the last named room until another room is entered.
            if room is not None and room != previous_rooms[identifier]:
                entry = Milestone(
                    event.tick,
                    f"{callsigns[identifier]} ENTERED {room}",
                    event.sequence,
                    identifier,
                )
                entries.append(entry)
                milestones.append(entry)
                previous_rooms[identifier] = room
            coverage_marks(event.tick, event.sequence)
            if details["control"] == "AUTO":
                last_auto = event
        elif event.kind == "scan" and identifier is not None:
            observation = observations[details["observation_id"]]
            if not first_scan:
                milestones.append(
                    Milestone(
                        event.tick, "FIRST SENSOR READING", event.sequence, identifier
                    )
                )
                first_scan = True
            if observation.positive and not first_positive:
                milestones.append(
                    Milestone(
                        event.tick,
                        "FIRST POSITIVE SIGNAL / UNCONFIRMED",
                        event.sequence,
                        identifier,
                    )
                )
                first_positive = True
            if modes[identifier] is OperationalMode.AUTO:
                last_auto = event
        elif event.kind == "blocked" and identifier is not None:
            if details["control"] == "AUTO":
                last_auto = event
        elif event.kind == "stop":
            last_auto = event
        elif event.kind == "terminal":
            milestones.append(
                Milestone(
                    event.tick, f"MISSION STOP / {details['status']}", event.sequence
                )
            )

    target_owner = None
    decision = snapshot.last_planner_decision
    if (
        last_auto is not None
        and last_auto.kind == "move"
        and decision is not None
        and decision.action.type is PlannerActionType.MOVE
        and decision.action.direction is not None
        and dict(last_auto.details)["direction"] == decision.action.direction.value
    ):
        target_owner = last_auto.drone_id
    physical = set().union(*(drone.visited for drone in frame.drones))
    rooms = (
        tuple(
            RoomCoverage(
                room.name,
                len(physical & (room.cells - frame.obstacles)),
                len(room.cells - frame.obstacles),
            )
            for room in layout.rooms
        )
        if layout is not None
        else ()
    )
    return FieldAwareness(tuple(milestones), tuple(entries), rooms, target_owner)


def awareness_text(awareness: FieldAwareness, *, recent: int | None = None) -> Text:
    result = Text("ROOM COVERAGE / PHYSICAL VISITS\n", style="bold #89c998")
    if awareness.room_coverage:
        for room in awareness.room_coverage:
            filled = round(room.fraction * 12)
            bar = "\u2501" * filled + "\u2500" * (12 - filled)
            result.append(
                f"{room.name:<12} [{bar}] {room.fraction:5.1%} "
                f"({room.visited}/{room.total})\n",
                style="#a7d4b4",
            )
    else:
        result.append("No named-room geometry in this view.\n", style="#a7d4b4")
    result.append("Visits are not verified room clearance.\n\n", style="#89a58e")
    result.append("MISSION MILESTONES\n", style="bold #e0b45c")
    milestones = awareness.milestones[-recent:] if recent else awareness.milestones
    for item in milestones:
        result.append(f"{item.tick:04d}  {item.label}\n", style="#a7d4b4")
    return result


def merge_room_entries(lines: list[str], entries: tuple[Milestone, ...]) -> list[str]:
    """Insert each derived entry after its recorded movement, before later events.

    Every accepted movement consumes a unique global tick. Its room-entry event
    therefore belongs after that tick's movement line and before zero-tick mode,
    planner-stop or terminal messages. Entries retain their typed event order.
    """
    result = list(lines)

    def tick(line: str) -> int:
        prefix, separator, _ = line.partition("]")
        return (
            int(prefix[1:])
            if separator and prefix.startswith("[") and prefix[1:].isdigit()
            else -1
        )

    for entry in sorted(entries, key=lambda item: item.event_sequence):
        if entry.log_line in result:
            continue
        callsign = entry.label.partition(" ENTERED ")[0]
        cause = next(
            (
                index
                for index, line in enumerate(result)
                if tick(line) == entry.tick
                and f" {callsign} " in line
                and (" MOVED " in line or " AUTO MOVE " in line)
            ),
            None,
        )
        insertion = (
            cause + 1
            if cause is not None
            else next(
                (
                    index
                    for index, line in enumerate(result)
                    if tick(line) >= entry.tick
                ),
                len(result),
            )
        )
        result.insert(insertion, entry.log_line)
    return result
