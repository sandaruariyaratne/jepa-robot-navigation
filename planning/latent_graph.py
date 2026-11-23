"""The imagined graph and imagined steps-to-goal D(c) (build plan step 7).

    python -m planning.latent_graph

Nodes are the 25 codebook entries. For every (entry, action) the predictor
imagines the next latent; it is snapped to the nearest entry, and becomes a
self-loop if the snap is unknown (farther than 3x the median one-step error).
Breadth-first search backwards from the goal entry then gives D(c), the
imagined number of steps from each entry to the goal.

Building the graph and D(c) uses only the world model and the goal image. The
simulator's true transitions and BFS distances appear only in `evaluate`.
"""

from __future__ import annotations

import argparse
import json
from collections import deque
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch

from .imagination import WorldModel

UNREACHABLE = -1


@dataclass(frozen=True)
class LatentGraph:
    next: np.ndarray       # [C, A] successor entry; self-loop where the move is unknown
    predicted: np.ndarray  # [C, A] nearest entry before the unknown rule
    known: np.ndarray      # [C, A] bool
    distance: np.ndarray   # [C, A] snap distance

    @property
    def n_entries(self) -> int:
        return self.next.shape[0]


@torch.no_grad()
def build_graph(world: WorldModel) -> LatentGraph:
    c, a = world.n_entries, world.n_actions
    z = world.codebook.repeat_interleave(a, dim=0)  # entry 0 x all actions, entry 1 x ..., [C*A, D]
    acts = torch.arange(a).repeat(c)
    s = world.snap(world.step(z, acts))
    predicted = s.index.view(c, a).numpy()
    known = s.known.view(c, a).numpy()
    nxt = np.where(known, predicted, np.arange(c)[:, None])
    return LatentGraph(nxt, predicted, known, s.distance.view(c, a).numpy())


def steps_to_goal(graph: LatentGraph, goal: int) -> np.ndarray:
    """BFS backwards from the goal entry. D[c] = imagined steps to goal, UNREACHABLE (-1) if none."""
    preds: list[set[int]] = [set() for _ in range(graph.n_entries)]
    for u in range(graph.n_entries):
        for v in graph.next[u]:
            if v != u:
                preds[int(v)].add(u)
    dist = np.full(graph.n_entries, UNREACHABLE, dtype=np.int64)
    dist[goal] = 0
    queue = deque([goal])
    while queue:
        v = queue.popleft()
        for u in sorted(preds[v]):
            if dist[u] == UNREACHABLE:
                dist[u] = dist[v] + 1
                queue.append(u)
    return dist


def goal_entry(world: WorldModel, goal_frame: np.ndarray) -> tuple[int, bool]:
    """Codebook entry of the goal image, and whether that snap is known."""
    s = world.snap(world.encode(goal_frame))
    return int(s.index), bool(s.known)


# --- evaluation against the simulator (oracle) ---------------------------------------
def evaluate(graph: LatentGraph, d_imagined: np.ndarray, heldout_pairs) -> dict:
    """Compare edges with the true transitions and D(c) with the true BFS distances."""
    from environment import ACTIONS, GridMap, distances_to_goal
    from evaluation.probes import CellIndex

    grid, cells = GridMap(), CellIndex()
    held = {tuple(p) for p in heldout_pairs}
    edges = []
    for i, (x, y) in enumerate(cells.cells):
        for a in ACTIONS:
            true_pos, collision = grid.transition((int(x), int(y)), a)
            true_idx = int(cells.ids(np.array(true_pos)))
            edges.append({
                "pair": [int(x), int(y), a], "heldout": (int(x), int(y), a) in held, "collision": collision,
                "true": true_idx, "predicted": int(graph.predicted[i, a]), "next": int(graph.next[i, a]),
                "known": bool(graph.known[i, a]), "distance": float(graph.distance[i, a]),
            })

    def tally(sel):
        sel = list(sel)
        return {
            "total": len(sel),
            "correct": sum(e["next"] == e["true"] for e in sel),
            "unknown": sum(not e["known"] for e in sel),
            "wrong_known": sum(e["known"] and e["next"] != e["true"] for e in sel),
            "unknown_but_right": sum(not e["known"] and e["predicted"] == e["true"] for e in sel),
        }

    d_true_grid = distances_to_goal(grid)
    d_true = np.array([d_true_grid[y, x] for x, y in cells.cells])
    both = (d_imagined >= 0) & (d_true >= 0)
    return {
        "edges": {
            "all": tally(edges),
            "trained": tally(e for e in edges if not e["heldout"]),
            "held-out": tally(e for e in edges if e["heldout"]),
            "trained moves": tally(e for e in edges if not e["heldout"] and not e["collision"]),
            "trained collisions": tally(e for e in edges if not e["heldout"] and e["collision"]),
        },
        "edge_details": [e for e in edges if e["heldout"] or e["next"] != e["true"] or not e["known"]],
        "d_imagined": d_imagined.tolist(),
        "d_true": d_true.tolist(),
        "d_exact": int((d_imagined == d_true).sum()),
        "d_over": int((both & (d_imagined > d_true)).sum()),
        "d_under": int((both & (d_imagined < d_true)).sum()),
        "d_unreachable": int((d_imagined < 0).sum()),
        "d_mean_abs_error": float(np.abs(d_imagined[both] - d_true[both]).mean()) if both.any() else None,
    }


