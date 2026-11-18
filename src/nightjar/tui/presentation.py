"""Public-snapshot explanations and a read-only mission brief/debrief."""

from functools import lru_cache

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from nightjar.core.discovery import (
    CONTACT_THRESHOLD,
    DiscoveryPhase,
    discovery_state,
)
from nightjar.core.provider import GridWorldFrame, MissionStatus
from nightjar.core.replay import MissionSnapshot
from nightjar.core.scenarios import ScenarioLayout, facility_layout
from nightjar.core.sensor import SensorType
from nightjar.core.world import Position
from nightjar.tui.awareness import FieldAwareness, awareness_text


@lru_cache(maxsize=6)
def _layout(width: int, height: int) -> ScenarioLayout | None:
    try:
        return facility_layout(width, height)
    except ValueError:
        return None


def room_name(frame: GridWorldFrame, position: Position) -> str:
    """Recognize only the authored public geometry, including historical frames."""
    if frame.scenario == "training_facility":
        layout = _layout(frame.width, frame.height)
        if layout is not None and layout.obstacles == frame.obstacles:
            for room in layout.rooms:
                if position in room.cells:
                    return room.name
    return f"GRID {position[0]:02d},{position[1]:02d}"


def coverage(snapshot: MissionSnapshot) -> float:
    frame = snapshot.frame
    visited = set().union(*(drone.visited for drone in frame.drones))
    return len(visited) / (frame.width * frame.height - len(frame.obstacles))


def progress_bar(fraction: float, width: int = 16) -> str:
    filled = round(max(0.0, min(1.0, fraction)) * width)
    return "[" + "\u2501" * filled + "\u2500" * (width - filled) + "]"


def mission_timeline(snapshot: MissionSnapshot, limit: int = 6) -> tuple[str, ...]:
    """Summarize the most recent public intel and candidate checks."""
    entries: list[str] = []
    for observation in snapshot.observations:
        drone = snapshot.frame.drone(observation.drone_id)
        location = room_name(snapshot.frame, observation.position)
        if observation.sensor_type is SensorType.VERIFICATION:
            outcome = (
                "BEACON VERIFIED" if observation.positive else "CANDIDATE REJECTED"
            )
            action = f"CHECK / {outcome}"
        else:
            outcome = "POSITIVE INTEL" if observation.positive else "NO SIGNAL"
            action = f"SCAN / {outcome}"
        entries.append(
            f"T{observation.tick:03d}  {drone.callsign}  {action}  /  {location}"
        )
    if not entries:
        return ("No scans or candidate checks recorded.",)
    omitted = max(0, len(entries) - limit)
    recent = entries[-limit:]
    if omitted:
        recent.insert(0, f"… {omitted} earlier intel events")
    return tuple(recent)


def evidence_text(snapshot: MissionSnapshot) -> str:
    if not snapshot.observations:
        return "SEARCHING / E scan / Space run fleet"
    observation = snapshot.observations[-1]
    discovery = discovery_state(snapshot)
    if observation.sensor_type is SensorType.VERIFICATION:
        reading = "CONFIRMED" if observation.positive else "REJECTED"
        label = "VERIFICATION"
    else:
        reading = "POSITIVE" if observation.positive else "NEGATIVE"
        label = "LATEST SCAN"
    position = room_name(snapshot.frame, observation.position)
    if discovery.phase is DiscoveryPhase.CONFIRMED:
        progress = (
            f"BEACON VERIFIED / {observation.drone_id} / {position} / "
            f"TICK {observation.tick}"
        )
    elif discovery.candidate_position is not None:
        candidate_name = room_name(snapshot.frame, discovery.candidate_position)
        candidate = discovery.candidate_position
        progress = (
            f"{discovery.phase.value} / CANDIDATE {candidate_name} "
            f"({candidate[0]:02d},{candidate[1]:02d}) "
            f"{snapshot.belief.stats.map_probability:.0%}"
        )
    else:
        progress = "SEARCHING / NO CANDIDATE ABOVE 60%"
    return f"{label} / {observation.drone_id} / {position} / {reading}\n{progress}"


