"""Authored equipment and doors are honest, connected public map geometry."""

from collections import deque

import pytest

from nightjar.core.mission import (
    MapPreset,
    MissionConfig,
    ScenarioPreset,
    create_simulation,
    create_world,
)
from nightjar.core.scenarios import facility_layout
from nightjar.core.world import BlockReason, Direction, GridWorld


@pytest.mark.parametrize("preset", list(MapPreset))
def test_site_features_preserve_door_aisles_labels_and_all_walkable_connectivity(
    preset,
):
    width, height = preset.dimensions
    layout = facility_layout(width, height)
    assert layout == facility_layout(width, height)
    equipment = [feature for feature in layout.features if feature.kind == "equipment"]
    doors = [feature for feature in layout.features if feature.kind.startswith("door_")]
    assert len(equipment) == 8 and len(doors) == 4
    assert len({feature.position for feature in layout.features}) == 12
    assert all(feature.position in layout.obstacles for feature in equipment)
    assert all(feature.position not in layout.obstacles for feature in doors)

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

    corners = {(0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)}
    assert corners <= traversable
    for room in layout.rooms:
        assert room.cells <= traversable
        assert room.label_position in room.cells
        assert len(room.cells) > 2
        room_equipment = [
            item
            for item in equipment
            if (item.position[0], item.position[1] - 1) in room.cells
        ]
        assert len(room_equipment) == 2
        # Labels occupy more than their anchor, and must remain fully on floor.
        x, y = room.label_position
        assert all(
            (x + offset // 2, y) in room.cells for offset in range(0, len(room.name), 2)
        )

    # Equipment does not close the straight row/column through any doorway.
    for door in doors:
        x, y = door.position
        aisle = (
            {(cell_x, y) for cell_x in range(width)}
            if door.kind == "door_vertical"
            else {(x, cell_y) for cell_y in range(height)}
        )
        assert not aisle & {item.position for item in equipment}


@pytest.mark.parametrize("preset", list(MapPreset))
def test_equipment_blocks_actual_movement_and_all_doors_remain_passable(preset):
    width, height = preset.dimensions
    layout = facility_layout(width, height)
    for feature in layout.features:
        x, y = feature.position
        if feature.kind == "door_vertical":
            start, direction = (x - 1, y), Direction.EAST
        else:
            start, direction = (x, y - 1), Direction.SOUTH
        world = GridWorld(
            width=width,
            height=height,
            obstacles=layout.obstacles,
            start_position=start,
            include_hidden_objective=False,
        )
        result = world.step(direction)
        assert result.tick == 1
        if feature.kind == "equipment":
            assert not result.moved
            assert result.position == start
            assert result.blocked_by is BlockReason.OBSTACLE
        else:
            assert result.moved and result.position == feature.position


@pytest.mark.parametrize("preset", list(MapPreset))
def test_enriched_facility_preserves_all_supported_fleet_spawns_and_seeded_state(
    preset,
):
    for count in range(1, 11):
        config = MissionConfig(
            scenario=ScenarioPreset.FACILITY,
            map_preset=preset,
            drone_count=count,
            seed=57,
        )
        first, second = create_simulation(config), create_simulation(config)
        assert first.frame() == second.frame()
        assert first.debug_objective_position() == second.debug_objective_position()
        starts = {drone.position for drone in first.frame().drones}
        assert len(starts) == count
        assert not starts & first.frame().obstacles
        assert first.debug_objective_position() not in starts | first.frame().obstacles


def test_other_scenario_geometry_is_unchanged():
    assert not create_world(MissionConfig(scenario=ScenarioPreset.OPEN_FIELD)).obstacles
    config = MissionConfig(scenario=ScenarioPreset.OBSTACLE_FIELD, seed=57)
    expected = GridWorld(
        width=config.width,
        height=config.height,
        seed=config.seed,
        obstacle_count=config.width * config.height // 12,
    )
    assert create_world(config).obstacles == expected.obstacles
