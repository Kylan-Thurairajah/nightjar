"""Deterministic fleet knowledge and soft target preferences."""

from dataclasses import replace
import hashlib

import numpy as np
import pytest

from nightjar.core.belief import BeliefMap
from nightjar.core.planning import (
    FrontierPlanner,
    InformationGainPlanner,
    PlannerActionType,
    PlannerState,
    RandomPlanner,
    SearchStrategy,
    create_planner,
)
from nightjar.core.provider import GridWorldSimulation, MissionStatus, OperationalMode
from nightjar.core.replay import HistoryCapacityError, ReplayTimeline
from nightjar.core.sensor import SensorConfig
from nightjar.core.world import Direction, GridWorld


def make_state(*, width=5, height=3, position=(2, 1), candidates=None):
    traversable = frozenset((x, y) for y in range(height) for x in range(width))
    belief = BeliefMap(
        width, height, (), candidates or ((0, 0), (width - 1, height - 1)), "M"
    )
    return PlannerState(
        width=width,
        height=height,
        obstacles=frozenset(),
        position=position,
        traversable=traversable,
        visited=frozenset({position}),
        movement_history=(position,),
        scanned_positions=frozenset({position}),
        occupied_positions=frozenset(),
        permitted_moves=tuple(Direction),
        scan_permitted=False,
        belief=belief.snapshot(),
        sensor_config=SensorConfig(detection_radius=0),
        remaining_budget=50,
    )


class RecordingPlanner:
    def __init__(self, planner):
        self.planner = planner
        self.calls = []

    def decide(self, state):
        decision = self.planner.decide(state)
        self.calls.append((state, decision))
        return decision


def make_simulation(*, strategy=SearchStrategy.FRONTIER, seed=31, **kwargs):
    return GridWorldSimulation(
        GridWorld(width=7, height=5, seed=seed, obstacle_count=6),
        search_strategy=strategy,
        **kwargs,
    )


def release_all(simulation):
    for drone in simulation.frame().drones:
        simulation.set_mode(drone.identifier, OperationalMode.AUTO)


@pytest.mark.parametrize("planner", [FrontierPlanner(), InformationGainPlanner()])
def test_claimed_best_target_prefers_an_eligible_alternative_without_mutating_state(
    planner,
):
    state = make_state()
    original = planner.decide(state)
    before = state.belief.probabilities.copy()
    reserved = replace(state, reserved_targets=frozenset({original.target}))
    decision = planner.decide(reserved)
    assert original.action.type is PlannerActionType.MOVE
    assert decision.action.type is PlannerActionType.MOVE
    assert decision.target != original.target
    assert decision.target not in reserved.reserved_targets
    assert state.reserved_targets == frozenset()
    np.testing.assert_array_equal(state.belief.probabilities, before)


@pytest.mark.parametrize("planner", [FrontierPlanner(), InformationGainPlanner()])
def test_all_targets_claimed_falls_back_to_original_action_instead_of_stop(planner):
    state = make_state()
    original = planner.decide(state)
    reserved = replace(state, reserved_targets=state.traversable)
    assert original.action.type is PlannerActionType.MOVE
    assert planner.decide(reserved) == original


def test_frontier_claims_do_not_change_frontier_priority_or_block_corridor():
    state = make_state(width=4, height=1, position=(0, 0))
    reserved = replace(state, reserved_targets=frozenset({(1, 0)}))
    decision = FrontierPlanner().decide(reserved)
    # Farther unvisited cells are not frontier candidates yet. The claimed frontier
    # remains usable, and passing through it is never prohibited.
    assert decision.target == (1, 0)
    assert decision.action.direction is Direction.EAST


def test_information_gain_fallback_only_considers_positive_utility_candidates():
    state = make_state(width=5, height=1, position=(2, 0))
    original = InformationGainPlanner().decide(state)
    # Only the two radius-zero objective cells carry information; the intervening
    # unclaimed positions must not replace positive-utility claimed positions.
    reserved = replace(state, reserved_targets=frozenset({(0, 0), (4, 0)}))
    assert original.action.type is PlannerActionType.MOVE
    assert InformationGainPlanner().decide(reserved) == original


