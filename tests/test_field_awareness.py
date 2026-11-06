"""Accepted field events, historical prefixes and read-only presentation."""

import asyncio

import pytest
from textual.widgets import Static

from nightjar.core.mission import (
    MapPreset,
    MissionConfig,
    ScenarioPreset,
    create_simulation,
)
from nightjar.core.provider import GridWorldSimulation
from nightjar.core.sensor import SensorConfig
from nightjar.core.world import GridWorld
from nightjar.tui.app import NightjarApp
from nightjar.tui.awareness import build_awareness
from nightjar.tui.drone_identity import drone_marker
from nightjar.tui.map_widget import MapWidget
from nightjar.tui.presentation import MissionSummaryScreen


def facility(max_ticks=80):
    return create_simulation(
        MissionConfig(
            scenario=ScenarioPreset.FACILITY,
            map_preset=MapPreset.COMPACT,
            drone_count=1,
            max_ticks=max_ticks,
        )
    )


def enter_server(simulation):
    for _ in range(7):
        simulation.step("east")
    simulation.step("east")  # Wall, not a room entry.
    for _ in range(3):
        simulation.step("south")
    simulation.step("east")  # Passable connecting doorway.
    doorway = simulation.snapshot()
    simulation.step("east")
    return doorway, simulation.snapshot()


def test_room_entries_ignore_blocks_and_doors_and_use_only_viewed_prefix():
    simulation = facility()
    doorway, entered = enter_server(simulation)
    simulation.scan("01")
    history = simulation.history
    old = build_awareness(history, doorway)
    current = build_awareness(history, entered)
    assert not old.room_entries
    assert [entry.label for entry in current.room_entries] == [
        "RAVEN ENTERED SERVER ROOM"
    ]
    assert current.room_entries[0].tick == entered.frame.tick
    assert not any("SENSOR" in item.label for item in current.milestones)
    assert any(
        "SENSOR" in item.label
        for item in build_awareness(history, simulation.snapshot()).milestones
    )
    for room in current.room_coverage:
        assert room.total > 0 and 0 <= room.visited <= room.total
    assert sum(room.total for room in current.room_coverage) == (
        entered.frame.width * entered.frame.height - len(entered.frame.obstacles) - 4
    )  # Four connecting door cells are outside the room polygons.


def test_coverage_milestones_and_terminal_reason_are_observed_not_inferred():
    simulation = GridWorldSimulation(
        GridWorld(width=4, height=3, obstacles=()),
        drone_count=1,
        max_ticks=11,
    )
    for direction in (
        "east",
        "east",
        "east",
        "south",
        "west",
        "west",
        "west",
        "south",
        "east",
        "east",
        "east",
    ):
        simulation.step(direction)
    history = simulation.history
    early = build_awareness(history, history.snapshots[2])
    assert any("25%" in item.label for item in early.milestones)
    assert not any(
        "50%" in item.label or "STOP" in item.label for item in early.milestones
    )
    final = build_awareness(history, simulation.snapshot())
    assert [item.label for item in final.milestones] == [
        "FLEET DEPLOYED",
        "25% PHYSICALLY VISITED",
        "50% PHYSICALLY VISITED",
        "75% PHYSICALLY VISITED",
        "MISSION STOP / BUDGET EXHAUSTED",
    ]


def test_positive_reading_is_labelled_unconfirmed_and_recorded_once():
    simulation = GridWorldSimulation(
        GridWorld(width=4, height=3, obstacles=()),
        drone_count=1,
        sensor_config=SensorConfig(sensitivity=1.0, false_positive_probability=1.0),
    )
    simulation.scan("01")
    first = simulation.snapshot()
    simulation.scan("01")
    awareness = build_awareness(simulation.history, first)
    assert [item.label for item in awareness.milestones] == [
        "FLEET DEPLOYED",
        "FIRST SENSOR READING",
        "FIRST POSITIVE SIGNAL / UNCONFIRMED",
    ]
    assert build_awareness(simulation.history, first) == awareness
    assert (
        len(build_awareness(simulation.history, simulation.snapshot()).milestones) == 3
    )


