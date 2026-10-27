import math

import numpy as np
import pytest

from nightjar.core.belief import BeliefMap, InconsistentEvidenceError
from nightjar.core.mission import MissionConfig, create_simulation
from nightjar.core.provider import GridWorldSimulation
from nightjar.core.sensor import Observation, SensorConfig, SensorPreset, SensorType
from nightjar.core.world import Direction, GridWorld


def make_observation(
    *,
    observation_id: str = "M-OBS-000001",
    tick: int = 1,
    positive: bool = True,
    position: tuple[int, int] = (0, 0),
    config: SensorConfig | None = None,
    drone_id: str = "01",
    mission_id: str = "M",
) -> Observation:
    return Observation(
        mission_id=mission_id,
        observation_id=observation_id,
        drone_id=drone_id,
        tick=tick,
        position=position,
        sensor_type=SensorType.PROXIMITY,
        positive=positive,
        sensor_config=config or SensorConfig(),
        sequence_number=tick,
    )


def test_initial_belief_is_uniform_over_candidates_and_zero_elsewhere():
    belief = BeliefMap(
        width=4,
        height=2,
        obstacles={(1, 1)},
        candidate_positions={(0, 0), (2, 0), (3, 1)},
        mission_id="M",
    )

    probabilities = belief.probabilities
    assert probabilities.shape == (2, 4)
    assert probabilities[0, 0] == pytest.approx(1 / 3)
    assert probabilities[0, 2] == pytest.approx(1 / 3)
    assert probabilities[1, 3] == pytest.approx(1 / 3)
    assert probabilities[1, 1] == 0
    assert probabilities[0, 1] == 0
    assert probabilities.sum() == pytest.approx(1)
    assert belief.stats.initial_entropy_bits == pytest.approx(math.log2(3))
    assert belief.stats.entropy_bits == pytest.approx(math.log2(3))
    assert belief.stats.candidate_count == 3
    assert belief.stats.map_position == (0, 0)
    assert belief.stats.map_probability == pytest.approx(1 / 3)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"candidate_positions": ()}, "at least one candidate"),
        ({"candidate_positions": ((0, 0), (0, 0))}, "unique"),
        ({"candidate_positions": ((2, 0),)}, "outside the grid"),
        ({"candidate_positions": ((1, 0),)}, "cannot be obstacles"),
    ],
)
def test_belief_rejects_invalid_candidate_sets(kwargs, message):
    base = {
        "width": 2,
        "height": 1,
        "obstacles": {(1, 0)},
        "candidate_positions": ((0, 0),),
        "mission_id": "M",
    }
    base.update(kwargs)

    with pytest.raises(ValueError, match=message):
        BeliefMap(**base)


@pytest.mark.parametrize(
    ("positive", "expected"),
    [
        (True, np.array([[8 / 17, 8 / 17, 0, 1 / 17]], dtype=np.float64)),
        (False, np.array([[2 / 13, 2 / 13, 0, 9 / 13]], dtype=np.float64)),
    ],
)
def test_bayesian_update_matches_hand_calculated_positive_and_negative(
    positive, expected
):
    belief = BeliefMap(
        width=4,
        height=1,
        obstacles={(2, 0)},
        candidate_positions={(0, 0), (1, 0), (3, 0)},
        mission_id="M",
    )
    observation = make_observation(
        positive=positive,
        config=SensorConfig(
            detection_radius=1,
            sensitivity=0.8,
            false_positive_probability=0.1,
        ),
    )

    stats = belief.update(observation)

    np.testing.assert_allclose(belief.probabilities, expected, rtol=1e-12)
    assert belief.probabilities.sum() == pytest.approx(1)
    assert belief.probabilities[0, 2] == 0
    assert stats.entropy_change_bits == pytest.approx(
        stats.entropy_bits - math.log2(3)
    )


def test_positive_and_negative_evidence_change_relative_likelihood_as_expected():
    config = SensorConfig(
        detection_radius=0,
        sensitivity=0.8,
        false_positive_probability=0.1,
    )
    positive_belief = BeliefMap(2, 1, (), ((0, 0), (1, 0)), "M")
    positive_belief.update(make_observation(config=config))
    assert positive_belief.probabilities[0, 0] > positive_belief.probabilities[0, 1]

    negative_belief = BeliefMap(2, 1, (), ((0, 0), (1, 0)), "M")
    negative_belief.update(make_observation(positive=False, config=config))
    assert negative_belief.probabilities[0, 0] < negative_belief.probabilities[0, 1]


def test_multiple_observations_and_reproducible_map_updates():
    def run() -> BeliefMap:
        belief = BeliefMap(
            width=5,
            height=1,
            obstacles=(),
            candidate_positions=((0, 0), (1, 0), (2, 0), (3, 0), (4, 0)),
            mission_id="M",
        )
        config = SensorConfig(
            detection_radius=1,
            sensitivity=0.9,
            false_positive_probability=0.05,
        )
        belief.update(make_observation(config=config))
        belief.update(
            make_observation(
                observation_id="M-OBS-000002",
                tick=2,
                position=(4, 0),
                positive=False,
                config=config,
            )
        )
        return belief

    first = run()
    second = run()

    np.testing.assert_array_equal(first.probabilities, second.probabilities)
    assert first.stats == second.stats
    assert first.observation_count == 2
    assert first.stats.candidate_count == 5