def test_random_baseline_ignores_coverage_and_soft_target_claims():
    state = make_state()
    changed = replace(
        state, visited=state.traversable, reserved_targets=state.traversable
    )
    first, second = RandomPlanner(17), RandomPlanner(17)
    assert [first.decide(state) for _ in range(30)] == [
        second.decide(changed) for _ in range(30)
    ]


def test_public_manual_and_idle_coverage_is_shared_without_changing_individual_histories():
    simulation = GridWorldSimulation(
        GridWorld(width=7, height=5, obstacles=(), seed=31),
        drone_count=3,
        search_strategy=SearchStrategy.FRONTIER,
        max_ticks=30,
    )
    simulation.step(Direction.EAST, drone_id="01")
    simulation.set_mode("02", OperationalMode.AUTO)
    simulation.set_mode("03", OperationalMode.IDLE)
    before = simulation.frame()
    recorder = RecordingPlanner(FrontierPlanner())
    simulation._planner = recorder
    simulation.autonomous_step("02")  # scan
    simulation.autonomous_step("02")  # choose frontier
    state, decision = recorder.calls[-1]
    expected = frozenset().union(*(drone.visited for drone in before.drones))
    assert state.visited == expected
    assert (1, 0) in state.visited  # manual exploration
    assert before.drone("03").position in state.visited  # parked spawn
    assert decision.target not in expected
    assert state.reserved_targets == frozenset()  # no cross-call claims
    assert simulation.frame().drone("01") == before.drone("01")
    assert simulation.frame().drone("03") == before.drone("03")
    assert not hasattr(state, "objective_position")
    assert not hasattr(state, "ground_truth")


@pytest.mark.parametrize(
    ("strategy", "seed", "rounds", "duplicate", "alternative"),
    [
        (SearchStrategy.FRONTIER, 1, 10, (5, 3), (5, 4)),
        (SearchStrategy.INFORMATION_GAIN, 0, 7, (1, 4), (4, 1)),
    ],
)
def test_real_serial_rounds_avoid_reproducible_duplicate_target_fixture(
    strategy, seed, rounds, duplicate, alternative
):
    simulation = make_simulation(
        strategy=strategy, seed=seed, drone_count=3, max_ticks=100
    )
    recorder = RecordingPlanner(create_planner(strategy, seed))
    simulation._planner = recorder
    release_all(simulation)
    avoided = []
    for _ in range(rounds):
        simulation.fleet_round()
    for state, actual in recorder.calls:
        uncoordinated = recorder.planner.decide(
            replace(state, reserved_targets=frozenset())
        )
        if (
            uncoordinated.target in state.reserved_targets
            and actual.target != uncoordinated.target
        ):
            avoided.append((uncoordinated.target, actual.target))
    assert (duplicate, alternative) in avoided
    assert simulation.frame().tick == 3 * rounds
    assert len({drone.position for drone in simulation.frame().drones}) == 3
    assert (
        ReplayTimeline.from_json(simulation.history.to_json()).to_json()
        == simulation.history.to_json()
    )


def test_round_claims_reset_and_only_successful_auto_moves_add_targets():
    simulation = GridWorldSimulation(
        GridWorld(width=7, height=5, obstacles=(), seed=31),
        drone_count=3,
        search_strategy=SearchStrategy.FRONTIER,
        max_ticks=50,
    )
    recorder = RecordingPlanner(FrontierPlanner())
    simulation._planner = recorder
    release_all(simulation)
    simulation.fleet_round()  # three scans; these create no claims
    assert len(recorder.calls) == 3
    assert all(not state.reserved_targets for state, _ in recorder.calls)
    assert len(recorder.calls[2][0].scanned_positions) == 2
    recorder.calls.clear()
    simulation.fleet_round()  # moves
    assert not recorder.calls[0][0].reserved_targets
    assert recorder.calls[0][1].target in recorder.calls[1][0].reserved_targets
    previous_claims = recorder.calls[2][0].reserved_targets
    assert previous_claims
    recorder.calls.clear()
    simulation.fleet_round()
    assert not recorder.calls[0][0].reserved_targets
    simulation.set_hybrid_control("02")
    simulation.set_mode("03", OperationalMode.IDLE)
    recorder.calls.clear()
    before = simulation.frame()
    simulation.fleet_round()
    assert len(recorder.calls) == 1
    assert not recorder.calls[0][0].reserved_targets
    assert simulation.frame().drone("02") == before.drone("02")
    assert simulation.frame().drone("03") == before.drone("03")


