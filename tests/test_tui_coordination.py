"""Real coordinated planners through hybrid controls and historical viewing."""

import asyncio

import pytest
from textual.widgets import Static

from nightjar.core.planning import PlannerActionType, SearchStrategy
from nightjar.core.provider import GridWorldSimulation, OperationalMode
from nightjar.core.replay import ReplayTimeline
from nightjar.core.world import GridWorld
from nightjar.tui.app import NightjarApp


@pytest.mark.parametrize("size", [(110, 42), (80, 24)])
@pytest.mark.parametrize(
    "strategy", [SearchStrategy.FRONTIER, SearchStrategy.INFORMATION_GAIN]
)
def test_coordinated_rounds_preserve_manual_handoff_parking_and_replay(size, strategy):
    simulation = GridWorldSimulation(
        GridWorld(width=8, height=6, obstacles=(), seed=43),
        drone_count=3,
        max_ticks=100,
        search_strategy=strategy,
    )
    actual_planner = simulation._planner
    recorded = []

    class RecordingPlanner:
        def decide(self, state):
            decision = actual_planner.decide(state)
            recorded.append((state, decision))
            return decision

    # Observe public planner inputs without substituting actions or using hidden state.
    simulation._planner = RecordingPlanner()
    app = NightjarApp(mode="gridworld", gridworld_simulation=simulation)

    async def exercise():
        async with app.run_test(size=size) as pilot:
            app._mission_timer.pause()
            await app.wait_for_commands()
            await pilot.press("d", "e", "space")
            await app.wait_for_commands()
            manual = simulation.frame().drone("01")
            assert manual.position == (1, 0)
            assert manual.mode is OperationalMode.MANUAL
            assert app.playing

            for _ in range(2):
                before = simulation.frame()
                coverage = frozenset().union(
                    *(drone.visited for drone in before.drones)
                )
                recorded.clear()
                app._timer_tick()
                await app.wait_for_commands()
                assert simulation.frame().tick == before.tick + 2
                assert len(recorded) == 2
                first_state, first = recorded[0]
                second_state, second = recorded[1]
                assert first_state.visited == coverage
                assert manual.visited <= first_state.visited
                assert coverage <= second_state.visited
                assert first_state.reserved_targets == frozenset()
                if first.action.type is PlannerActionType.MOVE:
                    assert second_state.reserved_targets == frozenset({first.target})
                    assert second.target != first.target
                else:
                    assert second_state.reserved_targets == frozenset()
                assert app._controller.live_snapshot.frame == simulation.frame()
                assert app._controller.live_snapshot.last_planner_decision == second
                assert simulation.frame().drone("01") == manual

            await pilot.press("tab", "e", "i")
            await app.wait_for_commands()
            assert app.selected_drone_id == "02"
            assert simulation.frame().drone("01").mode is OperationalMode.AUTO
            parked = simulation.frame().drone("02")
            assert parked.mode is OperationalMode.IDLE
            assert simulation.observations[-1].drone_id == "02"
            assert app.playing
            before = simulation.frame().tick
            recorded.clear()
            app._timer_tick()
            await app.wait_for_commands()
            assert simulation.frame().tick == before + 2
            assert len(recorded) == 2
            assert simulation.frame().drone("02") == parked

            await pilot.press("r")
            await app.wait_for_commands()
            saved = simulation.history.to_json()
            await pilot.press("left", "tab", "d", "e", "m", "i", "n")
            await app.wait_for_commands()
            assert app.replay_mode
            assert not app.playing
            assert app.selected_drone_id == "03"
            assert simulation.history.to_json() == saved
            await pilot.press("r")
            await app.wait_for_commands()
            assert not app.replay_mode
            assert not app.playing
            assert app.selected_drone_id == "02"
            assert simulation.history.to_json() == saved
            loaded = ReplayTimeline.from_json(saved)
            assert loaded.snapshots[-1].frame == simulation.frame()
            timeline = app.query_one("#timeline", Static)
            assert timeline.region.bottom <= size[1]
            assert "FLEET PAUSED" in timeline.render().plain

    asyncio.run(exercise())
