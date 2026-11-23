"""Level C pieces: fog-of-war rendering, maps that keep their view radius, per-map frame tables, the oracle explorer."""

import numpy as np
import pytest

from config import ROOT, load_config
from environment import GridMap, GridWorld, distances_to_goal
from environment.renderer import COLORS
from multimap.collect import collect
from multimap.explore import run_oracle
from multimap.maps import generate_maps, load_maps, save_maps
from multimap.train import set_grid, set_grid_from_frames

CFG = load_config(ROOT / "configs/fog.yaml")


def cell_color(frame, x, y, px=8):
    return tuple(int(v) for v in frame[:, y * px + 4, x * px + 4])


def test_fog_hides_cells_outside_the_view():
    grid = GridMap(cols=10, rows=10, walls=frozenset({(3, 3), (8, 8)}), goal=(9, 0), view_radius=1)
    f = GridWorld(grid).render((4, 4))
    assert f.shape == (3, 80, 80)
    assert cell_color(f, 4, 4) == COLORS["robot"]
    assert cell_color(f, 3, 3) == COLORS["wall"]                  # a wall inside the 3 x 3 view
    assert cell_color(f, 5, 5) == COLORS["floor"]
    assert cell_color(f, 8, 8) == COLORS["fog"]                   # a wall outside it
    assert cell_color(f, 9, 0) == COLORS["fog"]                   # so is the goal
    full = GridWorld(GridMap(cols=10, rows=10, walls=grid.walls, goal=(9, 0))).render((4, 4))
    assert cell_color(full, 8, 8) == COLORS["wall"]


def test_maps_keep_their_view_radius(tmp_path):
    maps = generate_maps(5, 0, 10, 25, cols=10, rows=10, goal=(9, 0), view_radius=1)
    assert all(m.view_radius == 1 and m.cols == 10 for m in maps)
    loaded, _ = load_maps(save_maps(maps, {"train": [0, 1, 2], "val": [3], "test": [4]}, tmp_path / "m.json"))
    assert [m.view_radius for m in loaded] == [1] * 5
    plain, _ = load_maps(save_maps(generate_maps(2, 0), {"train": [0], "val": [1], "test": []}, tmp_path / "p.json"))
    assert plain[0].view_radius is None


def test_fog_frames_are_kept_per_map():
    # two maps that differ only far from the robot: under fog their frames near the start coincide
    maps = generate_maps(2, 3, 10, 25, cols=10, rows=10, goal=(9, 0), view_radius=1)
    data = collect(maps, episodes_per_map=2, steps=30, seed=0)
    for m in range(2):
        cells = data["frame_pos"][data["frame_map"] == m]
        assert len(cells) == len({tuple(c) for c in cells})       # one frame per visited cell, per map
    ids = data["obs_id"]
    assert (data["frame_map"][ids] == data["map_id"]).all()       # every transition points at its own map's frames
    set_grid_from_frames(data["frames"])
    from multimap import train as T
    assert (T.COLS, T.ROWS) == (10, 10)
    set_grid(6, 5)


@pytest.mark.parametrize("radius", [None, 1])
def test_oracle_explorer(radius):
    grid = generate_maps(3, 7, 10, 25, cols=10, rows=10, goal=(9, 0), view_radius=radius)[1]
    env = GridWorld(grid, terminate_on_goal=True)
    cfg = {"planning": {"max_actions": 300, "max_visits": 10 ** 6}}
    d = distances_to_goal(grid)
    for start in grid.start_cells()[::17]:
        e = run_oracle(env, start, cfg)
        assert e["success"] and e["collisions"] == 0               # it always sees its neighbours
        assert e["steps"] >= e["optimal"] == d[start[1], start[0]]
        if radius is None:
            assert e["steps"] == e["optimal"]                      # full view: shortest path
