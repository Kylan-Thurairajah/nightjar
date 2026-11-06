"""Compact ASCII unit designators with selection-only color emphasis.

Two plain characters fit each map cell without pictogram overhang or emoji fonts.
Numeric IDs remain available; no simulation or archive state depends on display.
"""

from rich.cells import cell_len, set_cell_size


DRONE_ICONS = {
    "01": "R1",
    "02": "G2",
    "03": "V3",
}
DRONE_COLOR = "#a7d4b4"
SELECTED_DRONE_COLOR = "#e0b45c"
DRONE_LETTERS = {"01": "R", "02": "G", "03": "V"}


def drone_marker(identifier: str, animal_icons: bool = True) -> str:
    """Return exactly two Rich terminal cells, or the stable numeric ID."""
    icon = DRONE_ICONS.get(identifier) if animal_icons else None
    if icon is not None and cell_len(icon) == 2:
        return icon
    return set_cell_size(identifier, 2)


def drone_color(identifier: str, *, selected: bool = False) -> str:
    """All identities share one neutral color; only selection receives amber."""
    return SELECTED_DRONE_COLOR if selected else DRONE_COLOR


def drone_letter(identifier: str) -> str:
    """Owner letters distinguish neutral-colored paths without pictograms."""
    return DRONE_LETTERS.get(identifier, identifier[-1:] or "?")
