import asyncio

import pytest
from textual.widgets import Input, RadioButton, RadioSet, Static

from nightjar.core.mission import MapPreset, MissionConfig, ScenarioPreset
from nightjar.core.provider import GridWorldSimulation, MissionStatus, OperationalMode
from nightjar.core.planning import SearchStrategy
from nightjar.core.sensor import SensorPreset
from nightjar.core.world import Direction, GridWorld
from nightjar.tui.app import NightjarApp
from nightjar.tui.map_widget import MapWidget
from nightjar.tui.mission_screens import (
    DroneCountSlider,
    MissionConfigScreen,
    PreflightReviewScreen,
)


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
            assert (
                "POSITION    (00,00)"
                in app.query_one("#metrics", Static).render().plain
            )
            assert (
                "NEUTRAL TERRAIN" in app.query_one("#map_title", Static).render().plain
            )

    asyncio.run(check_rendered_grid())


def test_manual_keys_advance_one_gridworld_step_and_report_move_and_block():
    simulation = GridWorldSimulation(
        GridWorld(width=4, height=3, obstacles={(1, 1)}),
        (Direction.EAST, Direction.SOUTH),
    )
    app = NightjarApp(mode="gridworld", gridworld_simulation=simulation)

    async def check_step_behavior():
        async with app.run_test() as pilot:
            await pilot.press("d")
            await app.wait_for_commands()
            frame = simulation.frame()
            assert frame.tick == 1
            assert frame.position == (1, 0)
            assert "MOVED EAST" in app.query_one("#events", Static).render().plain
            assert "TICK" in app.query_one("#metrics", Static).render().plain
            assert "MOVED EAST" in app.query_one("#metrics", Static).render().plain

            await pilot.press("s")
            await app.wait_for_commands()
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
            await pilot.press("w")
            await app.wait_for_commands()
            assert simulation.frame().tick == 1
            assert simulation.frame().position == (0, 0)
            assert (
                "BLOCKED BY BOUNDARY" in app.query_one("#events", Static).render().plain
            )

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
            await app.wait_for_commands()
            assert simulation.frame().tick == 1
            assert simulation.frame().position == (0, 0)
            assert "BLOCKED BY WALL" in app.query_one("#events", Static).render().plain

            await pilot.press("w")
            await app.wait_for_commands()
            assert simulation.frame().tick == 2
            assert simulation.frame().position == (0, 0)
            assert (
                "BLOCKED BY BOUNDARY" in app.query_one("#events", Static).render().plain
            )

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
            await app.wait_for_commands()
            assert simulation.frame().position == (1, 0)
            assert simulation.frame().tick == 1

            await pilot.press("s")
            await app.wait_for_commands()
            assert simulation.frame().position == (1, 1)
            assert simulation.frame().tick == 2

            await pilot.press("c")
            await app.wait_for_commands()
            assert app.layer == "coverage"
            assert "VISITED CELLS" in app.query_one("#map_title", Static).render().plain
            coverage_map = app.query_one("#map", MapWidget).render().plain
            assert "▒▒" in coverage_map

            await pilot.press("a")
            await app.wait_for_commands()
            assert simulation.frame().position == (0, 1)
            assert app.layer == "coverage"
            assert "VISITED CELLS" in app.query_one("#map_title", Static).render().plain
            assert "▒▒" in app.query_one("#map", MapWidget).render().plain

            await pilot.press("p")
            await app.wait_for_commands()
            assert app.layer == "paths"
            assert (
                "TRAVEL HISTORY" in app.query_one("#map_title", Static).render().plain
            )
            assert "••" in app.query_one("#map", MapWidget).render().plain

            await pilot.press("d")
            await app.wait_for_commands()
            assert app.layer == "paths"
            assert (
                "TRAVEL HISTORY" in app.query_one("#map_title", Static).render().plain
            )

            await pilot.press("h")
            await app.wait_for_commands()
            assert app.layer == "belief"
            assert (
                "BELIEF HEATMAP" in app.query_one("#map_title", Static).render().plain
            )
            await pilot.press("h")
            await app.wait_for_commands()
            assert app.layer == "terrain"
            assert (
                "NEUTRAL TERRAIN" in app.query_one("#map_title", Static).render().plain
            )
            assert "██" not in app.query_one("#map", MapWidget).render().plain

    asyncio.run(check_manual_moves_and_overlays())


