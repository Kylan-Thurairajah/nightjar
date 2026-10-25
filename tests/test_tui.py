import asyncio

import pytest
from textual.widgets import Static

from nightjar.core.provider import GridWorldSimulation
from nightjar.core.world import Direction, GridWorld
from nightjar.tui.app import NightjarApp
from nightjar.tui.map_widget import MapWidget


def test_gridworld_renders_position_obstacles_and_neutral_cells():
    simulation = GridWorldSimulation(
        GridWorld(width=4, height=3, obstacles={(1, 1)}),
        (Direction.EAST,),
    )
    app = NightjarApp(mode="gridworld", gridworld_simulation=simulation)

    async def check_rendered_grid():
        async with app.run_test():
            map_text = app.query_one("#map", MapWidget).render().plain
            assert "01" in map_text
            assert "▓▓" in map_text
            assert "··" in map_text
            assert "██" not in map_text
            assert "POSITION    (00,00)" in app.query_one("#metrics", Static).render().plain
            assert "NEUTRAL TERRAIN" in app.query_one("#map_title", Static).render().plain

    asyncio.run(check_rendered_grid())


def test_n_advances_exactly_one_gridworld_step_and_reports_move_and_block():
    simulation = GridWorldSimulation(
        GridWorld(width=4, height=3, obstacles={(1, 1)}),
        (Direction.EAST, Direction.SOUTH),
    )
    app = NightjarApp(mode="gridworld", gridworld_simulation=simulation)

    async def check_step_behavior():
        async with app.run_test() as pilot:
            await pilot.press("n")
            frame = simulation.frame()
            assert frame.tick == 1
            assert frame.position == (1, 0)
            assert "MOVED EAST" in app.query_one("#events", Static).render().plain
            assert "TICK" in app.query_one("#metrics", Static).render().plain
            assert "MOVED EAST" in app.query_one("#metrics", Static).render().plain

            await pilot.press("n")
            frame = simulation.frame()
            assert frame.tick == 2
            assert frame.position == (1, 0)
            assert "BLOCKED BY WALL" in app.query_one("#events", Static).render().plain
            assert "BLOCKED BY WALL" in app.query_one("#metrics", Static).render().plain

    asyncio.run(check_step_behavior())


def test_boundary_block_is_reported_in_gridworld_mode():
    simulation = GridWorldSimulation(
        GridWorld(width=2, height=2, obstacles=()),
        (Direction.NORTH,),
    )
    app = NightjarApp(mode="gridworld", gridworld_simulation=simulation)

    async def check_boundary_feedback():
        async with app.run_test() as pilot:
            await pilot.press("n")
            assert simulation.frame().tick == 1
            assert simulation.frame().position == (0, 0)
            assert "BLOCKED BY BOUNDARY" in app.query_one("#events", Static).render().plain

    asyncio.run(check_boundary_feedback())


def test_manual_wasd_reports_wall_and_boundary_collisions():
    simulation = GridWorldSimulation(
        GridWorld(width=3, height=3, obstacles={(1, 0)}),
        (Direction.EAST,),
    )
    app = NightjarApp(mode="gridworld", gridworld_simulation=simulation)

    async def check_manual_collision_feedback():
        async with app.run_test() as pilot:
            await pilot.press("d")
            assert simulation.frame().tick == 1
            assert simulation.frame().position == (0, 0)
            assert "BLOCKED BY WALL" in app.query_one("#events", Static).render().plain

            await pilot.press("w")
            assert simulation.frame().tick == 2
            assert simulation.frame().position == (0, 0)
            assert "BLOCKED BY BOUNDARY" in app.query_one("#events", Static).render().plain

    asyncio.run(check_manual_collision_feedback())


def test_wasd_moves_use_world_step_and_preserve_coverage_and_path_layers():
    simulation = GridWorldSimulation(
        GridWorld(width=4, height=3, obstacles={(2, 1)}),
        (Direction.NORTH,),
    )
    app = NightjarApp(mode="gridworld", gridworld_simulation=simulation)

    async def check_manual_moves_and_overlays():
        async with app.run_test() as pilot:
            await pilot.press("d")
            assert simulation.frame().position == (1, 0)
            assert simulation.frame().tick == 1

            await pilot.press("s")
            assert simulation.frame().position == (1, 1)
            assert simulation.frame().tick == 2

            await pilot.press("c")
            assert app.layer == "coverage"
            assert "VISITED CELLS" in app.query_one("#map_title", Static).render().plain
            coverage_map = app.query_one("#map", MapWidget).render().plain
            assert "▒▒" in coverage_map

            await pilot.press("a")
            assert simulation.frame().position == (0, 1)
            assert app.layer == "coverage"
            assert "VISITED CELLS" in app.query_one("#map_title", Static).render().plain
            assert "▒▒" in app.query_one("#map", MapWidget).render().plain

            await pilot.press("p")
            assert app.layer == "paths"
            assert "TRAVEL HISTORY" in app.query_one("#map_title", Static).render().plain
            assert "••" in app.query_one("#map", MapWidget).render().plain

            await pilot.press("d")
            assert app.layer == "paths"
            assert "TRAVEL HISTORY" in app.query_one("#map_title", Static).render().plain

            await pilot.press("h")
            assert app.layer == "terrain"
            assert "NEUTRAL TERRAIN" in app.query_one("#map_title", Static).render().plain
            assert "██" not in app.query_one("#map", MapWidget).render().plain

    asyncio.run(check_manual_moves_and_overlays())


def test_demo_overlay_controls_remain_functional():
    app = NightjarApp()

    async def check_demo_overlays():
        async with app.run_test() as pilot:
            await pilot.press("c")
            assert app.layer == "coverage"
            assert "VISITED CELLS" in app.query_one("#map_title", Static).render().plain
            await pilot.press("p")
            assert app.layer == "paths"
            assert "TRAVEL HISTORY" in app.query_one("#map_title", Static).render().plain
            await pilot.press("h")
            assert app.layer == "belief"
            assert "PROBABILITY GRID" in app.query_one("#map_title", Static).render().plain

    asyncio.run(check_demo_overlays())


def test_demo_mode_remains_the_default_and_steps_its_scripted_timeline():
    app = NightjarApp()

    async def check_demo_mode():
        async with app.run_test() as pilot:
            assert "DEMO MODE" in app.query_one("#masthead", Static).render().plain
            await pilot.press("n")
            assert app.tick == 1
            assert len(app.sim.frame(app.tick).agents) == 3

    asyncio.run(check_demo_mode())
