"""Public metrics, matched inputs and real-thread cancellation ownership."""

import asyncio
import json
from dataclasses import asdict, replace
from threading import Event

import pytest

import nightjar.services.comparison as comparison
from nightjar.core.mission import MapPreset, MissionConfig, ScenarioPreset
from nightjar.core.planning import SearchStrategy
from nightjar.core.provider import GridWorldSimulation, MissionStatus, OperationalMode
from nightjar.core.replay import ReplayTimeline
from nightjar.core.sensor import SensorConfig
from nightjar.core.world import GridWorld


def configuration(**changes):
    return MissionConfig(
        **{
            "map_preset": MapPreset.COMPACT,
            "scenario": ScenarioPreset.OPEN_FIELD,
            "max_ticks": 5,
            "seed": 17,
            "drone_count": 3,
            **changes,
        }
    )


def test_pair_is_matched_deterministic_and_metrics_match_public_archives(monkeypatch):
    config = configuration(
        initial_control=OperationalMode.IDLE, search_strategy=SearchStrategy.RANDOM
    )
    seen = []
    create = comparison.create_simulation

    def record(settings):
        seen.append(settings)
        return create(settings)

    monkeypatch.setattr(comparison, "create_simulation", record)
    report = comparison.run_comparison(config)
    repeated = comparison.run_comparison(config)
    assert report.to_json() == repeated.to_json()
    assert seen[:2] == [
        replace(config, search_strategy=policy) for policy in comparison.POLICIES
    ]
    assert {
        key: value for key, value in asdict(seen[0]).items() if key != "search_strategy"
    } == {
        key: value for key, value in asdict(seen[1]).items() if key != "search_strategy"
    }
    assert tuple(run.strategy for run in report.runs) == comparison.POLICIES
    for run in report.runs:
        assert (
            ReplayTimeline.from_json(run.timeline.to_json()).to_json()
            == run.timeline.to_json()
        )
        for point, snapshot in zip(run.points, run.timeline.snapshots, strict=True):
            frame = snapshot.frame
            visited = set().union(*(drone.visited for drone in frame.drones))
            assert point.tick == frame.tick
            assert point.snapshot_index == snapshot.index
            assert point.coverage == len(visited) / (
                frame.width * frame.height - len(frame.obstacles)
            )
            assert point.scans == len(snapshot.observations)
            assert point.entropy_bits == snapshot.belief.stats.entropy_bits
        assert run.final.frame.tick == 5  # partial last three-drone round
        assert run.final.frame.status is MissionStatus.BUDGET_EXHAUSTED
        assert all(
            drone.mode is OperationalMode.AUTO for drone in run.final.frame.drones
        )
        for cursor in range(8):
            expected = [s for s in run.timeline.snapshots if s.frame.tick <= cursor][-1]
            assert run.at_tick(cursor) is expected
        assert run.at_tick(-1) is run.timeline.snapshots[0]
        with pytest.raises(ValueError, match="integer"):
            run.at_tick(1.5)
    data = json.loads(report.to_json())
    assert data["protocol"]["initial_control_ignored"] is True
    assert len(data["software"]["source_sha256"]) == 64
    assert data["runs"][0]["final"]["terminal_reason"] == "BUDGET EXHAUSTED"
    assert "objective_position" not in report.to_json()
    assert "rng" not in report.to_json()


@pytest.mark.parametrize("budget", [0, True, 1001])
def test_invalid_budget_is_rejected_before_creating_world(monkeypatch, budget):
    def unexpected(_):
        pytest.fail("invalid workload allocated a simulation")

    monkeypatch.setattr(comparison, "create_simulation", unexpected)
    with pytest.raises(ValueError, match="1 and 1000"):
        comparison.run_comparison(configuration(max_ticks=budget))


def test_pre_cancelled_comparison_creates_nothing(monkeypatch):
    cancel = Event()
    cancel.set()
    monkeypatch.setattr(
        comparison, "create_simulation", lambda _: pytest.fail("allocated")
    )
    with pytest.raises(comparison.ComparisonCancelled):
        comparison.run_comparison(configuration(), cancel_event=cancel)


def test_zero_tick_terminal_state_wins_over_initial_mode_boundaries():
    simulation = GridWorldSimulation(
        GridWorld(width=4, height=2, obstacles=(), seed=9),
        drone_count=1,
        sensor_config=SensorConfig(sensitivity=0.5, false_positive_probability=0.5),
        search_strategy=SearchStrategy.INFORMATION_GAIN,
    )
    simulation.set_mode("01", OperationalMode.AUTO)
    simulation.fleet_round()
    assert simulation.frame().status is MissionStatus.PLANNER_EXHAUSTED
    assert simulation.frame().tick == 0
    run = comparison.ComparisonRun(
        SearchStrategy.INFORMATION_GAIN, simulation.history, ()
    )
    assert run.at_tick(0) is run.final
    assert run.at_tick(100) is run.final


def test_no_progress_active_round_fails_instead_of_looping(monkeypatch):
    create = comparison.create_simulation

    def stalled(settings):
        simulation = create(settings)
        simulation.fleet_round = simulation.frame
        return simulation

    monkeypatch.setattr(comparison, "create_simulation", stalled)
    with pytest.raises(RuntimeError, match="no progress"):
        comparison.run_comparison(configuration())


@pytest.mark.parametrize("cancel_task", [False, True])
def test_delayed_round_cancel_retains_thread_until_completion(monkeypatch, cancel_task):
    entered, release, finished, cancel = Event(), Event(), Event(), Event()
    create = comparison.create_simulation
    allocations = []

    def delayed(settings):
        simulation = create(settings)
        allocations.append(simulation)
        original = simulation.fleet_round

        def wait_round():
            entered.set()
            assert release.wait(5), "test did not release delayed thread"
            try:
                return original()
            finally:
                finished.set()

        simulation.fleet_round = wait_round
        return simulation

    monkeypatch.setattr(comparison, "create_simulation", delayed)

    async def exercise():
        task = asyncio.create_task(
            comparison.compare_policies(configuration(), cancel_event=cancel)
        )
        try:
            for _ in range(1000):
                if entered.is_set():
                    break
                await asyncio.sleep(0.001)
            assert entered.is_set()
            if cancel_task:
                for _ in range(4):
                    task.cancel()
                    await asyncio.sleep(0)
            else:
                cancel.set()
            await asyncio.sleep(0.01)
            assert cancel.is_set()
            assert not task.done()
            assert not finished.is_set()
            release.set()
            expected = (
                asyncio.CancelledError
                if cancel_task
                else comparison.ComparisonCancelled
            )
            with pytest.raises(expected):
                await task
            assert finished.is_set()
            assert len(allocations) == 1  # never publish/start the second half
            history = allocations[0].history.to_json()
            await asyncio.sleep(0.01)
            assert allocations[0].history.to_json() == history
        finally:
            release.set()
            if not task.done():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, comparison.ComparisonCancelled):
                    pass

    asyncio.run(exercise())
