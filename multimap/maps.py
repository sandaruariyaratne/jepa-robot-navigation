"""Random layouts for the multi-map experiment (build plan step 12: many layouts, held-out layouts).

Every map is 6 x 5 with the goal fixed at (5, 0) and 3-7 walls placed at
random, such that every free cell can reach the goal. Layouts are distinct and
never equal to the v1 reference map. Maps are split by map (70 / 15 / 15), so
test layouts are never seen in training.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from environment import DEFAULT_GOAL, DEFAULT_WALLS, GridMap, distances_to_goal

SPLITS = ("train", "val", "test")


def is_valid(grid_map: GridMap) -> bool:
    """Every free cell can reach the goal (and there is at least one start)."""
    return len(grid_map.start_cells()) > 0 and (distances_to_goal(grid_map) >= 0).sum() == len(grid_map.free_cells())


def generate_maps(n: int, seed: int, min_walls: int = 3, max_walls: int = 7, cols: int = 6, rows: int = 5,
                  goal: tuple[int, int] = DEFAULT_GOAL, max_tries: int = 100_000,
                  exclude=()) -> list[GridMap]:
    """`exclude`: wall sets that must not be generated (e.g. the layouts a model was trained / tested on)."""
    rng = np.random.default_rng(seed)
    cells = [(x, y) for y in range(rows) for x in range(cols) if (x, y) != tuple(goal)]
    seen = {frozenset(DEFAULT_WALLS), *map(frozenset, exclude)}  # never the v1 reference layout
    maps: list[GridMap] = []
    for _ in range(max_tries):
        if len(maps) == n:
            return maps
        k = int(rng.integers(min_walls, max_walls + 1))
        walls = frozenset(cells[i] for i in rng.choice(len(cells), size=k, replace=False))
        if walls in seen:
            continue
        m = GridMap(cols=cols, rows=rows, walls=walls, goal=tuple(goal))
        if is_valid(m):
            seen.add(walls)
            maps.append(m)
    raise RuntimeError(f"only found {len(maps)} valid distinct maps in {max_tries} tries")


def split_maps(n: int, fractions, seed: int) -> dict[str, list[int]]:
    order = np.random.default_rng([seed, 7]).permutation(n)
    n_train, n_val = round(fractions[0] * n), round(fractions[1] * n)
    parts = {"train": order[:n_train], "val": order[n_train:n_train + n_val], "test": order[n_train + n_val:]}
    return {k: sorted(int(i) for i in v) for k, v in parts.items()}


def save_maps(maps: list[GridMap], splits: dict, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "maps": [{"walls": sorted(list(w) for w in m.walls), "goal": list(m.goal), "cols": m.cols, "rows": m.rows}
                 for m in maps],
        **splits,
    }, indent=1) + "\n")
    return path


def load_maps(path: str | Path) -> tuple[list[GridMap], dict[str, list[int]]]:
    raw = json.loads(Path(path).read_text())
    maps = [GridMap(cols=m["cols"], rows=m["rows"], walls=frozenset(tuple(w) for w in m["walls"]),
                    goal=tuple(m["goal"])) for m in raw["maps"]]
    return maps, {k: raw[k] for k in SPLITS}


def ascii_map(m: GridMap) -> str:
    return "\n".join(" ".join("G" if (x, y) == m.goal else "#" if (x, y) in m.walls else "."
                              for x in range(m.cols)) for y in range(m.rows))
