"""Stage 2: train the residual latent predictor (build plan step 6).

    python -m training.train_world_model

Latents come from the frozen Stage 1 encoder, standardised with its training
z_mean / z_std, and are computed once up front: targets carry no gradient.
Windows containing a held-out (state, action) pair are dropped from training
and from checkpoint selection. Training follows a rollout curriculum (K = 1,
then 2, then 4 steps fed back through the predictor), and the kept epoch is
the one with the best validation snap accuracy after 5 imagined steps -- not
the lowest one-step loss.

Snap: the nearest entry in the codebook (the latents of the 25 distinct
frames). Codebook entry i is cell i, so a snapped rollout says which cell the
model thinks the robot is in.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

import numpy as np
import torch
from torch.nn import functional as F

from config import load_config, resolve
from data import TransitionWindows, load_splits, load_transitions
from environment import ACTION_NAMES
from evaluation.metrics import CATEGORIES, category_masks, fmt_score, score, unique_pairs
from evaluation.probes import CellIndex
from models import Predictor, snap
from models.encoder import Encoder, load_encoder

PERSISTENCE_RATIO_PASS = 0.5  # "clearly below persistence": at most half its one-step error
TRAINED_PAIR_PASS = 0.99


# --- latents -------------------------------------------------------------------
@torch.no_grad()
def encode_latents(encoder: Encoder, data: dict, batch: int = 2048) -> dict[str, np.ndarray]:
    """Standardised latents of obs and next_obs for every transition."""
    out = {}
    for key, src in (("z_obs", "obs"), ("z_next", "next_obs")):
        frames = torch.as_tensor(data[src])
        z = torch.cat([encoder(frames[i:i + batch]) for i in range(0, len(frames), batch)])
        out[key] = encoder.standardize(z).numpy()
    return out


def window_tensors(ds: TransitionWindows, latents: dict, cells: CellIndex) -> dict[str, torch.Tensor]:
    """Everything a K-step rollout needs, for every window of a dataset (k must be set)."""
    k = ds.k or 1
    rows = ds.starts[:, None] + np.arange(k)  # [N, K]
    d = ds.data
    return {
        "z0": torch.as_tensor(latents["z_obs"][ds.starts]),
        "target": torch.as_tensor(latents["z_next"][rows]),            # [N, K, D]
        "action": torch.as_tensor(d["action"][rows]),                  # [N, K]
        "next_cell": torch.as_tensor(cells.ids(d["next_pos"][rows])),  # [N, K]
        "cell": torch.as_tensor(cells.ids(d["pos"][ds.starts])),
        "pos": torch.as_tensor(d["pos"][ds.starts]),
        "collision": torch.as_tensor(d["collision"][rows]),
    }


def k_for_epoch(curriculum, epoch: int) -> int:
    k = curriculum[0][1]
    for start, kk in curriculum:
        if epoch >= start:
            k = kk
    return k


# --- evaluation ----------------------------------------------------------------
@torch.no_grad()
def rollout_scores(model: Predictor, t: dict, codebook: torch.Tensor) -> dict[str, np.ndarray]:
    """Per-horizon snap accuracy and latent MSE for a set of windows."""
    model.eval()
    pred = model.rollout(t["z0"], t["action"])
    idx, _ = snap(pred, codebook)
    return {
        "snap_acc": (idx == t["next_cell"]).float().mean(0).numpy(),
        "mse": ((pred - t["target"]) ** 2).mean(dim=(0, 2)).numpy(),
    }


@torch.no_grad()
def evaluate(model: Predictor, data: dict, splits: dict, latents: dict, codebook: torch.Tensor,
             horizon: int) -> dict:
    model.eval()
    cells = CellIndex()
    held = splits["heldout_pairs"]
    metrics: dict = {}

    # One step on every test transition: error vs the persistence baseline, and snap accuracy.
    t = window_tensors(TransitionWindows(data, splits["test"], k=1), latents, cells)
    pred = model(t["z0"], t["action"][:, 0])
    target = t["target"][:, 0]
    err_model = ((pred - target) ** 2).mean(1).numpy()
    err_persist = ((t["z0"] - target) ** 2).mean(1).numpy()
    correct = (snap(pred, codebook)[0] == t["next_cell"][:, 0]).numpy()
    masks = category_masks(t["pos"].numpy(), t["action"][:, 0].numpy(), t["collision"][:, 0].numpy(), held)
    trained = ~masks["held-out (all)"]
    metrics["one_step"] = {
        "mse_model": {"all": float(err_model.mean()), "trained": float(err_model[trained].mean()),
                      **{n: float(err_model[m].mean()) for n, m in masks.items() if m.any()}},
        "mse_persistence": {"all": float(err_persist.mean()), "trained": float(err_persist[trained].mean()),
                            **{n: float(err_persist[m].mean()) for n, m in masks.items() if m.any()}},
    }
    metrics["one_step"]["ratio_trained"] = metrics["one_step"]["mse_model"]["trained"] / \
        metrics["one_step"]["mse_persistence"]["trained"]
    metrics["test_snap"] = score(correct, masks)

    # Every (cell, action) pair, starting from its codebook entry: the imagined graph's edges.
    p = unique_pairs(data)
    src = cells.ids(p["pos"])
    pred_idx = snap(model(codebook[src], torch.as_tensor(p["action"])), codebook)[0].numpy()
    true_idx = cells.ids(p["next_pos"])
    correct = pred_idx == true_idx
    masks = category_masks(p["pos"], p["action"], p["collision"], held)
    metrics["pairs"] = score(correct, masks)
    metrics["pair_details"] = [
        {"pair": [int(p["pos"][i, 0]), int(p["pos"][i, 1]), int(p["action"][i])],
         "heldout": bool(masks["held-out (all)"][i]), "collision": bool(p["collision"][i]),
         "true": cells.positions(true_idx[i]).tolist(), "pred": cells.positions(pred_idx[i]).tolist(),
         "correct": bool(correct[i])}
        for i in range(len(correct)) if masks["held-out (all)"][i] or not correct[i]
    ]

    # Multi-step rollouts on test windows: trained pairs only, and all windows.
    for name, excl in (("trained_windows", held), ("all_windows", ())):
        ds = TransitionWindows(data, splits["test"], k=horizon, exclude_pairs=excl)
        r = rollout_scores(model, window_tensors(ds, latents, cells), codebook)
        metrics[f"rollout_{name}"] = {"n": len(ds), "snap_acc": r["snap_acc"].tolist(), "mse": r["mse"].tolist()}
    return metrics


@torch.no_grad()
def median_one_step_error(model: Predictor, t: dict) -> float:
    """Median Euclidean distance between one-step prediction and target (used by step 7's 'unknown' test)."""
    pred = model(t["z0"], t["action"][:, 0])
    return float(torch.linalg.norm(pred - t["target"][:, 0], dim=-1).median())


# --- training ------------------------------------------------------------------
def train(cfg: dict, data: dict, splits: dict, latents: dict, codebook: torch.Tensor,
          verbose: bool = True) -> tuple[Predictor, dict]:
    pcfg = cfg["predictor"]
    seed = cfg["seed"]
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    cells = CellIndex()
    held = splits["heldout_pairs"]
    latent_dim = latents["z_obs"].shape[1]

    model = Predictor(latent_dim, 4, pcfg["hidden"], pcfg["last_layer_init"])
    opt = torch.optim.Adam(model.parameters(), lr=pcfg["lr"])
    ks = sorted({k for _, k in pcfg["curriculum"]})
    train_sets = {k: window_tensors(TransitionWindows(data, splits["train"], k=k, exclude_pairs=held), latents, cells)
                  for k in ks}
    h = pcfg["select_horizon"]
    val_sel = window_tensors(TransitionWindows(data, splits["val"], k=h, exclude_pairs=held), latents, cells)
    val_one = window_tensors(TransitionWindows(data, splits["val"], k=1, exclude_pairs=held), latents, cells)

    best = {"key": (-1.0, float("inf")), "epoch": 0, "state": None}
    history = []
    for epoch in range(1, pcfg["epochs"] + 1):
        k = k_for_epoch(pcfg["curriculum"], epoch)
        t = train_sets[k]
        n, bs = len(t["z0"]), pcfg["batch_size"]
        model.train()
        perm = torch.as_tensor(rng.permutation(n))
        total = 0.0
        for s in range(0, n, bs):
            idx = perm[s:s + bs]
            pred = model.rollout(t["z0"][idx], t["action"][idx])
            loss = F.mse_loss(pred, t["target"][idx])
            opt.zero_grad()
            loss.backward()
            opt.step()
            total += loss.item() * len(idx)

        sel = rollout_scores(model, val_sel, codebook)
        one = rollout_scores(model, val_one, codebook)
        acc_h, mse_h = float(sel["snap_acc"][-1]), float(sel["mse"][-1])
        history.append({"epoch": epoch, "k": k, "train_loss": total / n, "val_mse_1": float(one["mse"][0]),
                        "val_snap_1": float(one["snap_acc"][0]), f"val_snap_{h}": acc_h, f"val_mse_{h}": mse_h})
        key = (acc_h, mse_h)  # best snap accuracy at h steps; ties broken by lower h-step latent error
        if key[0] > best["key"][0] or (key[0] == best["key"][0] and key[1] < best["key"][1]):
            best = {"key": key, "epoch": epoch, "state": copy.deepcopy(model.state_dict())}
        if verbose and (epoch == 1 or epoch % 5 == 0 or epoch in {s for s, _ in pcfg["curriculum"]}):
            print(f"  epoch {epoch:3d}  K={k}  train {total / n:.5f}  val 1-step mse {one['mse'][0]:.5f}  "
                  f"val snap@1 {one['snap_acc'][0]:.1%}  val snap@{h} {acc_h:.1%}")

    model.load_state_dict(best["state"])
    model.requires_grad_(False).eval()
    metrics = evaluate(model, data, splits, latents, codebook, pcfg["eval_horizon"])
    metrics.update(best_epoch=best["epoch"], best_val_snap=best["key"][0], best_val_mse=best["key"][1],
                   select_horizon=h, median_one_step_error=median_one_step_error(model, val_one),
                   n_train_windows={str(k): len(train_sets[k]["z0"]) for k in ks}, history=history)
    return model, metrics


# --- outputs -------------------------------------------------------------------
def done_checks(metrics: dict) -> dict[str, bool]:
    p = metrics["pairs"]
    trained = (p["normal moves"]["correct"] + p["collisions"]["correct"]) / \
              (p["normal moves"]["total"] + p["collisions"]["total"])
    return {
        "one-step error clearly below persistence": metrics["one_step"]["ratio_trained"] <= PERSISTENCE_RATIO_PASS,
        "snap accuracy on trained pairs ~100%": trained >= TRAINED_PAIR_PASS,
        "held-out pair accuracy recorded": p["held-out (all)"]["total"] > 0,
    }


def print_report(metrics: dict) -> None:
    o = metrics["one_step"]
    print(f"\nBest epoch {metrics['best_epoch']}: val snap@{metrics['select_horizon']} "
          f"{metrics['best_val_snap']:.1%}, val {metrics['select_horizon']}-step mse {metrics['best_val_mse']:.5f}")
    print("\nOne-step latent MSE on test (standardised units)      model   persistence (z_hat = z)")
    for name in ("trained", *CATEGORIES):
        if name in o["mse_model"]:
            print(f"  {name:<22}{o['mse_model'][name]:>30.5f}{o['mse_persistence'][name]:>14.5f}")
    print(f"  ratio on trained transitions: {o['ratio_trained']:.4f}")

    print(f"\n{'Snap accuracy (1 step)':<24}{'test transitions':>17}{'all 100 pairs':>18}")
    for name in CATEGORIES:
        print(f"  {name:<22}{fmt_score(metrics['test_snap'][name]):>17}{fmt_score(metrics['pairs'][name]):>18}")

    print("\nHeld-out pairs, and any trained pair it gets wrong (from the codebook entry):")
    for d in metrics["pair_details"]:
        x, y, a = d["pair"]
        print(f"  {'ok   ' if d['correct'] else 'WRONG'} {'held-out' if d['heldout'] else 'TRAINED '} "
              f"({x},{y}) {ACTION_NAMES[a]:<5} {'collision' if d['collision'] else 'move':<9} "
              f"true {tuple(d['true'])}  pred {tuple(d['pred'])}")

    tw, aw = metrics["rollout_trained_windows"], metrics["rollout_all_windows"]
    print(f"\nImagined rollouts on test windows: snap accuracy at step 1..{len(tw['snap_acc'])}")
    print(f"  trained pairs only ({tw['n']:>4}): " + " ".join(f"{a:.0%}" for a in tw["snap_acc"]))
    print(f"  all windows        ({aw['n']:>4}): " + " ".join(f"{a:.0%}" for a in aw["snap_acc"]))
    print(f"\nMedian one-step error (val, Euclidean): {metrics['median_one_step_error']:.4f}")

    print()
    for name, ok in done_checks(metrics).items():
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")


def save_checkpoint(model: Predictor, cfg: dict, metrics: dict, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({
        "state_dict": model.state_dict(),
        "latent_dim": model.latent_dim,
        "n_actions": model.n_actions,
        "hidden": list(cfg["predictor"]["hidden"]),
        "latent_space": "standardised (encoder z_mean / z_std)",
        "median_one_step_error": metrics["median_one_step_error"],
        "best_epoch": metrics["best_epoch"],
        "seed": cfg["seed"],
    }, path)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the residual latent predictor (Stage 2).")
    parser.add_argument("--config", type=Path, default=None, help="config file (default: configs/single_map.yaml)")
    args = parser.parse_args()
    cfg = load_config(args.config)
    pcfg = cfg["predictor"]
    data = load_transitions(resolve(cfg["data"]["path"]))
    splits = load_splits(resolve(cfg["data"]["splits_path"]))
    encoder, enc_ckpt = load_encoder(resolve(cfg["encoder"]["checkpoint"]))
    if not enc_ckpt.get("gate_passed", False):
        raise SystemExit("the saved encoder did not pass the step 5 gate; retrain it first")

    latents = encode_latents(encoder, data)
    codebook = encoder.standardize(enc_ckpt["codebook"].float())
    print(f"Training predictor: hidden {pcfg['hidden']}, lr {pcfg['lr']}, batch {pcfg['batch_size']}, "
          f"{pcfg['epochs']} epochs, curriculum {pcfg['curriculum']}, seed {cfg['seed']}")
    model, metrics = train(cfg, data, splits, latents, codebook)
    print_report(metrics)

    ckpt = save_checkpoint(model, cfg, metrics, resolve(pcfg["checkpoint"]))
    mpath = resolve(pcfg["metrics"])
    mpath.write_text(json.dumps({**metrics, "done_checks": done_checks(metrics)}, indent=1) + "\n")
    print(f"\nSaved {ckpt}\n      {mpath}")
    if not all(done_checks(metrics).values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
