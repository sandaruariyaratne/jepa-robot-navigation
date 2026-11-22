"""Evaluate the multi-map model: `python -m multimap.evaluate --config config_multimap.yaml`.

Same questions as v1, asked separately of the training maps (fit), validation
maps and the 15 unseen test maps (generalization):

  * one-step snap accuracy for normal moves, border bumps and interior-wall bumps
    (wall bumps are the part that changes from map to map)
  * imagined rollouts at 1..10 steps
  * the imagined graph of each map (one WorldModel per map, with that map's
    codebook): edges correct / unknown / wrong-but-trusted, and D(c) vs the truth
  * navigation and the diagnostic ladder (Oracle, D1, D2, D3, Full = P2 with the
    learned model, Random) from every start cell of each map
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch

from config import load_config, resolve
from environment import ACTIONS, GridWorld, distances_to_goal
from evaluation.ladder import build_rungs, diagnose
from evaluation.navigation_test import RandomPolicy, report
from evaluation.probes import CellIndex
from models.encoder import load_encoder
from models.predictor import load_predictor
from planning.imagination import WorldModel
from planning.latent_graph import build_graph, goal_entry, steps_to_goal
from planning.mpc import run_episode
from planning.true_model import TrueModel

from .collect import load
from .maps import load_maps
from .train import codebooks, latent_table, rollout_scores, windows

RUNGS = ("Oracle", "D1", "D2", "D3", "Full", "Random")


# --- prediction ---------------------------------------------------------------------------
@torch.no_grad()
def prediction_metrics(predictor, table, data, map_ids, cb, mask, horizon: int) -> dict:
    t1 = windows(data, map_ids, 1)
    acc, _, cell = rollout_scores(predictor, table, t1, cb, mask)
    correct = (cell[:, 0] == t1["next_cell"][:, 0]).numpy()
    coll, wall = t1["collision"][:, 0].numpy(), t1["wall_bump"][:, 0].numpy()
    cats = {"normal moves": ~coll, "border bumps": coll & ~wall, "wall bumps": wall, "all": np.ones_like(coll)}
    pred = predictor(table[t1["obs"]], t1["action"][:, 0])
    target = table[t1["next"][:, 0]]
    th = windows(data, map_ids, horizon)
    acc_h, _, _ = rollout_scores(predictor, table, th, cb, mask)
    return {
        "one_step": {k: {"correct": int(correct[m].sum()), "total": int(m.sum())} for k, m in cats.items()},
        "mse_model": float(((pred - target) ** 2).mean()),
        "mse_persistence": float(((table[t1["obs"]] - target) ** 2).mean()),
        "rollout": acc_h.tolist(), "rollout_windows": int(len(th["obs"])),
    }


# --- per-map world models -------------------------------------------------------------------
def world_for_map(m: int, grid, encoder, predictor, table, data, median_err, factor) -> tuple[WorldModel, np.ndarray]:
    """WorldModel whose codebook is this map's frames in CellIndex(map) order; also the goal frame."""
    cells = CellIndex(grid)
    frames_of = {tuple(p): f for f, (mm, p) in enumerate(zip(data["frame_map"], data["frame_pos"])) if mm == m}
    order = [frames_of[(int(x), int(y))] for x, y in cells.cells]
    world = WorldModel(encoder, predictor, table[torch.as_tensor(order)], median_err, factor)
    return world, data["frames"][frames_of[tuple(grid.goal)]]


def graph_metrics(world: WorldModel, grid, goal_frame) -> dict:
    cells = CellIndex(grid)
    true = TrueModel(grid)
    g = build_graph(world)
    goal, _ = goal_entry(world, goal_frame)
    d = steps_to_goal(g, goal)
    dt = distances_to_goal(grid)
    d_true = np.array([dt[y, x] for x, y in cells.cells])
    tally = {k: {"total": 0, "correct": 0, "unknown": 0, "wrong_known": 0}
             for k in ("normal moves", "border bumps", "wall bumps")}
    for i, (x, y) in enumerate(cells.cells):
        for a in ACTIONS:
            t = int(true.next[i, a])
            if t != i:
                kind = "normal moves"
            else:
                dx, dy = [(0, -1), (0, 1), (-1, 0), (1, 0)][a]
                kind = "wall bumps" if grid.in_bounds((int(x) + dx, int(y) + dy)) else "border bumps"
            s = tally[kind]
            s["total"] += 1
            s["correct"] += int(g.next[i, a] == t)
            s["unknown"] += int(not g.known[i, a])
            s["wrong_known"] += int(g.known[i, a] and g.next[i, a] != t)
    return {"edges": tally, "d_exact": int((d == d_true).sum()), "d_cells": len(d),
            "d_unreachable": int((d < 0).sum()), "d_under": int(((d >= 0) & (d < d_true)).sum()),
            "goal_ok": bool(goal == int(cells.ids(np.array(grid.goal))))}


