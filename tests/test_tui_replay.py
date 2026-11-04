"""GridWorld replay uses recorded public state and cannot mutate the live mission."""

import asyncio

import numpy as np
import pytest
from textual.widgets import Static

from nightjar.core.planning import SearchStrategy
from nightjar.core.provider import GridWorldSimulation, OperationalMode
from nightjar.core.world import Direction, GridWorld
from nightjar.tui.app import NightjarApp
from nightjar.tui.map_widget import MapWidget
from nightjar.tui.mission_screens import MissionConfigScreen, PreflightReviewScreen


def make_simulation(**kwargs):
    return GridWorldSimulation(
        GridWorld(width=6, height=4, obstacles=(), seed=43),
        drone_count=2,
        search_strategy=SearchStrategy.FRONTIER,
        **kwargs,
    )


def text(app, selector):
    return app.query_one(selector, Static).render().plain


@pytest.mark.parametrize("size", [(110, 42), (80, 24)])
def test_initial_history_replay_and_seek_limits_work_with_keyboard(size):
    simulation = make_simulation()
    app = NightjarApp(mode="gridworld", gridworld_simulation=simulation)

    async def exercise():
        async with app.run_test(size=size) as pilot:
            before = simulation.history.to_json()
            await pilot.press("r", "left", "left", "right", "right")
            assert app.replay_mode
            assert app.tick == 0
            assert app._replay_index == 0
            assert "REPLAY 1/1" in text(app, "#timeline")
            assert "READ ONLY" in text(app, "#timeline")
            timeline = app.query_one("#timeline", Static)
            # The replay panel and its early keyboard hint must be in the viewport,
            # not merely present in an off-screen Static's render text.
            assert timeline.region.x >= 0
            assert timeline.region.right <= size[0]
            assert timeline.region.y >= 0
            assert timeline.region.bottom <= size[1]
            assert timeline.content_region.y + 2 < timeline.content_region.bottom
            assert "R replay / live" in text(app, "#timeline").splitlines()[2]
            assert simulation.history.to_json() == before
            await pilot.press("r")
            assert not app.replay_mode
            assert not app.playing
            assert "PAUSED" in text(app, "#timeline")

    asyncio.run(exercise())


def test_seek_renders_historical_positions_modes_observations_belief_and_events():
    simulation = make_simulation(max_ticks=20)
    initial = simulation.snapshot()
    simulation.step(Direction.EAST, drone_id="01")
    simulation.scan("01")
    after_scan = simulation.snapshot()
    simulation.set_mode("01", OperationalMode.AUTO)
    simulation.autonomous_step("01")
    latest = simulation.snapshot()
    archive = simulation.history.to_json()
    app = NightjarApp(mode="gridworld", gridworld_simulation=simulation)

    async def exercise():
        async with app.run_test(size=(110, 42)) as pilot:
            await pilot.press("h", "r")
            assert app.tick == latest.frame.tick
            app.action_seek(after_scan.index - app._replay_index)
            assert app.tick == after_scan.frame.tick
            metrics = text(app, "#metrics")
            assert "STATUS      MANUAL" in metrics
            assert f"OBSERVATIONS {len(after_scan.observations):4d}" in metrics
            assert f"BELIEF H    {after_scan.belief.stats.entropy_bits:6.2f}" in metrics
            assert "POSITION    (01,00)" in metrics
            assert text(app, "#events") == "\n".join(after_scan.frame.events)
            assert "PLAN: READY" in text(app, "#timeline")

            expected_map = MapWidget()
            expected_map.show_gridworld_frame(
                after_scan.frame, "belief", "01", after_scan.belief
            )
            actual_map = app.query_one("#map", MapWidget).render()
            assert actual_map == expected_map.render()

            app.action_seek(-10000)
            assert app.tick == initial.frame.tick == 0
            assert "POSITION    (00,00)" in text(app, "#metrics")
            assert "OBSERVATIONS    0" in text(app, "#metrics")
            assert "SENSOR      READY" in text(app, "#metrics")
            assert text(app, "#events") == "\n".join(initial.frame.events)
            assert "AUTO MOVE" not in text(app, "#events")
            app.action_seek(10000)
            assert app._replay_index == latest.index
            assert "STATUS      AUTO" in text(app, "#metrics")
            assert "PLAN: SCAN" in text(app, "#timeline") or "PLAN: MOVE" in text(
                app, "#timeline"
            )
            assert simulation.history.to_json() == archive
            await pilot.press("r")
            assert app.tick == latest.frame.tick
            assert not app.replay_mode and not app.playing

    asyncio.run(exercise())


