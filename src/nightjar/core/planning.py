"""Deterministic, ground-truth-blind search policies for GridWorld missions."""

from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

import numpy as np
from numpy.typing import NDArray

from nightjar.core.belief import BeliefSnapshot
from nightjar.core.sensor import SensorConfig
from nightjar.core.world import Direction, Position


class SearchStrategy(str, Enum):
    RANDOM = "random"
    FRONTIER = "frontier"
    INFORMATION_GAIN = "information_gain"

    @property
    def label(self) -> str:
        return {
            SearchStrategy.RANDOM: "RANDOM",
            SearchStrategy.FRONTIER: "FRONTIER",
            SearchStrategy.INFORMATION_GAIN: "INFORMATION GAIN",
        }[self]


class PlannerActionType(str, Enum):
    MOVE = "move"
    SCAN = "scan"
    STOP = "stop"


@dataclass(frozen=True)
class PlannerAction:
    type: PlannerActionType
    direction: Direction | None = None

    def __post_init__(self) -> None:
        if (self.type is PlannerActionType.MOVE) != (self.direction is not None):
            raise ValueError("only move actions must include a direction")


@dataclass(frozen=True)
class PlannerDecision:
    strategy: SearchStrategy
    action: PlannerAction
    reason: str
    target: Position | None = None
    expected_information_gain_bits: float | None = None
    travel_cost: int | None = None


@dataclass(frozen=True)
class PlannerState:
    """Read-only public mission information available to search policies."""

    width: int
    height: int
    obstacles: frozenset[Position]
    position: Position
    traversable: frozenset[Position]
    visited: frozenset[Position]
    movement_history: tuple[Position, ...]
    scanned_positions: frozenset[Position]
    occupied_positions: frozenset[Position]
    permitted_moves: tuple[Direction, ...]
    scan_permitted: bool
    belief: BeliefSnapshot
    sensor_config: SensorConfig
    remaining_budget: int | None

    def __post_init__(self) -> None:
        probabilities = np.array(self.belief.probabilities, dtype=np.float64, copy=True)
        probabilities.setflags(write=False)
        object.__setattr__(
            self,
            "belief",
            BeliefSnapshot(
                probabilities=probabilities,
                prior_cell_probability=self.belief.prior_cell_probability,
                candidate_positions=self.belief.candidate_positions,
                stats=self.belief.stats,
                observation_count=self.belief.observation_count,
            ),
        )


class SearchPlanner(Protocol):
    strategy: SearchStrategy

    def decide(self, state: PlannerState) -> PlannerDecision: ...


class RandomPlanner:
    """Seeded baseline: choose uniformly from legal moves and one-time scans."""

    strategy = SearchStrategy.RANDOM

    def __init__(self, seed: int) -> None:
        self._random = random.Random(seed)

    def decide(self, state: PlannerState) -> PlannerDecision:
        actions = [
            PlannerAction(PlannerActionType.MOVE, direction)
            for direction in state.permitted_moves
        ]
        if state.scan_permitted:
            actions.append(PlannerAction(PlannerActionType.SCAN))
        if not actions:
            return PlannerDecision(
                self.strategy,
                PlannerAction(PlannerActionType.STOP),
                "No legal exploration action remains.",
            )
        action = self._random.choice(actions)
        return PlannerDecision(
            self.strategy,
            action,
            "Seeded choice among legal moves and unscanned sensor positions.",
        )


