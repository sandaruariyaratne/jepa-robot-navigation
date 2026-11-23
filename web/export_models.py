"""Export the trained multi-map models for the browser demo, plus test vectors.

    .venv/bin/python web/export_models.py

Writes web/models/<key>.{json,bin} for the 6 x 5 model (jepa) and the 10 x 10 fog-of-war
model (fog, REPORT section 8): every tensor as float32, little-endian, concatenated; the
JSON lists names, shapes and offsets plus the grid and the planning settings (snapped P2,
unknown threshold calibrated on the validation maps; for fog also the stay / merge
thresholds of imagined maps and the explorer's budget). web/test/vectors.json holds
PyTorch results on a few layouts (frame hashes, latents, imagined graph, D(c), P2
first-plan costs, the map imagined from the start and goal pictures) that
web/test/check.mjs compares the JavaScript port against.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import torch  # noqa: E402

from config import load_config, resolve  # noqa: E402
from environment import COLORS, DEFAULT_GOAL, DEFAULT_WALLS, GridMap, GridWorld, distances_to_goal  # noqa: E402
from models.encoder import load_encoder  # noqa: E402
from models.predictor import load_predictor  # noqa: E402
from multimap.calibrate import load_threshold  # noqa: E402
from multimap.explore import _starts, fog_thresholds, imagined_map  # noqa: E402
from multimap.maps import load_maps  # noqa: E402
from planning.imagination import WorldModel  # noqa: E402
from planning.latent_graph import build_graph, goal_entry, steps_to_goal  # noqa: E402
from planning.planner import P2, PlanContext  # noqa: E402

OUT = ROOT / "web"
MODELS = {"jepa": ("configs/multimap_jepa.yaml", "Joint JEPA (v2)"),            # the demo shows the JEPA only
          "fog": ("configs/fog.yaml", "Joint JEPA, 10 x 10, fog of war")}


def export_model(key: str) -> tuple[dict, object, object]:
    cfg_path, label = MODELS[key]
    cfg = load_config(ROOT / cfg_path)
    mm = cfg["multimap"]
    encoder, _ = load_encoder(resolve(mm["encoder"]["checkpoint"]))
    predictor, pck = load_predictor(resolve(mm["predictor"]["checkpoint"]))
    tensors, blob, offset = [], bytearray(), 0
    for prefix, sd in (("encoder", encoder.state_dict()), ("predictor", predictor.state_dict())):
        for name, t in sd.items():
            a = t.detach().cpu().numpy().astype("<f4")
            tensors.append({"name": f"{prefix}.{name}", "shape": list(a.shape), "offset": offset, "size": int(a.size)})
            blob += a.tobytes()
            offset += a.size
    p = cfg["planning"]
    cal = load_threshold(cfg)        # the demo plans like the final evaluation: snapped P2, calibrated threshold
    ex = mm.get("explore", {})
    budget = ex.get("explorer", {"max_actions": p["max_actions"], "max_visits": p["max_visits"]}) if "explorer" in ex \
        else {"max_actions": p["max_actions"], "max_visits": p["max_visits"]}
    imagined = {"max_nodes": ex.get("max_nodes", 60)}
    if ex.get("two_thresholds"):     # imagined maps (A, B) under fog: separate stay / merge thresholds
        t = fog_thresholds(cfg)
        imagined.update(stay=t["stay"], merge=t["merge"], rule=t["rule"])
    meta = {
        "key": key, "label": label, "latent_dim": encoder.latent_dim, "hidden": pck["hidden"],
        "n_actions": predictor.n_actions, "median_one_step_error": pck["median_one_step_error"],
        "unknown_factor": cfg["imagination"]["unknown_factor"],
        "default_threshold": cfg["imagination"]["unknown_factor"] * pck["median_one_step_error"],
        "unknown_threshold": cal["threshold"], "unknown_rule": cal["rule"],
        "grid": {"cols": mm.get("cols", 6), "rows": mm.get("rows", 5), "goal": list(mm.get("goal", DEFAULT_GOAL)),
                 "view_radius": mm.get("view_radius")},
        "imagined": imagined,
        "planning": {"horizon": p["p2"]["horizon"], "max_actions": int(budget["max_actions"]),
                     "max_visits": int(budget["max_visits"]), "revisit_penalty": p["revisit_penalty"], "snap_each_step": True},
        "trained_on": {"maps": len(load_maps(resolve(mm["maps_path"]))[1]["train"]),
                       "walls": [mm["min_walls"], mm["max_walls"]], "goal": list(mm.get("goal", DEFAULT_GOAL))},
        "tensors": tensors, "floats": offset,
    }
    (OUT / "models").mkdir(parents=True, exist_ok=True)
    (OUT / "models" / f"{key}.bin").write_bytes(bytes(blob))
    (OUT / "models" / f"{key}.json").write_text(json.dumps(meta, indent=1) + "\n")
    return meta, encoder, predictor


def free_rowmajor(grid: GridMap) -> list[tuple[int, int]]:
    return [(x, y) for y in range(grid.rows) for x in range(grid.cols) if (x, y) not in grid.walls]


@torch.no_grad()
def vectors_for(grid: GridMap, meta: dict, encoder, predictor) -> dict:
    cells = free_rowmajor(grid)
    r = GridWorld(grid).renderer
    frames = np.stack([r.render(c) for c in cells])
    z = encoder.standardize(encoder(torch.as_tensor(frames)))
    world = WorldModel(encoder, predictor, z, meta["unknown_threshold"], 1.0)   # threshold = factor x err
    g = build_graph(world)
    goal_frame = r.render(grid.goal)
    goal, _ = goal_entry(world, goal_frame)
    d = steps_to_goal(g, goal)
    z_goal = world.encode(goal_frame)
    planner = P2(meta["planning"]["horizon"], snap_each_step=meta["planning"]["snap_each_step"])
    plans = []
    for i, c in enumerate(cells):
        if c == grid.goal:
            continue
        ctx = PlanContext(z_goal, d, {i: 1}, meta["planning"]["revisit_penalty"], np.random.default_rng(0))
        plan = planner.plan(world, z[i], ctx)
        costs = [c_ if np.isfinite(c_) else None for c_ in plan.extra["first_action_costs"]]  # JSON has no inf
        plans.append({"start": list(c), "first_action_costs": costs, "note": plan.note})
    d_true = distances_to_goal(grid)
    # the map imagined from the start and goal pictures (A / B before the first move), from the farthest cell
    start = max((c for c in cells if d_true[c[1], c[0]] >= 0), key=lambda c: d_true[c[1], c[0]])
    im = meta["imagined"]
    thr = (im["stay"], im["merge"]) if "stay" in im else meta["unknown_threshold"]
    m = imagined_map(encoder, predictor, torch.stack([z[cells.index(start)], z_goal]), 1, thr, im["max_nodes"])
    imagined = {"start": list(start), "nodes": len(m.next), "next": m.next.tolist(), "known": m.known.tolist(),
                "d": m.d.tolist(), "overflow": bool(m.overflow)}
    return {
        "walls": sorted(list(w) for w in grid.walls), "cells": [list(c) for c in cells],
        "frame_sha1": [hashlib.sha1(f.tobytes()).hexdigest() for f in frames],
        "latents": z.numpy().round(6).tolist(),
        "next": g.next.tolist(), "known": g.known.tolist(), "distance": g.distance.round(5).tolist(),
        "goal_entry": goal, "d": d.tolist(), "d_true": [int(d_true[y, x]) for x, y in cells], "plans": plans,
        "imagined": imagined,
    }


def main() -> None:
    new, _ = load_maps(ROOT / "datasets/new_maps/maps.json")
    maze, _ = load_maps(ROOT / "datasets/maze_maps/maps.json")
    hard, _ = load_maps(ROOT / "datasets/hard_maps/maps.json")
    fog_cfg = load_config(ROOT / "configs/fog.yaml")["multimap"]
    fog_maps, _ = load_maps(resolve(fog_cfg["fog_maps"]["maps_path"]))
    fog_mazes, _ = load_maps(resolve(fog_cfg["fog_mazes"]["maps_path"]))
    layouts = {
        "jepa": [("reference", GridMap(walls=frozenset(DEFAULT_WALLS))), ("new_0", new[0]), ("new_17", new[17]),
                 ("maze_0", maze[0]), ("maze_100", maze[100]), ("dense_13w", next(m for m in hard if len(m.walls) == 13))],
        "fog": [("fog_0", fog_maps[0]), ("fog_17", fog_maps[17]), ("fogmaze_0", fog_mazes[0]), ("fogmaze_50", fog_mazes[50])],
    }
    vec = {"colors": COLORS, "models": {}}
    for key in MODELS:
        meta, enc, pred = export_model(key)
        vec["models"][key] = {name: vectors_for(g, meta, enc, pred) for name, g in layouts[key]}
        print(f"{key}: {meta['floats']:,} floats -> web/models/{key}.bin, threshold {meta['unknown_threshold']:.4f}")
    (OUT / "test").mkdir(parents=True, exist_ok=True)
    (OUT / "test" / "vectors.json").write_text(json.dumps(vec) + "\n")
    # layouts for the JS-side navigation benchmark; fog sets keep the test runs' seeded start cells
    walls = lambda m: sorted(list(w) for w in m.walls)                                       # noqa: E731
    with_starts = lambda maps, key: [{"walls": walls(g), "starts": [list(c) for _, c in _starts(g, fog_cfg[key], k)]}  # noqa: E731
                                     for k, g in enumerate(maps)]
    bench = {"jepa": {"new_maps": [walls(m) for m in new[:100]], "maze_maps": [walls(m) for m in maze]},
             "fog": {"fog_maps": with_starts(fog_maps, "fog_maps"), "fog_mazes": with_starts(fog_mazes, "fog_mazes")}}
    (OUT / "test" / "bench_maps.json").write_text(json.dumps(bench) + "\n")
    print("wrote web/test/vectors.json and bench_maps.json")


if __name__ == "__main__":
    main()
