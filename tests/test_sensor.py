import math
from dataclasses import FrozenInstanceError
from typing import cast

import pytest

from nightjar.core.mission import (
    MissionConfig,
    create_simulation,
    validate_mission_config,
)
from nightjar.core.provider import GridWorldSimulation, MissionStatus
from nightjar.core.sensor import (
    Observation,
    ProximitySensor,
    SensorConfig,
    SensorPreset,
    SensorType,
)
from nightjar.core.world import Direction, GridWorld


def test_perfect_sensor_reports_positive_in_range_and_negative_out_of_range():
    sensor = ProximitySensor(
        SensorConfig(
            detection_radius=1,
            sensitivity=1.0,
            false_positive_probability=0.0,
        ),
        seed=7,
    )

    assert sensor.scan((0, 0), (1, 0))
    assert not sensor.scan((0, 0), (2, 0))


def test_zero_sensitivity_and_false_positive_rate_always_report_negative():
    sensor = ProximitySensor(
        SensorConfig(sensitivity=0.0, false_positive_probability=0.0),
        seed=7,
    )

    assert not sensor.scan((0, 0), (0, 0))
    assert not sensor.scan((0, 0), (20, 20))


@pytest.mark.parametrize(
    "kwargs",
    [
        {"detection_radius": -1},
        {"detection_radius": True},
        {"sensitivity": -0.01},
        {"sensitivity": 1.01},
        {"sensitivity": math.nan},
        {"sensitivity": True},
        {"false_positive_probability": -0.01},
        {"false_positive_probability": 1.01},
        {"false_positive_probability": math.inf},
        {"false_positive_probability": False},
    ],
)
def test_invalid_sensor_configuration_is_rejected(kwargs):
    with pytest.raises(ValueError):
        SensorConfig(**kwargs)


@pytest.mark.parametrize(
    ("preset", "sensitivity", "false_positive_probability"),
    [
        (SensorPreset.HIGH_RELIABILITY, 0.98, 0.02),
        (SensorPreset.STANDARD, 0.90, 0.05),
        (SensorPreset.DEGRADED, 0.75, 0.15),
    ],
)
def test_sensor_presets_create_their_documented_probability_model(
    preset, sensitivity, false_positive_probability
):
    config = SensorConfig.from_preset(preset)

    assert config.preset is preset
    assert config.detection_radius == 3
    assert config.sensitivity == sensitivity
    assert config.false_positive_probability == false_positive_probability


def test_scans_use_selected_drone_position_and_store_immutable_ordered_observations():
    simulation = GridWorldSimulation(
        GridWorld(width=8, height=6, obstacles=()),
        drone_count=3,
    )

    first = simulation.scan("02")
    simulation.step(Direction.WEST, drone_id="02")
    second = simulation.scan("02")
    third = simulation.scan("01")

    assert isinstance(first, Observation)
    assert first.position == (7, 5)
    assert second.position == simulation.frame().drone("02").position
    assert first.drone_id == second.drone_id == "02"
    assert [item.sequence_number for item in simulation.observations] == [1, 2, 1]
    assert [item.tick for item in simulation.observations] == [1, 3, 4]
    assert [item.drone_id for item in simulation.observations] == ["02", "02", "01"]
    assert len({item.observation_id for item in simulation.observations}) == 3
    assert first.sensor_type is SensorType.PROXIMITY
    assert first.sensor_config is simulation.sensor_config
    assert simulation.frame().tick == 4
    assert third.drone_id == "01"
    with pytest.raises(FrozenInstanceError):
        setattr(first, "positive", False)


def test_observation_history_and_identifiers_are_reproducible_for_same_actions():
    def run_actions() -> tuple[Observation, ...]:
        simulation = GridWorldSimulation(
            GridWorld(width=8, height=6, seed=31, obstacles=()),
            drone_count=2,
            operation_name="REPEATABLE",
        )
        simulation.scan("01")
        simulation.step(Direction.WEST, drone_id="02")
        simulation.scan("02")
        simulation.scan("01")
        return simulation.observations

    first = run_actions()
    second = run_actions()

    assert first == second
    assert [observation.observation_id for observation in first] == [
        "REPEATABLE-OBS-000001",
        "REPEATABLE-OBS-000002",
        "REPEATABLE-OBS-000003",
    ]


def test_observations_do_not_expose_hidden_objective_ground_truth():
    simulation = GridWorldSimulation(GridWorld(width=8, height=6, seed=10))
    observation = simulation.scan("01")

    assert not hasattr(observation, "objective_position")
    assert not hasattr(simulation.frame(), "objective_position")
    assert simulation.debug_objective_position() not in {
        item.position for item in simulation.observations
    }


def test_scans_consume_ticks_and_are_rejected_after_budget_exhaustion():
    simulation = GridWorldSimulation(
        GridWorld(width=8, height=6, obstacles=()),
        drone_count=1,
        max_ticks=1,
    )

    observation = simulation.scan("01")

    assert observation.tick == 1
    assert simulation.frame().tick == 1
    assert simulation.frame().status is MissionStatus.BUDGET_EXHAUSTED
    with pytest.raises(ValueError, match="mission has ended"):
        simulation.scan("01")
    assert len(simulation.observations) == 1


def test_scan_and_blocked_movement_each_consume_one_mission_tick():
    simulation = GridWorldSimulation(
        GridWorld(width=8, height=6, obstacles=()),
        drone_count=1,
        max_ticks=3,
    )
    simulation.step(Direction.NORTH, drone_id="01")
    observation = simulation.scan("01")
    frame = simulation.step(Direction.EAST, drone_id="01")

    assert observation.tick == 2
    assert frame.tick == 3
    assert frame.status is MissionStatus.BUDGET_EXHAUSTED


@pytest.mark.parametrize(
    ("preset", "sensitivity", "false_positive_probability"),
    [
        (SensorPreset.HIGH_RELIABILITY, 0.98, 0.02),
        (SensorPreset.STANDARD, 0.90, 0.05),
        (SensorPreset.DEGRADED, 0.75, 0.15),
    ],
)
def test_mission_sensor_preset_is_applied_to_the_simulation(
    preset, sensitivity, false_positive_probability
):
    simulation = create_simulation(MissionConfig(sensor_preset=preset))

    assert simulation.sensor_config.preset is preset
    assert simulation.sensor_config.sensitivity == sensitivity
    assert (
        simulation.sensor_config.false_positive_probability
        == false_positive_probability
    )


def test_invalid_mission_sensor_preset_fails_validation_and_creation():
    config = MissionConfig(sensor_preset=cast(SensorPreset, "unknown"))

    assert any(
        check.label == "Sensor preset" and not check.passed
        for check in validate_mission_config(config)
    )
    with pytest.raises(ValueError, match="Invalid mission configuration"):
        create_simulation(config)
