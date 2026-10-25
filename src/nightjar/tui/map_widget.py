"""Rich-colored grid widget. Swap the synthetic frame for real states later."""

from rich.text import Text
from textual.widgets import Static

from nightjar.core.demo import SimulationFrame
from nightjar.core.provider import GridWorldFrame

# Near-black, desaturated green, yellow, amber; intended for true-color terminals.
HEAT_COLORS = (
    "#172b20", "#244a34", "#356e48", "#54955b",
    "#8ebc68", "#c4c574", "#daa754", "#ecad61",
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
                        style=("bold #06120b on #c6fac2" if is_selected else "bold #06120b on #74d9a2"),
                    )
                elif frame.walls[y, x]:
                    output.append("▓▓", style="#6d8574")
                elif layer == "coverage":
                    output.append("▒▒" if point in frame.visited else "··", style="#7bd49b" if point in frame.visited else "#2c503a")
                elif layer == "paths":
                    output.append("••" if point in trails else "··", style="#a2d68f" if point in trails else "#31543c")
                else:
                    intensity = float(frame.belief[y, x] / peak)
                    index = min(int(intensity**0.8 * len(HEAT_COLORS)), len(HEAT_COLORS) - 1)
                    output.append("██" if index >= 2 else "░░", style=HEAT_COLORS[index])
            if y < frame.walls.shape[0] - 1:
                output.append("\n")
        self.update(output)

    def show_gridworld_frame(self, frame: GridWorldFrame, layer: str = "terrain") -> None:
        output = Text(no_wrap=True, overflow="crop")
        occupied = frame.position
        path = set(frame.path)

        for y in range(frame.height):
            for x in range(frame.width):
                point = (x, y)
                if point == occupied:
                    output.append("01", style="bold #06120b on #c6fac2")
                elif point in frame.obstacles:
                    output.append("▓▓", style="#6d8574")
                elif layer == "coverage" and point in frame.visited:
                    output.append("▒▒", style="#7bd49b")
                elif layer == "paths" and point in path:
                    output.append("••", style="#a2d68f")
                else:
                    output.append("··", style="#31543c")
            if y < frame.height - 1:
                output.append("\n")
        self.update(output)
