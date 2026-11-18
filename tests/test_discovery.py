import json

import pytest

from nightjar.core.discovery import (
    CONTACT_THRESHOLD,
    DiscoveryPhase,
    discovery_state,
)
from nightjar.core.mission import (
    MissionConfig,
    create_simulation,
    validate_mission_config,
)
from nightjar.core.provider import GridWorldSimulation, MissionStatus, OperationalMode
from nightjar.core.sensor import SensorConfig, SensorPreset, SensorType
from nightjar.core.world import Direction, GridWorld
from nightjar.core.replay import ReplayTimeline


def _move_to(simulation, target):
    x, y = simulation.frame().position
    target_x, target_y = target
    for direction, count in (
        (Direction.EAST, target_x - x),
        (Direction.WEST, x - target_x),
        (Direction.SOUTH, target_y - y),
        (Direction.NORTH, y - target_y),
    ):
        for _ in range(count):
            simulation.step(direction)


def _exact_scan_simulation(*, max_ticks=100, seed=43):
    return GridWorldSimulation(
        GridWorld(width=8, height=6, seed=seed, obstacles=()),
        drone_count=1,
        max_ticks=max_ticks,
        sensor_config=SensorConfig(
            detection_radius=0,
            sensitivity=1.0,
            false_positive_probability=0.01,
        ),
    )


def test_contact_requires_observation_and_meets_the_public_probability_threshold():
    simulation = _exact_scan_simulation()

    assert discovery_state(simulation.snapshot()).phase is DiscoveryPhase.SEARCHING
    target = simulation.debug_objective_position()
    _move_to(simulation, target)
    simulation.scan("01")

    state = discovery_state(simulation.snapshot())
    assert state.phase is DiscoveryPhase.VERIFYING
    assert state.candidate_position == target
    assert simulation.belief_stats.map_probability >= CONTACT_THRESHOLD


def test_verification_confirms_exact_candidate_and_wins_on_the_final_tick():
    simulation = GridWorldSimulation(
        GridWorld(width=3, height=3, seed=7, obstacles=()),
        drone_count=1,
        max_ticks=5,
        sensor_config=SensorConfig(
            detection_radius=0,
            sensitivity=1.0,
            false_positive_probability=0.01,
        ),
    )
    target = simulation.debug_objective_position()
    _move_to(simulation, target)
    simulation.scan("01")
    assert simulation.frame().tick == 4

    rng_state = simulation._sensor._random.getstate()
    observation = simulation.verify("01")

    assert observation.sensor_type is SensorType.VERIFICATION
    assert observation.sensor_config == SensorConfig.from_preset(
        SensorPreset.VERIFICATION
    )
    assert observation.positive
    assert simulation._sensor._random.getstate() == rng_state
    assert simulation.frame().tick == 5
    assert simulation.frame().status is MissionStatus.CONFIRMED
    assert simulation.belief_stats.map_probability == 1.0
    assert discovery_state(simulation.snapshot()).confirmed_position == target

    archive = simulation.history.to_json()
    assert '"objective_position"' not in archive
    assert '"version":2' in archive
    loaded = ReplayTimeline.from_json(archive)
    assert loaded.to_json() == archive
    version_one = json.loads(archive)
    version_one["version"] = 1
    with pytest.raises(ValueError, match="version"):
        ReplayTimeline.from_json(json.dumps(version_one))
    invalid_sensor = json.loads(archive)
    invalid_sensor["snapshots"][-1]["observations"][-1]["sensor_config"]["preset"] = (
        SensorPreset.STANDARD.value
    )
    with pytest.raises(ValueError):
        ReplayTimeline.from_json(json.dumps(invalid_sensor))
    with pytest.raises(ValueError, match="mission has ended"):
        simulation.verify("01")


def test_false_contact_is_rejected_and_removed_from_the_posterior(monkeypatch):
    simulation = _exact_scan_simulation()
    target = simulation.debug_objective_position()
    candidate = next(
        point for point in simulation.belief_map.candidate_positions if point != target
    )
    _move_to(simulation, candidate)
    monkeypatch.setattr(simulation._sensor, "scan", lambda _position, _target: True)

    simulation.scan("01")
    assert simulation.belief_stats.map_position == candidate
    assert simulation.belief_stats.map_probability >= CONTACT_THRESHOLD
    observation = simulation.verify("01")

    assert not observation.positive
    assert simulation.frame().status is MissionStatus.ACTIVE
    assert simulation.belief_map.probabilities[candidate[1], candidate[0]] == 0
    assert discovery_state(simulation.snapshot()).phase is DiscoveryPhase.SEARCHING
    assert ReplayTimeline.from_json(simulation.history.to_json()).to_json() == (
        simulation.history.to_json()
    )


def test_verification_requires_a_contact_at_the_manual_drone_position():
    simulation = _exact_scan_simulation()
    with pytest.raises(ValueError, match="no beacon candidate"):
        simulation.verify("01")
    assert simulation.frame().tick == 0

    target = simulation.debug_objective_position()
    _move_to(simulation, target)
    simulation.scan("01")
    simulation.step(Direction.NORTH)
    tick = simulation.frame().tick
    with pytest.raises(ValueError, match="before verifying"):
        simulation.verify("01")
    assert simulation.frame().tick == tick

    simulation.set_mode("01", OperationalMode.AUTO)
    with pytest.raises(ValueError, match="not in MANUAL mode"):
        simulation.verify("01")


def test_verification_preset_is_not_a_mission_search_sensor():
    config = SensorConfig.from_preset(SensorPreset.VERIFICATION)
    assert (
        config.detection_radius,
        config.sensitivity,
        config.false_positive_probability,
    ) == (
        0,
        1.0,
        0.0,
    )
    with pytest.raises(ValueError, match="reserved"):
        GridWorldSimulation(sensor_config=config)
    mission_config = MissionConfig(sensor_preset=SensorPreset.VERIFICATION)
    checks = validate_mission_config(mission_config)
    assert not next(check for check in checks if check.label == "Sensor preset").passed
    with pytest.raises(ValueError, match="Invalid mission configuration"):
        create_simulation(mission_config)
