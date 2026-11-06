"""Measured comparison viewing and isolated, cancellable screen lifecycle."""

import asyncio

import pytest
from textual.widgets import Static
from textual.containers import ScrollableContainer

from nightjar.core.mission import MapPreset, MissionConfig, ScenarioPreset
from nightjar.services.comparison import ComparisonCancelled
from nightjar.tui.app import NightjarApp
from nightjar.tui.comparison import ComparisonScreen, tick_samples


def config():
    return MissionConfig(
        map_preset=MapPreset.COMPACT, scenario=ScenarioPreset.FACILITY, max_ticks=7
    )


@pytest.mark.parametrize("size", [(110, 42), (80, 24)])
def test_real_paired_maps_replay_and_controls_preserve_live_mission(size):
    app = NightjarApp(mission_config=config())

    async def exercise():
        async with app.run_test(size=size) as pilot:
            app._mission_timer.pause()
            await app.wait_for_commands()
            app.action_scan()
            app.action_comparison()
            app.action_move("east")
            await app.wait_for_commands()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, ComparisonScreen)
            saved = app.gridworld_simulation.history.to_json()
            selected = app.selected_drone_id
            await pilot.press("enter")
            await screen.wait_for_run()
            await pilot.pause()
            assert screen.report is not None and len(screen.report.runs) == 2
            assert not screen.busy
            assert screen.maximum_tick == 7
            finals = screen.query_one("#comparison_finals", Static)
            visible = "\n".join(
                strip.text for strip in finals.render_lines(finals.size.region)
            )
            assert "FRONTIER" in visible and "INFO GAIN" in visible
            assert "BUDGET EXHAUSTED" in visible
            assert screen.query_one("#comparison_close").region.bottom <= size[1]
            active_map = screen.query_one("#comparison_scroll_0")
            assert active_map.content_size.height >= 5
            if size[1] < 30:
                assert not screen.query_one("#comparison_panel_1").display
            else:
                assert screen.query_one("#comparison_panel_1").display
            await pilot.press("tab")
            assert screen.selected_policy == 1
            await pilot.press("home")
            assert screen.cursor == 0
            await pilot.press("right", "c")
            assert screen.cursor == 1 and screen.map_layer == "coverage"
            for index, run in enumerate(screen.report.runs):
                assert run.at_tick(screen.cursor).frame.tick <= screen.cursor
                assert (
                    f"actual tick {run.at_tick(screen.cursor).frame.tick}"
                    in screen.query_one(f"#comparison_label_{index}", Static)
                    .render()
                    .plain
                )
            screen.action_play()
            screen._replay_tick()
            assert screen.cursor == 2
            screen.playing = False
            await pilot.press("q")
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert not isinstance(app.screen, ComparisonScreen)
            assert app.gridworld_simulation.history.to_json() == saved
            assert app.selected_drone_id == selected
            assert not app.playing and not app._comparison_open

    asyncio.run(exercise())


def test_comparison_entry_and_exit_preserve_historical_view():
    app = NightjarApp(mission_config=config())

    async def exercise():
        async with app.run_test() as pilot:
            app._mission_timer.pause()
            await app.wait_for_commands()
            app.action_step()
            app.action_toggle_replay()
            app.action_seek(-1)
            await app.wait_for_commands()
            saved = app.gridworld_simulation.history.to_json()
            index = app._replay_index
            selected = app.selected_drone_id
            await pilot.press("v")
            await app.wait_for_commands()
            assert isinstance(app.screen, ComparisonScreen)
            await pilot.press("q")
            await app.workers.wait_for_complete()
            assert app.replay_mode and app._replay_index == index
            assert app.selected_drone_id == selected and not app.playing
            assert app.gridworld_simulation.history.to_json() == saved

    asyncio.run(exercise())


