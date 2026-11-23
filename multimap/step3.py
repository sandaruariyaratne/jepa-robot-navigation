"""Step 3: does the JEPA result survive a fair baseline, other seeds and ablations?

    python -m multimap.step3 train --variants jepa,pixel --seeds 0,1,2 [--threads 4]
    python -m multimap.step3 eval  --variants jepa,pixel --seeds 0,1,2
    python -m multimap.step3 summary

Variants (same encoder, predictor, data, 100-map split, maps per step, curriculum and checkpoint
selection on validation-map snap@5; only the training objective changes):

  jepa       online encoder + EMA target + variance / covariance terms (the model so far)
  pixel      generative baseline: encoder, decoder and predictor trained end to end; the frame is
             reconstructed and every imagined step is decoded and compared with the real next frame
             (robot pixels x10). 128 windows per step instead of 512, because every prediction is decoded.
  no_ema     JEPA with the online encoder (stop-gradient) as its own target
  no_vicreg  JEPA without the variance / covariance terms

Every model is evaluated the same way, on the 15 held-out test maps and the 200 maze maps, with two
planner settings: "p2" (raw rollouts, unknown = 3 x median one-step error; as in all earlier results)
and "snap" (every imagined step snapped, unknown = 99.9% quantile of correct one-step snap distances on
the validation maps). Checkpoints: checkpoints_step3/<variant>_s<seed>/; results: results_step3/.
"""

from __future__ import annotations

import argparse
import copy
import json
import shutil
import time
from pathlib import Path

import numpy as np
import torch

from config import ROOT, load_config, resolve
from models.encoder import load_encoder
from models.predictor import load_predictor

from .calibrate import calibrate
from .collect import load
from .evaluate import _sum_edges, graph_metrics, navigate, world_for_map
from .maps import load_maps
from .new_maps import chunked_metrics, complete_frames, new_maps_and_data
from .train import codebooks, latent_table

BASE = ROOT / "config_multimap_jepa.yaml"
CKPT, RESULTS = ROOT / "checkpoints_step3", ROOT / "results_step3"
VARIANTS = {
    "jepa": {},
    "pixel": {"objective": "pixel", "windows_per_step": 128},
    "no_ema": {"target": "online"},
    "no_vicreg": {"var_weight": 0.0, "cov_weight": 0.0},
}
LABELS = {"jepa": "JEPA", "pixel": "Pixel world model (baseline)", "no_ema": "JEPA, no EMA target",
          "no_vicreg": "JEPA, no variance / covariance terms"}


def run_cfg(variant: str, seed: int) -> dict:
    cfg = load_config(BASE)
    cfg["seed"] = seed
    cfg["multimap"]["jepa"].update(VARIANTS[variant])
    d = CKPT / f"{variant}_s{seed}"
    cfg["multimap"]["encoder"]["checkpoint"] = str(d / "encoder.pt")
    cfg["multimap"]["predictor"]["checkpoint"] = str(d / "predictor.pt")
    cfg["multimap"]["jepa"]["metrics"] = str(d / "train_metrics.json")
    return cfg


def train_one(variant: str, seed: int) -> None:
    from .train_jepa import train

    cfg = run_cfg(variant, seed)
    mm = cfg["multimap"]
    d = Path(mm["encoder"]["checkpoint"]).parent
    if (d / "predictor.pt").exists():
        print(f"{variant} seed {seed}: already trained, skipping")
        return
    d.mkdir(parents=True, exist_ok=True)
    if variant == "jepa" and seed == 0:          # identical config to the multi-map JEPA run: reuse it
        src = resolve(load_config(BASE)["multimap"]["encoder"]["checkpoint"]).parent
        for f, g in (("encoder.pt", "encoder.pt"), ("predictor.pt", "predictor.pt"), ("jepa_metrics.json", "train_metrics.json")):
            shutil.copy(src / f, d / g)
        print("jepa seed 0: copied from checkpoints_multimap_jepa/ (same config and seed)")
        return
    maps, splits = load_maps(resolve(mm["maps_path"]))
    data = load(resolve(mm["data_path"]))
    print(f"\n=== {variant} seed {seed}: {VARIANTS[variant] or 'base JEPA config'}", flush=True)
    t0 = time.perf_counter()
    target, predictor, m = train(cfg, data, splits, len(maps))
    j = mm["jepa"]
    torch.save({"state_dict": target.state_dict(), "latent_dim": target.latent_dim, "input_shape": list(target.input_shape),
                "seed": seed, "variant": variant, "best_epoch": m["best_step"]}, d / "encoder.pt")
    torch.save({"state_dict": predictor.state_dict(), "latent_dim": predictor.latent_dim, "n_actions": predictor.n_actions,
                "hidden": list(j["hidden"]), "median_one_step_error": m["median_one_step_error"],
                "best_epoch": m["best_step"], "seed": seed, "variant": variant}, d / "predictor.pt")
    (d / "train_metrics.json").write_text(json.dumps({**m, "minutes": (time.perf_counter() - t0) / 60}, indent=1) + "\n")
    print(f"{variant} seed {seed}: val snap@5 {m['best_val_snap']:.1%} at step {m['best_step']}, "
          f"{(time.perf_counter() - t0) / 60:.1f} min", flush=True)


