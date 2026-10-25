"""Deterministic *demo* data powering the first Nightjar TUI.

This is NOT a target localization or Bayesian inference engine. The colored
probability field is synthetic and only establishes the UI/simulation contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import exp

import numpy as np

WIDTH = 32
HEIGHT = 16
MAX_TICK = 200


@dataclass(frozen=True)
class AgentState:
    identifier: str
    callsign: str
    position: tuple[int, int]
    status: str
    energy: int
    trail: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class SimulationFrame:
    tick: int
    belief: np.ndarray  # normalized synthetic grid, NOT a Bayesian posterior
    walls: np.ndarray   # shape (height, width), True for blocked cells
    visited: frozenset[tuple[int, int]]
    agents: tuple[AgentState, ...]
    events: tuple[str, ...]
    entropy_bits: float
    coverage_pct: float


def _expand_route(waypoints: tuple[tuple[int, int], ...]) -> tuple[tuple[int, int], ...]:
    """Convert straight-line waypoints into adjacent traversed cells."""
    result = [waypoints[0]]
    for goal_x, goal_y in waypoints[1:]:
        x, y = result[-1]
        while x != goal_x:
            x += 1 if goal_x > x else -1
            result.append((x, y))
        while y != goal_y:
            y += 1 if goal_y > y else -1
            result.append((x, y))
    return tuple(result)


ROUTES = (
    _expand_route(((3, 3), (6, 3), (6, 6), (13, 6), (13, 4), (19, 4), (19, 6), (22, 6))),
    _expand_route(((27, 2), (27, 5), (24, 5), (24, 8), (20, 8), (20, 12), (19, 12))),
    _expand_route(((3, 13), (7, 13), (7, 10), (11, 10), (11, 12), (14, 12), (17, 12))),
)

CALLSIGNS = ("RAVEN", "GHOST", "VIPER")


def build_walls() -> np.ndarray:
    walls = np.zeros((HEIGHT, WIDTH), dtype=bool)
    walls[1:6, 9:12] = True
    walls[7:9, 14:19] = True
    walls[11:15, 23:26] = True
    walls[9, 2:7] = True
    return walls


def _position_at(route: tuple[tuple[int, int], ...], tick: int) -> tuple[int, int]:
    """Ping-pong through a route, retaining determinism for arbitrary ticks."""
    period = 2 * (len(route) - 1)
    index = tick % period
    if index >= len(route):
        index = period - index
    return route[index]


class DemoSimulation:
    """Functional, deterministic provider of snapshots for the interface."""

    def __init__(self) -> None:
        self._walls = build_walls()
        for route in ROUTES:
            assert all(not self._walls[y, x] for x, y in route), "Demo route crosses wall"

    def frame(self, tick: int) -> SimulationFrame:
        tick = max(0, min(MAX_TICK, int(tick)))
        agents: list[AgentState] = []
        visited: set[tuple[int, int]] = set()

        for i, route in enumerate(ROUTES):
            path = tuple(_position_at(route, time) for time in range(tick + 1))
            visited.update(path)
            agents.append(
                AgentState(
                    identifier=f"{i + 1:02d}",
                    callsign=CALLSIGNS[i],
                    position=path[-1],
                    status=("SCANNING", "MOVING", "EXPLORING")[(tick // 6 + i) % 3],
                    energy=max(15, 100 - tick // (3 + i)),
                    trail=path,
                )
            )

        ys, xs = np.mgrid[0:HEIGHT, 0:WIDTH]
        peak_a_x = 23 + 1.6 * np.sin(tick / 35)
        peak_a_y = 4 + 0.5 * np.cos(tick / 29)
        peak_a = np.exp(-((xs - peak_a_x) ** 2 + (ys - peak_a_y) ** 2) / (2 * 3.0**2))
        peak_b = 0.55 * np.exp(-((xs - 7) ** 2 + (ys - 12) ** 2) / (2 * 2.4**2))
        belief = peak_a + peak_b + 0.01
        belief[self._walls] = 0.0
        belief = belief / belief.sum()
        nonzero = belief[belief > 0]
        entropy_bits = float(-(nonzero * np.log2(nonzero)).sum())
        free_cells = WIDTH * HEIGHT - int(self._walls.sum())
        coverage_pct = 100 * len(visited) / free_cells

        events = ["[0000]  SYSTEM START / DEMO SIMULATION"]
        first = max(1, tick - 4)
        for t in range(first, tick + 1):
            idx = t % len(agents)
            x, y = _position_at(ROUTES[idx], t)
            events.append(f"[{t:04d}]  D-{idx + 1:02d} MOVED TO ({x:02d},{y:02d})")
        return SimulationFrame(
            tick=tick,
            belief=belief,
            walls=self._walls.copy(),
            visited=frozenset(visited),
            agents=tuple(agents),
            events=tuple(events[-5:]),
            entropy_bits=entropy_bits,
            coverage_pct=coverage_pct,
        )