def navigate(world, grid, goal_frame, cfg, seeds) -> dict[str, list]:
    p = cfg["planning"]
    rungs = {r.label: r for r in build_rungs(TrueModel(grid), world, goal_frame, p["p2"]["horizon"])}
    env = GridWorld(grid, terminate_on_goal=True)
    out = {}
    for label in RUNGS:
        r = rungs[label]
        planner = RandomPolicy() if label == "Random" else r.planner
        out[label] = [run_episode(env, r.model, planner, r.mctx, start,
                                  int(np.random.SeedSequence([seed, i]).generate_state(1)[0]),
                                  p["max_actions"], p["max_visits"], p["revisit_penalty"])
                      for seed in seeds for i, start in enumerate(grid.start_cells())]
    return out


def _sum_edges(per_map: list[dict]) -> dict:
    out = {}
    for k in ("normal moves", "border bumps", "wall bumps"):
        out[k] = {f: sum(m["edges"][k][f] for m in per_map) for f in ("total", "correct", "unknown", "wrong_known")}
    out["all"] = {f: sum(out[k][f] for k in ("normal moves", "border bumps", "wall bumps"))
                  for f in ("total", "correct", "unknown", "wrong_known")}
    return out


# --- report -----------------------------------------------------------------------------------
def _pct(c, t):
    return f"{c}/{t} ({c / t:.0%})" if t else "-"