def eval_set(cfg, maps, data, ids, encoder, predictor, thresholds: dict) -> dict:
    table = latent_table(encoder, data)
    cb, mask = codebooks(table, data, len(maps))
    out = chunked_metrics(predictor, table, data, list(ids), cb, mask, cfg["multimap"]["predictor"]["eval_horizon"])
    seeds = cfg["multimap"]["new_maps"]["nav_seeds"]
    for name, (snap, thr) in thresholds.items():
        c = copy.deepcopy(cfg)
        c["planning"]["p2"]["snap_each_step"] = snap
        per_map, n, ok, opt = [], 0, 0, 0
        for m in ids:
            world, goal_frame = world_for_map(m, maps[m], encoder, predictor, table, data, thr, 1.0)
            per_map.append(graph_metrics(world, maps[m], goal_frame))
            for e in navigate(world, maps[m], goal_frame, c, seeds, labels=("Full",))["Full"]:
                n += 1
                ok += e.success
                opt += e.success and e.steps == e.optimal
        edges = _sum_edges(per_map)["all"]
        out[name] = {"threshold": thr, "episodes": n, "success": ok, "optimal": opt, "edges": edges,
                     "d_exact": sum(g["d_exact"] for g in per_map), "d_cells": sum(g["d_cells"] for g in per_map),
                     "d_under": sum(g["d_under"] for g in per_map)}
    return out


def eval_one(variant: str, seed: int) -> None:
    cfg = run_cfg(variant, seed)
    mm = cfg["multimap"]
    d = Path(mm["encoder"]["checkpoint"]).parent
    out_path = RESULTS / f"{variant}_s{seed}.json"
    if out_path.exists():
        print(f"{variant} seed {seed}: already evaluated, skipping")
        return
    encoder, _ = load_encoder(d / "encoder.pt")
    predictor, pck = load_predictor(d / "predictor.pt")
    cal = calibrate(cfg, verbose=False)
    thresholds = {"p2": (False, cfg["imagination"]["unknown_factor"] * pck["median_one_step_error"]),
                  "snap": (True, cal["threshold"])}
    tm = json.loads((d / "train_metrics.json").read_text())
    res = {"variant": variant, "seed": seed, "label": LABELS[variant], "overrides": VARIANTS[variant],
           "train": {k: tm.get(k) for k in ("best_step", "best_val_snap", "median_one_step_error", "probe_val_accuracy",
                                            "latent_geometry", "minutes")},
           "calibration": cal}
    t0 = time.perf_counter()
    maps, splits = load_maps(resolve(mm["maps_path"]))
    data = load(resolve(mm["data_path"]))
    res["test15"] = eval_set(cfg, maps, data, splits["test"], encoder, predictor, thresholds)
    mz, mzdata, _ = new_maps_and_data(cfg, "maze_maps")
    complete_frames(mzdata, mz)
    res["maze200"] = eval_set(cfg, mz, mzdata, range(len(mz)), encoder, predictor, thresholds)
    RESULTS.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(res, indent=1, default=float) + "\n")
    t, z = res["test15"], res["maze200"]
    print(f"{variant} seed {seed}: test one-step normal moves "
          f"{t['prediction']['one_step']['normal moves']['correct'] / t['prediction']['one_step']['normal moves']['total']:.1%}, "
          f"maze success p2 {z['p2']['success'] / z['p2']['episodes']:.1%} / snap {z['snap']['success'] / z['snap']['episodes']:.1%} "
          f"({(time.perf_counter() - t0) / 60:.1f} min)", flush=True)


# --- summary ------------------------------------------------------------------------------------------
def _ms(vals, pct=True):
    vals = [v for v in vals if v is not None]
    if not vals:
        return "-"
    f = (lambda v: f"{100 * v:.1f}%") if pct else (lambda v: f"{v:.2f}")
    if len(vals) == 1:
        return f(vals[0])
    sd = float(np.std(vals, ddof=1))
    return f"{f(float(np.mean(vals)))} ± {100 * sd:.1f}" if pct else f"{f(float(np.mean(vals)))} ± {sd:.2f}"