class FrontierPlanner:
    """Scan once per location, then route to the nearest reachable frontier."""

    strategy = SearchStrategy.FRONTIER

    def decide(self, state: PlannerState) -> PlannerDecision:
        if state.scan_permitted:
            return PlannerDecision(
                self.strategy,
                PlannerAction(PlannerActionType.SCAN),
                "Scan the current position once before continuing exploration.",
                target=state.position,
                travel_cost=0,
            )

        paths = _reachable_paths(state)
        frontier = [
            point
            for point in paths
            if point not in state.visited
            and any(neighbor in state.visited for neighbor in _neighbors(point))
        ]
        destinations = frontier or [
            point for point in paths if point not in state.visited
        ]
        if not destinations:
            return PlannerDecision(
                self.strategy,
                PlannerAction(PlannerActionType.STOP),
                "No reachable unvisited traversable cells remain.",
            )
        target = min(
            destinations,
            key=lambda point: (len(paths[point]), point[1], point[0]),
        )
        direction = _first_direction(paths[target])
        if direction is None:
            return PlannerDecision(
                self.strategy,
                PlannerAction(PlannerActionType.STOP),
                "Frontier is unreachable.",
            )
        return PlannerDecision(
            self.strategy,
            PlannerAction(PlannerActionType.MOVE, direction),
            "Route by shortest traversable path to the nearest frontier.",
            target=target,
            travel_cost=len(paths[target]),
        )


class InformationGainPlanner:
    """Choose reachable, unscanned sensor positions by gain minus travel cost."""

    strategy = SearchStrategy.INFORMATION_GAIN
    COST_PER_TICK_BITS = 0.01

    def decide(self, state: PlannerState) -> PlannerDecision:
        paths = _reachable_paths(state)
        sensing_positions = tuple(
            target for target in paths if target not in state.scanned_positions
        )
        gains = expected_information_gains(
            state.belief.probabilities,
            state.belief.candidate_positions,
            sensing_positions,
            state.sensor_config,
        )
        candidates: list[tuple[float, int, Position, float]] = []
        for target in sensing_positions:
            path = paths[target]
            gain = gains[target]
            travel_cost = len(path) + 1
            utility = gain - self.COST_PER_TICK_BITS * travel_cost
            if utility > 0:
                candidates.append((utility, travel_cost, target, gain))

        if not candidates:
            return PlannerDecision(
                self.strategy,
                PlannerAction(PlannerActionType.STOP),
                "No unscanned reachable position has positive information utility.",
            )

        utility, travel_cost, target, gain = min(
            candidates,
            key=lambda item: (-item[0], item[1], item[2][1], item[2][0]),
        )
        path = paths[target]
        if not path:
            return PlannerDecision(
                self.strategy,
                PlannerAction(PlannerActionType.SCAN),
                f"Expected information gain {gain:.4f} bits exceeds scan cost.",
                target=target,
                expected_information_gain_bits=gain,
                travel_cost=travel_cost,
            )
        direction = _first_direction(path)
        if direction is None:
            return PlannerDecision(
                self.strategy,
                PlannerAction(PlannerActionType.STOP),
                "Selected sensing position is unreachable.",
            )
        return PlannerDecision(
            self.strategy,
            PlannerAction(PlannerActionType.MOVE, direction),
            f"Move toward {gain:.4f} expected information bits.",
            target=target,
            expected_information_gain_bits=gain,
            travel_cost=travel_cost,
        )


def create_planner(strategy: SearchStrategy, seed: int) -> SearchPlanner:
    if strategy is SearchStrategy.RANDOM:
        return RandomPlanner(seed)
    if strategy is SearchStrategy.FRONTIER:
        return FrontierPlanner()
    if strategy is SearchStrategy.INFORMATION_GAIN:
        return InformationGainPlanner()
    raise ValueError(f"unsupported search strategy: {strategy!r}")


def expected_information_gain(
    probabilities: NDArray[np.float64],
    candidate_positions: tuple[Position, ...],
    sensing_position: Position,
    sensor_config: SensorConfig,
) -> float:
    """Return H(prior) - E[H(posterior)] using the sensor's binary likelihoods."""
    return expected_information_gains(
        probabilities,
        candidate_positions,
        (sensing_position,),
        sensor_config,
    )[sensing_position]


