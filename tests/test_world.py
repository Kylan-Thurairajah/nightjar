import pytest

from nightjar.core.world import BlockReason, Direction, GridWorld


def test_legal_moves_update_position_and_tick():
    world = GridWorld(width=3, height=3, obstacles=())

    result = world.step(Direction.EAST)
    assert result.position == (1, 0)
    assert result.moved
    assert result.blocked_by is None
    assert result.tick == 1

    result = world.step("south")
    assert result.position == (1, 1)
    assert result.moved
    assert result.tick == 2


@pytest.mark.parametrize(
    ("direction", "reason"),
    [
        (Direction.NORTH, BlockReason.BOUNDARY),
        (Direction.WEST, BlockReason.BOUNDARY),
    ],
)
def test_out_of_bounds_moves_are_blocked(direction, reason):
    world = GridWorld(width=3, height=3, obstacles=())

    result = world.step(direction)

    assert not result.moved
    assert result.position == (0, 0)
    assert result.blocked_by is reason
    assert result.tick == 1


def test_obstacle_blocks_movement_without_changing_position():
    world = GridWorld(width=3, height=3, obstacles={(1, 0)})

    result = world.step(Direction.EAST)

    assert not result.moved
    assert result.position == (0, 0)
    assert result.blocked_by is BlockReason.OBSTACLE
    assert result.tick == 1


def test_invalid_action_raises_without_changing_world():
    world = GridWorld(width=3, height=3, obstacles=())

    with pytest.raises(ValueError, match="unsupported direction"):
        world.step("diagonal")

    assert world.position == (0, 0)
    assert world.tick == 0


def test_same_seed_reproduces_obstacles_and_movement():
    first = GridWorld(width=12, height=8, seed=42)
    second = GridWorld(width=12, height=8, seed=42)
    actions = (Direction.EAST, Direction.SOUTH, Direction.WEST, Direction.NORTH)

    assert first.obstacles == second.obstacles
    first_results = [first.step(action) for action in actions]
    second_results = [second.step(action) for action in actions]

    assert first_results == second_results
    assert first.position == second.position
    assert first.tick == second.tick == len(actions)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"width": 0},
        {"height": -1},
        {"obstacle_count": -1},
        {"width": 1, "height": 1, "obstacle_count": 1},
        {"obstacles": {(0, 0)}},
        {"width": 3, "height": 3, "obstacles": {(3, 0)}},
    ],
)
def test_invalid_world_configuration_raises(kwargs):
    with pytest.raises(ValueError):
        GridWorld(**kwargs)
