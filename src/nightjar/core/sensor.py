"""Synthetic, deterministic proximity sensing for simulated missions."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from enum import Enum

from nightjar.core.world import Position


class SensorPreset(str, Enum):
    HIGH_RELIABILITY = "high_reliability"
    STANDARD = "standard"
    DEGRADED = "degraded"
    VERIFICATION = "verification"

    @property
    def probabilities(self) -> tuple[float, float]:
        return {
            SensorPreset.HIGH_RELIABILITY: (0.98, 0.02),
            SensorPreset.STANDARD: (0.90, 0.05),
            SensorPreset.DEGRADED: (0.75, 0.15),
            SensorPreset.VERIFICATION: (1.0, 0.0),
        }[self]


class SensorType(str, Enum):
    PROXIMITY = "PROXIMITY"
    VERIFICATION = "VERIFICATION"


@dataclass(frozen=True)
class SensorConfig:
    detection_radius: int = 3
    sensitivity: float = 0.90
    false_positive_probability: float = 0.05
    preset: SensorPreset = SensorPreset.STANDARD

    def __post_init__(self) -> None:
        if type(self.detection_radius) is not int or self.detection_radius < 0:
            raise ValueError("detection_radius must be a non-negative integer")
        for name, probability in (
            ("sensitivity", self.sensitivity),
            ("false_positive_probability", self.false_positive_probability),
        ):
            if (
                type(probability) not in (int, float)
                or not math.isfinite(probability)
                or not 0 <= probability <= 1
            ):
                raise ValueError(f"{name} must be a finite probability from 0 to 1")
        if not isinstance(self.preset, SensorPreset):
            raise ValueError("preset must be a supported SensorPreset")
        if self.preset is SensorPreset.VERIFICATION and (
            self.detection_radius != 0
            or self.sensitivity != 1.0
            or self.false_positive_probability != 0.0
        ):
            raise ValueError("verification sensor configuration must be exact-cell")

    @classmethod
    def from_preset(cls, preset: SensorPreset) -> SensorConfig:
        if not isinstance(preset, SensorPreset):
            raise ValueError("preset must be a supported SensorPreset")
        sensitivity, false_positive_probability = preset.probabilities
        return cls(
            detection_radius=0 if preset is SensorPreset.VERIFICATION else 3,
            sensitivity=sensitivity,
            false_positive_probability=false_positive_probability,
            preset=preset,
        )


@dataclass(frozen=True)
class Observation:
    mission_id: str
    observation_id: str
    drone_id: str
    tick: int
    position: Position
    sensor_type: SensorType
    positive: bool
    sensor_config: SensorConfig
    sequence_number: int


class ProximitySensor:
    """Binary Manhattan-distance sensor with an independent seeded RNG."""

    def __init__(self, config: SensorConfig, seed: int) -> None:
        if type(seed) is not int:
            raise ValueError("sensor seed must be an integer")
        self.config = config
        self._random = random.Random(seed)

    def scan(self, position: Position, objective_position: Position) -> bool:
        within_range = (
            abs(position[0] - objective_position[0])
            + abs(position[1] - objective_position[1])
            <= self.config.detection_radius
        )
        probability = (
            self.config.sensitivity
            if within_range
            else self.config.false_positive_probability
        )
        return self._random.random() < probability


VERIFICATION_SENSOR_CONFIG = SensorConfig.from_preset(SensorPreset.VERIFICATION)
