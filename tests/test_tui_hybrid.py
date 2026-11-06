"""Hybrid fleet input, publication and replay ordering through the real TUI."""

import asyncio
import threading

import pytest
from textual.widgets import Static

from nightjar.core.planning import SearchStrategy
from nightjar.core.provider import GridWorldSimulation, OperationalMode
from nightjar.core.replay import ReplayTimeline
from nightjar.core.world import GridWorld
from nightjar.tui.app import NightjarApp


def make_app(*, initial_mode=OperationalMode.MANUAL, max_ticks=80):
    simulation = GridWorldSimulation(
        GridWorld(width=8, height=6, obstacles=(), seed=43),
        drone_count=3,
        initial_mode=initial_mode,
        max_ticks=max_ticks,
        search_strategy=SearchStrategy.FRONTIER,
    )
    return NightjarApp(mode="gridworld", gridworld_simulation=simulation), simulation


def modes(simulation):
    return [drone.mode for drone in simulation.frame().drones]


@pytest.mark.parametrize("size", [(110, 42), (80, 24)])
def test_manual_drone_keeps_control_while_other_drones_run_and_handoff(size):
    app, simulation = make_app()

    async def exercise():
        async with app.run_test(size=size) as pilot:
            app._mission_timer.pause()
            await app.wait_for_commands()
            assert modes(simulation) == [
                OperationalMode.MANUAL,
                OperationalMode.AUTO,
                OperationalMode.AUTO,
            ]
            assert not app.playing
            await pilot.press("space")
            await app.wait_for_commands()
            assert app.playing
            app._timer_tick()
            await app.wait_for_commands()
            assert simulation.frame().tick == 2
            assert [
                observation.drone_id for observation in simulation.observations
            ] == [
                "02",
                "03",
            ]
            assert simulation.frame().drone("01").position == (0, 0)
            await pilot.press("d", "e")
            await app.wait_for_commands()
            assert app.playing
            assert simulation.frame().tick == 4
            assert simulation.frame().drone("01").position == (1, 0)
            await pilot.press("tab")
            await app.wait_for_commands()
            assert app.selected_drone_id == "02"
            assert modes(simulation) == [
                OperationalMode.AUTO,
                OperationalMode.MANUAL,
                OperationalMode.AUTO,
            ]
            assert app.playing
            before = simulation.frame().tick
            app._timer_tick()
            await app.wait_for_commands()
            assert simulation.frame().tick == before + 2
            await pilot.press("space")
            await app.wait_for_commands()
            assert not app.playing
            paused = simulation.history.to_json()
            app._timer_tick()
            await app.wait_for_commands()
            assert simulation.history.to_json() == paused
            ReplayTimeline.from_json(paused)
            timeline = app.query_one("#timeline", Static)
            assert timeline.region.bottom <= size[1]
            assert "FLEET PAUSED" in timeline.render().plain

    asyncio.run(exercise())


def test_idle_launch_stays_parked_and_explicit_activation_then_space_is_ordered():
    app, simulation = make_app(initial_mode=OperationalMode.IDLE)

    async def exercise():
        async with app.run_test() as pilot:
            app._mission_timer.pause()
            await app.wait_for_commands()
            await pilot.press("space", "n", "tab", "d", "e")
            await app.wait_for_commands()
            assert simulation.frame().tick == 0
            assert all(mode is OperationalMode.IDLE for mode in modes(simulation))
            assert not app.playing
            # These requests are submitted without waiting between them: Space
            # must see M's committed AUTO activation rather than stale IDLE state.
            app.action_toggle_control()  # IDLE -> MANUAL
            app.action_toggle_control()  # MANUAL -> AUTO
            app.action_toggle_play()
            await app.wait_for_commands()
            assert app.playing
            assert modes(simulation) == [
                OperationalMode.IDLE,
                OperationalMode.AUTO,
                OperationalMode.IDLE,
            ]
            app._timer_tick()
            await app.wait_for_commands()
            assert simulation.frame().tick == 1
            app.action_set_control("IDLE")
            await app.wait_for_commands()
            assert not app.playing
            assert all(mode is OperationalMode.IDLE for mode in modes(simulation))

    asyncio.run(exercise())