def summary_text(
    snapshot: MissionSnapshot,
    initial_entropy: float,
    *,
    replay: bool = False,
    compact_debrief: bool = False,
) -> Text:
    frame = snapshot.frame
    visited = set().union(*(drone.visited for drone in frame.drones))
    traversable = frame.width * frame.height - len(frame.obstacles)
    stats = snapshot.belief.stats
    status = (
        "ACTIVE / paused for review"
        if frame.status is MissionStatus.ACTIVE
        else frame.status.value
    )
    heading = "HISTORICAL VIEW" if replay else "COMMITTED MISSION STATE"
    budget = "OPEN" if frame.max_ticks is None else str(frame.max_ticks)
    result = Text()
    result.append(f"{heading}\n", style="bold #e0b45c")
    result.append(
        f"{frame.operation_name}  /  {frame.scenario.replace('_', ' ').upper()}\n\n"
    )
    if compact_debrief:
        result.append(f"TICKS       {frame.tick} / {budget} action ticks\n")
        if frame.status is not MissionStatus.CONFIRMED:
            result.append(f"STATE       {status}\n")
    else:
        result.append(
            f"MISSION     {len(frame.drones)} drones / find the hidden beacon\n"
            f"STATE       {status}\n"
            f"TICKS       {frame.tick} / {budget} action ticks\n"
            f"COVERAGE    {coverage(snapshot):.1%}  ({len(visited)}/{traversable} cells)\n"
        )
        result.append(progress_bar(coverage(snapshot), 28) + "\n", style="#89c998")
    scans = tuple(
        item
        for item in snapshot.observations
        if item.sensor_type is SensorType.PROXIMITY
    )
    positive_scans = sum(item.positive for item in scans)
    checks = sum(
        item.sensor_type is SensorType.VERIFICATION for item in snapshot.observations
    )
    result.append(
        f"SCANS       {len(scans)} synthetic readings / {positive_scans} positive intel\n"
        f"CANDIDATE CHECKS {checks}\n"
    )
    if compact_debrief:
        result.append("\n")
    else:
        result.append(
            f"UNCERTAINTY {stats.entropy_bits:.3f} bits\n"
            f"CHANGE      {stats.entropy_bits - initial_entropy:+.3f} bits from initial\n"
            f"MAP CELL    {stats.map_position} at {stats.map_probability:.1%} belief\n\n"
        )
    discovery = discovery_state(snapshot)
    if discovery.phase is DiscoveryPhase.CONFIRMED:
        verifier = frame.drone(discovery.verifier_id or "").callsign
        position = discovery.confirmed_position
        if position is None or discovery.confirmed_tick is None:
            raise RuntimeError("confirmed discovery is missing its public evidence")
        result.append(
            f"BEACON VERIFIED / {verifier} / "
            f"{room_name(frame, position)} / TICK {discovery.confirmed_tick}\n",
            style="bold #89c998",
        )
    elif discovery.candidate_position is not None:
        position = discovery.candidate_position
        result.append(
            f"{discovery.phase.value} / CANDIDATE "
            f"{room_name(frame, position)} ({position[0]:02d},{position[1]:02d}) "
            f"{stats.map_probability:.1%}\n",
            style="bold #e0b45c",
        )
        result.append(
            "Press F to verify this cell.\n"
            if discovery.phase is DiscoveryPhase.VERIFYING
            else "A candidate is still a clue. Stand on it and press F to verify.\n"
        )
    else:
        result.append(
            f"SEARCHING / no candidate above {CONTACT_THRESHOLD:.0%} yet.\n",
            style="bold #e0b45c",
        )
    result.append("WHAT HAPPENED\n", style="bold #e0b45c")
    result.append(
        "\n".join(mission_timeline(snapshot, limit=4 if compact_debrief else 6))
    )
    if not compact_debrief:
        result.append(
            "\n\nVerification checks one exact cell; all sensors and targets are synthetic.\n"
            "Coverage counts physical visits, including spawn cells.\n"
            "Close to return to the same mission view, paused."
        )
    return result


class MissionSummaryScreen(ModalScreen[None]):
    """A fixed committed snapshot; opening/closing never executes simulation actions."""

    BINDINGS = [
        Binding("escape", "close", "Close", priority=True),
        Binding("enter", "close", "Close", priority=True),
        Binding("q", "close", "Close", priority=True),
        Binding("b", "close", "Close", priority=True),
        Binding("t", "close", "Close", priority=True),
    ]

    def __init__(
        self,
        snapshot: MissionSnapshot,
        initial_entropy: float,
        *,
        replay=False,
        field_awareness: FieldAwareness | None = None,
        milestones_only: bool = False,
    ):
        super().__init__()
        self.snapshot = snapshot
        self.initial_entropy = initial_entropy
        self.replay = replay
        self.field_awareness = field_awareness
        self.milestones_only = milestones_only

    def compose(self) -> ComposeResult:
        title = (
            "MISSION BRIEF / LIVE SUMMARY"
            if self.snapshot.frame.status is MissionStatus.ACTIVE
            else "MISSION DEBRIEF"
        )
        if self.milestones_only:
            title = "MISSION MILESTONES / FIELD AWARENESS"
        compact_debrief = (
            not self.replay and self.snapshot.frame.status is not MissionStatus.ACTIVE
        )
        body = summary_text(
            self.snapshot,
            self.initial_entropy,
            replay=self.replay,
            compact_debrief=compact_debrief,
        )
        if self.field_awareness is not None:
            if self.milestones_only:
                body = awareness_text(self.field_awareness)
                if self.replay:
                    body = Text("HISTORICAL VIEW / DISPLAYED PREFIX ONLY\n\n") + body
            else:
                body.append("\n\n")
                body.append_text(awareness_text(self.field_awareness, recent=4))
        with Vertical(id="mission_summary_panel"):
            yield Static(f" \u25c8 {title}", id="summary_title")
            with VerticalScroll(id="summary_scroll"):
                yield Static(
                    body,
                    id="summary_body",
                )
            yield Button("RETURN TO MISSION  /  ESC", id="summary_close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "summary_close":
            self.action_close()

    def action_close(self) -> None:
        self.dismiss(None)
