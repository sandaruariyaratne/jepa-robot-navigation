"""Shared scoring helpers: split results into normal moves / collisions / held-out pairs."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import numpy as np

from data import pair_mask

CATEGORIES = ("normal moves", "collisions", "held-out moves", "held-out collisions", "held-out (all)")


def category_masks(pos: np.ndarray, action: np.ndarray, collision: np.ndarray,
                   heldout: Iterable[Sequence[int]]) -> dict[str, np.ndarray]:
    held = pair_mask(pos, action, heldout)
    coll = np.asarray(collision, dtype=bool)
    return {
        "normal moves": ~held & ~coll,
        "collisions": ~held & coll,
        "held-out moves": held & ~coll,
        "held-out collisions": held & coll,
        "held-out (all)": held,
    }


def score(correct: np.ndarray, masks: dict[str, np.ndarray]) -> dict[str, dict]:
    """{category: {correct, total, accuracy}} (accuracy None when a category is empty)."""
    out = {}
    for name, m in masks.items():
        n, c = int(m.sum()), int(np.asarray(correct)[m].sum())
        out[name] = {"correct": c, "total": n, "accuracy": c / n if n else None}
    return out


def unique_pairs(data: dict) -> dict[str, np.ndarray]:
    """One record per (pos, action) pair seen in the data, with its observed outcome (sorted by x, y, action)."""
    keys = np.concatenate([data["pos"], data["action"][:, None]], axis=1)
    _, first = np.unique(keys, axis=0, return_index=True)
    return {k: data[k][first] for k in ("pos", "action", "next_pos", "collision")}


def fmt_score(s: dict, width: int = 15) -> str:
    if not s["total"]:
        return f"{'-':>{width}}"
    return f"{s['correct']:>5}/{s['total']:<5} {s['accuracy']:6.1%}"