@pytest.mark.parametrize(
    ("preset", "expected_ratio"),
    [
        (SensorPreset.HIGH_RELIABILITY, 49.0),
        (SensorPreset.STANDARD, 18.0),
        (SensorPreset.DEGRADED, 5.0),
    ],
)
def test_sensor_presets_control_bayesian_likelihoods(preset, expected_ratio):
    belief = BeliefMap(2, 1, (), ((0, 0), (1, 0)), "M")
    sensitivity, false_positive_probability = preset.probabilities
    belief.update(
        make_observation(
            config=SensorConfig(
                detection_radius=0,
                sensitivity=sensitivity,
                false_positive_probability=false_positive_probability,
                preset=preset,
            ),
        )
    )

    assert belief.probabilities[0, 0] / belief.probabilities[0, 1] == pytest.approx(
        expected_ratio
    )


def test_duplicate_and_out_of_order_observations_are_rejected_without_mutation():
    belief = BeliefMap(2, 1, (), ((0, 0), (1, 0)), "M")
    observation = make_observation()
    belief.update(observation)
    after_first = belief.probabilities.copy()

    with pytest.raises(ValueError, match="already applied"):
        belief.update(observation)
    with pytest.raises(ValueError, match="strictly increasing"):
        belief.update(
            make_observation(observation_id="M-OBS-000002", tick=1, positive=False)
        )

    np.testing.assert_array_equal(belief.probabilities, after_first)
    assert belief.observation_count == 1


def test_impossible_evidence_does_not_mutate_prior_and_exact_zeros_stay_impossible():
    belief = BeliefMap(2, 1, (), ((0, 0), (1, 0)), "M")
    perfect_sensor = SensorConfig(
        detection_radius=0,
        sensitivity=1.0,
        false_positive_probability=0.0,
    )
    belief.update(make_observation(config=perfect_sensor))
    after_first = belief.probabilities.copy()
    assert after_first[0, 1] == 0

    with pytest.raises(InconsistentEvidenceError, match="impossible"):
        belief.update(
            make_observation(
                observation_id="M-OBS-000002",
                tick=2,
                positive=False,
                config=perfect_sensor,
            )
        )

    np.testing.assert_array_equal(belief.probabilities, after_first)
    assert belief.observation_count == 1
    assert belief.stats.candidate_count == 1


def test_log_domain_remains_finite_and_normalized_for_many_observations():
    belief = BeliefMap(5, 1, (), tuple((x, 0) for x in range(5)), "M")
    config = SensorConfig(
        detection_radius=1,
        sensitivity=0.99,
        false_positive_probability=0.01,
    )
    for tick in range(1, 1001):
        belief.update(
            make_observation(
                observation_id=f"M-OBS-{tick:06d}",
                tick=tick,
                positive=tick % 2 == 0,
                config=config,
            )
        )

    probabilities = belief.probabilities
    assert np.isfinite(probabilities).all()
    assert (probabilities >= 0).all()
    assert probabilities.sum() == pytest.approx(1)
    assert belief.stats.candidate_count > 0


def test_probability_array_cannot_mutate_internal_belief():
    belief = BeliefMap(2, 1, (), ((0, 0), (1, 0)), "M")

    with pytest.raises(ValueError):
        belief.probabilities[0, 0] = 0.0
    assert belief.probabilities.sum() == pytest.approx(1)


def test_simulation_uses_one_shared_belief_and_only_scans_update_it():
    simulation = GridWorldSimulation(
        GridWorld(width=8, height=6, seed=2, obstacles=()),
        drone_count=2,
    )
    initial = simulation.belief_map.probabilities.copy()

    simulation.step(Direction.EAST, drone_id="01")
    np.testing.assert_array_equal(simulation.belief_map.probabilities, initial)

    first = simulation.scan("01")
    after_first = simulation.belief_map.probabilities.copy()
    assert simulation.belief_map.observation_count == 1
    assert len(simulation.observations) == 1
    assert first.drone_id == "01"

    second = simulation.scan("02")
    assert second.drone_id == "02"
    assert simulation.belief_map.observation_count == 2
    assert len(simulation.observations) == 2
    assert not np.array_equal(simulation.belief_map.probabilities, after_first)

    assert simulation.belief_map.observation_count == 2


def test_prior_depends_on_public_geometry_not_sampled_objective_location():
    first = GridWorldSimulation(
        GridWorld(width=8, height=6, seed=3, obstacles=()),
        drone_count=2,
    )
    second = GridWorldSimulation(
        GridWorld(width=8, height=6, seed=19, obstacles=()),
        drone_count=2,
    )

    assert first.belief_map.candidate_positions == second.belief_map.candidate_positions
    np.testing.assert_array_equal(
        first.belief_map.probabilities,
        second.belief_map.probabilities,
    )


def test_distinct_scans_at_same_location_both_update_shared_belief():
    simulation = GridWorldSimulation(
        GridWorld(width=8, height=6, obstacles=()),
        drone_count=1,
    )

    first = simulation.scan("01")
    second = simulation.scan("01")

    assert first.position == second.position
    assert first.observation_id != second.observation_id
    assert simulation.belief_map.observation_count == 2
    assert len(simulation.observations) == 2


def test_identical_seed_and_action_sequence_reproduce_observations_and_belief():
    def run() -> tuple[tuple[Observation, ...], np.ndarray]:
        simulation = create_simulation(
            MissionConfig(seed=5, drone_count=2, max_ticks=20)
        )
        simulation.scan("01")
        simulation.step(Direction.WEST, drone_id="02")
        simulation.scan("02")
        simulation.scan("01")
        return simulation.observations, simulation.belief_map.probabilities

    first_observations, first_belief = run()
    second_observations, second_belief = run()

    assert first_observations == second_observations
    np.testing.assert_array_equal(first_belief, second_belief)
