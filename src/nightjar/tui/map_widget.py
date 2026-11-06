"""Rich-colored renderer for demo frames and GridWorld mission state."""

import math

from rich.text import Text
from textual.widgets import Static

from nightjar.core.belief import BeliefSnapshot
from nightjar.core.demo import SimulationFrame
from nightjar.core.provider import GridWorldFrame
from nightjar.core.planning import PlannerActionType, PlannerDecision
from nightjar.core.scenarios import facility_layout
from nightjar.core.sensor import Observation
from nightjar.tui.drone_identity import drone_color, drone_letter, drone_marker

# Near-black, desaturated green, yellow, amber; intended for true-color terminals.
HEAT_COLORS = (
    "#172b20",
    "#244a34",
    "#356e48",
    "#54955b",
    "#8ebc68",
    "#c4c574",
    "#daa754",
    "#ecad61",
)


class MapWidget(Static):
    """Displays demo frames or neutral GridWorld state as a Rich Text grid."""

    def show_frame(self, frame: SimulationFrame, layer: str, selected: int) -> None:
        output = Text(no_wrap=True, overflow="crop")
        peak = max(float(frame.belief.max()), 1e-12)
        occupied = {agent.position: index for index, agent in enumerate(frame.agents)}
        trails = {point for agent in frame.agents for point in agent.trail}

        for y in range(frame.walls.shape[0]):
            for x in range(frame.walls.shape[1]):
                point = (x, y)
                agent_index = occupied.get(point)
                if agent_index is not None:
                    is_selected = agent_index == selected
                    output.append(
                        frame.agents[agent_index].identifier,
                        style=(
                            "bold #06120b on #c6fac2"
                            if is_selected
                            else "bold #06120b on #74d9a2"
                        ),
                    )
                elif frame.walls[y, x]:
                    output.append("▓▓", style="#6d8574")
                elif layer == "coverage":
                    output.append(
                        "▒▒" if point in frame.visited else "··",
                        style="#7bd49b" if point in frame.visited else "#2c503a",
                    )
                elif layer == "paths":
                    output.append(
                        "••" if point in trails else "··",
                        style="#a2d68f" if point in trails else "#31543c",
                    )
                else:
                    intensity = float(frame.belief[y, x] / peak)
                    index = min(
                        int(intensity**0.8 * len(HEAT_COLORS)), len(HEAT_COLORS) - 1
                    )
                    output.append(
                        "██" if index >= 2 else "░░", style=HEAT_COLORS[index]
                    )
            if y < frame.walls.shape[0] - 1:
                output.append("\n")
        self.update(output)

    def show_gridworld_frame(
        self,
        frame: GridWorldFrame,
        layer: str = "terrain",
        selected_drone_id: str = "01",
        belief_map: BeliefSnapshot | None = None,
        *,
        last_observation: Observation | None = None,
        planner_decision: PlannerDecision | None = None,
        animal_icons: bool = False,
        styled_drones: bool = False,
        target_owner: str | None = None,
    ) -> None:
        output = Text(no_wrap=True, overflow="crop")
        occupied = {drone.position: drone for drone in frame.drones}
        visited = set().union(*(drone.visited for drone in frame.drones))
        path = set().union(*(set(drone.path) for drone in frame.drones))
        path_owners: dict[tuple[int, int], set[str]] = {}
        if styled_drones:
            for drone in frame.drones:
                for point in drone.path:
                    path_owners.setdefault(point, set()).add(drone.identifier)
        probabilities = belief_map.probabilities if belief_map is not None else None
        prior_probability = (
            belief_map.prior_cell_probability if belief_map is not None else 0.0
        )
        maximum_probability = (
            float(probabilities.max()) if probabilities is not None else 0.0
        )
        has_evidence = maximum_probability > prior_probability * (1.0 + 1e-12)
        map_position = (
            belief_map.stats.map_position
            if belief_map is not None and has_evidence
            else None
        )

        room_labels = self._room_labels(frame) if layer == "terrain" else {}
        features = self._site_features(frame) if layer == "terrain" else {}
        if target_owner not in {drone.identifier for drone in frame.drones}:
            target_owner = None
        target = (
            planner_decision.target
            if planner_decision is not None
            and planner_decision.action.type is PlannerActionType.MOVE
            else None
        )
        scan_background = (
            "on #49391e"
            if last_observation is not None and last_observation.positive
            else "on #142e25"
        )
        for y in range(frame.height):
            for x in range(frame.width):
                point = (x, y)
                drone = occupied.get(point)
                if drone is not None:
                    style = (
                        "bold #080f0c on #e0b45c"
                        if drone.identifier == selected_drone_id
                        else f"bold {drone_color(drone.identifier)} on #14251c"
                    )
                    output.append(
                        drone_marker(drone.identifier, animal_icons), style=style
                    )
                elif point in frame.obstacles:
                    if features.get(point) == "equipment":
                        output.append("\u25a5\u25a5", style="#71866d")
                    else:
                        output.append("▓▓", style="#6d8574")
                elif point == target and not (
                    layer == "belief" and point == map_position
                ):
                    if styled_drones and target_owner is not None:
                        output.append(
                            f"{drone_letter(target_owner)}+",
                            style=f"bold {drone_color(target_owner)}",
                        )
                    else:
                        output.append("+ ", style="bold #89a58e")
                elif point in features:
                    glyph = (
                        "\u250a\u250a"
                        if features[point] == "door_vertical"
                        else "\u2504\u2504"
                    )
                    output.append(glyph, style="#4b7356")
                elif layer == "terrain" and point in room_labels:
                    output.append(room_labels[point], style="bold #89a58e")
                elif layer == "coverage" and point in visited:
                    output.append("▒▒", style="#7bd49b")
                elif layer == "paths" and point in path:
                    owners = path_owners.get(point, set())
                    if len(owners) == 1:
                        owner = next(iter(owners))
                        output.append(
                            f"{drone_letter(owner)}\u00b7", style=drone_color(owner)
                        )
                    elif owners:
                        output.append("\u2573 ", style="#90b99e")
                    else:
                        output.append("••", style="#a2d68f")
                elif layer == "belief" and probabilities is not None:
                    probability = float(probabilities[y, x])
                    if probability <= 0:
                        output.append("··", style="#182b20")
                    elif has_evidence and point == map_position:
                        output.append("██", style="bold #080f0c on #e0b45c")
                    elif not has_evidence:
                        output.append("░░", style="#31543c")
                    else:
                        ratio = max(probability / prior_probability, 1.0)
                        peak_ratio = maximum_probability / prior_probability
                        intensity = max(
                            0.0,
                            min(1.0, math.log(ratio) / math.log(peak_ratio)),
                        )
                        index = min(
                            int(intensity * (len(HEAT_COLORS) - 1)),
                            len(HEAT_COLORS) - 1,
                        )
                        glyph = ("░░", "▒▒", "▒▒", "▓▓", "▓▓", "██", "██", "██")[index]
                        output.append(glyph, style=HEAT_COLORS[index])
                else:
                    output.append("··", style="#31543c")
                if (
                    last_observation is not None
                    and drone is None
                    and point not in frame.obstacles
                    and not (layer == "belief" and point == map_position)
                    and abs(x - last_observation.position[0])
                    + abs(y - last_observation.position[1])
                    <= last_observation.sensor_config.detection_radius
                ):
                    output.stylize(scan_background, len(output) - 2, len(output))
            if y < frame.height - 1:
                output.append("\n")
        self.update(output)

    @staticmethod
    def _site_features(frame: GridWorldFrame) -> dict[tuple[int, int], str]:
        if frame.scenario != "training_facility":
            return {}
        try:
            layout = facility_layout(frame.width, frame.height)
        except ValueError:
            return {}
        if layout.obstacles != frame.obstacles:
            return {}
        return {feature.position: feature.kind for feature in layout.features}

    @staticmethod
    def _room_labels(frame: GridWorldFrame) -> dict[tuple[int, int], str]:
        """Derive public labels only for the actual known authored floor plan."""
        if frame.scenario != "training_facility":
            return {}
        try:
            layout = facility_layout(frame.width, frame.height)
        except ValueError:
            return {}
        if frame.obstacles != layout.obstacles:
            return {}
        labels: dict[tuple[int, int], str] = {}
        for room in layout.rooms:
            x, y = room.label_position
            for offset in range(0, len(room.name), 2):
                point = (x + offset // 2, y)
                if point not in room.cells:
                    break
                labels[point] = room.name[offset : offset + 2].ljust(2)
        return labels