def test_drone_selection_hands_off_modes_and_manual_controls_move_selected_drone():
    simulation = GridWorldSimulation(
        GridWorld(width=5, height=4, obstacles=()),
        (Direction.EAST,),
    )
    app = NightjarApp(mode="gridworld", gridworld_simulation=simulation)

    async def check_drone_selection_and_movement():
        async with app.run_test() as pilot:
            initial = simulation.frame()
            assert all(
                f"[{drone.identifier}] {drone.callsign}"
                in app.query_one("#agents", Static).render().plain
                for drone in initial.drones
            )

            await pilot.press("d")
            await app.wait_for_commands()
            before_selection = simulation.frame()
            await pilot.press("2")
            await app.wait_for_commands()
            selected_state = simulation.frame()
            assert before_selection.tick == selected_state.tick
            assert [d.position for d in before_selection.drones] == [
                d.position for d in selected_state.drones
            ]
            assert selected_state.drone("01").mode is OperationalMode.AUTO
            assert selected_state.drone("02").mode is OperationalMode.MANUAL
            assert app.selected_drone_id == "02"
            assert (
                "SELECTED 02 GHOST" in app.query_one("#events", Static).render().plain
            )

            await pilot.press("a")
            await app.wait_for_commands()
            moved = simulation.frame()
            assert moved.drone("01").position == (1, 0)
            assert moved.drone("01").path == ((0, 0), (1, 0))
            assert moved.drone("02").position == (3, 3)
            assert moved.drone("02").path == ((4, 3), (3, 3))
            assert moved.drone("03").position == (4, 0)
            assert app.selected_drone_id == "02"
            assert "[02] GHOST" in app.query_one("#agents", Static).render().plain

            await pilot.press("tab")
            await app.wait_for_commands()
            assert app.selected_drone_id == "03"
            assert (
                "SELECTED 03 VIPER" in app.query_one("#events", Static).render().plain
            )

    asyncio.run(check_drone_selection_and_movement())


def test_multi_drone_coverage_and_path_overlays_combine_agent_state():
    simulation = GridWorldSimulation(
        GridWorld(width=5, height=4, obstacles=()),
        (Direction.EAST,),
    )
    app = NightjarApp(mode="gridworld", gridworld_simulation=simulation)

    async def check_aggregate_overlays():
        async with app.run_test() as pilot:
            await pilot.press("d", "2", "a", "c")
            await app.wait_for_commands()
            coverage_map = app.query_one("#map", MapWidget).render().plain
            assert "▒▒" in coverage_map

            await pilot.press("p")
            await app.wait_for_commands()
            path_map = app.query_one("#map", MapWidget).render().plain
            assert "••" in path_map
            assert "01" in path_map
            assert "02" in path_map
            assert "03" in path_map

    asyncio.run(check_aggregate_overlays())


def test_demo_overlay_controls_remain_functional():
    app = NightjarApp(mode="demo")

    async def check_demo_overlays():
        async with app.run_test() as pilot:
            await pilot.press("c")
            await app.wait_for_commands()
            assert app.layer == "coverage"
            assert "VISITED CELLS" in app.query_one("#map_title", Static).render().plain
            await pilot.press("p")
            await app.wait_for_commands()
            assert app.layer == "paths"
            assert (
                "TRAVEL HISTORY" in app.query_one("#map_title", Static).render().plain
            )
            await pilot.press("h")
            await app.wait_for_commands()
            assert app.layer == "belief"
            assert (
                "PROBABILITY GRID" in app.query_one("#map_title", Static).render().plain
            )

    asyncio.run(check_demo_overlays())


def test_explicit_demo_mode_steps_the_original_scripted_timeline():
    app = NightjarApp(mode="demo")

    async def check_demo_mode():
        async with app.run_test() as pilot:
            assert "DEMO MODE" in app.query_one("#masthead", Static).render().plain
            await pilot.press("n")
            await app.wait_for_commands()
            assert app.tick == 1
            assert len(app.sim.frame(app.tick).agents) == 3

    asyncio.run(check_demo_mode())


