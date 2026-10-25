import pytest

from nightjar.core.mission import (
    MapPreset,
    MissionConfig,
    ScenarioPreset,
    create_simulation,
    create_world,
    validate_mission_config,
)
from nightjar.core.provider import MissionStatus, OperationalMode
from nightjar.core.provider import DRONE_CALLSIGNS
from nightjar.core.world import Direction


def test_default_mission_configuration_is_valid():
    config = MissionConfig()

    assert all(check.passed for check in validate_mission_config(config))
    simulation = create_simulation(config)
    assert simulation.frame().tick == 0
    assert len(simulation.frame().drones) == config.drone_count


@pytest.mark.parametrize(
    ("updates", "failed_check"),
    [
        ({"drone_count": 0}, "Drone count"),
        ({"drone_count": 11}, "Drone count"),
        ({"map_preset": "small"}, "Map dimensions"),
        ({"max_ticks": 0}, "Tick budget"),
        ({"max_ticks": True}, "Tick budget"),
        ({"operation_name": "   "}, "Operation name"),
        ({"operation_name": "bad/name"}, "Operation name"),
        ({"seed": -1}, "Random seed"),
        ({"seed": True}, "Random seed"),
        ({"scenario": "unknown"}, "Scenario"),
        ({"initial_control": OperationalMode.AUTO}, "Initial control"),
    ],
)
def test_invalid_mission_configuration_is_rejected(updates, failed_check):
    config = MissionConfig(**updates)

    checks = validate_mission_config(config)

    assert any(check.label == failed_check and not check.passed for check in checks)
    with pytest.raises(ValueError, match="Invalid mission configuration"):
        create_simulation(config)


def test_open_scenario_has_capacity_for_maximum_configured_drone_count():
    config = MissionConfig(
        scenario=ScenarioPreset.OPEN_FIELD,
        map_preset=MapPreset.COMPACT,
        drone_count=10,
    )
    assert all(check.passed for check in validate_mission_config(config))


@pytest.mark.parametrize(
    ("preset", "dimensions"),
    [
        (MapPreset.COMPACT, (16, 12)),
        (MapPreset.STANDARD, (32, 16)),
        (MapPreset.EXTENDED, (40, 20)),
    ],
)
def test_map_presets_create_requested_dimensions(preset, dimensions):
    world = create_world(MissionConfig(map_preset=preset))
    assert (world.width, world.height) == dimensions


def test_same_configuration_and_seed_produce_identical_worlds_and_spawns():
    config = MissionConfig(seed=82, map_preset=MapPreset.COMPACT)
    first = create_simulation(config).frame()
    second = create_simulation(config).frame()

    assert first.obstacles == second.obstacles
    assert [drone.position for drone in first.drones] == [
        drone.position for drone in second.drones
    ]
    assert len(first.drones) == config.drone_count
    assert all(drone.position not in first.obstacles for drone in first.drones)
    assert len({drone.position for drone in first.drones}) == config.drone_count


@pytest.mark.parametrize("drone_count", [1, 3, 10])
def test_callsign_roster_is_stable_and_allocates_only_requested_drones(drone_count):
    config = MissionConfig(drone_count=drone_count, map_preset=MapPreset.COMPACT, seed=9)
    frame = create_simulation(config).frame()

    assert len(frame.drones) == drone_count
    assert [drone.identifier for drone in frame.drones] == [
        f"{index:02d}" for index in range(1, drone_count + 1)
    ]
    assert [drone.callsign for drone in frame.drones] == list(
        DRONE_CALLSIGNS[:drone_count]
    )
    assert len({drone.position for drone in frame.drones}) == drone_count
    assert all(drone.position not in frame.obstacles for drone in frame.drones)


def test_callsign_roster_is_centralized_in_simulation_core():
    assert DRONE_CALLSIGNS == (
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


def test_configured_initial_idle_mode_and_mission_tick_budget():
    config = MissionConfig(
        operation_name="HOLD POINT",
        scenario=ScenarioPreset.OPEN_FIELD,
        drone_count=1,
        map_preset=MapPreset.COMPACT,
        initial_control=OperationalMode.IDLE,
        max_ticks=2,
        seed=7,
    )
    simulation = create_simulation(config)

    assert simulation.frame().drones[0].mode is OperationalMode.IDLE
    simulation.set_mode("01", OperationalMode.MANUAL)
    simulation.step(Direction.EAST, drone_id="01")
    complete = simulation.step(Direction.SOUTH, drone_id="01")

    assert complete.tick == 2
    assert complete.status is MissionStatus.BUDGET_EXHAUSTED
    before = complete
    after = simulation.step(Direction.WEST, drone_id="01")
    assert after == before
