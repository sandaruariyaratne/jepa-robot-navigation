"""Recalibrate the "unknown" snap threshold on the validation maps: `python -m multimap.calibrate --config ...`.

The default rule is threshold = 3 x the median one-step error. For the joint
JEPA the one-step errors have a long tail: on the validation maps it makes no
wrong one-step snap at all, yet 3 x median rejects ~1% of its correct ones,
and the planner then treats those moves as walls.

Calibrated rule, fixed before looking at any test map:
    threshold = the `quantile` (99.9%) of the snap distance of *correct* one-step
                predictions on the validation maps (each map snapped to its own codebook).

Only validation maps are used. The planner also snaps imagined steps 2..H with
the same threshold; those statistics are recorded too (correct rejected, wrong
trusted, before / after), because there distance separates right from wrong far
less well.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch

from config import load_config, resolve
from models.encoder import load_encoder
from models.predictor import load_predictor

from .collect import load
from .maps import load_maps
from .train import codebooks, latent_table, snap_in_map, windows


def threshold_path(cfg: dict) -> Path:
    return resolve(cfg["multimap"]["predictor"]["checkpoint"]).with_name("unknown_threshold.json")


@torch.no_grad()
def calibrate(cfg: dict, verbose: bool = True) -> dict:
    mm = cfg["multimap"]
    c = mm.get("calibration", {"quantile": 0.999, "horizon": 3})
    maps, splits = load_maps(resolve(mm["maps_path"]))
    data = load(resolve(mm["data_path"]))
    encoder, _ = load_encoder(resolve(mm["encoder"]["checkpoint"]))
    predictor, pck = load_predictor(resolve(mm["predictor"]["checkpoint"]))
    table = latent_table(encoder, data)
    cb, mask = codebooks(table, data, len(maps))
    t = windows(data, splits["val"], c["horizon"])
    cell, dist = snap_in_map(predictor.rollout(table[t["obs"]], t["action"]), t["map"], cb, mask)
    ok, d = (cell == t["next_cell"]).numpy(), dist.numpy()

    default = cfg["imagination"]["unknown_factor"] * pck["median_one_step_error"]
    thr = float(np.quantile(d[ok[:, 0], 0], c["quantile"]))
    steps = []
    for k in range(c["horizon"]):
        right, wrong = d[ok[:, k], k], d[~ok[:, k], k]
        steps.append({"step": k + 1, "correct": int(len(right)), "wrong": int(len(wrong)),
                      "correct_rejected_default": float((right > default).mean()),
                      "correct_rejected_calibrated": float((right > thr).mean()),
                      "wrong_trusted_default": float((wrong <= default).mean()) if len(wrong) else None,
                      "wrong_trusted_calibrated": float((wrong <= thr).mean()) if len(wrong) else None})
    out = {"threshold": thr, "rule": f"{c['quantile']:.1%} quantile of correct one-step snap distances, validation maps",
           "quantile": c["quantile"], "default_threshold": float(default),
           "median_one_step_error": float(pck["median_one_step_error"]), "val_maps": len(splits["val"]),
           "windows": int(len(d)), "steps": steps}
    if verbose:
        print(f"unknown threshold: default {default:.3f} (3 x median) -> calibrated {thr:.3f} ({out['rule']})")
        for s in steps:
            wd = "-" if s["wrong"] == 0 else f"{s['wrong_trusted_default']:.1%} -> {s['wrong_trusted_calibrated']:.1%}"
            print(f"  step {s['step']}: correct rejected {s['correct_rejected_default']:.2%} -> "
                  f"{s['correct_rejected_calibrated']:.2%};  wrong ({s['wrong']}) trusted {wd}")
    return out


def load_threshold(cfg: dict) -> dict:
    """The saved calibration, computing (and saving) it first if needed."""
    p = threshold_path(cfg)
    if not p.exists():
        p.write_text(json.dumps(calibrate(cfg, verbose=False), indent=1) + "\n")
    return json.loads(p.read_text())


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibrate the unknown threshold on the validation maps.")
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args()
    cfg = load_config(args.config)
    out = calibrate(cfg)
    p = threshold_path(cfg)
    p.write_text(json.dumps(out, indent=1) + "\n")
    print(f"Saved {p}")


if __name__ == "__main__":
    main()