def test_default_startup_opens_mission_configuration():
    app = NightjarApp()

    async def check_default_startup():
        async with app.run_test(size=(100, 40)):
            assert isinstance(app.screen, MissionConfigScreen)

    asyncio.run(check_default_startup())


def test_preflight_settings_persist_when_returning_to_configuration_and_launch():
    app = NightjarApp()

    async def configure_review_and_launch():
        async with app.run_test(size=(100, 42)) as pilot:
            config_screen = app.screen
            assert isinstance(config_screen, MissionConfigScreen)
            config_screen.query_one("#operation_name", Input).value = "NIGHTFALL"
            config_screen.query_one("#drone_count", DroneCountSlider).value = 5
            config_screen.query_one("#map-compact", RadioButton).value = True
            config_screen.query_one("#scenario-open", RadioButton).value = True
            config_screen.query_one("#max_ticks", Input).value = "17"
            config_screen.query_one("#seed", Input).value = "29"
            config_screen.query_one("#sensor-degraded", RadioButton).value = True
            config_screen.query_one("#planner-random", RadioButton).value = True

            await pilot.press("enter")
            await app.wait_for_commands()
            assert isinstance(app.screen, PreflightReviewScreen)
            summary = app.screen.query_one("#mission_summary", Static).render().plain
            validation = (
                app.screen.query_one("#validation_results", Static).render().plain
            )
            assert "NIGHTFALL" in summary
            assert "16" in summary and "12" in summary
            assert "5" in summary
            assert "17" in summary
            assert "29" in summary
            assert "DEGRADED" in summary
            assert "RANDOM" in summary
            assert "75% sensitivity / 15% false positive" in summary
            callsigns = app.screen.query_one("#callsigns", Static).render().plain
            assert "01  RAVEN" in callsigns
            assert "05  SPECTER" in callsigns
            assert "PASS" in validation

            await pilot.press("escape")
            await app.wait_for_commands()
            assert isinstance(app.screen, MissionConfigScreen)
            assert app.screen.query_one("#operation_name", Input).value == "NIGHTFALL"
            assert app.screen.query_one("#drone_count", DroneCountSlider).value == 5
            assert (
                app.screen.query_one("#map_preset", RadioSet).pressed_button.id
                == "map-compact"
            )
            assert (
                app.screen.query_one("#scenario", RadioSet).pressed_button.id
                == "scenario-open"
            )
            assert (
                app.screen.query_one("#sensor_preset", RadioSet).pressed_button.id
                == "sensor-degraded"
            )

            await pilot.press("enter")
            await app.wait_for_commands()
            assert isinstance(app.screen, PreflightReviewScreen)
            await pilot.press("enter")
            await app.wait_for_commands()
            frame = app.gridworld_simulation.frame()
            assert app.mode == "gridworld"
            assert app.mission_config.operation_name == "NIGHTFALL"
            assert (frame.width, frame.height) == (16, 12)
            assert len(frame.drones) == 5
            assert frame.tick == 0
            assert frame.max_ticks == 17
            assert frame.seed == 29
            assert app.mission_config.sensor_preset is SensorPreset.DEGRADED
            assert app.gridworld_simulation.sensor_config.sensitivity == 0.75
            assert app.gridworld_simulation.search_strategy is SearchStrategy.RANDOM

    asyncio.run(configure_review_and_launch())


def test_invalid_configuration_displays_error_without_opening_preflight():
    app = NightjarApp()

    async def submit_invalid_seed():
        async with app.run_test(size=(100, 42)) as pilot:
            assert isinstance(app.screen, MissionConfigScreen)
            app.screen.query_one("#seed", Input).value = "-1"
            await pilot.press("enter")
            await app.wait_for_commands()
            assert isinstance(app.screen, MissionConfigScreen)
            error = app.screen.query_one("#form_error", Static).render().plain
            assert "CONFIGURATION INVALID" in error
            assert "Random seed" in error

    asyncio.run(submit_invalid_seed())


