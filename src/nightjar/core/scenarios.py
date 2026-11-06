"""Original authored geometry and public room metadata for training missions."""

from dataclasses import dataclass

from nightjar.core.world import Position


@dataclass(frozen=True)
class Room:
    name: str
    label_position: Position
    cells: frozenset[Position]


@dataclass(frozen=True)
class SiteFeature:
    name: str
    position: Position
    kind: str


@dataclass(frozen=True)
class ScenarioLayout:
    obstacles: frozenset[Position]
    rooms: tuple[Room, ...]
    features: tuple[SiteFeature, ...] = ()


def facility_layout(width: int, height: int) -> ScenarioLayout:
    """Return a connected four-room training layout for a supported map size.

    Walls constrain movement only. They do not change the synthetic proximity
    sensor's Manhattan-distance model. Room metadata contains no objective state.
    """
    if (width, height) not in {(16, 12), (32, 16), (40, 20)}:
        raise ValueError("training facility requires a supported mission map size")
    middle_x, middle_y = width // 2, height // 2
    doors_y = {height // 4, 3 * height // 4}
    doors_x = {width // 4, 3 * width // 4}
    partitions = {(middle_x, y) for y in range(height) if y not in doors_y} | {
        (x, middle_y) for x in range(width) if x not in doors_x
    }
    regions = (
        ("GARAGE", 0, middle_x, 0, middle_y),
        ("SERVER ROOM", middle_x + 1, width, 0, middle_y),
        ("WEST HALL", 0, middle_x, middle_y + 1, height),
        ("OPERATIONS", middle_x + 1, width, middle_y + 1, height),
    )
    features = [
        SiteFeature("PARTITION DOOR", (middle_x, y), "door_vertical")
        for y in sorted(doors_y)
    ] + [
        SiteFeature("PARTITION DOOR", (x, middle_y), "door_horizontal")
        for x in sorted(doors_x)
    ]
    equipment_names = ("LOADING RACK", "SERVER RACK", "UTILITY BANK", "CONTROL CONSOLE")
    for (_, left, _, _, bottom), name in zip(regions, equipment_names):
        # Small islands retain a walkable perimeter and leave the straight
        # doorway aisles open. These are actual collision geometry, not props
        # drawn over traversable cells.
        for x in (left + 1, left + 2):
            features.append(SiteFeature(name, (x, bottom - 2), "equipment"))
    obstacles = frozenset(partitions) | frozenset(
        feature.position for feature in features if feature.kind == "equipment"
    )
    rooms = tuple(
        Room(
            name=name,
            label_position=(left + 1, top + 1),
            cells=frozenset(
                (x, y)
                for y in range(top, bottom)
                for x in range(left, right)
                if (x, y) not in obstacles
            ),
        )
        for name, left, right, top, bottom in regions
    )
    return ScenarioLayout(obstacles=obstacles, rooms=rooms, features=tuple(features))
