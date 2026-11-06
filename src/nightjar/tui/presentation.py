"""Public-snapshot explanations and a read-only mission brief/debrief."""

from functools import lru_cache

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from nightjar.core.provider import GridWorldFrame, MissionStatus
from nightjar.core.replay import MissionSnapshot
from nightjar.core.scenarios import ScenarioLayout, facility_layout
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


def evidence_text(snapshot: MissionSnapshot) -> str:
    if not snapshot.observations:
        return "NO READINGS YET / E scan / Space run fleet"
    observation = snapshot.observations[-1]
    reading = "POSITIVE" if observation.positive else "NEGATIVE"
    position = room_name(snapshot.frame, observation.position)
    model = observation.sensor_config
    if model.sensitivity > model.false_positive_probability:
        effect = "higher" if observation.positive else "lower"
        explanation = f"Nearby hypotheses receive {effect} likelihood."
    else:
        explanation = "Belief updated using the recorded sensor model."
    return (
        f"LATEST SCAN / {observation.drone_id} / {position} / {reading}\n"
        f"{explanation} No confirmed discovery."
    )


def summary_text(
    snapshot: MissionSnapshot, initial_entropy: float, *, replay: bool = False
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
    result.append(
        f"MISSION     {len(frame.drones)} drones / one hidden synthetic objective\n"
        f"STATE       {status}\n"
        f"TICKS       {frame.tick} / {budget} action ticks\n"
        f"COVERAGE    {coverage(snapshot):.1%}  ({len(visited)}/{traversable} cells)\n"
    )
    result.append(progress_bar(coverage(snapshot), 28) + "\n", style="#89c998")
    result.append(
        f"SCANS       {len(snapshot.observations)} synthetic readings\n"
        f"UNCERTAINTY {stats.entropy_bits:.3f} bits\n"
        f"CHANGE      {stats.entropy_bits - initial_entropy:+.3f} bits from initial\n"
        f"MAP CELL    {stats.map_position} at {stats.map_probability:.1%} belief\n\n"
    )
    result.append("CONFIRMATION NOT MODELED\n", style="bold #e0b45c")
    result.append(
        "Concentrated belief is not a verified discovery.\n"
        "Sensors use synthetic Manhattan radius, without wall occlusion.\n"
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
        body = summary_text(self.snapshot, self.initial_entropy, replay=self.replay)
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