def render_markdown(res: dict, cfg: dict) -> str:
    mm = cfg["multimap"]
    L = [f"# Multi-map results ({mm.get('label', 'v1 model')}, held-out layouts)\n",
         f"{mm['n_maps']} random layouts (3-7 walls, goal fixed at (5,0)), split by map: "
         f"train {res['n_maps']['train']} / val {res['n_maps']['val']} / test {res['n_maps']['test']}. "
         "Training maps measure fit; test maps were never seen in training and measure generalization. "
         f"Navigation uses {res['nav_maps']['train']} of the training maps and all validation / test maps, every start "
         f"cell, seeds {mm['evaluation']['seeds']}.\n",
         "## One-step prediction (snap to the map's own codebook)\n",
         "| | train maps (fit) | val maps | **test maps** |", "|---|---|---|---|"]
    for k in ("normal moves", "border bumps", "wall bumps", "all"):
        L.append(f"| {k} | " + " | ".join(_pct(res["prediction"][s]["one_step"][k]["correct"],
                                                 res["prediction"][s]["one_step"][k]["total"]) for s in ("train", "val", "test")) + " |")
    L.append("| latent MSE, model / persistence | " + " | ".join(
        f"{res['prediction'][s]['mse_model']:.4f} / {res['prediction'][s]['mse_persistence']:.4f}"
        for s in ("train", "val", "test")) + " |\n")
    h = len(res["prediction"]["test"]["rollout"])
    L += ["Imagined rollouts, snap accuracy by step:\n",
          "| | " + " | ".join(str(i + 1) for i in range(h)) + " |", "|---|" + "---|" * h]
    for s in ("train", "val", "test"):
        L.append(f"| {s} maps | " + " | ".join(f"{v:.0%}" for v in res["prediction"][s]["rollout"]) + " |")
    L += ["", "## Imagined graph, per map\n",
          "| edges | train maps | val maps | **test maps** |", "|---|---|---|---|"]
    for k in ("normal moves", "border bumps", "wall bumps", "all"):
        L.append(f"| {k}: correct | " + " | ".join(_pct(res["graph"][s]["edges"][k]["correct"],
                                                         res["graph"][s]["edges"][k]["total"]) for s in ("train", "val", "test")) + " |")
    for f, label in (("unknown", "unknown -> self-loop"), ("wrong_known", "wrong but trusted")):
        L.append(f"| all: {label} | " + " | ".join(_pct(res["graph"][s]["edges"]["all"][f], res["graph"][s]["edges"]["all"]["total"])
                                                   for s in ("train", "val", "test")) + " |")
    L.append("| D(c) exact (cells) | " + " | ".join(_pct(res["graph"][s]["d_exact"], res["graph"][s]["d_cells"])
                                                    for s in ("train", "val", "test")) + " |")
    L.append("| D(c) under-estimates (fake shortcuts) | " + " | ".join(str(res["graph"][s]["d_under"]) for s in ("train", "val", "test")) + " |")
    L.append("| maps with D(c) exact everywhere | " + " | ".join(_pct(res["graph"][s]["maps_exact"], res["graph"][s]["maps"])
                                                               for s in ("train", "val", "test")) + " |\n")
    L += ["## Navigation and ladder (P2 on D1-Full)\n",
          "| | dynamics | cost | train maps: success / optimal | val maps | **test maps** |", "|---|---|---|---|---|---|"]
    desc = {"Oracle": ("true", "A*"), "D1": ("true", "true"), "D2": ("true", "learned"), "D3": ("learned", "true"),
            "Full": ("learned", "learned"), "Random": ("-", "-")}
    for r in RUNGS:
        cells = []
        for s in ("train", "val", "test"):
            n = res["navigation"][s][r]
            cells.append(f"{n['success'] / n['episodes']:.0%} / {n['optimal'] / n['episodes']:.0%}")
        L.append(f"| {r} | {desc[r][0]} | {desc[r][1]} | " + " | ".join(cells) + " |")
    L += ["", "Reading (test maps):\n"] + [f"- {line}" for line in res["diagnosis_test"]]
    return "\n".join(L) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the multi-map model on train / val / test maps.")
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args()
    cfg = load_config(args.config)
    mm = cfg["multimap"]
    maps, splits = load_maps(resolve(mm["maps_path"]))
    data = load(resolve(mm["data_path"]))
    encoder, _ = load_encoder(resolve(mm["encoder"]["checkpoint"]))
    predictor, pck = load_predictor(resolve(mm["predictor"]["checkpoint"]))
    table = latent_table(encoder, data)
    cb, mask = codebooks(table, data, len(maps))
    seeds = mm["evaluation"]["seeds"]
    factor = cfg["imagination"]["unknown_factor"]
    nav_maps = {"train": splits["train"][:15], "val": splits["val"], "test": splits["test"]}

    res = {"n_maps": {k: len(v) for k, v in splits.items()}, "nav_maps": {k: len(v) for k, v in nav_maps.items()},
           "median_one_step_error": pck["median_one_step_error"], "prediction": {}, "graph": {}, "navigation": {},
           "per_test_map": []}
    for s in ("train", "val", "test"):
        print(f"{s} maps ...", flush=True)
        res["prediction"][s] = prediction_metrics(predictor, table, data, splits[s], cb, mask,
                                                  mm["predictor"]["eval_horizon"])
        per_map, episodes = [], {r: [] for r in RUNGS}
        for m in splits[s]:
            world, goal_frame = world_for_map(m, maps[m], encoder, predictor, table, data,
                                              pck["median_one_step_error"], factor)
            gm = graph_metrics(world, maps[m], goal_frame)
            per_map.append(gm)
            if m in nav_maps[s]:
                eps = navigate(world, maps[m], goal_frame, cfg, seeds)
                for r in RUNGS:
                    episodes[r] += eps[r]
                if s == "test":
                    e = _sum_edges([gm])["all"]
                    full = eps["Full"]
                    res["per_test_map"].append({"map": m, "walls": len(maps[m].walls),
                                                "edges_correct": e["correct"], "edges": e["total"],
                                                "d_exact": gm["d_exact"], "d_cells": gm["d_cells"],
                                                "full_optimal": sum(x.success and x.steps == x.optimal for x in full),
                                                "full_success": sum(x.success for x in full), "episodes": len(full)})
        res["graph"][s] = {"edges": _sum_edges(per_map), "d_exact": sum(g["d_exact"] for g in per_map),
                           "d_cells": sum(g["d_cells"] for g in per_map), "d_under": sum(g["d_under"] for g in per_map),
                           "maps_exact": sum(g["d_exact"] == g["d_cells"] for g in per_map), "maps": len(per_map)}
        res["navigation"][s] = {r: report(v) for r, v in episodes.items()}
    res["diagnosis_test"] = diagnose(res["navigation"]["test"])

    out = resolve(mm["evaluation"]["results_dir"])
    out.mkdir(parents=True, exist_ok=True)
    md = render_markdown(res, cfg)
    (out / "results.md").write_text(md)
    (out / "results.json").write_text(json.dumps(res, indent=1, default=str) + "\n")
    print("\n" + md)
    print(f"Wrote {out / 'results.md'} and results.json")


if __name__ == "__main__":
    main()
