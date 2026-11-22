"""Model metrics (build plan step 9): how good is the world model, before any planning?

  * one-step latent error vs the persistence baseline (z_hat = z)
  * snap accuracy and position-probe accuracy at 1..10 imagined steps
  * latent MSE at 1..10 steps, against persistence (z_hat_k = z_0)
  * all 100 (cell, action) pairs, split into trained / held-out
  * imagined graph correctness and D(c) vs the true distance
  * the numerical baseline (step 3) on the same pairs, for comparison

Everything is computed on the test split, from the saved checkpoints.
"""

from __future__ import annotations

import numpy as np
import torch

from config import resolve
from data import TransitionWindows
from environment import GridWorld
from evaluation.probes import CellIndex, LinearProbe, probe_kwargs
from models.encoder import load_encoder
from models.predictor import load_predictor
from planning.imagination import WorldModel
from planning.latent_graph import build_graph, goal_entry, steps_to_goal
from planning.latent_graph import evaluate as evaluate_graph
from training.train_world_model import encode_latents, window_tensors
from training.train_world_model import evaluate as evaluate_predictor


@torch.no_grad()
def horizon_curves(predictor, data: dict, splits: dict, latents: dict, codebook: torch.Tensor,
                   probe: LinearProbe, horizon: int) -> dict:
    """Per-horizon snap / probe accuracy and MSE (model and persistence), trained-only and all test windows."""
    from models import snap

    cells = CellIndex()
    out = {}
    for name, excl in (("trained", splits["heldout_pairs"]), ("all", ())):
        ds = TransitionWindows(data, splits["test"], k=horizon, exclude_pairs=excl)
        t = window_tensors(ds, latents, cells)
        pred = predictor.rollout(t["z0"], t["action"])  # [N, K, D]
        idx, _ = snap(pred, codebook)
        probe_pred = torch.as_tensor(probe.predict(pred.reshape(-1, pred.shape[-1]))).view(idx.shape)
        persist = t["z0"][:, None].expand_as(t["target"])
        out[name] = {
            "n": len(ds),
            "snap_acc": (idx == t["next_cell"]).float().mean(0).tolist(),
            "probe_acc": (probe_pred == t["next_cell"]).float().mean(0).tolist(),
            "mse": ((pred - t["target"]) ** 2).mean(dim=(0, 2)).tolist(),
            "mse_persistence": ((persist - t["target"]) ** 2).mean(dim=(0, 2)).tolist(),
        }
    return out


def numerical_baseline(cfg: dict, data: dict, splits: dict) -> dict | None:
    path = resolve(cfg["numerical"]["checkpoint"])
    if not path.exists():
        return None
    from training.train_numerical import evaluate, load_checkpoint

    m = evaluate(load_checkpoint(path), data, splits)
    return {"pairs": m["pairs"], "test": m["test"]}


def model_metrics(cfg: dict, data: dict, splits: dict) -> dict:
    encoder, enc_ckpt = load_encoder(resolve(cfg["encoder"]["checkpoint"]))
    predictor, pred_ckpt = load_predictor(resolve(cfg["predictor"]["checkpoint"]))
    latents = encode_latents(encoder, data)
    codebook = encoder.standardize(enc_ckpt["codebook"].float())
    horizon = cfg["evaluation"]["horizon"]

    pred = evaluate_predictor(predictor, data, splits, latents, codebook, horizon)

    # Position probe fit on real training latents, then applied to imagined ones.
    cells = CellIndex()
    tr = TransitionWindows(data, splits["train"])
    probe = LinearProbe(latents["z_obs"].shape[1], len(cells)).fit(
        latents["z_obs"][tr.starts], cells.ids(data["pos"][tr.starts]), **probe_kwargs(cfg))
    curves = horizon_curves(predictor, data, splits, latents, codebook, probe, horizon)

    world = WorldModel(encoder, predictor, codebook, pred_ckpt["median_one_step_error"],
                       cfg["imagination"]["unknown_factor"])
    graph = build_graph(world)
    goal, _ = goal_entry(world, GridWorld().goal_obs())
    g = evaluate_graph(graph, steps_to_goal(graph, goal), splits["heldout_pairs"])

    return {
        "one_step": pred["one_step"],
        "test_snap": pred["test_snap"],
        "pairs": pred["pairs"],
        "pair_details": pred["pair_details"],
        "curves": curves,
        "graph": {"edges": g["edges"], "d_exact": g["d_exact"], "d_over": g["d_over"], "d_under": g["d_under"],
                  "d_unreachable": g["d_unreachable"], "d_imagined": g["d_imagined"], "d_true": g["d_true"]},
        "numerical_baseline": numerical_baseline(cfg, data, splits),
        "median_one_step_error": pred_ckpt["median_one_step_error"],
    }