def test_n_steps_auto_fleet_without_implicitly_moving_manual_drone():
    app, simulation = make_app(max_ticks=1)

    async def exercise():
        async with app.run_test() as pilot:
            app._mission_timer.pause()
            await app.wait_for_commands()
            initial_position = simulation.frame().drone("01").position
            await pilot.press("n")
            await app.wait_for_commands()
            assert simulation.frame().tick == 1
            assert simulation.frame().drone("01").position == initial_position
            assert [o.drone_id for o in simulation.observations] == ["02"]
            assert simulation.frame().status.value == "BUDGET EXHAUSTED"
            assert not app.playing
            saved = simulation.history.to_json()
            await pilot.press("n", "space", "m", "d", "e")
            await app.wait_for_commands()
            assert simulation.history.to_json() == saved
            ReplayTimeline.from_json(saved)

    asyncio.run(exercise())


def install_slow_planner(simulation):
    entered = threading.Event()
    release = threading.Event()
    planner = simulation._planner

    class SlowPlanner:
        def decide(self, state):
            entered.set()
            if not release.wait(timeout=10):
                raise RuntimeError("test failed to release the planner")
            return planner.decide(state)

    simulation._planner = SlowPlanner()
    return entered, release


def test_slow_round_keeps_ui_responsive_and_serializes_manual_handoff_input():
    app, simulation = make_app()
    entered, release = install_slow_planner(simulation)

    async def exercise():
        async with app.run_test():
            app._mission_timer.pause()
            await app.wait_for_commands()
            app.action_toggle_play()
            await app.wait_for_commands()
            initial = app._gridworld_snapshot()
            app._timer_tick()
            try:
                assert await asyncio.wait_for(asyncio.to_thread(entered.wait), 3)
                for _ in range(10):
                    app._timer_tick()
                assert app._pending_commands == 1
                app.action_move("east")
                app.action_select_drone("02")
                app.action_scan()
                heartbeat = asyncio.Event()
                asyncio.get_running_loop().call_soon(heartbeat.set)
                await asyncio.wait_for(heartbeat.wait(), 1)
                assert app._gridworld_snapshot() is initial
                assert app._pending_commands == 4
            finally:
                release.set()
            await app.wait_for_commands()
            assert app.playing
            assert app.selected_drone_id == "02"
            assert simulation.frame().tick == 4
            assert simulation.frame().drone("01").position == (1, 0)
            assert simulation.observations[-1].drone_id == "02"
            assert simulation.frame().drone("02").mode is OperationalMode.MANUAL
            ReplayTimeline.from_json(simulation.history.to_json())

    asyncio.run(exercise())


def test_replay_waits_for_round_and_preserves_queued_view_and_exit_input_order():
    app, simulation = make_app()
    entered, release = install_slow_planner(simulation)

    async def exercise():
        async with app.run_test():
            app._mission_timer.pause()
            await app.wait_for_commands()
            app.action_toggle_play()
            await app.wait_for_commands()
            app._timer_tick()
            try:
                assert await asyncio.wait_for(asyncio.to_thread(entered.wait), 3)
                app.action_toggle_replay()
                app.action_seek(-1)
                app.action_select_drone("02")
                app.action_move("east")  # after replay entry: viewing-only no-op
                assert not app.playing
            finally:
                release.set()
            await app.wait_for_commands()
            assert app.replay_mode
            assert app._replay_index == len(simulation.history.snapshots) - 2
            assert simulation.frame().tick == 2
            assert app.selected_drone_id == "02"
            saved = simulation.history.to_json()
            assert simulation.frame().drone("01").mode is OperationalMode.MANUAL
            app.action_toggle_replay()
            app.action_move("east")  # after exit: operates restored live owner 01
            await app.wait_for_commands()
            assert not app.replay_mode
            assert app.selected_drone_id == "01"
            assert simulation.frame().tick == 3
            assert simulation.frame().drone("01").position == (1, 0)
            assert not app.playing
            assert (
                len(simulation.history.snapshots)
                == len(ReplayTimeline.from_json(saved).snapshots) + 1
            )

    asyncio.run(exercise())


