import ast
from pathlib import Path

import numpy as np
import pytest

from nightjar.core.belief import BeliefMap
from nightjar.core.mission import MissionConfig, create_simulation
from nightjar.core.planning import (
    FrontierPlanner,
    InformationGainPlanner,
    PlannerActionType,
    PlannerState,
    RandomPlanner,
    SearchStrategy,
    expected_information_gain,
)
from nightjar.core.provider import (
    GridWorldSimulation,
    MissionStatus,
    OperationalMode,
)
from nightjar.core.sensor import Observation, SensorConfig, SensorType
from nightjar.core.world import Direction, GridWorld


def make_state(
    *,
    width=4,
    height=2,
    obstacles=(),
    candidates=((0, 0), (3, 1)),
    position=(0, 0),
    visited=((0, 0),),
    scanned=(),
    sensor_config=None,
):
    obstacles = frozenset(obstacles)
    traversable = frozenset(
        (x, y)
        for y in range(height)
        for x in range(width)
        if (x, y) not in obstacles
    )
    belief = BeliefMap(width, height, obstacles, candidates, "M")
    x, y = position
    moves = tuple(
        direction
        for direction, point in (
            (Direction.NORTH, (x, y - 1)),
            (Direction.EAST, (x + 1, y)),
            (Direction.SOUTH, (x, y + 1)),
            (Direction.WEST, (x - 1, y)),
        )
        if point in traversable
    )
    return PlannerState(
        width=width,
        height=height,
        obstacles=obstacles,
        position=position,
        traversable=traversable,
        visited=frozenset(visited),
        movement_history=(position,),
        scanned_positions=frozenset(scanned),
        occupied_positions=frozenset(),
        permitted_moves=moves,
        scan_permitted=position not in scanned,
        belief=belief.snapshot(),
        sensor_config=sensor_config or SensorConfig(),
        remaining_budget=20,
    )


def make_observation(*, positive=True):
    return Observation(
        mission_id="M",
        observation_id="M-OBS-000001",
        drone_id="01",
        tick=1,
        position=(0, 0),
        sensor_type=SensorType.PROXIMITY,
        positive=positive,
        sensor_config=SensorConfig(
            detection_radius=0,
            sensitivity=1.0,
            false_positive_probability=0.0,
        ),
        sequence_number=1,
    )


def test_planner_module_has_no_tui_or_rich_imports():
    source = Path(__file__).parents[1] / "src" / "nightjar" / "core" / "planning.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))

    imports = [
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    ]
    imports.extend(
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    )
    assert not any(name.startswith(("textual", "rich")) for name in imports)


def test_seeded_random_planners_make_reproducible_decisions():
    state = make_state()

    first = RandomPlanner(17)
    second = RandomPlanner(17)

    assert [first.decide(state) for _ in range(12)] == [
        second.decide(state) for _ in range(12)
    ]
    assert all(
        decision.action.type is PlannerActionType.SCAN
        or decision.action.direction in state.permitted_moves
        for decision in [RandomPlanner(17).decide(state)]
    )


def test_frontier_chooses_nearest_reachable_unvisited_cell_around_wall():
    state = make_state(
        width=3,
        height=2,
        obstacles={(1, 0)},
        candidates=((0, 0), (2, 1)),
        position=(0, 0),
        visited={(0, 0)},
        scanned={(0, 0)},
    )

    decision = FrontierPlanner().decide(state)

    assert decision.action.type is PlannerActionType.MOVE
    assert decision.action.direction is Direction.SOUTH
    assert decision.target == (0, 1)


def test_frontier_ties_break_by_row_then_column():
    state = make_state(
        width=3,
        height=3,
        candidates=((0, 0), (2, 2)),
        position=(1, 1),
        visited={(1, 1)},
        scanned={(1, 1)},
    )

    decision = FrontierPlanner().decide(state)

    assert decision.target == (1, 0)
    assert decision.action.direction is Direction.NORTH


def test_frontier_scans_each_position_once_then_stops_when_coverage_is_complete():
    state = make_state(
        width=1,
        height=1,
        candidates=((0, 0),),
        visited={(0, 0)},
    )
    planner = FrontierPlanner()

    assert planner.decide(state).action.type is PlannerActionType.SCAN
    scanned_state = make_state(
        width=1,
        height=1,
        candidates=((0, 0),),
        visited={(0, 0)},
        scanned={(0, 0)},
    )
    assert planner.decide(scanned_state).action.type is PlannerActionType.STOP


def test_expected_information_gain_matches_perfect_binary_partition():
    probabilities = np.array([[0.5, 0.5]], dtype=np.float64)
    gain = expected_information_gain(
        probabilities,
        ((0, 0), (1, 0)),
        (0, 0),
        SensorConfig(
            detection_radius=0,
            sensitivity=1.0,
            false_positive_probability=0.0,
        ),
    )

    assert gain == pytest.approx(1.0)


def test_expected_information_gain_is_nonnegative_and_uninformative_sensor_is_zero():
    probabilities = np.array([[0.2, 0.3, 0.5]], dtype=np.float64)
    candidates = ((0, 0), (1, 0), (2, 0))
    perfect_gain = expected_information_gain(
        probabilities,
        candidates,
        (0, 0),
        SensorConfig(detection_radius=0, sensitivity=0.9, false_positive_probability=0.1),
    )
    zero_gain = expected_information_gain(
        probabilities,
        candidates,
        (1, 0),
        SensorConfig(detection_radius=0, sensitivity=0.4, false_positive_probability=0.4),
    )

    assert perfect_gain >= -1e-12
    assert zero_gain == pytest.approx(0.0, abs=1e-12)


def test_information_gain_candidate_routing_avoids_walls_and_counts_travel():
    state = make_state(
        width=4,
        height=2,
        obstacles={(1, 0)},
        candidates=((3, 0), (3, 1)),
        position=(0, 0),
        visited={(0, 0)},
        scanned={(0, 0)},
        sensor_config=SensorConfig(
            detection_radius=0,
            sensitivity=1.0,
            false_positive_probability=0.0,
        ),
    )

    decision = InformationGainPlanner().decide(state)

    assert decision.action.type is PlannerActionType.MOVE
    assert decision.action.direction is Direction.SOUTH
    assert decision.target == (3, 1)
    assert decision.travel_cost == 5
    assert decision.expected_information_gain_bits == pytest.approx(1.0)


def test_information_gain_ties_break_by_row_then_column():
    state = make_state(
        width=3,
        height=1,
        candidates=((0, 0), (2, 0)),
        position=(1, 0),
        visited={(1, 0)},
        scanned={(1, 0)},
        sensor_config=SensorConfig(
            detection_radius=0,
            sensitivity=1.0,
            false_positive_probability=0.0,
        ),
    )

    decision = InformationGainPlanner().decide(state)

    assert decision.target == (0, 0)
    assert decision.action.direction is Direction.WEST


def test_information_gain_does_not_mutate_the_shared_belief_snapshot():
    state = make_state(
        sensor_config=SensorConfig(
            detection_radius=0,
            sensitivity=1.0,
            false_positive_probability=0.0,
        )
    )
    before = state.belief.probabilities.copy()

    InformationGainPlanner().decide(state)

    np.testing.assert_array_equal(state.belief.probabilities, before)


def test_information_gain_decision_changes_after_belief_becomes_certain():
    belief = BeliefMap(2, 1, (), ((0, 0), (1, 0)), "M")
    prior_state = make_state(
        width=2,
        height=1,
        candidates=((0, 0), (1, 0)),
        position=(0, 0),
        scanned={(1, 0)},
        sensor_config=SensorConfig(
            detection_radius=0,
            sensitivity=1.0,
            false_positive_probability=0.0,
        ),
    )
    before = InformationGainPlanner().decide(prior_state)
    belief.update(make_observation())
    certain_state = PlannerState(
        width=2,
        height=1,
        obstacles=frozenset(),
        position=(0, 0),
        traversable=frozenset({(0, 0), (1, 0)}),
        visited=frozenset({(0, 0)}),
        movement_history=((0, 0),),
        scanned_positions=frozenset({(1, 0)}),
        occupied_positions=frozenset(),
        permitted_moves=(Direction.EAST,),
        scan_permitted=False,
        belief=belief.snapshot(),
        sensor_config=prior_state.sensor_config,
        remaining_budget=20,
    )

    after = InformationGainPlanner().decide(certain_state)

    assert before.action.type is PlannerActionType.SCAN
    assert after.action.type is PlannerActionType.STOP


def test_autonomous_policy_selection_changes_real_simulation_actions():
    def run(strategy):
        simulation = create_simulation(
            MissionConfig(
                drone_count=1,
                seed=1,
                max_ticks=20,
                search_strategy=strategy,
            )
        )
        simulation.set_mode("01", OperationalMode.AUTO)
        simulation.autonomous_step("01")
        return simulation.last_planner_decision, simulation.frame()

    random_decision, random_frame = run(SearchStrategy.RANDOM)
    frontier_decision, frontier_frame = run(SearchStrategy.FRONTIER)

    assert random_decision is not None and frontier_decision is not None
    assert random_decision.strategy is SearchStrategy.RANDOM
    assert frontier_decision.strategy is SearchStrategy.FRONTIER
    assert (
        random_decision.action != frontier_decision.action
        or random_frame != frontier_frame
    )


def test_autonomous_actions_advance_one_tick_and_respect_budget_and_manual_mode():
    simulation = create_simulation(
        MissionConfig(drone_count=1, seed=3, max_ticks=2, search_strategy=SearchStrategy.FRONTIER)
    )
    with pytest.raises(ValueError, match="not in AUTO"):
        simulation.autonomous_step("01")

    simulation.set_mode("01", OperationalMode.AUTO)
    simulation.autonomous_step("01")
    assert simulation.frame().tick == 1
    simulation.autonomous_step("01")
    assert simulation.frame().tick == 2
    assert simulation.frame().status is MissionStatus.BUDGET_EXHAUSTED
    assert simulation.autonomous_step("01").tick == 2


def test_manual_move_is_rejected_for_auto_drone_and_no_ground_truth_is_in_planner_state():
    simulation = GridWorldSimulation(
        GridWorld(width=5, height=4, obstacles=()),
        drone_count=1,
        search_strategy=SearchStrategy.FRONTIER,
    )
    simulation.set_mode("01", OperationalMode.AUTO)
    with pytest.raises(ValueError, match="not in MANUAL"):
        simulation.step(Direction.EAST, drone_id="01")

    simulation.autonomous_step("01")
    state_fields = PlannerState.__dataclass_fields__
    assert "objective_position" not in state_fields
    assert "ground_truth" not in state_fields
    assert "objective_position" not in simulation.frame().__dataclass_fields__


def test_autonomous_mission_smoke_is_reproducible():
    def run():
        simulation = create_simulation(
            MissionConfig(
                drone_count=1,
                seed=12,
                max_ticks=8,
                search_strategy=SearchStrategy.FRONTIER,
            )
        )
        simulation.set_mode("01", OperationalMode.AUTO)
        while simulation.frame().tick < 8:
            simulation.autonomous_step("01")
        return simulation.frame(), simulation.observations, simulation.belief_map.probabilities

    first = run()
    second = run()

    assert first[0] == second[0]
    assert first[1] == second[1]
    np.testing.assert_array_equal(first[2], second[2])
