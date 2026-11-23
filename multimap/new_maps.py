"""Stress test on 500 brand-new layouts, no retraining:

    python -m multimap.new_maps --config config_multimap_jepa.yaml     (joint JEPA)
    python -m multimap.new_maps --config config_multimap.yaml          (v1, for comparison)

The layouts come from a different seed, with all 100 experiment layouts
(train / val / test) and the v1 reference map excluded, so the model has never
seen any of them. The trained encoder and predictor are only loaded.

  rollout accuracy      random-action episodes on each map; snap accuracy after 1..10 imagined steps
  collision accuracy    does the model predict "the robot stays put" exactly when the move is blocked?
                        on the episode data (stay vs move), and over every (cell, action) pair of every
                        map via the imagined graph (border bumps, interior-wall bumps)
  navigation            P2 + MPC from every free start cell of every map (and the diagnostic ladder):
                        success, and shortest-path accuracy = episodes that took exactly the BFS length

Each map's codebook is its ~25 frames (the robot on each free cell), encoded by
the frozen encoder, as in the multi-map evaluation.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch

from config import load_config, resolve
from data.collect_data import save_npz
from environment import GridWorld, distances_to_goal
from evaluation.ladder import diagnose
from evaluation.navigation_test import report
from models.encoder import load_encoder
from models.predictor import load_predictor

from .collect import collect, coverage, grid_kwargs, load
from .evaluate import RUNGS, _sum_edges, graph_metrics, navigate, prediction_metrics, world_for_map
from .maps import generate_maps, load_maps, save_maps
from .train import cell_ids, codebooks, latent_table, rollout_scores, windows


def _pct(c, t):
    """One decimal: on ~24,000 episodes, 99.86% must not read as 100%."""
    return f"{c}/{t} ({100 * c / t:.1f}%)" if t else "-"


def complete_frames(data: dict, maps) -> int:
    """Add a rendered frame for any free cell the random episodes never visited, so every codebook is full."""
    have = {(int(m), int(x), int(y)) for m, (x, y) in zip(data["frame_map"], data["frame_pos"])}
    extra, emap, epos = [], [], []
    for m, grid in enumerate(maps):
        r = GridWorld(grid).renderer
        for c in grid.free_cells():
            if (m, *c) not in have:
                extra.append(np.asarray(r.render(c), dtype=data["frames"].dtype))
                emap.append(m)
                epos.append(c)
    if extra:
        data["frames"] = np.concatenate([data["frames"], np.stack(extra)])
        data["frame_map"] = np.concatenate([data["frame_map"], np.array(emap, dtype=np.int64)])
        data["frame_pos"] = np.concatenate([data["frame_pos"], np.array(epos, dtype=np.int64)])
    return len(extra)


def mean_distance(grid) -> float:
    """Average shortest-path length to the goal over the start cells: how winding the layout is."""
    d = distances_to_goal(grid)
    return float(d[d > 0].mean())


def new_maps_and_data(cfg: dict, key: str = "new_maps"):
    """Generate (or reload) one test set of layouts and their random-action episodes.

    `multimap.<key>` may set its own min_walls / max_walls (default: the experiment's) and
    `select: longest_paths` with `pool`: draw `pool` valid layouts, keep the `n_maps` with the
    longest average path to the goal (maze-like corridors)."""
    mm, nm = cfg["multimap"], cfg["multimap"][key]
    maps_path, data_path = resolve(nm["maps_path"]), resolve(nm["data_path"])
    old, _ = load_maps(resolve(mm["maps_path"]))
    if maps_path.exists() and data_path.exists():
        maps, _ = load_maps(maps_path)
        data = load(data_path)
    else:
        lo, hi = nm.get("min_walls", mm["min_walls"]), nm.get("max_walls", mm["max_walls"])
        exclude = [m.walls for m in old]
        for other in nm.get("exclude_sets", []):            # e.g. keep validation layouts out of every test set
            exclude += [m.walls for m in load_maps(resolve(mm[other]["maps_path"]))[0]]
        if nm.get("select") == "longest_paths":
            pool = generate_maps(nm["pool"], nm["seed"], lo, hi, exclude=exclude, max_tries=50 * nm["pool"],
                                 **grid_kwargs(mm))
            order = np.argsort([-mean_distance(m) for m in pool], kind="stable")
            maps = [pool[i] for i in order[: nm["n_maps"]]]
        else:
            maps = generate_maps(nm["n_maps"], nm["seed"], lo, hi, exclude=exclude,
                                 max_tries=50 * nm["n_maps"] + 100_000, **grid_kwargs(mm))
        save_maps(maps, {"train": [], "val": [], "test": list(range(len(maps)))}, maps_path)
        maps, _ = load_maps(maps_path)
        data = collect(maps, nm["episodes_per_map"], nm["steps_per_episode"], nm["seed"], cfg["data"]["cell_px"])
        save_npz(data, data_path)
        from .train import set_grid_from_frames
        set_grid_from_frames(data["frames"], cfg["data"]["cell_px"])
    assert not {m.walls for m in maps} & {m.walls for m in old}, "a new map repeats an experiment layout"
    for other in nm.get("exclude_sets", []):
        assert not {m.walls for m in maps} & {m.walls for m in load_maps(resolve(mm[other]["maps_path"]))[0]}, other
    return maps, data, old


@torch.no_grad()
def collision_metrics(predictor, table, data, map_ids, cb, mask) -> dict:
    """Stay-vs-move on the episode data: predicted stay = the imagined next state snaps to the current cell."""
    t = windows(data, map_ids, 1)
    _, _, cell = rollout_scores(predictor, table, t, cb, mask)
    here = torch.as_tensor(cell_ids(data["frame_pos"][t["obs"].numpy()]))
    stay = (cell[:, 0] == here).numpy()
    coll, wall = t["collision"][:, 0].numpy(), t["wall_bump"][:, 0].numpy()
    tp, fp = int((stay & coll).sum()), int((stay & ~coll).sum())
    return {"accuracy": float((stay == coll).mean()), "transitions": int(len(stay)),
            "blocked_predicted_blocked": {"correct": tp, "total": int(coll.sum())},
            "wall_bumps_predicted_blocked": {"correct": int((stay & wall).sum()), "total": int(wall.sum())},
            "border_bumps_predicted_blocked": {"correct": int((stay & coll & ~wall).sum()), "total": int((coll & ~wall).sum())},
            "free_moves_predicted_blocked": {"wrong": fp, "total": int((~coll).sum())},
            "precision": tp / (tp + fp) if tp + fp else None}


def chunked_metrics(predictor, table, data, ids, cb, mask, horizon: int, chunk: int = 20) -> dict:
    """prediction_metrics + collision_metrics over `chunk` maps at a time (per-map snapping is [B, 30, D] in memory),
    combined exactly: counts summed, means weighted by their sample counts."""
    preds, colls = [], []
    for i in range(0, len(ids), chunk):
        part = ids[i:i + chunk]
        preds.append(prediction_metrics(predictor, table, data, part, cb, mask, horizon))
        colls.append(collision_metrics(predictor, table, data, part, cb, mask))
    n1 = [c["transitions"] for c in colls]
    nh = [p["rollout_windows"] for p in preds]
    pred = {"one_step": {k: {f: sum(p["one_step"][k][f] for p in preds) for f in ("correct", "total")}
                         for k in preds[0]["one_step"]},
            "mse_model": float(np.average([p["mse_model"] for p in preds], weights=n1)),
            "mse_persistence": float(np.average([p["mse_persistence"] for p in preds], weights=n1)),
            "rollout": np.average([p["rollout"] for p in preds], axis=0, weights=nh).tolist(),
            "rollout_windows": int(sum(nh))}
    coll = {"accuracy": float(np.average([c["accuracy"] for c in colls], weights=n1)), "transitions": int(sum(n1))}
    for k in ("blocked_predicted_blocked", "wall_bumps_predicted_blocked", "border_bumps_predicted_blocked",
              "free_moves_predicted_blocked"):
        coll[k] = {f: sum(c[k][f] for c in colls) for f in colls[0][k]}
    tp, fp = coll["blocked_predicted_blocked"]["correct"], coll["free_moves_predicted_blocked"]["wrong"]
    coll["precision"] = tp / (tp + fp) if tp + fp else None
    return {"prediction": pred, "collision": coll}


def render(res: dict, label: str) -> str:
    n = res["n_maps"]
    L = [f"# {n} {res.get('title', 'new maps')}: {label}, no retraining\n",
         f"{n} layouts never used for training, validation or testing (seed {res['seed']}; all 100 experiment layouts "
         f"and the reference map excluded), {res['walls_min']}-{res['walls_max']} walls, goal (5,0). Navigation starts "
         f"from every free cell of every map ({res['starts']} start cells), seeds {res['nav_seeds']} "
         f"-> {res['navigation']['Full']['episodes']} episodes per rung."
         + (f" Average shortest path to the goal {res['mean_distance']:.1f} steps, longest {res['longest_path']}."
            if "mean_distance" in res else "")
         + (f" Unknown threshold {res['unknown_threshold']['threshold']:.2f} ({res['unknown_threshold']['rule']})."
            if "unknown_threshold" in res else "")
         + (" Planner: P2 with every imagined step snapped to the codebook." if res.get("planner") == "snap" else "") + "\n",
         "## Headline\n", "| metric | result |", "|---|---|"]
    f = res["navigation"]["Full"]
    c = res["collision"]
    g = res["graph"]["edges"]
    L += [f"| navigation success (Full: learned dynamics + learned cost) | {_pct(f['success'], f['episodes'])} |",
          f"| shortest-path accuracy (episodes with exactly the BFS length) | {_pct(f['optimal'], f['episodes'])} |",
          f"| shortest path, among successful episodes | {_pct(f['optimal'], f['success'])} |",
          f"| maps solved optimally from every start | {_pct(res['maps_all_optimal'], n)} |",
          f"| collision accuracy, episode data (stay vs move) | {c['accuracy']:.2%} of {c['transitions']} transitions |",
          f"| collision accuracy, every (cell, action) pair: wall bumps | {_pct(g['wall bumps']['correct'], g['wall bumps']['total'])} |",
          f"| collision accuracy, every (cell, action) pair: border bumps | {_pct(g['border bumps']['correct'], g['border bumps']['total'])} |",
          f"| rollout accuracy at 1 / 5 / 10 steps | " + " / ".join(f"{res['prediction']['rollout'][i]:.1%}" for i in (0, 4, 9)) + " |",
          ""]
    L += ["## Collisions (episode data)\n", "| | correct |", "|---|---|"]
    for k, name in (("blocked_predicted_blocked", "blocked moves predicted as blocked"),
                    ("wall_bumps_predicted_blocked", "  interior-wall bumps"),
                    ("border_bumps_predicted_blocked", "  border bumps")):
        L.append(f"| {name} | {_pct(c[k]['correct'], c[k]['total'])} |")
    fm = c["free_moves_predicted_blocked"]
    L += [f"| free moves wrongly predicted as blocked | {_pct(fm['wrong'], fm['total'])} |",
          f"| precision of \"blocked\" | {c['precision']:.2%} |" if c["precision"] is not None else "", ""]
    p = res["prediction"]
    L += ["## One-step prediction and rollouts (episode data)\n", "| move type | correct |", "|---|---|"]
    for k in ("normal moves", "border bumps", "wall bumps", "all"):
        L.append(f"| {k} | {_pct(p['one_step'][k]['correct'], p['one_step'][k]['total'])} |")
    h = len(p["rollout"])
    L += ["", f"Rollout snap accuracy by imagined step ({p['rollout_windows']} windows):\n",
          "| " + " | ".join(str(i + 1) for i in range(h)) + " |", "|" + "---|" * h,
          "| " + " | ".join(f"{v:.1%}" for v in p["rollout"]) + " |", ""]
    L += ["## Imagined graph (every cell x action of every map)\n", "| edges | correct | unknown -> self-loop | wrong but trusted |",
          "|---|---|---|---|"]
    for k in ("normal moves", "border bumps", "wall bumps", "all"):
        e = g[k]
        L.append(f"| {k} | {_pct(e['correct'], e['total'])} | {_pct(e['unknown'], e['total'])} | {_pct(e['wrong_known'], e['total'])} |")
    gr = res["graph"]
    L += [f"| D(c) exact | {_pct(gr['d_exact'], gr['d_cells'])} cells; {_pct(gr['maps_exact'], n)} maps exact everywhere; "
          f"{gr['d_under']} fake shortcuts | | |", ""]
    L += ["## Navigation and ladder\n", "| rung | dynamics | cost | success | shortest path | collisions / action | loop failures | timeouts |",
          "|---|---|---|---|---|---|---|---|"]
    desc = {"Oracle": ("true", "A*"), "D1": ("true", "true"), "D2": ("true", "learned"), "D3": ("learned", "true"),
            "Full": ("learned", "learned"), "Random": ("-", "-")}
    for r in RUNGS:
        s = res["navigation"][r]
        L.append(f"| {r} | {desc[r][0]} | {desc[r][1]} | {_pct(s['success'], s['episodes'])} | "
                 f"{_pct(s['optimal'], s['episodes'])} | {s['collision_rate']:.1%} | {s['loop_failures']} | {s['timeouts']} |")
    L += ["", "Full, by number of walls:\n", "| walls | maps | success | shortest path |", "|---|---|---|---|"]
    for w, s in sorted(res["full_by_walls"].items(), key=lambda kv: int(kv[0])):
        L.append(f"| {w} | {s['maps']} | {_pct(s['success'], s['episodes'])} | {_pct(s['optimal'], s['episodes'])} |")
    L += ["", "Full, by shortest-path length from the start:\n", "| BFS distance | episodes | success | shortest path |",
          "|---|---|---|---|"]
    for d, s in res["navigation"]["Full"]["by_distance"].items():
        L.append(f"| {d} | {s['total']} | {_pct(s['success'], s['total'])} | {_pct(s['optimal'], s['total'])} |")
    if res["worst_maps"]:
        L += ["", "Maps where Full was not optimal from every start:\n",
              "| map | walls | optimal | success | wrong edges | D(c) exact |", "|---|---|---|---|---|---|"]
        for w in res["worst_maps"]:
            L.append(f"| {w['map']} | {w['walls']} | {w['optimal']}/{w['episodes']} | {w['success']}/{w['episodes']} | "
                     f"{w['wrong_edges']} | {w['d_exact']}/{w['d_cells']} |")
    L += ["", "Reading:\n"] + [f"- {line}" for line in res["diagnosis"]]
    return "\n".join(x for x in L) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a trained multi-map model on 500 new layouts.")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--set", default="new_maps", help="test set under `multimap:` (new_maps, hard_maps, maze_maps)")
    parser.add_argument("--threshold", choices=["default", "calibrated"], default="default",
                        help="unknown threshold: 3 x median one-step error, or calibrated on the validation maps")
    parser.add_argument("--planner", choices=["p2", "snap"], default="p2",
                        help="p2: roll out raw latents (as in steps 8-12); snap: snap every imagined step")
    args = parser.parse_args()
    cfg = load_config(args.config)
    cfg["planning"]["p2"]["snap_each_step"] = args.planner == "snap"
    mm, nm = cfg["multimap"], cfg["multimap"][args.set]
    label = mm.get("label", "v1 model")

    maps, data, old = new_maps_and_data(cfg, args.set)
    added = complete_frames(data, maps)
    cov = coverage(data, maps)
    print(f"{len(maps)} new maps (none of the {len(old)} experiment layouts), {len(data['action'])} transitions, "
          f"{len(data['frames'])} frames ({added} rendered for cells the episodes missed); every (cell, action) seen "
          f"on {sum(c['pairs'] == c['all_pairs'] for c in cov)}/{len(maps)} maps", flush=True)

    encoder, _ = load_encoder(resolve(mm["encoder"]["checkpoint"]))
    predictor, pck = load_predictor(resolve(mm["predictor"]["checkpoint"]))
    print(f"Model: {label} ({resolve(mm['encoder']['checkpoint']).parent.name}), loaded, no retraining", flush=True)
    table = latent_table(encoder, data)
    cb, mask = codebooks(table, data, len(maps))
    ids = list(range(len(maps)))
    factor = cfg["imagination"]["unknown_factor"]
    median_err = pck["median_one_step_error"]
    thr = {"kind": "default", "threshold": factor * median_err, "rule": f"{factor:g} x median one-step error"}
    if args.threshold == "calibrated":
        from .calibrate import load_threshold
        cal = load_threshold(cfg)
        thr = {"kind": "calibrated", "threshold": cal["threshold"], "rule": cal["rule"]}
        median_err, factor = cal["threshold"], 1.0          # WorldModel: threshold = factor x median_err
    name = args.set + ("_calibrated" if args.threshold == "calibrated" else "") + ("_snap" if args.planner == "snap" else "")
    print(f"Unknown threshold {thr['threshold']:.3f} ({thr['rule']})", flush=True)

    dist = [mean_distance(m) for m in maps]
    res = {"label": label, "set": args.set, "unknown_threshold": thr, "planner": args.planner, "title": nm.get("title", "new maps"), "n_maps": len(maps),
           "seed": nm["seed"], "nav_seeds": nm["nav_seeds"],
           "mean_distance": float(np.mean(dist)), "longest_path": int(max(distances_to_goal(m).max() for m in maps)),
           "walls_min": min(len(m.walls) for m in maps), "walls_max": max(len(m.walls) for m in maps),
           "starts": sum(len(m.start_cells()) for m in maps), "frames_rendered": added,
           **chunked_metrics(predictor, table, data, ids, cb, mask, mm["predictor"]["eval_horizon"])}
    per_map, episodes, by_walls, maps_all_optimal, worst = [], defaultdict(list), defaultdict(list), 0, []
    for m, grid in enumerate(maps):
        world, goal_frame = world_for_map(m, grid, encoder, predictor, table, data, median_err, factor)
        gm = graph_metrics(world, grid, goal_frame)
        per_map.append(gm)
        eps = navigate(world, grid, goal_frame, cfg, nm["nav_seeds"])
        for r in RUNGS:
            episodes[r] += eps[r]
        full = eps["Full"]
        by_walls[len(grid.walls)].append(full)
        opt = sum(e.success and e.steps == e.optimal for e in full)
        if opt == len(full):
            maps_all_optimal += 1
        else:
            e = _sum_edges([gm])["all"]
            worst.append({"map": m, "walls": len(grid.walls), "optimal": opt, "success": sum(x.success for x in full),
                          "episodes": len(full), "wrong_edges": e["wrong_known"] + e["unknown"],
                          "d_exact": gm["d_exact"], "d_cells": gm["d_cells"]})
        if (m + 1) % 100 == 0:
            s = report(episodes["Full"])
            print(f"  {m + 1} maps: Full success {s['success'] / s['episodes']:.1%}, "
                  f"shortest path {s['optimal'] / s['episodes']:.1%}", flush=True)

    res["graph"] = {"edges": _sum_edges(per_map), "d_exact": sum(g["d_exact"] for g in per_map),
                    "d_cells": sum(g["d_cells"] for g in per_map), "d_under": sum(g["d_under"] for g in per_map),
                    "maps_exact": sum(g["d_exact"] == g["d_cells"] for g in per_map)}
    res["navigation"] = {r: report(v) for r, v in episodes.items()}
    res["full_by_walls"] = {str(w): {"maps": len(v), "episodes": sum(map(len, v)),
                                     "success": sum(e.success for ep in v for e in ep),
                                     "optimal": sum(e.success and e.steps == e.optimal for ep in v for e in ep)}
                            for w, v in by_walls.items()}
    res["maps_all_optimal"] = maps_all_optimal
    res["worst_maps"] = sorted(worst, key=lambda w: w["optimal"] / w["episodes"])[:15]
    res["diagnosis"] = diagnose(res["navigation"])

    out = resolve(mm["evaluation"]["results_dir"])
    out.mkdir(parents=True, exist_ok=True)
    md = render(res, label)
    (out / f"{name}.md").write_text(md)
    (out / f"{name}.json").write_text(json.dumps(res, indent=1, default=str) + "\n")
    print("\n" + md)
    print(f"Wrote {out / (name + '.md')} and {name}.json")


if __name__ == "__main__":
    main()