def test_drone_count_slider_keyboard_limits_and_navigation_buttons():
    app = NightjarApp()

    async def check_slider_and_buttons():
        async with app.run_test(size=(100, 42)) as pilot:
            assert isinstance(app.screen, MissionConfigScreen)
            slider = app.screen.query_one("#drone_count", DroneCountSlider)
            slider.focus()
            await pilot.press("right", "right")
            await app.wait_for_commands()
            assert slider.value == 5
            assert "05 DRONES" in slider.render().plain

            await pilot.press("end", "right")
            await app.wait_for_commands()
            assert slider.value == 10
            await pilot.press("right")
            await app.wait_for_commands()
            assert slider.value == 10
            await pilot.press("home", "left")
            await app.wait_for_commands()
            assert slider.value == 1
            await pilot.press("left")
            await app.wait_for_commands()
            assert slider.value == 1

            slider.value = 6
            await pilot.click("#next")
            await app.wait_for_commands()
            assert isinstance(app.screen, PreflightReviewScreen)
            summary = app.screen.query_one("#mission_summary", Static).render().plain
            assert "DRONES        06" in summary

            await pilot.click("#back")
            await app.wait_for_commands()
            assert isinstance(app.screen, MissionConfigScreen)
            assert app.screen.query_one("#drone_count", DroneCountSlider).value == 6

    asyncio.run(check_slider_and_buttons())


def test_configuration_navigation_buttons_remain_visible_in_compact_terminal():
    app = NightjarApp()

    async def check_compact_navigation():
        async with app.run_test(size=(80, 24)) as pilot:
            assert isinstance(app.screen, MissionConfigScreen)
            await pilot.click("#next")
            await app.wait_for_commands()
            assert isinstance(app.screen, PreflightReviewScreen)
            await pilot.pause()
            await pilot.click("#back")
            await app.wait_for_commands()
            assert isinstance(app.screen, MissionConfigScreen)

    asyncio.run(check_compact_navigation())


def test_mission_ui_enforces_tick_budget_and_allows_idle_to_manual_transition():
    config = MissionConfig(
        scenario=ScenarioPreset.OPEN_FIELD,
        drone_count=1,
        map_preset=MapPreset.COMPACT,
        max_ticks=1,
    )
    app = NightjarApp(mode="gridworld", mission_config=config)

    async def check_mission_controls():
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.press("d")
            await app.wait_for_commands()
            frame = app.gridworld_simulation.frame()
            assert frame.tick == 1
            assert frame.status.value == "BUDGET EXHAUSTED"
            await pilot.press("d")
            await app.wait_for_commands()
            assert app.gridworld_simulation.frame().tick == 1
            assert (
                "BUDGET EXHAUSTED" in app.query_one("#metrics", Static).render().plain
            )

    asyncio.run(check_mission_controls())


def test_e_scans_with_selected_drone_and_renders_the_observation():
    config = MissionConfig(
        scenario=ScenarioPreset.OPEN_FIELD,
        drone_count=3,
        map_preset=MapPreset.COMPACT,
        max_ticks=5,
    )
    app = NightjarApp(mode="gridworld", mission_config=config)

    async def check_sensor_scan():
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.press("2", "e")
            await app.wait_for_commands()
            observation = app.gridworld_simulation.observations[-1]
            assert observation.drone_id == "02"
            assert (
                observation.position
                == app.gridworld_simulation.frame().drone("02").position
            )
            assert observation.tick == 1
            metrics = app.query_one("#metrics", Static).render().plain
            assert "SENSOR      LAST 001" in metrics
            assert "PRESET      STANDARD" in metrics
            assert "OBSERVATIONS" in metrics
            assert "LAST READING" in metrics
            events = app.query_one("#events", Static).render().plain
            assert "GHOST SENSOR SCAN INITIATED" in events
            assert "GHOST PROXIMITY:" in events
            assert app.gridworld_simulation.debug_objective_position() not in {
                drone.position for drone in app.gridworld_simulation.frame().drones
            }

    asyncio.run(check_sensor_scan())


