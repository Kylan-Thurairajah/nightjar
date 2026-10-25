import subprocess
import sys

from nightjar.core.provider import GridWorldSimulation
from nightjar.core.world import Direction, GridWorld


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
import nightjar.core.world
"""
    subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )
