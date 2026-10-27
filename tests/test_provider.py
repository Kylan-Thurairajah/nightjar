import subprocess
import sys

import pytest

from nightjar.core.provider import GridWorldSimulation, OperationalMode
from nightjar.core.world import BlockReason, Direction, GridWorld


def test_provider_exposes_public_grid_state_and_advances_one_step():
    world = GridWorld(width=4, height=3, obstacles={(1, 1)})
    simulation = GridWorldSimulation(world, (Direction.EAST, Direction.SOUTH))

    initial = simulation.frame()
    assert initial.position == (0, 0)
    assert initial.obstacles == frozenset({(1, 1)})
    assert initial.visited == frozenset({(0, 0)})
    assert initial.path == ((0, 0),)
    assert initial.tick == 0
    assert "GRIDWORLD READY" in initial.events[0]
    assert initial.last_result is None

    moved = simulation.step()
    assert moved.position == (1, 0)
    assert moved.visited == frozenset({(0, 0), (1, 0)})
    assert moved.path == ((0, 0), (1, 0))
    assert moved.tick == 1
    assert moved.last_direction is Direction.EAST
    assert moved.last_result is not None and moved.last_result.moved
    assert "MOVED EAST" in moved.events[-1]

    blocked = simulation.step()
    assert blocked.position == (1, 0)
    assert blocked.visited == moved.visited
    assert blocked.path == moved.path
    assert blocked.tick == 2
    assert blocked.last_direction is Direction.SOUTH
    assert blocked.last_result is not None
    assert blocked.last_result.blocked_by.value == "obstacle"
    assert "BLOCKED BY WALL" in blocked.events[-1]
    assert len(blocked.events) == 3


def test_fixed_seed_reproduces_provider_frames_and_steps():
    first = GridWorldSimulation(GridWorld(width=12, height=8, seed=42))
    second = GridWorldSimulation(GridWorld(width=12, height=8, seed=42))

    assert first.frame() == second.frame()
    for _ in range(8):
        assert first.step() == second.step()


def test_three_drones_start_distinct_with_expected_identities_and_modes():
    frame = GridWorldSimulation(GridWorld(width=8, height=6, seed=42)).frame()

    assert [(drone.identifier, drone.callsign) for drone in frame.drones] == [
        ("01", "RAVEN"),
        ("02", "GHOST"),
        ("03", "VIPER"),
    ]
    assert len({drone.position for drone in frame.drones}) == 3
    assert all(drone.position not in frame.obstacles for drone in frame.drones)
    assert all(drone.mode is OperationalMode.MANUAL for drone in frame.drones)


def test_drone_count_preserves_a_free_cell_for_the_hidden_objective():
    simulation = GridWorldSimulation(
        GridWorld(width=2, height=2, obstacles=()),
        drone_count=3,
    )
    assert len(simulation.frame().drones) == 3
    assert len({drone.position for drone in simulation.frame().drones}) == 3
    assert simulation.debug_objective_position() not in {
        drone.position for drone in simulation.frame().drones
    }

    with pytest.raises(ValueError, match="enough free cells"):
        GridWorldSimulation(GridWorld(width=2, height=2, obstacles=()), drone_count=4)
    with pytest.raises(ValueError, match="between 1 and 10"):
        GridWorldSimulation(GridWorld(width=20, height=20, obstacles=()), drone_count=11)


def test_drone_movement_and_history_are_independent():
    simulation = GridWorldSimulation(
        GridWorld(width=5, height=4, obstacles=()),
        directions=(Direction.EAST,),
    )
    before = simulation.frame()

    after = simulation.step(Direction.EAST, drone_id="01")

    assert before.drones[1:] == after.drones[1:]
    assert after.drone("01").position == (1, 0)
    assert after.drone("01").path == ((0, 0), (1, 0))
    assert after.drone("01").visited == frozenset({(0, 0), (1, 0)})
    assert after.drone("01").moves == 1
    assert "01 RAVEN MOVED EAST" in after.events[-1]


def test_drone_collision_blocks_step_without_changing_path_or_position():
    simulation = GridWorldSimulation(
        GridWorld(width=3, height=3, obstacles=()),
        directions=(Direction.NORTH,),
    )

    simulation.step(Direction.NORTH, drone_id="02")
    frame = simulation.step(Direction.SOUTH, drone_id="03")

    assert frame.drone("02").position == (2, 1)
    assert frame.drone("03").position == (2, 0)
    assert frame.drone("03").last_result is not None
    assert frame.drone("03").last_result.blocked_by is BlockReason.DRONE
    assert frame.drone("03").path == ((2, 0),)
    assert "DRONE COLLISION" in frame.events[-1]


def test_non_manual_operational_modes_do_not_accept_manual_movement():
    simulation = GridWorldSimulation(GridWorld(width=4, height=3, obstacles=()))
    simulation.set_mode("02", OperationalMode.IDLE)

    with pytest.raises(ValueError, match="not in MANUAL mode"):
        simulation.step(Direction.WEST, drone_id="02")
    assert simulation.frame().drone("02").mode is OperationalMode.IDLE
    assert simulation.frame().drone("02").position == (3, 2)


def test_core_provider_imports_without_textual_or_rich():
    script = """
import importlib.abc
import sys

class RejectTuiImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "textual" or fullname.startswith("textual."):
            raise AssertionError("core imported Textual")
        if fullname == "rich" or fullname.startswith("rich."):
            raise AssertionError("core imported Rich")
        return None

sys.meta_path.insert(0, RejectTuiImports())
sys.path.insert(0, "src")
import nightjar.core.provider
import nightjar.core.mission
import nightjar.core.world
"""
    subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )
