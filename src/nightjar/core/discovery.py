"""Public, snapshot-derived beacon discovery state."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from nightjar.core.provider import OperationalMode
from nightjar.core.sensor import SensorType
from nightjar.core.world import Position

if TYPE_CHECKING:
    from nightjar.core.replay import MissionSnapshot


CONTACT_THRESHOLD = 0.6


class DiscoveryPhase(str, Enum):
    SEARCHING = "SEARCHING"
    CONTACT = "CONTACT"
    VERIFYING = "VERIFYING"
    CONFIRMED = "CONFIRMED"


@dataclass(frozen=True)
class DiscoveryState:
    phase: DiscoveryPhase
    candidate_position: Position | None = None
    verifier_id: str | None = None
    confirmed_position: Position | None = None
    confirmed_tick: int | None = None


def discovery_state(snapshot: MissionSnapshot) -> DiscoveryState:
    """Derive public discovery progress without reading hidden objective state."""
    for observation in reversed(snapshot.observations):
        if observation.sensor_type is SensorType.VERIFICATION and observation.positive:
            return DiscoveryState(
                phase=DiscoveryPhase.CONFIRMED,
                candidate_position=observation.position,
                verifier_id=observation.drone_id,
                confirmed_position=observation.position,
                confirmed_tick=observation.tick,
            )

    if (
        not snapshot.observations
        or snapshot.belief.stats.map_probability < CONTACT_THRESHOLD
    ):
        return DiscoveryState(DiscoveryPhase.SEARCHING)

    candidate = snapshot.belief.stats.map_position
    verifier = next(
        (
            drone
            for drone in snapshot.frame.drones
            if drone.mode is OperationalMode.MANUAL and drone.position == candidate
        ),
        None,
    )
    return DiscoveryState(
        phase=(
            DiscoveryPhase.VERIFYING if verifier is not None else DiscoveryPhase.CONTACT
        ),
        candidate_position=candidate,
        verifier_id=None if verifier is None else verifier.identifier,
    )