@pytest.mark.parametrize("size", [(110, 42), (80, 24)])
def test_icons_room_logs_and_milestone_modal_preserve_live_and_historical_state(size):
    simulation = facility()
    doorway, entered = enter_server(simulation)
    app = NightjarApp(mode="gridworld", gridworld_simulation=simulation)

    async def exercise():
        async with app.run_test(size=size) as pilot:
            app._mission_timer.pause()
            await app.wait_for_commands()
            original = simulation.history.to_json()
            assert drone_marker("01") in app.query_one("#map", MapWidget).render().plain
            assert (
                "RAVEN ENTERED SERVER ROOM"
                in app.query_one("#events", Static).render().plain
            )
            before = list(app._ui_events)
            app._refresh_screen()
            assert app._ui_events == before
            await pilot.press("g")
            assert "01" in app.query_one("#map", MapWidget).render().plain
            assert simulation.history.to_json() == original
            await pilot.press("t")
            await app.wait_for_commands()
            await pilot.pause()
            assert isinstance(app.screen, MissionSummaryScreen)
            body = app.screen.query_one("#summary_body", Static).render().plain
            assert "MISSION MILESTONES" in body and "SERVER ROOM" in body
            assert "FLEET DEPLOYED" in body and "CLEARED" not in body
            assert app.screen.query_one("#summary_close").region.bottom <= size[1]
            await pilot.press("d", "e", "n", "tab", "g")
            await app.wait_for_commands()
            assert simulation.history.to_json() == original
            await pilot.press("escape", "r")
            await app.wait_for_commands()
            app.action_seek(doorway.index - app._replay_index)
            await app.wait_for_commands()
            live_log = list(app._ui_events)
            await pilot.press("t")
            await app.wait_for_commands()
            await pilot.pause()
            body = app.screen.query_one("#summary_body", Static).render().plain
            assert "HISTORICAL VIEW" in body
            assert "ENTERED SERVER ROOM" not in body
            await pilot.press("q")
            await pilot.pause()
            assert app.replay_mode and app._replay_index == doorway.index
            assert app._ui_events == live_log
            assert simulation.history.to_json() == original
            assert not app.playing

    asyncio.run(exercise())


def test_final_tick_room_entry_precedes_terminal_message_live_and_replay():
    simulation = facility(max_ticks=13)
    enter_server(simulation)
    app = NightjarApp(mode="gridworld", gridworld_simulation=simulation)

    async def exercise():
        async with app.run_test(size=(80, 24)) as pilot:
            app._mission_timer.pause()
            await app.wait_for_commands()
            for replay in (False, True):
                if replay:
                    await pilot.press("r")
                    await app.wait_for_commands()
                events = app.query_one("#events", Static).render().plain
                assert events.index("ENTERED SERVER ROOM") < events.index(
                    "MISSION COMPLETE"
                )
                assert events.count("ENTERED SERVER ROOM") == 1

    asyncio.run(exercise())


@pytest.mark.parametrize("size", [(110, 42), (80, 24)])
def test_unit_designators_stay_inside_their_actual_terminal_grid_cells(size):
    simulation = GridWorldSimulation(
        GridWorld(width=6, height=4, obstacles={(1, 0), (4, 3)}),
        drone_count=3,
    )
    app = NightjarApp(mode="gridworld", gridworld_simulation=simulation)

    async def exercise():
        async with app.run_test(size=size) as pilot:
            app._mission_timer.pause()
            await app.wait_for_commands()
            await pilot.pause()
            widget = app.query_one("#map", MapWidget)
            origin = widget.content_region
            terminal = app.screen._compositor.render_strips()
            for drone, label in zip(simulation.frame().drones, ("R1", "G2", "V3")):
                x, y = drone.position
                row = terminal[origin.y + y].text
                column = origin.x + 2 * x
                assert row[column : column + 2] == label
            # The wall immediately beside R1 must retain its two full cells.
            row = terminal[origin.y].text
            assert row[origin.x : origin.x + 4] == "R1\u2593\u2593"
            await pilot.press("tab", "g")
            await app.wait_for_commands()
            await pilot.pause()
            assert not app.animal_icons
            terminal = app.screen._compositor.render_strips()
            assert terminal[origin.y].text[origin.x : origin.x + 4] == "01\u2593\u2593"

    asyncio.run(exercise())
