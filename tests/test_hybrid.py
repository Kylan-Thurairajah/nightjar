"""Atomic hybrid ownership and serialized, off-loop mission control."""

import asyncio
import threading

import numpy as np
import pytest

from nightjar.core.planning import SearchStrategy
from nightjar.core.provider import GridWorldSimulation, MissionStatus, OperationalMode
from nightjar.core.replay import HistoryCapacityError, ReplayTimeline
from nightjar.core.world import Direction, GridWorld
from nightjar.services.hybrid import ControlDeniedError, HybridMissionController


def make_simulation(**kwargs):
    return GridWorldSimulation(
        GridWorld(width=6, height=4, obstacles=(), seed=43),
        drone_count=3,
        search_strategy=SearchStrategy.FRONTIER,
        **kwargs,
    )


def modes(simulation):
    return tuple(drone.mode for drone in simulation.frame().drones)


def test_control_handoff_is_one_zero_tick_boundary_and_preserves_parked_drones():
    simulation = make_simulation()
    simulation.set_mode("03", OperationalMode.IDLE)
    before = len(simulation.history.snapshots)
    simulation.set_hybrid_control("01")
    assert modes(simulation) == (
        OperationalMode.MANUAL,
        OperationalMode.AUTO,
        OperationalMode.IDLE,
    )
    assert len(simulation.history.snapshots) == before + 1

    before = len(simulation.history.snapshots)
    simulation.set_hybrid_control("02")
    assert modes(simulation) == (
        OperationalMode.AUTO,
        OperationalMode.MANUAL,
        OperationalMode.IDLE,
    )
    assert simulation.frame().tick == 0
    assert len(simulation.history.snapshots) == before + 1
    events = [event for event in simulation.history.events if event.boundary == before]
    assert [(event.drone_id, dict(event.details)["mode"]) for event in events] == [
        ("01", "AUTO"),
        ("02", "MANUAL"),
    ]
    simulation.set_hybrid_control("03")
    assert modes(simulation) == (
        OperationalMode.AUTO,
        OperationalMode.AUTO,
        OperationalMode.IDLE,
    )
    simulation.set_hybrid_control("03", OperationalMode.AUTO)
    assert simulation.frame().drone("03").mode is OperationalMode.IDLE
    simulation.set_hybrid_control("03", OperationalMode.MANUAL)
    assert simulation.frame().drone("03").mode is OperationalMode.MANUAL
    ReplayTimeline.from_json(simulation.history.to_json())


def test_handoff_rejects_before_partial_modes_or_queue_changes_at_capacity():
    simulation = make_simulation(history_capacity=1)
    simulation.queue_manual_action("02", Direction.WEST)
    before = simulation.frame()
    before_history = simulation.history.to_json()
    with pytest.raises(HistoryCapacityError):
        simulation.set_hybrid_control("02")
    assert simulation.frame() == before
    assert simulation.history.to_json() == before_history
    assert simulation._manual_requests == {"02": Direction.WEST}
    with pytest.raises(ValueError):
        simulation.set_hybrid_control("01", "unsupported")
    with pytest.raises(KeyError):
        simulation.set_hybrid_control("missing")
    assert simulation.frame() == before


def test_identical_and_terminal_control_requests_do_not_add_history():
    simulation = make_simulation(max_ticks=1)
    simulation.set_hybrid_control("01")
    saved = simulation.history.to_json()
    simulation.set_hybrid_control("01")
    assert simulation.history.to_json() == saved
    simulation.step(Direction.EAST)
    assert simulation.frame().status is MissionStatus.BUDGET_EXHAUSTED
    saved = simulation.history.to_json()
    simulation.set_hybrid_control("02")
    simulation.set_hybrid_control("01", OperationalMode.IDLE)
    assert simulation.history.to_json() == saved