def print_report(world: WorldModel, goal: int, goal_known: bool, ev: dict) -> None:
    from environment import ACTION_NAMES, GridMap
    from evaluation.probes import CellIndex

    grid, cells = GridMap(), CellIndex()
    print(f"Unknown threshold: {world.unknown_factor:g} x median one-step error "
          f"{world.median_one_step_error:.4f} = {world.unknown_threshold:.4f}")
    gx, gy = cells.cells[goal]
    print(f"Goal image snaps to entry {goal} = cell ({gx},{gy}) ({'known' if goal_known else 'UNKNOWN'})")

    print(f"\n{'Imagined edges':<22}{'correct':>9}{'unknown':>9}{'wrong (known)':>15}")
    for name, t in ev["edges"].items():
        print(f"  {name:<20}{t['correct']:>4}/{t['total']:<4}{t['unknown']:>9}{t['wrong_known']:>15}")
    print("\nHeld-out, unknown or wrong edges:")
    for e in ev["edge_details"]:
        x, y, a = e["pair"]
        tx, ty = cells.cells[e["true"]]
        px, py = cells.cells[e["predicted"]]
        status = "ok     " if e["next"] == e["true"] else ("unknown" if not e["known"] else "WRONG  ")
        print(f"  {status} {'held-out' if e['heldout'] else 'trained '} ({x},{y}) {ACTION_NAMES[a]:<5} "
              f"true ({tx},{ty})  nearest ({px},{py}) at {e['distance']:.3f}"
              + ("  -> self-loop" if not e["known"] else ""))

    def grid_text(values):
        rows = []
        for y in range(grid.rows):
            row = []
            for x in range(grid.cols):
                if (x, y) in grid.walls:
                    row.append(" #")
                else:
                    v = values[int(cells.ids(np.array([x, y])))]
                    row.append(" ?" if v < 0 else f"{v:2d}")
            rows.append(" ".join(row))
        return rows

    print(f"\n{'Imagined D(c)':<22}{'True distance':<22}Difference (imagined - true)")
    diff = [i - t if i >= 0 else -99 for i, t in zip(ev["d_imagined"], ev["d_true"])]
    for a, b, c in zip(grid_text(ev["d_imagined"]), grid_text(ev["d_true"]),
                       [r.replace("-99", "  ?") for r in grid_text(diff)]):
        print(f"{a:<22}{b:<22}{c}")
    print(f"\nD(c) exact for {ev['d_exact']}/25 cells; over {ev['d_over']}, under {ev['d_under']}, "
          f"unreachable {ev['d_unreachable']}; mean |error| {ev['d_mean_abs_error']:.2f}")


def main() -> None:
    from config import load_config, resolve
    from data import load_splits
    from environment import GridWorld

    parser = argparse.ArgumentParser(description="Build the imagined graph and D(c).")
    parser.add_argument("--config", type=Path, default=None, help="config file (default: configs/single_map.yaml)")
    args = parser.parse_args()
    cfg = load_config(args.config)
    world = WorldModel.from_checkpoints(resolve(cfg["encoder"]["checkpoint"]),
                                        resolve(cfg["predictor"]["checkpoint"]),
                                        cfg["imagination"]["unknown_factor"])
    goal_frame = GridWorld().goal_obs()  # the goal image the agent is given

    graph = build_graph(world)
    goal, goal_known = goal_entry(world, goal_frame)
    d_imagined = steps_to_goal(graph, goal)

    ev = evaluate(graph, d_imagined, load_splits(resolve(cfg["data"]["splits_path"]))["heldout_pairs"])
    print_report(world, goal, goal_known, ev)
    out = resolve(cfg["imagination"]["metrics"])
    metrics = {"unknown_threshold": world.unknown_threshold, "goal_entry": goal,
               "next": graph.next.tolist(), "known": graph.known.tolist(), **ev}
    out.write_text(json.dumps(metrics, indent=1) + "\n")

    from .graph_view import render_all
    pngs = render_all(metrics, load_splits(resolve(cfg["data"]["splits_path"]))["heldout_pairs"], out.parent)
    print(f"\nSaved {out}" + "".join(f"\n      {p}" for p in pngs))


if __name__ == "__main__":
    main()