def summary() -> str:
    runs: dict[str, list[dict]] = {}
    for p in sorted(RESULTS.glob("*_s*.json")):
        r = json.loads(p.read_text())
        runs.setdefault(r["variant"], []).append(r)
    order = [v for v in VARIANTS if v in runs]
    frac = lambda a, b: a / b if b else None  # noqa: E731
    rows = {
        "Seeds": lambda rs: ", ".join(str(r["seed"]) for r in rs),
        "Val-map snap@5 (selection)": lambda rs: _ms([r["train"]["best_val_snap"] for r in rs]),
        "Robot cell from latent, linear probe (val maps)": lambda rs: _ms([r["train"]["probe_val_accuracy"] for r in rs]),
        "Test maps: one-step, normal moves": lambda rs: _ms([frac(r["test15"]["prediction"]["one_step"]["normal moves"]["correct"],
                                                                 r["test15"]["prediction"]["one_step"]["normal moves"]["total"]) for r in rs]),
        "Test maps: rollout accuracy, step 5": lambda rs: _ms([r["test15"]["prediction"]["rollout"][4] for r in rs]),
        "Test maps: navigation success (p2)": lambda rs: _ms([frac(r["test15"]["p2"]["success"], r["test15"]["p2"]["episodes"]) for r in rs]),
        "Test maps: navigation success (snap)": lambda rs: _ms([frac(r["test15"]["snap"]["success"], r["test15"]["snap"]["episodes"]) for r in rs]),
        "Mazes: one-step, normal moves": lambda rs: _ms([frac(r["maze200"]["prediction"]["one_step"]["normal moves"]["correct"],
                                                             r["maze200"]["prediction"]["one_step"]["normal moves"]["total"]) for r in rs]),
        "Mazes: collision accuracy": lambda rs: _ms([r["maze200"]["collision"]["accuracy"] for r in rs]),
        "Mazes: imagined edges wrong but trusted (p2)": lambda rs: _ms([frac(r["maze200"]["p2"]["edges"]["wrong_known"],
                                                                            r["maze200"]["p2"]["edges"]["total"]) for r in rs]),
        "Mazes: navigation success (p2)": lambda rs: _ms([frac(r["maze200"]["p2"]["success"], r["maze200"]["p2"]["episodes"]) for r in rs]),
        "Mazes: shortest path (p2)": lambda rs: _ms([frac(r["maze200"]["p2"]["optimal"], r["maze200"]["p2"]["episodes"]) for r in rs]),
        "Mazes: navigation success (snap)": lambda rs: _ms([frac(r["maze200"]["snap"]["success"], r["maze200"]["snap"]["episodes"]) for r in rs]),
        "Mazes: shortest path (snap)": lambda rs: _ms([frac(r["maze200"]["snap"]["optimal"], r["maze200"]["snap"]["episodes"]) for r in rs]),
        "Latent: smallest per-dimension std": lambda rs: _ms([r["train"]["latent_geometry"]["min_dim_std"] for r in rs], pct=False),
    }
    L = ["# Step 3: fair baseline, seeds and ablations\n",
         "Mean ± standard deviation (percentage points) over training seeds. Same data, 100-map split, encoder, predictor, "
         "curriculum and checkpoint selection; only the training objective differs. Navigation: every free start cell, "
         "2 planning seeds. p2 = raw rollouts with unknown = 3 x median one-step error; snap = every imagined step snapped, "
         "unknown = 99.9% quantile of correct one-step snap distances on the validation maps.\n",
         "| | " + " | ".join(LABELS[v] for v in order) + " |", "|---|" + "---|" * len(order)]
    for name, fn in rows.items():
        L.append(f"| {name} | " + " | ".join(fn(runs[v]) for v in order) + " |")
    L.append("\nPer run:\n")
    L.append("| run | val snap@5 | test nav (p2) | maze nav (p2) | maze nav (snap) | training min |")
    L.append("|---|---|---|---|---|---|")
    for v in order:
        for r in runs[v]:
            L.append(f"| {v} s{r['seed']} | {r['train']['best_val_snap']:.1%} | "
                     f"{r['test15']['p2']['success'] / r['test15']['p2']['episodes']:.1%} | "
                     f"{r['maze200']['p2']['success'] / r['maze200']['p2']['episodes']:.1%} | "
                     f"{r['maze200']['snap']['success'] / r['maze200']['snap']['episodes']:.1%} | "
                     f"{(r['train'].get('minutes') or 0):.0f} |")
    return "\n".join(L) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["train", "eval", "summary"])
    parser.add_argument("--variants", default=",".join(VARIANTS))
    parser.add_argument("--seeds", default="0,1,2")
    parser.add_argument("--threads", type=int, default=0, help="torch CPU threads (0 = default)")
    args = parser.parse_args()
    if args.threads:
        torch.set_num_threads(args.threads)
    if args.command == "summary":
        md = summary()
        RESULTS.mkdir(parents=True, exist_ok=True)
        (RESULTS / "summary.md").write_text(md)
        print(md)
        return
    for v in args.variants.split(","):
        if v not in VARIANTS:
            raise SystemExit(f"unknown variant {v}; choose from {', '.join(VARIANTS)}")
        for s in (int(x) for x in args.seeds.split(",")):
            (train_one if args.command == "train" else eval_one)(v, s)


if __name__ == "__main__":
    main()
