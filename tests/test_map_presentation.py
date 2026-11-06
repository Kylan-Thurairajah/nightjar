"""Snapshot-only map overlays retain terrain/layer/occupancy meaning."""

from dataclasses import replace
from unittest.mock import patch

import pytest
from rich.console import Console

from nightjar.core.planning import (
    PlannerAction,
    PlannerActionType,
    PlannerDecision,
    SearchStrategy,
)
from nightjar.core.provider import GridWorldSimulation
from nightjar.core.scenarios import facility_layout
from nightjar.core.sensor import SensorConfig
from nightjar.core.world import Direction, GridWorld
from nightjar.tui.map_widget import MapWidget


def render(frame, layer="terrain", belief=None, **overlays):
    widget = MapWidget()
    with patch.object(widget, "update") as update:
        widget.show_gridworld_frame(frame, layer, "01", belief, **overlays)
    return update.call_args.args[0]


def cell(text, frame, point):
    x, y = point
    start = y * (frame.width * 2 + 1) + x * 2
    return text.plain[start : start + 2], text.get_style_at_offset(Console(), start)


def move_target(point):
    return PlannerDecision(
        SearchStrategy.FRONTIER,
        PlannerAction(PlannerActionType.MOVE, Direction.EAST),
        "Latest fleet route",
        target=point,
    )


def test_facility_labels_require_matching_public_geometry_and_terrain_layer():
    layout = facility_layout(16, 12)
    simulation = GridWorldSimulation(
        GridWorld(width=16, height=12, obstacles=layout.obstacles),
        drone_count=1,
        scenario="training_facility",
    )
    frame = simulation.frame()
    plain = render(frame).plain
    for room in layout.rooms:
        assert room.name in plain
    assert all(len(line) == 2 * frame.width for line in plain.splitlines())
    assert "GARAGE" not in render(frame, "coverage").plain
    assert "GARAGE" not in render(replace(frame, scenario="open_field")).plain
    assert "GARAGE" not in render(replace(frame, obstacles=frozenset())).plain
    # Custom provider frames retain support even if they reuse the scenario name.
    custom = GridWorldSimulation(
        GridWorld(width=5, height=4, obstacles=()), scenario="training_facility"
    ).frame()
    assert "GARAGE" not in render(custom).plain


@pytest.mark.parametrize("layer", ["terrain", "belief", "coverage", "paths"])
def test_scan_tint_preserves_base_glyphs_and_walls_and_drone_priority(layer):
    simulation = GridWorldSimulation(
        GridWorld(width=6, height=4, obstacles={(1, 1)}),
        drone_count=1,
        sensor_config=SensorConfig(detection_radius=2),
    )
    observation = simulation.scan("01")
    frame = simulation.frame()
    before = render(frame, layer, simulation.belief_map)
    shown = render(frame, layer, simulation.belief_map, last_observation=observation)
    assert shown.plain == before.plain
    assert cell(shown, frame, (0, 0)) == cell(before, frame, (0, 0))
    assert cell(shown, frame, (1, 1)) == cell(before, frame, (1, 1))
    # Manhattan distance, rather than square sensor extent; walls do not occlude it.
    inside = (0, 2)
    if layer != "belief" or simulation.belief_stats.map_position != inside:
        assert cell(shown, frame, inside)[1].bgcolor is not None
    assert cell(shown, frame, (2, 2))[1].bgcolor is None


def test_target_marker_and_room_labels_cannot_hide_walls_or_drones():
    simulation = GridWorldSimulation(
        GridWorld(width=6, height=4, obstacles={(2, 1)}), drone_count=1
    )
    frame = simulation.frame()
    assert (
        cell(render(frame, planner_decision=move_target((2, 0))), frame, (2, 0))[0]
        == "+ "
    )
    assert (
        cell(render(frame, planner_decision=move_target((2, 1))), frame, (2, 1))[0]
        == "\u2593\u2593"
    )
    assert (
        cell(render(frame, planner_decision=move_target((0, 0))), frame, (0, 0))[0]
        == "01"
    )
    scan = PlannerDecision(
        SearchStrategy.FRONTIER,
        PlannerAction(PlannerActionType.SCAN),
        "Historical scan",
        target=(2, 0),
    )
    assert "+ " not in render(frame, planner_decision=scan).plain


def test_belief_map_maximum_stays_visible_above_target_and_scan_tint():
    simulation = GridWorldSimulation(
        GridWorld(width=6, height=4, obstacles=()), drone_count=1
    )
    observation = simulation.scan("01")
    frame = simulation.frame()
    belief = simulation.belief_map
    target = belief.stats.map_position
    before = render(frame, "belief", belief)
    shown = render(
        frame,
        "belief",
        belief,
        last_observation=observation,
        planner_decision=move_target(target),
    )
    assert cell(shown, frame, target) == cell(before, frame, target)


def test_historical_observation_position_and_radius_control_highlight_only():
    simulation = GridWorldSimulation(
        GridWorld(width=8, height=4, obstacles=()),
        drone_count=1,
        sensor_config=SensorConfig(detection_radius=1),
    )
    old_observation = simulation.scan("01")
    old_frame = simulation.frame()
    for _ in range(3):
        simulation.step(Direction.EAST)
    latest_observation = simulation.scan("01")
    latest_frame = simulation.frame()
    old = render(old_frame, last_observation=old_observation)
    latest = render(latest_frame, last_observation=latest_observation)
    assert cell(old, old_frame, (0, 1))[1].bgcolor is not None
    assert cell(latest, latest_frame, (0, 1))[1].bgcolor is None
    assert cell(latest, latest_frame, (3, 1))[1].bgcolor is not None
    assert cell(old, old_frame, (3, 1))[1].bgcolor is None
    # An unscanned historical frame has no inherited future highlight.
    initial = simulation.history.snapshots[0]
    unscanned = render(initial.frame)
    assert cell(unscanned, initial.frame, (3, 1))[1].bgcolor is None


def test_facility_features_distinguish_passages_and_equipment_without_fake_walls():
    layout = facility_layout(16, 12)
    simulation = GridWorldSimulation(
        GridWorld(width=16, height=12, obstacles=layout.obstacles),
        drone_count=1,
        scenario="training_facility",
    )
    frame = simulation.frame()
    terrain = render(frame)
    coverage = render(frame, "coverage")
    assert {feature.kind for feature in layout.features} == {
        "equipment",
        "door_vertical",
        "door_horizontal",
    }
    for feature in layout.features:
        glyph = cell(terrain, frame, feature.position)[0]
        if feature.kind == "equipment":
            assert feature.position in frame.obstacles
            assert glyph == "\u25a5\u25a5"
            assert cell(coverage, frame, feature.position)[0] == "\u2593\u2593"
        else:
            assert feature.position not in frame.obstacles
            assert glyph == (
                "\u250a\u250a" if feature.kind == "door_vertical" else "\u2504\u2504"
            )
    mismatched = render(replace(frame, obstacles=frozenset()))
    assert "\u25a5\u25a5" not in mismatched.plain
    assert "\u250a\u250a" not in mismatched.plain
