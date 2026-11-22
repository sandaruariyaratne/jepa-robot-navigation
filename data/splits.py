"""Episode splits and held-out (state, action) pairs (build plan step 2).

Two kinds of "unseen" data, kept separate in the report:
  * fit: train / val / test split by episode (80/10/10). On a fixed map every
    (state, action) pair shows up in every split, so this measures fit, not
    generalization.
  * generalization: a few (state, action) pairs are held out entirely from
    predictor training. Accuracy on them is the only evidence the model
    inferred the rules instead of memorising transitions.

The true map is used here only to label pairs as collisions when choosing the
held-out set. Models never see it.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from pathlib import Path

import numpy as np

from environment import ACTIONS, GridMap

Pair = tuple[int, int, int]  # (x, y, action)


def all_pairs(grid_map: GridMap) -> list[Pair]:
    """Every (free cell, action) pair, row-major then by action id: 25 x 4 = 100 on the reference map."""
    return [(x, y, a) for (x, y) in grid_map.free_cells() for a in ACTIONS]


def pair_mask(pos: np.ndarray, action: np.ndarray, pairs: Iterable[Sequence[int]]) -> np.ndarray:
    """Boolean mask of transitions whose (pos, action) is in `pairs`."""
    wanted = {(int(x), int(y), int(a)) for x, y, a in pairs}
    pos = np.asarray(pos)
    action = np.asarray(action)
    if not wanted:
        return np.zeros(len(action), dtype=bool)
    return np.fromiter(
        ((int(p[0]), int(p[1]), int(a)) in wanted for p, a in zip(pos, action)),
        dtype=bool,
        count=len(action),
    )


def pair_counts(data: dict[str, np.ndarray], grid_map: GridMap) -> dict[Pair, int]:
    """How often each (state, action) pair occurs. Pairs never visited count 0."""
    counts = {p: 0 for p in all_pairs(grid_map)}
    for (x, y), a in zip(data["pos"].tolist(), data["action"].tolist()):
        counts[(x, y, a)] += 1
    return counts


def is_collision_pair(grid_map: GridMap, pair: Sequence[int]) -> bool:
    x, y, a = pair
    return grid_map.transition((x, y), a)[1]


def choose_heldout_pairs(
    grid_map: GridMap, n: int, min_collisions: int, rng: np.random.Generator
) -> list[Pair]:
    """Pick n pairs, stratified by type, at most one per cell.

    Collisions get their natural share of all pairs (34 of 100 on the reference
    map -> 3 of 10), but never fewer than min_collisions; the rest are normal
    moves. One per cell means every cell keeps three trained actions, so a
    held-out pair always tests an unseen action from a state the model knows.
    """
    pairs = all_pairs(grid_map)
    collide = [p for p in pairs if is_collision_pair(grid_map, p)]
    moves = [p for p in pairs if not is_collision_pair(grid_map, p)]
    if min_collisions > n:
        raise ValueError(f"min_collisions ({min_collisions}) > n ({n})")
    if n > len(grid_map.free_cells()):
        raise ValueError(f"cannot hold out {n} pairs with at most one per cell on {len(grid_map.free_cells())} cells")
    n_collide = max(min_collisions, round(n * len(collide) / len(pairs)))

    chosen: list[Pair] = []
    cells: set[tuple[int, int]] = set()
    for pool, quota in ((collide, n_collide), (moves, n)):
        for idx in rng.permutation(len(pool)):
            if len(chosen) >= quota:
                break
            p = pool[idx]
            if p[:2] not in cells:
                chosen.append(p)
                cells.add(p[:2])
    if len(chosen) < n or sum(is_collision_pair(grid_map, p) for p in chosen) < min_collisions:
        raise ValueError("could not choose enough held-out pairs on this map")
    return sorted(chosen)


def split_episodes(n_episodes: int, fractions: Sequence[float], rng: np.random.Generator) -> dict[str, list[int]]:
    if len(fractions) != 3 or abs(sum(fractions) - 1.0) > 1e-9:
        raise ValueError(f"fractions must be three numbers summing to 1, got {fractions}")
    order = rng.permutation(n_episodes)
    n_train = round(fractions[0] * n_episodes)
    n_val = round(fractions[1] * n_episodes)
    parts = {"train": order[:n_train], "val": order[n_train:n_train + n_val], "test": order[n_train + n_val:]}
    return {k: sorted(int(e) for e in v) for k, v in parts.items()}


def make_splits(
    n_episodes: int,
    fractions: Sequence[float],
    n_heldout: int,
    min_collisions: int,
    seed: int,
    grid_map: GridMap,
) -> dict:
    # Independent streams so changing one setting doesn't reshuffle the other.
    rng_eps, rng_pairs = (np.random.default_rng(s) for s in np.random.SeedSequence(seed).spawn(2))
    splits = split_episodes(n_episodes, fractions, rng_eps)
    held = choose_heldout_pairs(grid_map, n_heldout, min_collisions, rng_pairs)
    return {
        "seed": seed,
        **splits,
        "heldout_pairs": [list(p) for p in held],
        "heldout_collision": [is_collision_pair(grid_map, p) for p in held],
    }


def save_splits(splits: dict, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(splits, indent=1) + "\n")
    return path


def load_splits(path: str | Path) -> dict:
    splits = json.loads(Path(path).read_text())
    splits["heldout_pairs"] = [tuple(p) for p in splits["heldout_pairs"]]
    return splits
