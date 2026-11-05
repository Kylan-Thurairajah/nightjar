"""Small deterministic checks for the offline public-API benchmark adapter."""

import json
import subprocess
import sys
from dataclasses import replace

import pytest

import nightjar.benchmark as benchmark
from nightjar.benchmark import BenchmarkConfig, main, run_benchmark, summarize
from nightjar.core.mission import (
    MapPreset,
    MissionConfig,
    ScenarioPreset,
    create_simulation,
)
from nightjar.core.planning import SearchStrategy
from nightjar.core.provider import GridWorldSimulation, MissionStatus, OperationalMode
from nightjar.core.sensor import SensorPreset
from nightjar.core.world import GridWorld


def test_identical_configuration_produces_identical_json_and_ordered_equal_budgets():
    config = BenchmarkConfig(seeds=(7, 2), max_ticks=4, drone_count=3)
    first, second = run_benchmark(config), run_benchmark(config)
    assert first.to_json() == second.to_json()
    assert [(run.seed, run.strategy) for run in first.runs] == [
        (seed, strategy.value) for seed in (7, 2) for strategy in SearchStrategy
    ]
    for run in first.runs:
        assert run.tick_budget == 4
        assert run.ticks <= 4
        assert run.ticks == run.scans + run.movement_attempts
        assert run.movement_attempts == run.successful_moves + run.blocked_attempts
        assert run.coverage == run.visited_cells / run.traversable_cells
    data = json.loads(first.to_json())
    assert data["protocol"]["execution"] == "all_auto_serial_fleet_rounds"
    assert data["protocol"]["coordination"] == "shared_coverage_soft_round_targets"
    assert data["configuration"]["drone_count"] == 3
    assert data["configuration"]["sensor_preset"] == "standard"
    assert len(data["software"]["source_sha256"]) == 64
    assert len(first.summaries) == 3
    assert all(summary.sample_count == 2 for summary in first.summaries)
    assert "timestamp" not in data and "timing" not in data


def test_metrics_match_independent_public_state_with_partial_final_fleet_round():
    config = BenchmarkConfig(seeds=(3,), max_ticks=4, drone_count=3)
    report = run_benchmark(config)
    mission = MissionConfig(
        operation_name="BENCHMARK",
        scenario=config.scenario,
        map_preset=config.map_preset,
        drone_count=3,
        max_ticks=4,
        seed=3,
        search_strategy=SearchStrategy.FRONTIER,
    )
    simulation = create_simulation(mission)
    initial_entropy = simulation.belief_stats.entropy_bits
    for drone in simulation.frame().drones:
        simulation.set_mode(drone.identifier, OperationalMode.AUTO)
    rounds = 0
    while simulation.frame().status is MissionStatus.ACTIVE:
        simulation.fleet_round()
        rounds += 1
    frame = simulation.frame()
    actual = next(run for run in report.runs if run.strategy == "frontier")
    assert frame.tick == actual.ticks == 4
    assert actual.rounds == rounds == 2
    assert actual.terminal_reason == "BUDGET EXHAUSTED"
    assert actual.scans == len(simulation.observations)
    visited = set().union(*(drone.visited for drone in frame.drones))
    assert actual.visited_cells == len(visited)
    assert actual.traversable_cells == 16 * 12
    assert actual.initial_entropy_bits == initial_entropy
    assert actual.final_entropy_bits == simulation.belief_stats.entropy_bits
    assert actual.entropy_reduction_bits == initial_entropy - actual.final_entropy_bits


def test_all_policies_receive_identical_inputs_except_strategy(monkeypatch):
    seen = []
    original = benchmark.create_simulation

    def capture(config):
        seen.append(config)
        return original(config)

    monkeypatch.setattr(benchmark, "create_simulation", capture)
    config = BenchmarkConfig(
        seeds=(3,),
        max_ticks=1,
        drone_count=2,
        scenario=ScenarioPreset.OBSTACLE_FIELD,
        sensor_preset=SensorPreset.DEGRADED,
    )
    run_benchmark(config)
    assert [item.search_strategy for item in seen] == list(SearchStrategy)
    normalized = [replace(item, search_strategy=SearchStrategy.RANDOM) for item in seen]
    assert normalized == [normalized[0]] * 3


def test_metrics_count_blocked_attempts_and_unreachable_traversable_cells():
    # Three wall cells split this 5x3 map: nine free cells on the right cannot
    # be reached from the three free cells on the left, but remain in coverage.
    simulation = GridWorldSimulation(
        GridWorld(width=5, height=3, obstacles={(1, 0), (1, 1), (1, 2)}),
        drone_count=1,
        max_ticks=3,
    )
    initial_entropy = simulation.belief_stats.entropy_bits
    simulation.step("east")  # blocked by the wall
    simulation.step("south")
    simulation.scan("01")

    result = benchmark._result(
        simulation, MissionConfig(max_ticks=3), initial_entropy, rounds=0
    )

    assert result.ticks == 3
    assert result.movement_attempts == 2
    assert result.successful_moves == result.blocked_attempts == result.scans == 1
    assert result.visited_cells == 2
    assert result.traversable_cells == 12
    assert result.coverage == pytest.approx(1 / 6)
    assert result.terminal_reason == "BUDGET EXHAUSTED"


