"""Offline, deterministic comparison of existing synthetic search policies."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from dataclasses import asdict, dataclass, replace
from importlib import metadata, resources
from pathlib import Path
from statistics import fmean
from typing import Sequence

import numpy as np

from nightjar.core.mission import (
    MapPreset,
    MissionConfig,
    ScenarioPreset,
    create_simulation,
)
from nightjar.core.planning import SearchStrategy
from nightjar.core.provider import GridWorldSimulation, MissionStatus, OperationalMode
from nightjar.core.sensor import SensorPreset


POLICIES = tuple(SearchStrategy)
SOURCE_FILES = (
    "benchmark.py",
    "core/world.py",
    "core/mission.py",
    "core/provider.py",
    "core/sensor.py",
    "core/belief.py",
    "core/planning.py",
    "core/replay.py",
)


@dataclass(frozen=True)
class BenchmarkConfig:
    seeds: tuple[int, ...] = (0, 1, 2)
    max_ticks: int = 50
    drone_count: int = 1
    map_preset: MapPreset = MapPreset.COMPACT
    scenario: ScenarioPreset = ScenarioPreset.OPEN_FIELD
    sensor_preset: SensorPreset = SensorPreset.STANDARD

    def __post_init__(self) -> None:
        if not isinstance(self.seeds, tuple) or not 1 <= len(self.seeds) <= 32:
            raise ValueError("provide 1–32 distinct nonnegative integer seeds")
        if any(type(seed) is not int or seed < 0 for seed in self.seeds):
            raise ValueError("seeds must be nonnegative integers")
        if len(set(self.seeds)) != len(self.seeds):
            raise ValueError("seeds must be distinct")
        if type(self.max_ticks) is not int or not 1 <= self.max_ticks <= 1000:
            raise ValueError("ticks must be an integer between 1 and 1000")
        if type(self.drone_count) is not int or not 1 <= self.drone_count <= 10:
            raise ValueError("drones must be an integer between 1 and 10")
        for value, kind in (
            (self.map_preset, MapPreset),
            (self.scenario, ScenarioPreset),
            (self.sensor_preset, SensorPreset),
        ):
            if not isinstance(value, kind):
                raise ValueError(f"unsupported {kind.__name__}")


@dataclass(frozen=True)
class BenchmarkResult:
    seed: int
    strategy: str
    tick_budget: int
    ticks: int
    terminal_reason: str
    rounds: int
    scans: int
    movement_attempts: int
    successful_moves: int
    blocked_attempts: int
    visited_cells: int
    traversable_cells: int
    coverage: float
    initial_entropy_bits: float
    final_entropy_bits: float
    entropy_reduction_bits: float


@dataclass(frozen=True)
class BenchmarkSummary:
    strategy: str
    sample_count: int
    mean_ticks: float
    mean_scans: float
    mean_coverage: float
    mean_final_entropy_bits: float
    mean_entropy_reduction_bits: float


@dataclass(frozen=True)
class BenchmarkReport:
    config: BenchmarkConfig
    runs: tuple[BenchmarkResult, ...]
    summaries: tuple[BenchmarkSummary, ...]
    python_version: str
    numpy_version: str
    application_version: str
    source_sha256: str

    def to_json(self) -> str:
        data = {
            "schema_version": 1,
            "protocol": {
                "version": 1,
                "execution": "all_auto_serial_fleet_rounds",
                "policy_order": [policy.value for policy in POLICIES],
                "row_order": "seed_input_order_then_policy_order",
                "budget": "global_simulation_ticks",
                "planner_exhaustion": "mission_wide",
                "coverage_denominator": "all_non_obstacle_cells_including_unreachable",
                "coverage_includes_spawns": True,
                "entropy_reduction": "initial_minus_final_bits",
                "timing_included": False,
            },
            "configuration": asdict(self.config),
            "software": {
                "python": self.python_version,
                "numpy": self.numpy_version,
                "nightjar_sim": self.application_version,
                "source_sha256": self.source_sha256,
                "source_files": SOURCE_FILES,
            },
            "runs": [asdict(run) for run in self.runs],
            "summaries": [asdict(summary) for summary in self.summaries],
        }
        return json.dumps(data, sort_keys=True, indent=2, allow_nan=False) + "\n"


def source_fingerprint() -> str:
    """Hash named packaged sources, independent of location, git or timestamps."""
    digest = hashlib.sha256()
    package = resources.files("nightjar")
    for name in SOURCE_FILES:
        content = package.joinpath(name).read_bytes()
        digest.update(name.encode("utf-8") + b"\0")
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def summarize(runs: Sequence[BenchmarkResult]) -> tuple[BenchmarkSummary, ...]:
    """Descriptive means over raw rows; no ranking or significance inference."""
    summaries = []
    for strategy in POLICIES:
        selected = [run for run in runs if run.strategy == strategy.value]
        if not selected:
            continue
        summaries.append(
            BenchmarkSummary(
                strategy=strategy.value,
                sample_count=len(selected),
                mean_ticks=fmean(run.ticks for run in selected),
                mean_scans=fmean(run.scans for run in selected),
                mean_coverage=fmean(run.coverage for run in selected),
                mean_final_entropy_bits=fmean(
                    run.final_entropy_bits for run in selected
                ),
                mean_entropy_reduction_bits=fmean(
                    run.entropy_reduction_bits for run in selected
                ),
            )
        )
    return tuple(summaries)


def _run_mission(config: MissionConfig) -> BenchmarkResult:
    simulation = create_simulation(config)
    initial_entropy = simulation.belief_stats.entropy_bits
    for drone in simulation.frame().drones:
        simulation.set_mode(drone.identifier, OperationalMode.AUTO)
    rounds = 0
    while simulation.frame().status is MissionStatus.ACTIVE:
        previous_tick = simulation.frame().tick
        simulation.fleet_round()
        rounds += 1
        frame = simulation.frame()
        if frame.status is MissionStatus.ACTIVE and frame.tick <= previous_tick:
            raise RuntimeError("ACTIVE fleet round made no simulation-tick progress")
    return _result(simulation, config, initial_entropy, rounds)


def _result(
    simulation: GridWorldSimulation,
    config: MissionConfig,
    initial_entropy: float,
    rounds: int,
) -> BenchmarkResult:
    frame = simulation.frame()
    scans = len(simulation.observations)
    attempts = sum(drone.tick for drone in frame.drones)
    moves = sum(len(drone.path) - 1 for drone in frame.drones)
    visited = set().union(*(drone.visited for drone in frame.drones))
    traversable = frame.width * frame.height - len(frame.obstacles)
    entropy = simulation.belief_stats.entropy_bits
    if frame.tick != attempts + scans or not 0 <= frame.tick <= config.max_ticks:
        raise RuntimeError("simulation action counts violate the benchmark tick budget")
    return BenchmarkResult(
        seed=config.seed,
        strategy=config.search_strategy.value,
        tick_budget=config.max_ticks,
        ticks=frame.tick,
        terminal_reason=frame.status.value,
        rounds=rounds,
        scans=scans,
        movement_attempts=attempts,
        successful_moves=moves,
        blocked_attempts=attempts - moves,
        visited_cells=len(visited),
        traversable_cells=traversable,
        coverage=len(visited) / traversable,
        initial_entropy_bits=initial_entropy,
        final_entropy_bits=entropy,
        entropy_reduction_bits=initial_entropy - entropy,
    )


def run_benchmark(config: BenchmarkConfig = BenchmarkConfig()) -> BenchmarkReport:
    if not isinstance(config, BenchmarkConfig):
        raise ValueError("config must be a BenchmarkConfig")
    base = MissionConfig(
        operation_name="BENCHMARK",
        scenario=config.scenario,
        drone_count=config.drone_count,
        map_preset=config.map_preset,
        sensor_preset=config.sensor_preset,
        max_ticks=config.max_ticks,
    )
    runs = tuple(
        _run_mission(replace(base, seed=seed, search_strategy=strategy))
        for seed in config.seeds
        for strategy in POLICIES
    )
    try:
        application_version = metadata.version("nightjar-sim")
    except metadata.PackageNotFoundError:
        application_version = "uninstalled"
    return BenchmarkReport(
        config=config,
        runs=runs,
        summaries=summarize(runs),
        python_version=platform.python_version(),
        numpy_version=np.__version__,
        application_version=application_version,
        source_sha256=source_fingerprint(),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2])
    parser.add_argument("--ticks", type=int, default=50)
    parser.add_argument("--drones", type=int, default=1)
    parser.add_argument(
        "--map", choices=[value.value for value in MapPreset], default="compact"
    )
    parser.add_argument(
        "--scenario",
        choices=[value.value for value in ScenarioPreset],
        default="open_field",
    )
    parser.add_argument(
        "--sensor", choices=[value.value for value in SensorPreset], default="standard"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="exclusively create a JSON report; existing files are preserved",
    )
    args = parser.parse_args(argv)
    try:
        config = BenchmarkConfig(
            seeds=tuple(args.seeds),
            max_ticks=args.ticks,
            drone_count=args.drones,
            map_preset=MapPreset(args.map),
            scenario=ScenarioPreset(args.scenario),
            sensor_preset=SensorPreset(args.sensor),
        )
        # Refuse existing paths before expensive work. Exclusive creation at write
        # time also preserves files created by another process during the run.
        if args.output is not None and args.output.exists():
            raise FileExistsError(f"output already exists: {args.output}")
        report = run_benchmark(config).to_json()
        if args.output is None:
            sys.stdout.write(report)
        else:
            with args.output.open("x", encoding="utf-8", newline="\n") as output:
                output.write(report)
    except (ValueError, RuntimeError, OSError) as error:
        parser.exit(2, f"benchmark: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
