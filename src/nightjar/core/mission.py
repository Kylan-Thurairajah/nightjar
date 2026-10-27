"""Validated, deterministic configuration for a Nightjar GridWorld mission."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from nightjar.core.provider import GridWorldSimulation, OperationalMode
from nightjar.core.sensor import SensorConfig, SensorPreset
from nightjar.core.world import GridWorld


class ScenarioPreset(str, Enum):
    OPEN_FIELD = "open_field"
    OBSTACLE_FIELD = "obstacle_field"


class MapPreset(str, Enum):
    COMPACT = "compact"
    STANDARD = "standard"
    EXTENDED = "extended"

    @property
    def dimensions(self) -> tuple[int, int]:
        return {
            MapPreset.COMPACT: (16, 12),
            MapPreset.STANDARD: (32, 16),
            MapPreset.EXTENDED: (40, 20),
        }[self]


@dataclass(frozen=True)
class MissionConfig:
    operation_name: str = "NIGHTJAR-01"
    scenario: ScenarioPreset = ScenarioPreset.OBSTACLE_FIELD
    drone_count: int = 3
    map_preset: MapPreset = MapPreset.STANDARD
    initial_control: OperationalMode = OperationalMode.MANUAL
    max_ticks: int = 500
    seed: int = 0
    sensor_preset: SensorPreset = SensorPreset.STANDARD

    @property
    def mission_id(self) -> str:
        normalized = re.sub(r"[^A-Z0-9]+", "-", self.operation_name.strip().upper())
        return normalized.strip("-")

    @property
    def width(self) -> int:
        return self.map_preset.dimensions[0]

    @property
    def height(self) -> int:
        return self.map_preset.dimensions[1]


@dataclass(frozen=True)
class ValidationCheck:
    label: str
    passed: bool
    detail: str


def create_world(config: MissionConfig) -> GridWorld:
    """Build the selected deterministic environment from mission settings."""
    if not isinstance(config.scenario, ScenarioPreset):
        raise ValueError("scenario must be a supported ScenarioPreset")
    if not isinstance(config.map_preset, MapPreset):
        raise ValueError("map_preset must be a supported MapPreset")
    width, height = config.map_preset.dimensions
    obstacle_count = (
        0
        if config.scenario is ScenarioPreset.OPEN_FIELD
        else width * height // 12
    )
    return GridWorld(
        width=width,
        height=height,
        seed=config.seed,
        obstacle_count=obstacle_count,
    )


def validate_mission_config(config: MissionConfig) -> tuple[ValidationCheck, ...]:
    """Run all configuration checks, including actual deterministic spawn capacity."""
    checks: list[ValidationCheck] = []
    checks.append(
        ValidationCheck(
            "Operation name",
            isinstance(config.operation_name, str)
            and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 _-]{0,39}", config.operation_name.strip())
            is not None,
            "Use 1–40 letters, numbers, spaces, hyphens, or underscores.",
        )
    )
    checks.append(
        ValidationCheck(
            "Scenario",
            isinstance(config.scenario, ScenarioPreset),
            "Selected environment preset is supported."
            if isinstance(config.scenario, ScenarioPreset)
            else "Select a supported environment preset.",
        )
    )
    checks.append(
        ValidationCheck(
            "Map dimensions",
            isinstance(config.map_preset, MapPreset),
            (
                f"{config.width} × {config.height} cells."
                if isinstance(config.map_preset, MapPreset)
                else "Select a supported map size."
            ),
        )
    )
    checks.append(
        ValidationCheck(
            "Drone count",
            type(config.drone_count) is int and 1 <= config.drone_count <= 10,
            "Between 1 and 10 drones."
            if type(config.drone_count) is int and 1 <= config.drone_count <= 10
            else "Drone count must be an integer from 1 to 10.",
        )
    )
    checks.append(
        ValidationCheck(
            "Initial control",
            isinstance(config.initial_control, OperationalMode)
            and config.initial_control in (OperationalMode.MANUAL, OperationalMode.IDLE),
            "Drones start in MANUAL or IDLE control."
            if isinstance(config.initial_control, OperationalMode)
            and config.initial_control in (OperationalMode.MANUAL, OperationalMode.IDLE)
            else "Select MANUAL or IDLE.",
        )
    )
    checks.append(
        ValidationCheck(
            "Tick budget",
            type(config.max_ticks) is int and config.max_ticks > 0,
            "Positive simulation tick limit."
            if type(config.max_ticks) is int and config.max_ticks > 0
            else "Tick budget must be a positive integer.",
        )
    )
    checks.append(
        ValidationCheck(
            "Random seed",
            type(config.seed) is int and config.seed >= 0,
            "Nonnegative deterministic seed."
            if type(config.seed) is int and config.seed >= 0
            else "Seed must be a nonnegative integer.",
        )
    )
    checks.append(
        ValidationCheck(
            "Sensor preset",
            isinstance(config.sensor_preset, SensorPreset),
            "Supported synthetic sensor reliability preset."
            if isinstance(config.sensor_preset, SensorPreset)
            else "Select a supported sensor reliability preset.",
        )
    )

    foundational_checks_pass = all(check.passed for check in checks)
    if not foundational_checks_pass:
        checks.append(
            ValidationCheck(
                "Spawn capacity",
                False,
                "Resolve the invalid fields before spawn capacity can be checked.",
            )
        )
        return tuple(checks)

    try:
        world = create_world(config)
        GridWorldSimulation(
            world,
            drone_count=config.drone_count,
            initial_mode=config.initial_control,
            max_ticks=config.max_ticks,
            operation_name=config.operation_name,
            scenario=config.scenario.value,
            sensor_config=SensorConfig.from_preset(config.sensor_preset),
        )
    except ValueError as error:
        checks.append(ValidationCheck("Spawn capacity", False, str(error)))
    else:
        checks.append(
            ValidationCheck(
                "Spawn capacity",
                True,
                f"{config.drone_count} unique traversable spawn cells available.",
            )
        )
    return tuple(checks)


def create_simulation(config: MissionConfig) -> GridWorldSimulation:
    """Validate and initialize a mission's world and requested drone fleet."""
    checks = validate_mission_config(config)
    failures = [f"{check.label}: {check.detail}" for check in checks if not check.passed]
    if failures:
        raise ValueError("Invalid mission configuration:\n" + "\n".join(failures))
    return GridWorldSimulation(
        create_world(config),
        drone_count=config.drone_count,
        initial_mode=config.initial_control,
        max_ticks=config.max_ticks,
        operation_name=config.operation_name,
        scenario=config.scenario.value,
        sensor_config=SensorConfig.from_preset(config.sensor_preset),
    )
