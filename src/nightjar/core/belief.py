"""Numerically stable Bayesian belief mapping for synthetic observations."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

import numpy as np
from numpy.typing import NDArray

from nightjar.core.sensor import Observation, SensorType
from nightjar.core.world import Position


class InconsistentEvidenceError(ValueError):
    """Raised when an observation has zero likelihood under every hypothesis."""


@dataclass(frozen=True)
class BeliefStats:
    initial_entropy_bits: float
    entropy_bits: float
    entropy_change_bits: float
    map_position: Position
    map_probability: float
    candidate_count: int


@dataclass(frozen=True)
class BeliefSnapshot:
    probabilities: NDArray[np.float64]
    prior_cell_probability: float
    candidate_positions: tuple[Position, ...]
    stats: BeliefStats
    observation_count: int


class BeliefMap:
    """Mission-level posterior over valid objective locations.

    Candidate cells are supplied by the world geometry, never by its sampled
    hidden objective. Log probabilities preserve exact-zero hypotheses and
    avoid cumulative probability underflow.
    """

    def __init__(
        self,
        width: int,
        height: int,
        obstacles: Iterable[Position],
        candidate_positions: Iterable[Position],
        mission_id: str,
    ) -> None:
        if type(width) is not int or width < 1:
            raise ValueError("width must be a positive integer")
        if type(height) is not int or height < 1:
            raise ValueError("height must be a positive integer")
        if not isinstance(mission_id, str) or not mission_id:
            raise ValueError("mission_id must be a non-empty string")

        self._width = width
        self._height = height
        self._mission_id = mission_id
        self._obstacles = frozenset(obstacles)
        candidates = tuple(candidate_positions)
        if not candidates:
            raise ValueError("belief map requires at least one candidate cell")
        if len(set(candidates)) != len(candidates):
            raise ValueError("candidate positions must be unique")
        for position in candidates:
            if (
                not isinstance(position, tuple)
                or len(position) != 2
                or any(type(coordinate) is not int for coordinate in position)
            ):
                raise ValueError("candidate positions must be integer (x, y) tuples")
            x, y = position
            if not (0 <= x < width and 0 <= y < height):
                raise ValueError(f"candidate position {position!r} is outside the grid")
            if position in self._obstacles:
                raise ValueError("candidate positions cannot be obstacles")

        self._candidate_positions = candidates
        self._log_probabilities = np.full((height, width), -np.inf, dtype=np.float64)
        log_prior = -math.log(len(candidates))
        for x, y in candidates:
            self._log_probabilities[y, x] = log_prior
        self._initial_entropy_bits = math.log2(len(candidates))
        self._applied_observation_ids: set[str] = set()
        self._last_observation_tick = -1

    @property
    def probabilities(self) -> NDArray[np.float64]:
        """Return a read-only probability array in [y, x] order."""
        probabilities = np.exp(self._log_probabilities)
        probabilities.setflags(write=False)
        return probabilities

    @property
    def prior_cell_probability(self) -> float:
        return 1.0 / len(self._candidate_positions)

    @property
    def candidate_positions(self) -> tuple[Position, ...]:
        return self._candidate_positions

    @property
    def observation_count(self) -> int:
        return len(self._applied_observation_ids)

    @property
    def stats(self) -> BeliefStats:
        probabilities = self.probabilities
        finite = np.isfinite(self._log_probabilities)
        map_y, map_x = np.unravel_index(
            int(np.argmax(self._log_probabilities)),
            self._log_probabilities.shape,
        )
        nonzero = probabilities > 0
        entropy = float(
            -np.sum(probabilities[nonzero] * np.log2(probabilities[nonzero]))
        )
        return BeliefStats(
            initial_entropy_bits=self._initial_entropy_bits,
            entropy_bits=entropy,
            entropy_change_bits=entropy - self._initial_entropy_bits,
            map_position=(int(map_x), int(map_y)),
            map_probability=float(probabilities[map_y, map_x]),
            candidate_count=int(np.count_nonzero(finite)),
        )

    def snapshot(self) -> BeliefSnapshot:
        return BeliefSnapshot(
            probabilities=self.probabilities,
            prior_cell_probability=self.prior_cell_probability,
            candidate_positions=self._candidate_positions,
            stats=self.stats,
            observation_count=self.observation_count,
        )

    def update(self, observation: Observation) -> BeliefStats:
        """Apply one observation in mission order and return updated statistics."""
        if observation.mission_id != self._mission_id:
            raise ValueError("observation mission_id does not match this belief map")
        if not observation.observation_id:
            raise ValueError("observation_id must not be empty")
        if observation.observation_id in self._applied_observation_ids:
            raise ValueError(f"observation already applied: {observation.observation_id}")
        if type(observation.tick) is not int or observation.tick <= self._last_observation_tick:
            raise ValueError("observations must be applied in strictly increasing tick order")
        if observation.sensor_type is not SensorType.PROXIMITY:
            raise ValueError(f"unsupported sensor type: {observation.sensor_type!r}")
        if (
            not isinstance(observation.position, tuple)
            or len(observation.position) != 2
            or any(type(coordinate) is not int for coordinate in observation.position)
        ):
            raise ValueError("observation position must be an integer (x, y) tuple")
        px, py = observation.position
        if not (0 <= px < self._width and 0 <= py < self._height):
            raise ValueError("observation position is outside the belief map")

        config = observation.sensor_config
        likelihoods = np.empty(len(self._candidate_positions), dtype=np.float64)
        for index, (x, y) in enumerate(self._candidate_positions):
            in_range = (
                abs(x - px) + abs(y - py) <= config.detection_radius
            )
            positive_likelihood = (
                config.sensitivity
                if in_range
                else config.false_positive_probability
            )
            likelihoods[index] = (
                positive_likelihood
                if observation.positive
                else 1.0 - positive_likelihood
            )

        updated = self._log_probabilities.copy()
        with np.errstate(divide="ignore"):
            log_likelihoods = np.log(likelihoods)
        for index, (x, y) in enumerate(self._candidate_positions):
            updated[y, x] += log_likelihoods[index]

        maximum = float(np.max(updated))
        if not math.isfinite(maximum):
            raise InconsistentEvidenceError(
                f"observation {observation.observation_id} is impossible under "
                "every remaining hypothesis"
            )
        normalizer = maximum + math.log(float(np.exp(updated - maximum).sum()))
        updated -= normalizer

        self._log_probabilities = updated
        self._applied_observation_ids.add(observation.observation_id)
        self._last_observation_tick = observation.tick
        return self.stats
