"""Isolated, deterministic paired-policy experiments over public mission state."""

from __future__ import annotations

import asyncio
import hashlib
import json
import platform
from dataclasses import asdict, dataclass, replace
from importlib import metadata, resources
from threading import Event

import numpy as np

from nightjar.benchmark import source_fingerprint
from nightjar.core.mission import MissionConfig, create_simulation
from nightjar.core.planning import SearchStrategy
from nightjar.core.provider import MissionStatus, OperationalMode
from nightjar.core.replay import MissionSnapshot, ReplayTimeline


POLICIES = (SearchStrategy.FRONTIER, SearchStrategy.INFORMATION_GAIN)


class ComparisonCancelled(RuntimeError):
    """The caller requested cancellation before the complete pair was available."""


@dataclass(frozen=True)
class ComparisonPoint:
    tick: int
    snapshot_index: int
    coverage: float
    entropy_bits: float
    scans: int


@dataclass(frozen=True)
class ComparisonRun:
    strategy: SearchStrategy
    timeline: ReplayTimeline
    points: tuple[ComparisonPoint, ...]

    @property
    def final(self) -> MissionSnapshot:
        return self.timeline.snapshots[-1]

    def at_tick(self, tick: int) -> MissionSnapshot:
        """Return actual committed state, never an interpolated partial round."""
        if type(tick) is not int:
            raise ValueError("comparison tick must be an integer")
        for snapshot in reversed(self.timeline.snapshots):
            if snapshot.frame.tick <= tick:
                return snapshot
        return self.timeline.snapshots[0]


@dataclass(frozen=True)
class ComparisonReport:
    config: MissionConfig
    runs: tuple[ComparisonRun, ...]
    source_sha256: str
    python_version: str
    numpy_version: str
    application_version: str

    def to_json(self) -> str:
        """Raw measured traces and provenance, without hidden state or file writes."""
        runs = []
        for run in self.runs:
            final = run.final
            first = run.points[0]
            last = run.points[-1]
            runs.append(
                {
                    "strategy": run.strategy.value,
                    "points": [asdict(point) for point in run.points],
                    "final": {
                        "tick": final.frame.tick,
                        "scans": last.scans,
                        "coverage": last.coverage,
                        "entropy_bits": last.entropy_bits,
                        "entropy_change_bits": last.entropy_bits - first.entropy_bits,
                        "terminal_reason": final.frame.status.value,
                    },
                }
            )
        data = {
            "schema_version": 1,
            "configuration": asdict(self.config),
            "protocol": {
                "execution": "all_auto_serial_fleet_rounds",
                "policy_order": [policy.value for policy in POLICIES],
                "initial_control_ignored": True,
                "configured_search_strategy_ignored": True,
                "budget": "global_simulation_tick_ceiling",
                "planner_exhaustion": "mission_wide",
                "coordination": "shared_coverage_soft_round_targets",
                "coverage_denominator": "all_non_obstacle_cells_including_unreachable",
                "coverage_includes_spawns": True,
                "trace_sampling": "committed_snapshot_boundaries",
                "entropy_change": "current_minus_initial_bits",
                "sensor_stream": "same_seed_different_paths_may_consume_differently",
            },
            "software": {
                "python": self.python_version,
                "numpy": self.numpy_version,
                "nightjar_sim": self.application_version,
                "source_sha256": self.source_sha256,
                "fingerprint": "benchmark_core_fingerprint_plus_services/comparison.py",
            },
            "runs": runs,
        }
        return json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + "\n"


def _check_cancel(cancel_event: Event) -> None:
    if cancel_event.is_set():
        raise ComparisonCancelled("Policy comparison cancelled.")


def _point(snapshot: MissionSnapshot) -> ComparisonPoint:
    frame = snapshot.frame
    visited = set().union(*(drone.visited for drone in frame.drones))
    return ComparisonPoint(
        tick=frame.tick,
        snapshot_index=snapshot.index,
        coverage=len(visited) / (frame.width * frame.height - len(frame.obstacles)),
        entropy_bits=snapshot.belief.stats.entropy_bits,
        scans=len(snapshot.observations),
    )


def _source_fingerprint() -> str:
    digest = hashlib.sha256(source_fingerprint().encode("ascii"))
    digest.update(b"\0services/comparison.py\0")
    digest.update(
        resources.files("nightjar").joinpath("services/comparison.py").read_bytes()
    )
    return digest.hexdigest()


def run_comparison(
    config: MissionConfig, *, cancel_event: Event | None = None
) -> ComparisonReport:
    """Build two independent all-AUTO runs using the same requested settings."""
    cancel = cancel_event if cancel_event is not None else Event()
    _check_cancel(cancel)
    if not isinstance(config, MissionConfig):
        raise ValueError("comparison requires a MissionConfig")
    if type(config.max_ticks) is not int or not 1 <= config.max_ticks <= 1000:
        raise ValueError("comparison tick budget must be between 1 and 1000")

    runs = []
    for strategy in POLICIES:
        _check_cancel(cancel)
        simulation = create_simulation(replace(config, search_strategy=strategy))
        _check_cancel(cancel)
        for drone in simulation.frame().drones:
            simulation.set_mode(drone.identifier, OperationalMode.AUTO)
        while simulation.frame().status is MissionStatus.ACTIVE:
            _check_cancel(cancel)
            before = simulation.frame().tick
            frame = simulation.fleet_round()
            _check_cancel(cancel)
            if frame.status is MissionStatus.ACTIVE and frame.tick == before:
                raise RuntimeError("comparison fleet round made no progress")
        timeline = simulation.history
        runs.append(
            ComparisonRun(
                strategy=strategy,
                timeline=timeline,
                points=tuple(_point(snapshot) for snapshot in timeline.snapshots),
            )
        )
    _check_cancel(cancel)
    try:
        application_version = metadata.version("nightjar-sim")
    except metadata.PackageNotFoundError:
        application_version = "uninstalled"
    report = ComparisonReport(
        config=config,
        runs=tuple(runs),
        source_sha256=_source_fingerprint(),
        python_version=platform.python_version(),
        numpy_version=np.__version__,
        application_version=application_version,
    )
    _check_cancel(cancel)
    return report


async def compare_policies(
    config: MissionConfig, *, cancel_event: Event | None = None
) -> ComparisonReport:
    """Run off-loop; cancellation retains ownership until the actual thread exits."""
    cancel = cancel_event if cancel_event is not None else Event()
    future = asyncio.get_running_loop().run_in_executor(
        None, lambda: run_comparison(config, cancel_event=cancel)
    )
    cancelled = False
    while True:
        try:
            report = await asyncio.shield(future)
            break
        except asyncio.CancelledError:
            cancelled = True
            cancel.set()
        except Exception:
            if cancelled:
                raise asyncio.CancelledError from None
            raise
    if cancelled:
        raise asyncio.CancelledError
    return report
