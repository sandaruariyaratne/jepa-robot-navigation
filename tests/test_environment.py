import numpy as np
import pytest

from environment import (
    ACTIONS,
    DOWN,
    LEFT,
    REFERENCE_START,
    RIGHT,
    UP,
    COLORS,
    GridMap,
    GridWorld,
    distances_to_goal,
    save_png,
    shortest_path,
)

# Distance table from spec v1.1, section 02 (-1 = wall).
EXPECTED_DIST = np.array(
    [
        [5, 4, 3, 2, 1, 0],
        [6, 5, -1, 3, 2, 1],
        [7, 6, -1, 4, 3, 2],
        [8, 7, -1, 5, -1, 3],
        [9, 8, 7, 6, -1, 4],
    ]
)


@pytest.fixture
def env():
    return GridWorld(seed=0)


# --- map and observations --------------------------------------------------
def test_reference_map_counts(env):
    assert len(env.map.free_cells()) == 25
    assert len(env.map.start_cells()) == 24
    assert env.map.goal not in env.map.start_cells()


def test_observation_contract(env):
    obs = env.reset(start=REFERENCE_START)
    assert obs.dtype == np.uint8
    assert obs.shape == (3, 40, 48) == env.obs_shape


def test_every_position_renders_a_unique_frame(env):
    frames = [env.render(c).tobytes() for c in env.map.free_cells()]
    assert len(set(frames)) == 25


def test_robot_pixels_and_goal_frame(env):
    robot = np.array(COLORS["robot"], dtype=np.uint8)
    goal = np.array(COLORS["goal"], dtype=np.uint8)
    hwc = env.render(REFERENCE_START).transpose(1, 2, 0)
    assert (hwc[33:40, 1:8] == robot).all()  # cell (0, 4) interior is 7x7
    assert (hwc[1:8, 41:48] == goal).all()  # goal visible when robot is elsewhere
    g = env.goal_obs().transpose(1, 2, 0)
    assert (g[1:8, 41:48] == robot).all()  # robot drawn on top of the goal
    assert not (g == goal).all(axis=-1).any()  # no goal colour left in the goal frame


def test_render_returns_independent_copies(env):
    a = env.render(REFERENCE_START)
    a[:] = 0
    assert env.render(REFERENCE_START).any()


def test_render_rejects_wall(env):
    with pytest.raises(ValueError):
        env.render((2, 1))


# --- dynamics ----------------------------------------------------------------
@pytest.mark.parametrize(
    "start, action, expected, collision",
    [
        ((0, 4), RIGHT, (1, 4), False),
        ((0, 4), LEFT, (0, 4), True),  # border
        ((0, 4), DOWN, (0, 4), True),  # border
        ((0, 4), UP, (0, 3), False),
        ((1, 2), RIGHT, (1, 2), True),  # wall at (2, 2)
        ((3, 4), RIGHT, (3, 4), True),  # wall at (4, 4)
        ((5, 4), LEFT, (5, 4), True),  # wall at (4, 4)
        ((5, 0), UP, (5, 0), True),  # goal corner
        ((5, 0), RIGHT, (5, 0), True),
    ],
)
def test_transitions(env, start, action, expected, collision):
    env.reset(start=start)
    r = env.step(action)
    assert r.pos == expected == env.pos
    assert r.collision is collision
    assert np.array_equal(r.obs, env.render(expected))


def test_dynamics_are_deterministic():
    m = GridMap()
    for c in m.free_cells():
        for a in ACTIONS:
            assert m.transition(c, a) == m.transition(c, a)


def test_invalid_action_and_lifecycle(env):
    with pytest.raises(RuntimeError):
        env.step(UP)  # before reset
    env.reset(start=REFERENCE_START)
    with pytest.raises(ValueError):
        env.step(4)
    with pytest.raises(ValueError):
        env.reset(start=(2, 1))  # wall


def test_numpy_integer_actions_accepted(env):
    env.reset(start=REFERENCE_START)
    assert env.step(np.int64(RIGHT)).pos == (1, 4)


# --- episodes ----------------------------------------------------------------
def test_terminates_on_goal(env):
    env.reset(start=(4, 0))
    r = env.step(RIGHT)
    assert r.at_goal and r.terminated and r.done
    with pytest.raises(RuntimeError):
        env.step(UP)


def test_collection_mode_does_not_stop_at_goal():
    env = GridWorld(terminate_on_goal=False, seed=0)
    env.reset(start=(4, 0))
    r = env.step(RIGHT)
    assert r.at_goal and not r.done
    r = env.step(LEFT)
    assert r.pos == (4, 0) and not r.at_goal


def test_truncation_at_max_steps():
    env = GridWorld(max_steps=3, seed=0)
    env.reset(start=REFERENCE_START)
    results = [env.step(LEFT) for _ in range(3)]
    assert [r.truncated for r in results] == [False, False, True]
    assert results[-1].done and not results[-1].terminated


def test_goal_on_final_step_is_terminated_not_truncated():
    env = GridWorld(max_steps=1, seed=0)
    env.reset(start=(4, 0))
    r = env.step(RIGHT)
    assert r.terminated and not r.truncated


def test_seeded_random_starts_are_reproducible_and_valid():
    a, b = GridWorld(seed=7), GridWorld(seed=7)
    starts_a, starts_b = [], []
    for _ in range(200):
        a.reset()
        b.reset()
        starts_a.append(a.pos)
        starts_b.append(b.pos)
    assert starts_a == starts_b
    assert set(starts_a) <= set(a.map.start_cells())
    assert len(set(starts_a)) == 24  # 200 draws cover all start cells


# --- BFS oracle --------------------------------------------------------------
def test_distance_table_matches_spec():
    assert np.array_equal(distances_to_goal(GridMap()), EXPECTED_DIST)


def test_horizon_facts_from_spec():
    d = distances_to_goal(GridMap())
    starts = d[(d > 0)]
    assert d[4, 0] == 9 and d.max() == 9
    assert (starts > 5).sum() == 9 and starts.size == 24


def test_shortest_path_reaches_goal_optimally(env):
    d = distances_to_goal(env.map)
    for start in env.map.start_cells():
        path = shortest_path(env.map, start)
        assert len(path) == d[start[1], start[0]]
        env.reset(start=start)
        for a in path:
            r = env.step(a)
            assert not r.collision
        assert r.terminated


def test_unreachable_cells_are_marked():
    # Wall off the bottom-left cell from the rest of the map.
    m = GridMap(walls={(1, 4), (0, 3)})
    d = distances_to_goal(m)
    assert d[4, 0] == -1
    with pytest.raises(ValueError):
        shortest_path(m, (0, 4))


# --- map validation and PNG ----------------------------------------------------
@pytest.mark.parametrize(
    "kwargs",
    [
        {"walls": {(5, 0)}},  # wall on goal
        {"walls": {(6, 0)}},  # out of bounds
        {"goal": (9, 9)},
    ],
)
def test_bad_maps_rejected(kwargs):
    with pytest.raises(ValueError):
        GridMap(**kwargs)


def test_save_png(tmp_path, env):
    p = save_png(env.render(REFERENCE_START), tmp_path / "f.png", scale=4)
    data = p.read_bytes()
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    assert int.from_bytes(data[16:20], "big") == 48 * 4  # width
    assert int.from_bytes(data[20:24], "big") == 40 * 4  # height