def test_cancel_waits_without_blocking_screen_and_no_restart(monkeypatch):
    entered = asyncio.Event()
    release = asyncio.Event()
    cancellation = []

    async def delayed(config, *, cancel_event):
        entered.set()
        cancellation.append(cancel_event)
        await release.wait()
        assert cancel_event.is_set()
        raise ComparisonCancelled("cancelled")

    monkeypatch.setattr("nightjar.tui.comparison.compare_policies", delayed)
    app = NightjarApp(mission_config=config())

    async def exercise():
        async with app.run_test() as pilot:
            app._mission_timer.pause()
            await app.wait_for_commands()
            app.action_comparison()
            await app.wait_for_commands()
            screen = app.screen
            assert isinstance(screen, ComparisonScreen)
            await pilot.pause()
            screen.action_run()
            await entered.wait()
            original = screen._experiment_task
            await pilot.press("escape")
            await pilot.pause()
            assert app.screen is screen and screen.busy
            assert (
                "CANCELLING"
                in screen.query_one("#comparison_status", Static).render().plain
            )
            assert cancellation[0].is_set()
            # Resize and switch continue to be handled before the worker completes.
            await pilot.resize_terminal(80, 24)
            await pilot.press("2", "enter")
            assert screen.selected_policy == 1
            assert screen._experiment_task is original
            release.set()
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert app.screen is not screen and not app._comparison_open
            assert not app.playing

    asyncio.run(exercise())


def test_trace_sampling_uses_uniform_ticks_instead_of_snapshot_indices():
    class Recorder:
        def __init__(self):
            self.ticks = []

        def at_tick(self, tick):
            self.ticks.append(tick)
            return tick

    run = Recorder()
    assert tick_samples(run, 10, 6) == (0, 2, 4, 6, 8, 10)


@pytest.mark.parametrize("preset", [MapPreset.COMPACT, MapPreset.EXTENDED])
def test_comparison_scroll_reveals_actual_bottom_and_right_map_cells(preset):
    settings = MissionConfig(
        map_preset=preset, scenario=ScenarioPreset.FACILITY, max_ticks=1
    )
    app = NightjarApp(mission_config=settings)

    async def exercise():
        async with app.run_test(size=(80, 24)) as pilot:
            app._mission_timer.pause()
            await app.wait_for_commands()
            await pilot.press("v")
            await app.wait_for_commands()
            await pilot.press("enter")
            screen = app.screen
            assert isinstance(screen, ComparisonScreen)
            await screen.wait_for_run()
            await pilot.press("h")
            # Terrain room labels make lower rows recognizable; scan tint remains.
            screen.action_layer("terrain")
            await pilot.pause()
            viewport = screen.query_one("#comparison_scroll_0", ScrollableContainer)
            map_widget = screen.query_one("#comparison_map_0")
            assert map_widget.size.height == settings.height
            assert map_widget.size.width == settings.width * 2
            await pilot.press("pagedown")
            await pilot.pause()
            assert viewport.scroll_y > 0
            viewport.scroll_end(animate=False)
            await pilot.pause()
            assert viewport.scroll_y == viewport.max_scroll_y
            if preset is MapPreset.EXTENDED:
                await pilot.press("shift+right")
                await pilot.pause()
                assert viewport.scroll_x > 0
            # Actual terminal compositor output contains bottom-right drone02,
            # not merely offscreen Rich Text retained by a childless Static.
            x = map_widget.region.x + (settings.width - 1) * 2
            y = map_widget.region.y + settings.height - 1
            assert viewport.region.y <= y < viewport.region.bottom
            terminal = screen._compositor.render_strips()
            assert terminal[y].text[x : x + 2] == "02"
            if preset is MapPreset.COMPACT:
                visible = "\n".join(strip.text for strip in terminal)
                assert "WEST HALL" in visible and "OPERATIONS" in visible

    asyncio.run(exercise())


def test_narrow_tall_view_shows_complete_metrics_for_both_policies():
    app = NightjarApp(mission_config=config())

    async def exercise():
        async with app.run_test(size=(80, 30)) as pilot:
            app._mission_timer.pause()
            await app.wait_for_commands()
            await pilot.press("v")
            await app.wait_for_commands()
            await pilot.press("enter")
            screen = app.screen
            assert isinstance(screen, ComparisonScreen)
            await screen.wait_for_run()
            await pilot.pause()
            finals = screen.query_one("#comparison_finals", Static)
            lines = [strip.text for strip in finals.render_lines(finals.size.region)]
            assert len(lines) == 2
            for name, line in zip(("FRONTIER", "INFO GAIN"), lines):
                assert name in line
                assert "7t" in line and "s C" in line and " H" in line
                assert "dH" in line and "BUDGET EXHAUSTED" in line
            assert screen.query_one("#comparison_close").region.bottom <= 30

    asyncio.run(exercise())
