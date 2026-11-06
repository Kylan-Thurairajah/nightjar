"""Authored facility geometry and configuration-to-preflight integration."""

import asyncio
from collections import deque
from dataclasses import replace

import pytest
from textual.widgets import RadioButton, Static

from nightjar.core.mission import (
    MapPreset,
    MissionConfig,
    ScenarioPreset,
    create_simulation,
    create_world,
)
from nightjar.core.scenarios import facility_layout
from nightjar.tui.app import NightjarApp


@pytest.mark.parametrize("preset", list(MapPreset))
def test_facility_is_connected_and_rooms_and_doors_are_public_geometry(preset):
    width, height = preset.dimensions
    layout = facility_layout(width, height)
    assert layout == facility_layout(width, height)
    traversable = {
        (x, y)
        for y in range(height)
        for x in range(width)
        if (x, y) not in layout.obstacles
    }
    reached = {(0, 0)}
    pending = deque(reached)
    while pending:
        x, y = pending.popleft()
        for point in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if point in traversable and point not in reached:
                reached.add(point)
                pending.append(point)
    assert reached == traversable
    assert {room.name for room in layout.rooms} == {
        "GARAGE",
        "SERVER ROOM",
        "WEST HALL",
        "OPERATIONS",
    }
    for room in layout.rooms:
        assert room.label_position in room.cells
        assert room.cells <= traversable
    assert all(
        not room.cells & other.cells
        for index, room in enumerate(layout.rooms)
        for other in layout.rooms[index + 1 :]
    )


@pytest.mark.parametrize("preset", list(MapPreset))
@pytest.mark.parametrize("count", [1, 10])
def test_facility_launch_has_valid_seeded_spawns_and_hidden_objective(preset, count):
    config = MissionConfig(
        scenario=ScenarioPreset.FACILITY,
        map_preset=preset,
        drone_count=count,
        seed=41,
    )
    first, second = create_simulation(config), create_simulation(config)
    frame = first.frame()
    starts = {drone.position for drone in frame.drones}
    assert frame == second.frame()
    assert len(starts) == count
    assert starts.isdisjoint(frame.obstacles)
    assert frame.obstacles == facility_layout(config.width, config.height).obstacles
    assert first.debug_objective_position() == second.debug_objective_position()
    assert first.debug_objective_position() not in starts | frame.obstacles
    # Seed affects synthetic state, not the authored room/wall layout.
    assert create_world(replace(config, seed=42)).obstacles == frame.obstacles


def test_facility_rejects_unsupported_dimensions_and_preserves_existing_presets():
    with pytest.raises(ValueError, match="supported mission map size"):
        facility_layout(8, 6)
    assert MissionConfig().scenario is ScenarioPreset.OBSTACLE_FIELD
    assert not create_world(MissionConfig(scenario=ScenarioPreset.OPEN_FIELD)).obstacles
    normal = create_world(MissionConfig())
    assert len(normal.obstacles) == normal.width * normal.height // 12


@pytest.mark.parametrize("size", [(110, 42), (80, 24)])
def test_facility_selector_and_mission_brief_preserve_configuration_flow(size):
    app = NightjarApp()

    async def exercise():
        async with app.run_test(size=size) as pilot:
            app.screen.query_one("#scenario-facility", RadioButton).value = True
            await pilot.press("enter")
            await pilot.pause()
            brief = app.screen.query_one("#mission_brief", Static).render().plain
            assert "one hidden synthetic objective" in brief
            assert "500 action ticks" in brief
            assert "high belief is not confirmation" in brief
            assert "Space runs available AUTO drones" in brief
            summary = app.screen.query_one("#mission_summary", Static).render().plain
            assert "TRAINING FACILITY" in summary
            await pilot.press("escape")
            assert app.screen.query_one("#scenario-facility", RadioButton).value
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press("enter")
            await app.wait_for_commands()
            assert app.mission_config.scenario is ScenarioPreset.FACILITY
            assert app._controller.live_snapshot.frame.scenario == "training_facility"
            assert app._controller.live_snapshot.frame.tick == 0
            assert not app.playing

    asyncio.run(exercise())