def test_rapid_tab_replay_toggles_and_pause_supersede_stale_resume():
    app, simulation = make_app()

    async def exercise():
        async with app.run_test():
            app._mission_timer.pause()
            await app.wait_for_commands()
            app.action_next_agent()
            app.action_next_agent()
            await app.wait_for_commands()
            assert app.selected_drone_id == "03"
            before = simulation.history.to_json()
            app.action_toggle_replay()
            app.action_toggle_replay()
            app.action_toggle_play()
            app.action_step()
            await app.wait_for_commands()
            assert not app.replay_mode and not app.playing
            assert simulation.frame().tick == 2
            # Only the explicit N round executed; no stale resume/timer action.
            assert (
                len(simulation.history.snapshots)
                == len(ReplayTimeline.from_json(before).snapshots) + 1
            )

    asyncio.run(exercise())


def test_denied_manual_keys_on_parked_drone_do_not_pause_other_auto_drones():
    app, simulation = make_app()

    async def exercise():
        async with app.run_test() as pilot:
            app._mission_timer.pause()
            await app.wait_for_commands()
            await pilot.press("space", "i", "d", "e")
            await app.wait_for_commands()
            assert app.playing
            assert simulation.frame().drone("01").mode is OperationalMode.IDLE
            assert simulation.frame().tick == 0
            app._timer_tick()
            await app.wait_for_commands()
            assert simulation.frame().tick == 2
            assert [o.drone_id for o in simulation.observations] == ["02", "03"]
            assert "NOT MANUAL" in app.query_one("#events", Static).render().plain

    asyncio.run(exercise())


def test_replay_blocked_resume_cannot_cancel_newer_run_after_exit():
    app, simulation = make_app()

    async def exercise():
        async with app.run_test():
            app._mission_timer.pause()
            await app.wait_for_commands()
            app.action_toggle_replay()
            await app.wait_for_commands()
            saved = simulation.history.to_json()
            app.action_toggle_play()  # rejected in replay, superseded below
            app.action_toggle_replay()  # exit, paused
            app.action_toggle_play()  # valid explicit resume after exit
            app._timer_tick()  # cached replay must not discard queued run intent
            await app.wait_for_commands()
            assert not app.replay_mode
            assert app.playing
            assert simulation.history.to_json() == saved
            app._timer_tick()
            await app.wait_for_commands()
            assert simulation.frame().tick == 2
            app.action_toggle_play()  # pause must supersede prior run intent
            app.action_toggle_play()
            app.action_toggle_play()
            await app.wait_for_commands()
            assert not app.playing
            before = simulation.history.to_json()
            app._timer_tick()
            await app.wait_for_commands()
            assert simulation.history.to_json() == before

    asyncio.run(exercise())


def test_stale_no_auto_resume_cannot_cancel_newer_run_after_activation():
    app, simulation = make_app(initial_mode=OperationalMode.IDLE)

    async def exercise():
        async with app.run_test():
            app._mission_timer.pause()
            await app.wait_for_commands()
            app.action_toggle_play()  # no AUTO yet
            app.action_toggle_control()  # IDLE -> MANUAL
            app.action_toggle_control()  # MANUAL -> AUTO
            app.action_toggle_play()  # cancel old projected resume
            app.action_toggle_play()  # resume activated fleet
            await app.wait_for_commands()
            assert app.playing
            app._timer_tick()
            await app.wait_for_commands()
            assert simulation.frame().tick == 1

    asyncio.run(exercise())
