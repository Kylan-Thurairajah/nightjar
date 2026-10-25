import numpy as np

from nightjar.core.demo import DemoSimulation, HEIGHT, MAX_TICK, WIDTH


def test_shape_and_normalization():
    frame = DemoSimulation().frame(50)
    assert frame.belief.shape == (HEIGHT, WIDTH)
    assert frame.walls.shape == (HEIGHT, WIDTH)
    assert np.isclose(float(frame.belief.sum()), 1.0)
    assert np.all(frame.belief[frame.walls] == 0)


def test_deterministic_snapshots():
    sim = DemoSimulation()
    a = sim.frame(30)
    b = sim.frame(30)
    assert np.array_equal(a.belief, b.belief)
    assert [x.position for x in a.agents] == [x.position for x in b.agents]
    assert a.events == b.events


def test_agents_avoid_walls():
    sim = DemoSimulation()
    for tick in range(MAX_TICK + 1):
        frame = sim.frame(tick)
        for agent in frame.agents:
            x, y = agent.position
            assert not frame.walls[y, x]


def test_coverage_progresses():
    sim = DemoSimulation()
    assert sim.frame(75).coverage_pct >= sim.frame(30).coverage_pct


def test_tick_clamping():
    sim = DemoSimulation()
    assert sim.frame(-5).tick == 0
    assert sim.frame(MAX_TICK + 500).tick == MAX_TICK