@pytest.mark.parametrize("strategy", list(SearchStrategy))
@pytest.mark.parametrize("budget", [1, 2, 5, 23])
def test_coordinated_traces_reproduce_budget_caps_and_valid_replay(strategy, budget):
    def run():
        simulation = make_simulation(strategy=strategy, drone_count=3, max_ticks=budget)
        release_all(simulation)
        while simulation.frame().status is MissionStatus.ACTIVE:
            simulation.fleet_round()
            frame = simulation.frame()
            assert frame.tick <= budget
            assert len({drone.position for drone in frame.drones}) == 3
            probabilities = simulation.belief_map.probabilities
            assert np.isfinite(probabilities).all()
            assert (probabilities >= 0).all()
            assert probabilities.sum() == pytest.approx(1.0)
            assert all(probabilities[y, x] == 0 for x, y in frame.obstacles)
        saved = simulation.history.to_json()
        assert ReplayTimeline.from_json(saved).to_json() == saved
        assert simulation.fleet_round() == frame
        assert simulation.history.to_json() == saved
        return saved

    assert run() == run()


def test_full_history_rejects_before_planner_queue_or_random_mutation():
    simulation = make_simulation(drone_count=3, history_capacity=3)
    simulation.set_mode("01", OperationalMode.AUTO)
    simulation.set_mode("02", OperationalMode.AUTO)
    simulation.queue_manual_action("03", Direction.SOUTH)
    before = (
        simulation.history.to_json(),
        simulation.frame(),
        simulation._manual_requests.copy(),
    )
    recorder = RecordingPlanner(FrontierPlanner())
    simulation._planner = recorder
    with pytest.raises(HistoryCapacityError):
        simulation.fleet_round()
    assert (
        simulation.history.to_json(),
        simulation.frame(),
        simulation._manual_requests,
    ) == before
    assert not recorder.calls


@pytest.mark.parametrize(
    ("strategy", "count", "archive_sha256"),
    [
        (
            SearchStrategy.RANDOM,
            1,
            "cde04fd600e8a5625957e9820c8fd36be9abcd8434ba1f19fbb4af31e9548929",
        ),
        (
            SearchStrategy.FRONTIER,
            1,
            "a7e43def20c3564a53a53553593cabc79373b05435031cfa555075c097f49aa0",
        ),
        (
            SearchStrategy.INFORMATION_GAIN,
            1,
            "ad4c77daf3b72436ebb16a17064be662293284ebc636a66b8443486bb70114fe",
        ),
        (
            SearchStrategy.RANDOM,
            3,
            "6c0ab328e2f60fea91fd02c6b1bda14d82b02fd1ebdc26b22ea0b55bed5a5228",
        ),
    ],
)
def test_single_drone_and_random_archives_preserve_pre_coordination_baseline(
    strategy, count, archive_sha256
):
    # Captured from the public API before implementing coordination, seed 31,
    # open 7x4 map, 24 global ticks, all-AUTO fleet-round calls.
    simulation = GridWorldSimulation(
        GridWorld(width=7, height=4, obstacles=(), seed=31),
        drone_count=count,
        search_strategy=strategy,
        max_ticks=24,
    )
    release_all(simulation)
    while simulation.frame().status is MissionStatus.ACTIVE:
        simulation.fleet_round()
    assert (
        hashlib.sha256(simulation.history.to_json().encode()).hexdigest()
        == archive_sha256
    )


def test_inaccessible_frontier_remains_a_genuine_global_terminal_stop():
    simulation = GridWorldSimulation(
        GridWorld(width=4, height=2, obstacles={(1, 0), (1, 1)}, seed=3),
        drone_count=2,
        search_strategy=SearchStrategy.FRONTIER,
        max_ticks=30,
    )
    release_all(simulation)
    for _ in range(10):
        if simulation.frame().status is not MissionStatus.ACTIVE:
            break
        simulation.fleet_round()
    assert simulation.frame().status is MissionStatus.PLANNER_EXHAUSTED
    assert simulation.frame().tick < 30
    saved = simulation.history.to_json()
    assert ReplayTimeline.from_json(saved).to_json() == saved
    assert simulation.fleet_round().status is MissionStatus.PLANNER_EXHAUSTED
    assert simulation.history.to_json() == saved
