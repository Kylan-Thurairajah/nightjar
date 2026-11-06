"""Snapshot-based mission briefing and replay-safe debrief interaction."""

import asyncio

import pytest
from textual.widgets import Static

from nightjar.core.mission import MissionConfig
from nightjar.core.planning import SearchStrategy
from nightjar.core.provider import GridWorldSimulation
from nightjar.core.world import GridWorld
from nightjar.tui.app import NightjarApp
from nightjar.tui.presentation import MissionSummaryScreen, coverage, summary_text


@pytest.mark.parametrize("size", [(110, 42), (80, 24)])
def test_brief_pauses_after_accepted_scan_and_blocks_mission_keys(size):
    simulation = GridWorldSimulation(
        GridWorld(width=8, height=6, obstacles=(), seed=43),
        drone_count=3,
        max_ticks=30,
        search_strategy=SearchStrategy.FRONTIER,
    )
    app = NightjarApp(mode="gridworld", gridworld_simulation=simulation)

    async def exercise():
        async with app.run_test(size=size) as pilot:
            app._mission_timer.pause()
            await app.wait_for_commands()
            app.action_toggle_play()
            app.action_scan()
            app.action_mission_summary()
            # Input arriving behind the summary intent cannot alter the mission.
            app.action_move("east")
            app.action_next_agent()
            app.action_toggle_play()
            await app.wait_for_commands()
            await pilot.pause()
            assert isinstance(app.screen, MissionSummaryScreen)
            assert app.screen.snapshot.frame.tick == 1
            assert simulation.frame().tick == 1
            assert app.screen.snapshot.observations == simulation.observations
            assert not app.playing
            saved = simulation.history.to_json()
            await pilot.press("space", "d", "e", "tab", "r", "n")
            await app.wait_for_commands()
            assert simulation.history.to_json() == saved
            assert app.selected_drone_id == "01"
            assert not app.replay_mode
            body = app.screen.query_one("#summary_body", Static).render().plain
            assert "SCANS       1" in body
            assert "CONFIRMATION NOT MODELED" in body
            assert app.screen.query_one("#summary_close").region.bottom <= size[1]
            await pilot.press("q")
            await pilot.pause()
            assert not isinstance(app.screen, MissionSummaryScreen)
            assert app.is_running
            assert not app.playing and not app._summary_open
            assert simulation.history.to_json() == saved

    asyncio.run(exercise())


def test_terminal_debrief_and_historical_brief_use_the_viewed_snapshot():
    simulation = GridWorldSimulation(
        GridWorld(width=8, height=6, obstacles=(), seed=43),
        drone_count=3,
        max_ticks=2,
        search_strategy=SearchStrategy.FRONTIER,
    )
    app = NightjarApp(mode="gridworld", gridworld_simulation=simulation)

    async def exercise():
        async with app.run_test() as pilot:
            app._mission_timer.pause()
            await app.wait_for_commands()
            app.action_step()
            await app.wait_for_commands()
            assert simulation.frame().tick == 2
            assert "B DEBRIEF" in app.query_one("#mission_focus", Static).render().plain
            await pilot.press("b")
            await app.wait_for_commands()
            await pilot.pause()
            assert isinstance(app.screen, MissionSummaryScreen)
            body = app.screen.query_one("#summary_body", Static).render().plain
            assert "BUDGET EXHAUSTED" in body
            assert "SCANS       2" in body
            assert "TICKS       2 / 2" in body
            await pilot.press("escape", "r")
            await app.wait_for_commands()
            app.action_seek(-100)
            app.action_mission_summary()
            await app.wait_for_commands()
            await pilot.pause()
            assert app.replay_mode
            assert app.screen.snapshot.frame.tick == 0
            body = app.screen.query_one("#summary_body", Static).render().plain
            assert "HISTORICAL VIEW" in body
            assert "SCANS       0" in body
            assert "CHANGE      +0.000" in body
            assert "BUDGET EXHAUSTED" not in body
            await pilot.press("enter")
            await pilot.pause()
            assert app.replay_mode and not app.playing
            assert simulation.frame().tick == 2
            app.action_toggle_replay()
            await app.wait_for_commands()
            assert not app.replay_mode and not app.playing

    asyncio.run(exercise())


def test_summary_coverage_and_entropy_come_from_public_state():
    simulation = GridWorldSimulation(
        GridWorld(width=4, height=3, obstacles={(1, 1)}, seed=4),
        drone_count=1,
    )
    initial = simulation.snapshot()
    simulation.step("east")
    simulation.scan("01")
    snapshot = simulation.snapshot()
    assert coverage(snapshot) == 2 / 11
    text = summary_text(snapshot, initial.belief.stats.entropy_bits).plain
    assert "(2/11 cells)" in text
    assert "SCANS       1" in text
    assert f"{snapshot.belief.stats.entropy_bits:.3f} bits" in text
    assert (
        f"{snapshot.belief.stats.entropy_bits - initial.belief.stats.entropy_bits:+.3f}"
        in text
    )


def test_compact_presentation_keeps_bar_legend_map_rows_and_terminal_status_visible():
    app = NightjarApp(mode="gridworld", mission_config=MissionConfig(max_ticks=2))

    async def exercise():
        async with app.run_test(size=(80, 24)) as pilot:
            app._mission_timer.pause()
            await app.wait_for_commands()
            await pilot.pause()
            focus = app.query_one("#mission_focus", Static)
            focus_lines = [
                strip.text for strip in focus.render_lines(focus.size.region)
            ]
            assert len(focus_lines) == 2
            assert "B BRIEF" in focus_lines[0]
            assert "COVERAGE [" in focus_lines[1] and "]" in focus_lines[1]
            legend = app.query_one("#legend", Static)
            legend_lines = [
                strip.text for strip in legend.render_lines(legend.size.region)
            ]
            assert "RELATIVE INTENSITY" in legend_lines[0]
            assert "TINT LATEST SCAN" in legend_lines[1]
            assert app.query_one("#map").content_size.height >= 5
            app.action_step()
            await app.wait_for_commands()
            await pilot.pause()
            timeline = app.query_one("#timeline", Static)
            visible = "\n".join(
                strip.text for strip in timeline.render_lines(timeline.size.region)
            )
            assert "PLAN:" in visible and "COST" in visible
            assert "BUDGET EXHAUSTED" in visible
            assert "R replay" in visible
            assert timeline.region.bottom <= 24

    asyncio.run(exercise())