def expected_information_gains(
    probabilities: NDArray[np.float64],
    candidate_positions: tuple[Position, ...],
    sensing_positions: tuple[Position, ...],
    sensor_config: SensorConfig,
) -> dict[Position, float]:
    """Vectorized expected entropy reductions for several candidate sensor sites."""
    prior = np.array(
        [probabilities[y, x] for x, y in candidate_positions],
        dtype=np.float64,
    )
    if not sensing_positions:
        return {}
    candidate_x = np.array([x for x, _ in candidate_positions])[:, np.newaxis]
    candidate_y = np.array([y for _, y in candidate_positions])[:, np.newaxis]
    sensing_x = np.array([x for x, _ in sensing_positions])[np.newaxis, :]
    sensing_y = np.array([y for _, y in sensing_positions])[np.newaxis, :]
    in_range = (
        np.abs(candidate_x - sensing_x) + np.abs(candidate_y - sensing_y)
    ) <= sensor_config.detection_radius
    positive_likelihoods = np.where(
        in_range,
        sensor_config.sensitivity,
        sensor_config.false_positive_probability,
    ).T
    weighted_positive = positive_likelihoods * prior[np.newaxis, :]
    positive_probability = weighted_positive.sum(axis=1)
    negative_likelihoods = 1.0 - positive_likelihoods
    weighted_negative = negative_likelihoods * prior[np.newaxis, :]
    negative_probability = weighted_negative.sum(axis=1)

    positive_posteriors = np.divide(
        weighted_positive,
        positive_probability[:, np.newaxis],
        out=np.zeros_like(weighted_positive),
        where=positive_probability[:, np.newaxis] > 0,
    )
    negative_posteriors = np.divide(
        weighted_negative,
        negative_probability[:, np.newaxis],
        out=np.zeros_like(weighted_negative),
        where=negative_probability[:, np.newaxis] > 0,
    )
    expected_entropy = (
        positive_probability * _entropy_rows(positive_posteriors)
        + negative_probability * _entropy_rows(negative_posteriors)
    )
    prior_entropy = _entropy_bits(prior)
    information_gains = np.maximum(0.0, prior_entropy - expected_entropy)
    return {
        position: float(gain)
        for position, gain in zip(sensing_positions, information_gains)
    }


def _entropy_bits(probabilities: NDArray[np.float64]) -> float:
    nonzero = probabilities > 0
    return float(-np.sum(probabilities[nonzero] * np.log2(probabilities[nonzero])))


def _entropy_rows(probabilities: NDArray[np.float64]) -> NDArray[np.float64]:
    entropy_terms = np.zeros_like(probabilities)
    nonzero = probabilities > 0
    entropy_terms[nonzero] = probabilities[nonzero] * np.log2(
        probabilities[nonzero]
    )
    return -entropy_terms.sum(axis=1)


def _neighbors(position: Position) -> tuple[Position, ...]:
    x, y = position
    return ((x, y - 1), (x + 1, y), (x, y + 1), (x - 1, y))


def _reachable_paths(state: PlannerState) -> dict[Position, tuple[Direction, ...]]:
    direction_for_delta = {
        (0, -1): Direction.NORTH,
        (1, 0): Direction.EAST,
        (0, 1): Direction.SOUTH,
        (-1, 0): Direction.WEST,
    }
    paths: dict[Position, tuple[Direction, ...]] = {state.position: ()}
    queue = deque([state.position])
    blocked = state.obstacles | state.occupied_positions
    while queue:
        current = queue.popleft()
        for neighbor in _neighbors(current):
            if neighbor not in state.traversable or neighbor in blocked or neighbor in paths:
                continue
            dx = neighbor[0] - current[0]
            dy = neighbor[1] - current[1]
            paths[neighbor] = (*paths[current], direction_for_delta[(dx, dy)])
            queue.append(neighbor)
    return paths


def _first_direction(path: tuple[Direction, ...]) -> Direction | None:
    return path[0] if path else None
