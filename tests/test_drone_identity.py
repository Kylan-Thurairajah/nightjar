"""Two-cell identities and readable ownership without depending on emoji fonts."""

from unittest.mock import patch
from dataclasses import replace

import pytest
from rich.cells import cell_len
from rich.console import Console

from nightjar.core.planning import (
    PlannerAction,
    PlannerActionType,
    PlannerDecision,
    SearchStrategy,
)
from nightjar.core.provider import GridWorldSimulation, OperationalMode
from nightjar.core.world import Direction, GridWorld
from nightjar.tui.drone_identity import (
    DRONE_ICONS,
    drone_color,
    drone_letter,
    drone_marker,
)
from nightjar.tui.map_widget import MapWidget


def render(frame, layer="terrain", **options):
    widget = MapWidget()
    with patch.object(widget, "update") as update:
        widget.show_gridworld_frame(frame, layer, styled_drones=True, **options)
    return update.call_args.args[0]


def cell(text, frame, point):
    x, y = point
    offset = y * (2 * frame.width + 1) + 2 * x
    return text.plain[offset : offset + 2], text.get_style_at_offset(Console(), offset)


@pytest.mark.parametrize("identifier", ["01", "02", "03", "04", "10"])
def test_animal_and_numeric_markers_keep_exact_two_cell_width(identifier):
    assert cell_len(drone_marker(identifier)) == 2
    assert drone_marker(identifier, animal_icons=False) == identifier
    if identifier in {"01", "02", "03"}:
        assert drone_marker(identifier) != identifier
        assert drone_marker(identifier).isascii()
    else:
        assert drone_marker(identifier) == identifier


def test_marker_falls_back_when_terminal_width_contract_cannot_be_met(monkeypatch):
    monkeypatch.setitem(DRONE_ICONS, "01", "x")
    assert drone_marker("01") == "01"
    assert len({drone_color(key) for key in ("01", "02", "03")}) == 1
    assert [drone_letter(key) for key in ("01", "02", "03")] == ["R", "G", "V"]


def test_animal_map_rows_keep_world_alignment_and_numeric_toggle():
    frame = GridWorldSimulation(
        GridWorld(width=6, height=4, obstacles={(1, 1)})
    ).frame()
    animals = render(frame, animal_icons=True)
    numeric = render(frame, animal_icons=False)
    assert all(cell_len(line) == 2 * frame.width for line in animals.plain.splitlines())
    assert len(animals.plain.splitlines()) == frame.height
    for drone in frame.drones:
        assert cell(animals, frame, drone.position)[0] == drone_marker(drone.identifier)
        assert cell(numeric, frame, drone.position)[0] == drone.identifier
    assert cell(animals, frame, (1, 1))[0] == "\u2593\u2593"


def test_owned_and_shared_paths_use_distinct_glyphs_and_owner_colors():
    simulation = GridWorldSimulation(GridWorld(width=4, height=3, obstacles=()))
    for direction in (Direction.EAST, Direction.SOUTH, Direction.WEST):
        simulation.step(direction, drone_id="01")
    for direction in (
        Direction.WEST,
        Direction.NORTH,
        Direction.NORTH,
        Direction.WEST,
        Direction.EAST,
    ):
        simulation.step(direction, drone_id="02")
    frame = simulation.frame()
    text = render(frame, "paths")
    assert cell(text, frame, (1, 1))[0] == "R\u00b7"
    assert cell(text, frame, (1, 1))[1].color.name == drone_color("01")
    assert cell(text, frame, (2, 1))[0] == "G\u00b7"
    assert cell(text, frame, (2, 1))[1].color.name == drone_color("02")
    assert cell(text, frame, (1, 0))[0] == "\u2573 "
    # Occupancy remains above paths, including a path shared by several drones.
    assert cell(text, frame, frame.drone("02").position)[0] == "02"


def test_latest_target_owner_is_explicit_and_never_invented():
    frame = GridWorldSimulation(GridWorld(width=4, height=3, obstacles=())).frame()
    decision = PlannerDecision(
        SearchStrategy.FRONTIER,
        PlannerAction(PlannerActionType.MOVE, Direction.EAST),
        "Latest recorded fleet decision",
        target=(0, 2),
    )

    text = render(frame, planner_decision=decision, target_owner="03")
    assert cell(text, frame, (0, 2))[0] == "V+"
    assert cell(text, frame, (0, 2))[1].color.name == drone_color("03")
    assert cell(render(frame, planner_decision=decision), frame, (0, 2))[0] == "+ "
    assert (
        cell(
            render(frame, planner_decision=decision, target_owner="99"), frame, (0, 2)
        )[0]
        == "+ "
    )


@pytest.mark.parametrize("selected", ["01", "02", "03"])
@pytest.mark.parametrize("mode", list(OperationalMode))
def test_only_selected_marker_is_highlighted_regardless_of_mode(selected, mode):
    initial = GridWorldSimulation(GridWorld(width=6, height=4, obstacles=())).frame()
    frame = replace(
        initial, drones=tuple(replace(drone, mode=mode) for drone in initial.drones)
    )
    text = render(frame, animal_icons=True, selected_drone_id=selected)
    for drone in frame.drones:
        marker, style = cell(text, frame, drone.position)
        assert marker == drone_marker(drone.identifier)
        assert style.bgcolor.name == (
            "#e0b45c" if drone.identifier == selected else "#14251c"
        )
        if drone.identifier != selected:
            assert style.color.name == drone_color(drone.identifier)