def test_controller_initialization_idle_explicit_reactivation_and_manual_inputs():
    async def exercise():
        simulation = make_simulation(initial_mode=OperationalMode.IDLE)
        controller = HybridMissionController(simulation)
        await controller.initialize()
        assert all(mode is OperationalMode.IDLE for mode in modes(simulation))
        assert not await controller.can_run()
        await controller.select("02")
        assert controller.selected_drone_id == "02"
        assert all(mode is OperationalMode.IDLE for mode in modes(simulation))
        await controller.toggle_control()
        assert modes(simulation) == (
            OperationalMode.IDLE,
            OperationalMode.MANUAL,
            OperationalMode.IDLE,
        )
        await controller.move(Direction.WEST)
        await controller.scan()
        assert controller.live_snapshot.frame.tick == 2
        assert len(controller.live_snapshot.observations) == 1
        await controller.toggle_control()
        assert await controller.can_run()
        with pytest.raises(ControlDeniedError, match="NOT MANUAL"):
            await controller.move(Direction.EAST)
        await controller.set_control(OperationalMode.IDLE)
        assert not await controller.can_run()
        saved = controller.live_history.to_json()
        await controller.fleet_round()
        assert controller.live_history.to_json() == saved

    asyncio.run(exercise())


def test_controller_repeated_ordered_commands_reproduce_complete_mixed_history():
    async def trace():
        simulation = make_simulation(max_ticks=20)
        controller = HybridMissionController(simulation)
        await controller.initialize()
        await controller.move(Direction.EAST)
        await controller.fleet_round()
        await controller.select("02")
        await controller.scan()
        await controller.fleet_round()
        await controller.set_control(OperationalMode.IDLE)
        await controller.select("03")
        await controller.fleet_round()
        return controller.live_history

    first, second = asyncio.run(trace()), asyncio.run(trace())
    assert first.to_json() == second.to_json()
    np.testing.assert_array_equal(
        first.snapshots[-1].belief.probabilities,
        second.snapshots[-1].belief.probabilities,
    )
    assert ReplayTimeline.from_json(first.to_json()).to_json() == first.to_json()


def test_single_manual_drone_has_no_fleet_work_and_terminal_control_is_a_noop():
    async def exercise():
        simulation = GridWorldSimulation(
            GridWorld(width=6, height=4, obstacles=()),
            drone_count=1,
            max_ticks=1,
        )
        controller = HybridMissionController(simulation)
        await controller.initialize()
        assert not await controller.can_run()
        saved = controller.live_history.to_json()
        await controller.fleet_round()
        assert controller.live_history.to_json() == saved
        await controller.move(Direction.EAST)
        assert controller.live_snapshot.frame.status is MissionStatus.BUDGET_EXHAUSTED
        saved = controller.live_history.to_json()
        await controller.toggle_control()
        await controller.set_control(OperationalMode.IDLE)
        assert controller.live_history.to_json() == saved
        assert not await controller.can_run()

    asyncio.run(exercise())


def block_second_planner_call(simulation, started, release):
    original = simulation._planner.decide
    calls = 0

    def delayed(state):
        nonlocal calls
        calls += 1
        if calls == 2:
            started.set()
            if not release.wait(5):
                raise RuntimeError("test did not release planner")
        return original(state)

    simulation._planner.decide = delayed


async def wait_started(started):
    assert await asyncio.to_thread(started.wait, 2), "core worker did not start"


def test_slow_round_keeps_loop_responsive_cache_atomic_and_explicit_input_fifo():
    async def exercise():
        simulation = make_simulation(max_ticks=20)
        controller = HybridMissionController(simulation)
        await controller.initialize()
        started, release = threading.Event(), threading.Event()
        block_second_planner_call(simulation, started, release)
        running = True
        round_task = asyncio.create_task(controller.fleet_round())
        await wait_started(started)
        try:
            # One drone has scanned, but its partial round is not published.
            assert simulation.frame().tick == 1
            assert controller.live_snapshot.frame.tick == 0
            assert controller.busy
            await asyncio.wait_for(asyncio.sleep(0), 1)
            select = asyncio.create_task(controller.select("02"))
            move = asyncio.create_task(controller.move(Direction.WEST))
            next_one = asyncio.create_task(controller.next_drone())
            next_two = asyncio.create_task(controller.next_drone())
            stale_timer = asyncio.create_task(
                controller.fleet_round(should_run=lambda: running)
            )
            await asyncio.sleep(0)
            running = False
            assert not move.done()
        finally:
            release.set()
        await asyncio.gather(round_task, select, move, next_one, next_two, stale_timer)
        assert controller.live_snapshot.frame.tick == 3
        assert controller.selected_drone_id == "01"
        assert controller.live_snapshot.frame.drone("02").position == (4, 3)
        assert modes(simulation) == (
            OperationalMode.MANUAL,
            OperationalMode.AUTO,
            OperationalMode.AUTO,
        )
        assert not controller.busy
        ReplayTimeline.from_json(controller.live_history.to_json())

    asyncio.run(exercise())