def test_e_after_tick_budget_exhaustion_is_rejected_and_logged():
    config = MissionConfig(
        scenario=ScenarioPreset.OPEN_FIELD,
        drone_count=1,
        map_preset=MapPreset.COMPACT,
        max_ticks=1,
    )
    app = NightjarApp(mode="gridworld", mission_config=config)

    async def check_rejected_scan():
        async with app.run_test() as pilot:
            await pilot.press("e")
            await app.wait_for_commands()
            assert (
                app.gridworld_simulation.frame().status
                is MissionStatus.BUDGET_EXHAUSTED
            )
            assert len(app.gridworld_simulation.observations) == 1
            await pilot.press("e")
            await app.wait_for_commands()
            assert len(app.gridworld_simulation.observations) == 1
            assert app.gridworld_simulation.frame().tick == 1
            assert (
                "SCAN DENIED / MISSION INACTIVE"
                in app.query_one("#events", Static).render().plain
            )

    asyncio.run(check_rejected_scan())


def test_h_displays_shared_belief_heatmap_and_scan_updates_map_and_statistics():
    app = NightjarApp(
        mode="gridworld",
        mission_config=MissionConfig(
            scenario=ScenarioPreset.OBSTACLE_FIELD,
            drone_count=2,
            map_preset=MapPreset.COMPACT,
            seed=12,
            max_ticks=20,
        ),
    )

    async def check_belief_overlay():
        async with app.run_test(size=(110, 42)) as pilot:
            simulation = app.gridworld_simulation
            initial_probabilities = simulation.belief_map.probabilities.copy()
            initial_entropy = simulation.belief_stats.entropy_bits
            await pilot.press("h")
            await app.wait_for_commands()
            assert app.layer == "belief"
            assert (
                "BELIEF HEATMAP" in app.query_one("#map_title", Static).render().plain
            )
            assert (
                "RELATIVE INTENSITY" in app.query_one("#legend", Static).render().plain
            )
            initial_map = app.query_one("#map", MapWidget).render().plain
            assert "01" in initial_map and "▓▓" in initial_map
            assert "░░" in initial_map

            await pilot.press("e")
            await app.wait_for_commands()
            assert not (
                simulation.belief_map.probabilities == initial_probabilities
            ).all()
            assert simulation.belief_stats.entropy_bits != initial_entropy
            updated_map = app.query_one("#map", MapWidget).render().plain
            assert updated_map != initial_map
            assert "01" in updated_map and "▓▓" in updated_map
            metrics = app.query_one("#metrics", Static).render().plain
            assert "BELIEF H" in metrics
            assert "ΔH / PRIOR" in metrics
            assert "MAP CELL" in metrics
            assert "MAP PROB" in metrics
            assert "CANDIDATES" in metrics
            assert "ΔH" in app.query_one("#events", Static).render().plain

            after_scan = simulation.belief_map.probabilities.copy()
            await pilot.press("d")
            await app.wait_for_commands()
            assert app.layer == "belief"
            assert (simulation.belief_map.probabilities == after_scan).all()

            await pilot.press("c", "p")
            await app.wait_for_commands()
            assert app.layer == "paths"
            await pilot.press("h")
            await app.wait_for_commands()
            assert app.layer == "belief"
            await pilot.press("h")
            await app.wait_for_commands()
            assert app.layer == "terrain"

    asyncio.run(check_belief_overlay())


def test_idle_mission_blocks_movement_until_manual_control_is_selected():
    config = MissionConfig(
        scenario=ScenarioPreset.OPEN_FIELD,
        drone_count=1,
        map_preset=MapPreset.COMPACT,
        initial_control=OperationalMode.IDLE,
    )
    app = NightjarApp(mode="gridworld", mission_config=config)

    async def check_idle_transition():
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.press("d")
            await app.wait_for_commands()
            assert app.gridworld_simulation.frame().tick == 0
            assert "MOVEMENT DENIED" in app.query_one("#events", Static).render().plain
            await pilot.press("m", "d")
            await app.wait_for_commands()
            frame = app.gridworld_simulation.frame()
            assert frame.tick == 1
            assert frame.drones[0].mode.value == "MANUAL"

    asyncio.run(check_idle_transition())