@pytest.mark.parametrize("size", [(110, 42), (80, 24)])
def test_replay_blocks_all_mutation_shortcuts_and_timer_but_allows_view_controls(size):
    simulation = make_simulation(max_ticks=30)
    simulation.set_mode("01", OperationalMode.AUTO)
    simulation.autonomous_step("01")
    app = NightjarApp(mode="gridworld", gridworld_simulation=simulation)

    async def exercise():
        async with app.run_test(size=size) as pilot:
            app.playing = True
            await pilot.press("r", "left")
            assert not app.playing
            baseline = simulation.history.to_json()
            before = simulation.snapshot()
            await pilot.press("n", "space", "w", "a", "s", "d", "e", "m", "i")
            # An already scheduled timer callback is harmless even if its play flag
            # was stale when replay began.
            app.playing = True
            app._timer_tick()
            app.action_set_control("AUTO")
            assert not app.playing
            assert simulation.history.to_json() == baseline
            assert simulation.frame() == before.frame
            np.testing.assert_array_equal(
                simulation.belief_map.probabilities, before.belief.probabilities
            )
            await pilot.press("tab")
            assert app.selected_drone_id == "02"
            await pilot.press("1", "h", "c", "p")
            assert app.selected_drone_id == "01"
            assert app.layer == "paths"
            assert app.replay_mode
            assert simulation.history.to_json() == baseline
            await pilot.press("r")
            assert simulation.frame() == before.frame
            assert app.tick == before.frame.tick
            assert not app.playing

    asyncio.run(exercise())


@pytest.mark.parametrize("auto", [False, True])
def test_full_history_is_reported_without_crashing_or_mutating_live_state(auto):
    simulation = make_simulation(history_capacity=2 if auto else 1)
    if auto:
        simulation.set_mode("01", OperationalMode.AUTO)
    app = NightjarApp(mode="gridworld", gridworld_simulation=simulation)

    async def exercise():
        async with app.run_test() as pilot:
            baseline = simulation.history.to_json()
            await pilot.press("n", "d", "e", "m", "i")
            if auto:
                app.playing = True
                app._timer_tick()
            assert "HISTORY FULL" in text(app, "#events")
            assert simulation.history.to_json() == baseline
            assert not app.playing
            assert simulation.frame().tick == 0

    asyncio.run(exercise())


def test_resize_during_configuration_preserves_visible_replay_controls_after_launch():
    app = NightjarApp()

    async def exercise():
        async with app.run_test(size=(110, 42)) as pilot:
            assert isinstance(app.screen, MissionConfigScreen)
            await pilot.resize_terminal(80, 24)
            await pilot.press("enter")
            assert isinstance(app.screen, PreflightReviewScreen)
            await pilot.press("enter", "r")
            assert app.replay_mode
            assert app.screen.has_class("compact")
            timeline = app.query_one("#timeline", Static)
            assert timeline.region.bottom <= 24
            assert timeline.region.right <= 80
            assert "R replay / live" in text(app, "#timeline").splitlines()[2]
            await pilot.resize_terminal(110, 42)
            assert not app.screen.has_class("compact")
            assert timeline.region.bottom <= 42

    asyncio.run(exercise())