def test_replay_queued_during_round_freezes_after_commit_and_restores_live_selection():
    async def exercise():
        simulation = make_simulation()
        controller = HybridMissionController(simulation)
        await controller.initialize()
        started, release = threading.Event(), threading.Event()
        block_second_planner_call(simulation, started, release)
        current = asyncio.create_task(controller.fleet_round())
        await wait_started(started)
        try:
            entry = asyncio.create_task(controller.enter_replay())
            move = asyncio.create_task(controller.move(Direction.EAST))
            toggle = asyncio.create_task(controller.toggle_control())
            selection = asyncio.create_task(controller.select("03"))
            await asyncio.sleep(0)
            assert not controller.replay_mode
            assert controller.live_snapshot.frame.tick == 0
        finally:
            release.set()
        await asyncio.gather(current, entry, move, toggle, selection)
        assert controller.replay_mode
        assert controller.selected_drone_id == "03"
        assert controller.view_snapshot.frame.tick == 2
        saved = controller.live_history.to_json()
        controller.seek(-1000)
        assert controller.view_snapshot.index == 0
        await controller.next_drone()
        await controller.fleet_round()
        await controller.scan()
        await controller.set_control(OperationalMode.IDLE)
        assert controller.live_history.to_json() == saved
        await controller.exit_replay()
        assert controller.selected_drone_id == "01"
        assert not controller.replay_mode
        assert controller.view_snapshot.frame.tick == 2
        assert controller.live_history.to_json() == saved

    asyncio.run(exercise())


def test_cancelled_owner_waits_for_thread_and_cancelled_waiter_releases_pending():
    async def exercise():
        simulation = make_simulation()
        controller = HybridMissionController(simulation)
        await controller.initialize()
        started, release = threading.Event(), threading.Event()
        block_second_planner_call(simulation, started, release)
        owner = asyncio.create_task(controller.fleet_round())
        await wait_started(started)
        try:
            owner.cancel()
            await asyncio.sleep(0)
            owner.cancel()
            await asyncio.sleep(0)
            assert not owner.done()
            waiter = asyncio.create_task(controller.select("02"))
            cancelled_waiter = asyncio.create_task(controller.scan())
            await asyncio.sleep(0)
            cancelled_waiter.cancel()
            with pytest.raises(asyncio.CancelledError):
                await cancelled_waiter
            assert not waiter.done()
            assert controller.live_snapshot.frame.tick == 0
        finally:
            release.set()
        with pytest.raises(asyncio.CancelledError):
            await owner
        await waiter
        assert controller.selected_drone_id == "02"
        assert controller.live_snapshot.frame.tick == 2
        assert not controller.busy
        assert modes(simulation) == (
            OperationalMode.AUTO,
            OperationalMode.MANUAL,
            OperationalMode.AUTO,
        )

    asyncio.run(exercise())


def test_core_failure_after_partial_round_publishes_commit_and_unlocks_controller():
    async def exercise():
        simulation = make_simulation()
        controller = HybridMissionController(simulation)
        await controller.initialize()
        original = simulation._planner.decide
        calls = 0

        def fail_second(state):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("deliberate planner failure")
            return original(state)

        simulation._planner.decide = fail_second
        with pytest.raises(RuntimeError, match="deliberate"):
            await controller.fleet_round()
        assert not controller.busy
        assert controller.live_snapshot.frame.tick == 1
        assert controller.live_snapshot.frame == simulation.frame()
        simulation._planner.decide = original
        await controller.select("02")
        assert controller.selected_drone_id == "02"
        ReplayTimeline.from_json(controller.live_history.to_json())

    asyncio.run(exercise())


def test_controller_handoff_capacity_failure_preserves_selection_and_cached_state():
    async def exercise():
        simulation = make_simulation(history_capacity=2)
        controller = HybridMissionController(simulation)
        await controller.initialize()
        saved = controller.live_history.to_json()
        with pytest.raises(HistoryCapacityError):
            await controller.select("02")
        assert controller.selected_drone_id == "01"
        assert controller.live_history.to_json() == saved
        assert not controller.busy
        await controller.enter_replay()
        await controller.select("02")
        await controller.exit_replay()
        assert controller.selected_drone_id == "01"
        assert controller.live_history.to_json() == saved

    asyncio.run(exercise())