def test_autonomous_toggle_and_n_execute_one_planner_action_per_tick():
    simulation = GridWorldSimulation(
        GridWorld(width=8, height=6, obstacles=()),
        drone_count=1,
        max_ticks=10,
        search_strategy=SearchStrategy.RANDOM,
    )
    app = NightjarApp(mode="gridworld", gridworld_simulation=simulation)

    async def check_autonomous_controls():
        async with app.run_test() as pilot:
            await pilot.press("m")
            await app.wait_for_commands()
            assert simulation.frame().drone("01").mode is OperationalMode.AUTO
            await pilot.press("e")
            await app.wait_for_commands()
            assert simulation.frame().tick == 0
            assert (
                "SCAN DENIED / SELECTED DRONE NOT MANUAL"
                in app.query_one("#events", Static).render().plain
            )
            await pilot.press("n")
            await app.wait_for_commands()
            assert simulation.frame().tick == 1
            assert simulation.last_planner_decision is not None
            assert simulation.last_planner_decision.strategy is SearchStrategy.RANDOM
            metrics = app.query_one("#metrics", Static).render().plain
            assert "PLANNER     RANDOM" in metrics
            assert "PLAN:" in app.query_one("#timeline", Static).render().plain

            await pilot.press("n")
            await app.wait_for_commands()
            assert simulation.frame().tick == 2
            await pilot.press("m")
            await app.wait_for_commands()
            assert simulation.frame().drone("01").mode is OperationalMode.MANUAL
            before_manual_move = simulation.frame().tick
            await pilot.press("d")
            await app.wait_for_commands()
            assert simulation.frame().tick == before_manual_move + 1

    asyncio.run(check_autonomous_controls())


def test_space_runs_and_pauses_single_drone_fleet():
    simulation = GridWorldSimulation(
        GridWorld(width=8, height=6, obstacles=()),
        drone_count=1,
        max_ticks=10,
        search_strategy=SearchStrategy.FRONTIER,
    )
    app = NightjarApp(mode="gridworld", gridworld_simulation=simulation)

    async def check_auto_pause_resume():
        async with app.run_test() as pilot:
            await pilot.press("m")
            await app.wait_for_commands()
            await pilot.press("space")
            await app.wait_for_commands()
            assert app.playing
            app._timer_tick()
            await app.wait_for_commands()
            assert simulation.frame().tick >= 1
            await pilot.press("space")
            await app.wait_for_commands()
            assert not app.playing
            paused_tick = simulation.frame().tick
            app._timer_tick()
            assert simulation.frame().tick == paused_tick

    asyncio.run(check_auto_pause_resume())


def test_information_gain_decision_is_summarized_in_existing_timeline():
    simulation = GridWorldSimulation(
        GridWorld(width=8, height=6, obstacles=()),
        drone_count=1,
        max_ticks=10,
        search_strategy=SearchStrategy.INFORMATION_GAIN,
    )
    app = NightjarApp(mode="gridworld", gridworld_simulation=simulation)

    async def check_summary():
        async with app.run_test() as pilot:
            await pilot.press("m", "n")
            await app.wait_for_commands()
            timeline = app.query_one("#timeline", Static).render().plain
            assert "INFORMATION GAIN" in timeline
            assert "PLAN:" in timeline
            assert "IG" in timeline
            assert "COST" in timeline

    asyncio.run(check_summary())


def test_inline_environment_and_map_selectors_support_keyboard_navigation():
    app = NightjarApp()

    async def navigate_selectors():
        async with app.run_test(size=(100, 42)) as pilot:
            assert isinstance(app.screen, MissionConfigScreen)
            scenario = app.screen.query_one("#scenario", RadioSet)
            map_preset = app.screen.query_one("#map_preset", RadioSet)

            scenario.focus()
            await pilot.press("right")
            await app.wait_for_commands()
            assert app.focused is scenario
            await pilot.press("space")
            await app.wait_for_commands()
            assert scenario.pressed_button.id == "scenario-obstacle"

            map_preset.focus()
            await pilot.press("right", "right")
            await app.wait_for_commands()
            await pilot.press("space")
            await app.wait_for_commands()
            assert map_preset.pressed_button.id == "map-extended"

            await pilot.press("enter")
            await app.wait_for_commands()
            assert isinstance(app.screen, PreflightReviewScreen)
            summary = app.screen.query_one("#mission_summary", Static).render().plain
            assert "OBSTACLE FIELD" in summary
            assert "40" in summary and "20" in summary

    asyncio.run(navigate_selectors())