def test_early_planner_stop_is_recorded_instead_of_forcing_equal_consumption(
    monkeypatch,
):
    original = benchmark.create_simulation

    def small(config):
        if config.search_strategy is SearchStrategy.INFORMATION_GAIN:
            return GridWorldSimulation(
                GridWorld(width=2, height=2, obstacles=()),
                drone_count=1,
                search_strategy=config.search_strategy,
                max_ticks=config.max_ticks,
            )
        return original(config)

    monkeypatch.setattr(benchmark, "create_simulation", small)
    report = run_benchmark(BenchmarkConfig(seeds=(0,), max_ticks=2))
    gain = report.runs[-1]
    assert gain.terminal_reason == "PLANNER EXHAUSTED"
    assert gain.ticks == gain.scans == gain.movement_attempts == 0
    assert gain.rounds == 1
    assert gain.visited_cells == 1 and gain.traversable_cells == 4
    assert gain.coverage == 0.25


def test_summary_is_arithmetic_mean_with_explicit_sample_count():
    raw = run_benchmark(BenchmarkConfig(seeds=(0,), max_ticks=1)).runs[0]
    other = replace(
        raw,
        ticks=3,
        scans=1,
        coverage=0.5,
        final_entropy_bits=2,
        entropy_reduction_bits=-1,
    )
    summary = summarize((raw, other))[0]
    assert summary.sample_count == 2
    assert summary.mean_ticks == (raw.ticks + 3) / 2
    assert summary.mean_scans == (raw.scans + 1) / 2
    assert summary.mean_coverage == (raw.coverage + 0.5) / 2
    assert summary.mean_final_entropy_bits == (raw.final_entropy_bits + 2) / 2
    assert summary.mean_entropy_reduction_bits == (raw.entropy_reduction_bits - 1) / 2


@pytest.mark.parametrize(
    "updates",
    [
        {"seeds": ()},
        {"seeds": (1, 1)},
        {"seeds": (-1,)},
        {"seeds": (True,)},
        {"seeds": tuple(range(33))},
        {"seeds": [1]},
        {"max_ticks": 0},
        {"max_ticks": 1001},
        {"max_ticks": True},
        {"drone_count": 0},
        {"drone_count": 11},
        {"drone_count": True},
        {"map_preset": "compact"},
        {"scenario": "open_field"},
        {"sensor_preset": "standard"},
    ],
)
def test_invalid_config_fails_before_any_simulation(updates, monkeypatch):
    def unexpected(config):
        pytest.fail("invalid config started simulation")

    monkeypatch.setattr(benchmark, "create_simulation", unexpected)
    with pytest.raises(ValueError):
        run_benchmark(BenchmarkConfig(**updates))


def test_stalled_active_round_fails_instead_of_looping(monkeypatch):
    original = benchmark.create_simulation

    def stalled(config):
        simulation = original(config)
        simulation.fleet_round = lambda: simulation.frame()
        return simulation

    monkeypatch.setattr(benchmark, "create_simulation", stalled)
    with pytest.raises(RuntimeError, match="no simulation-tick progress"):
        run_benchmark(BenchmarkConfig(seeds=(0,), max_ticks=1))


def test_cli_stdout_help_invalid_input_and_exclusive_output(
    tmp_path, capsys, monkeypatch
):
    assert main(["--seeds", "4", "--ticks", "1"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert len(data["runs"]) == 3
    with pytest.raises(SystemExit) as help_exit:
        main(["--help"])
    assert help_exit.value.code == 0
    assert "--seeds" in capsys.readouterr().out
    destination = tmp_path / "report.json"
    assert main(["--seeds", "4", "--ticks", "1", "--output", str(destination)]) == 0
    assert capsys.readouterr().out == ""
    saved = destination.read_bytes()

    def unexpected(config):
        pytest.fail("existing output started expensive benchmark")

    monkeypatch.setattr(benchmark, "run_benchmark", unexpected)
    with pytest.raises(SystemExit) as exists_exit:
        main(["--output", str(destination)])
    assert exists_exit.value.code == 2
    assert destination.read_bytes() == saved
    with pytest.raises(SystemExit) as invalid_exit:
        main(["--seeds", "1", "1"])
    assert invalid_exit.value.code == 2
    assert "distinct" in capsys.readouterr().err


def test_benchmark_import_and_execution_do_not_import_ui_or_read_hidden_objective():
    script = """
import importlib.abc
import sys
class RejectUI(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in {"textual", "rich"}:
            raise AssertionError("benchmark imported UI")
sys.meta_path.insert(0, RejectUI())
from nightjar.benchmark import BenchmarkConfig, run_benchmark
from nightjar.core.provider import GridWorldSimulation
def forbidden(self):
    raise AssertionError("benchmark requested hidden target")
GridWorldSimulation.debug_objective_position = forbidden
report = run_benchmark(BenchmarkConfig(seeds=(0,), max_ticks=1))
assert len(report.runs) == 3
"""
    subprocess.run(
        [sys.executable, "-c", script], check=True, capture_output=True, text=True
    )


def test_failed_run_does_not_create_empty_output(tmp_path, monkeypatch, capsys):
    destination = tmp_path / "failed.json"

    def fail(config):
        raise RuntimeError("ACTIVE fleet round made no simulation-tick progress")

    monkeypatch.setattr(benchmark, "run_benchmark", fail)
    with pytest.raises(SystemExit) as failure:
        main(["--output", str(destination)])
    assert failure.value.code == 2
    assert "no simulation-tick progress" in capsys.readouterr().err
    assert not destination.exists()


def test_extended_preset_bounds_can_be_constructed_without_executing_large_matrix():
    config = BenchmarkConfig(
        seeds=tuple(range(32)),
        max_ticks=1000,
        drone_count=10,
        map_preset=MapPreset.EXTENDED,
    )
    assert len(config.seeds) == 32 and config.max_ticks == 1000
