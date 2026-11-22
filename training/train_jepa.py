"""v2 experiment 1: joint JEPA training (build plan step 12).

    python main.py train-jepa --config config_v2.yaml

v1 froze a pixel autoencoder and then fit a predictor on top; its latents had
no grid geometry, and held-out (state, action) pairs scored 1/10. Here the
encoder is trained *for prediction*:

    online encoder E      trained by the prediction loss and the anti-collapse terms
    target encoder E_tgt  exponential moving average of E (tau = 0.99), no gradient
    predictor P           residual MLP, as in v1: z_hat = z + f(z, a)

    loss = pred_w * || rollout_P(E(x_t), a_t..t+K-1) - E_tgt(x_t+1..t+K) ||^2
         + var_w  * mean_d relu(1 - std_d(E(frames)))         (keep every dimension alive)
         + cov_w  * sum_{i != j} cov(E(frames))_ij^2 / D       (decorrelate dimensions)

Variance / covariance are taken over the 25 distinct frames (each state
counted once). Same data, held-out pairs, rollout curriculum and checkpoint
selection (validation snap accuracy at 5 steps) as v1. After training the EMA
target encoder is frozen and saved with its codebook in the v1 checkpoint
formats, so the imagined graph, planners and evaluation run unchanged.

Speed: every frame is one of 25 distinct images, so each step encodes those
25 once and indexes into the result -- identical maths, ~10x faster.
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
from evaluation.probes import CellIndex
from models import Encoder, Predictor, snap
from training.train_world_model import done_checks, evaluate, k_for_epoch, print_report


# --- pieces ------------------------------------------------------------------------------
def frame_table(data: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Distinct frames [U, 3, H, W] and, per transition, the index of obs and next_obs in that table."""
    index: dict[bytes, int] = {}
    frames = []

    def ids(arr):
        out = np.empty(len(arr), dtype=np.int64)
        for i, f in enumerate(arr):
            key = f.tobytes()
            if key not in index:
                index[key] = len(frames)
                frames.append(f)
            out[i] = index[key]
        return out

    obs_id, next_id = ids(data["obs"]), ids(data["next_obs"])
    return np.stack(frames), obs_id, next_id


def vicreg_terms(z: torch.Tensor, eps: float = 1e-4) -> tuple[torch.Tensor, torch.Tensor]:
    """(variance hinge, off-diagonal covariance) of a batch of embeddings [N, D]."""
    z = z - z.mean(0)
    std = torch.sqrt(z.var(0) + eps)
    var_loss = F.relu(1.0 - std).mean()
    cov = (z.T @ z) / (len(z) - 1)
    off = cov - torch.diag(torch.diag(cov))
    return var_loss, (off ** 2).sum() / z.shape[1]


@torch.no_grad()
def ema_update(target: Encoder, online: Encoder, tau: float) -> None:
    for t, o in zip(target.parameters(), online.parameters()):
        t.mul_(tau).add_(o, alpha=1.0 - tau)


def coordinate_r2(codebook: np.ndarray, cells: np.ndarray) -> float:
    """How linearly the latents encode (x, y): R^2 of a least-squares fit codebook -> cell coordinates.

    25 points in 32-D can be fit exactly, so this uses the top principal components
    (as many as there are coordinates + 1) to ask whether the *dominant* directions
    of the latent space are the grid axes.
    """
    z = codebook - codebook.mean(0)
    u, s, _ = np.linalg.svd(z, full_matrices=False)
    feats = np.concatenate([u[:, :3] * s[:3], np.ones((len(z), 1))], axis=1)
    y = cells.astype(np.float64)
    coef, *_ = np.linalg.lstsq(feats, y, rcond=None)
    resid = ((feats @ coef - y) ** 2).sum()
    return float(1.0 - resid / ((y - y.mean(0)) ** 2).sum())


def effective_rank(codebook: np.ndarray) -> float:
    s = np.linalg.svd(codebook - codebook.mean(0), compute_uv=False)
    p = s / s.sum()
    return float(np.exp(-(p * np.log(p + 1e-12)).sum()))


# --- training ------------------------------------------------------------------------------
def _windows(data, episodes, k, held, obs_id, next_id):
    ds = TransitionWindows(data, episodes, k=k, exclude_pairs=held)
    rows = ds.starts[:, None] + np.arange(k)
    cells = CellIndex()
    return {
        "obs": torch.as_tensor(obs_id[ds.starts]),
        "next": torch.as_tensor(next_id[rows]),
        "action": torch.as_tensor(data["action"][rows]),
        "next_cell": torch.as_tensor(cells.ids(data["next_pos"][rows])),
    }


def codebook_ids(data: dict, splits: dict, obs_id: np.ndarray) -> np.ndarray:
    """Frame-table index of each cell's frame (entry i = cell i), from training transitions."""
    cells = CellIndex()
    tr = TransitionWindows(data, splits["train"])
    cell = cells.ids(data["pos"][tr.starts])
    out = np.full(len(cells), -1, dtype=np.int64)
    for c, f in zip(cell, obs_id[tr.starts]):
        if out[c] < 0:
            out[c] = f
    if (out < 0).any():
        raise ValueError("some cell never appears in the training frames")
    return out


@torch.no_grad()
def _val_scores(predictor, table, t, codebook):
    pred = predictor.rollout(table[t["obs"]], t["action"])
    idx, _ = snap(pred, codebook)
    return (idx == t["next_cell"]).float().mean(0), ((pred - table[t["next"]]) ** 2).mean(dim=(0, 2))


def train(cfg: dict, data: dict, splits: dict, verbose: bool = True) -> tuple[Encoder, Predictor, dict]:
    j = cfg["jepa"]
    seed = cfg["seed"]
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    held = splits["heldout_pairs"]

    frames_np, obs_id, next_id = frame_table(data)
    frames = torch.as_tensor(frames_np)
    cb_ids = torch.as_tensor(codebook_ids(data, splits, obs_id))

    online = Encoder(j["latent_dim"])
    target = copy.deepcopy(online).requires_grad_(False)
    predictor = Predictor(j["latent_dim"], 4, j["hidden"], j["last_layer_init"])
    opt = torch.optim.Adam([*online.parameters(), *predictor.parameters()], lr=j["lr"])

    ks = sorted({k for _, k in j["curriculum"]})
    train_sets = {k: _windows(data, splits["train"], k, held, obs_id, next_id) for k in ks}
    h = j["select_horizon"]
    val_sel = _windows(data, splits["val"], h, held, obs_id, next_id)

    best = {"key": (-1.0, float("inf")), "epoch": 0}
    history = []
    for epoch in range(1, j["epochs"] + 1):
        k = k_for_epoch(j["curriculum"], epoch)
        t = train_sets[k]
        n, bs = len(t["obs"]), j["batch_size"]
        perm = torch.as_tensor(rng.permutation(n))
        online.train()
        predictor.train()
        tot = {"loss": 0.0, "pred": 0.0, "var": 0.0, "cov": 0.0}
        for s in range(0, n, bs):
            idx = perm[s:s + bs]
            z_table = online(frames)                 # [U, D], gradient flows into the encoder
            with torch.no_grad():
                tgt_table = target(frames)
            pred = predictor.rollout(z_table[t["obs"][idx]], t["action"][idx])
            l_pred = F.mse_loss(pred, tgt_table[t["next"][idx]])
            l_var, l_cov = vicreg_terms(z_table)
            loss = j["pred_weight"] * l_pred + j["var_weight"] * l_var + j["cov_weight"] * l_cov
            opt.zero_grad()
            loss.backward()
            opt.step()
            ema_update(target, online, j["ema_tau"])
            for name, v in (("loss", loss), ("pred", l_pred), ("var", l_var), ("cov", l_cov)):
                tot[name] += v.item() * len(idx)

        target.eval()
        predictor.eval()
        with torch.no_grad():
            tgt_table = target(frames)
        acc, mse = _val_scores(predictor, tgt_table, val_sel, tgt_table[cb_ids])
        acc_h, mse_h = float(acc[-1]), float(mse[-1])
        row = {"epoch": epoch, "k": k, **{f"train_{n_}": v / n for n_, v in tot.items()},
               f"val_snap_{h}": acc_h, f"val_mse_{h}": mse_h, "val_snap_1": float(acc[0])}
        history.append(row)
        key = (acc_h, mse_h)
        if key[0] > best["key"][0] or (key[0] == best["key"][0] and key[1] < best["key"][1]):
            best = {"key": key, "epoch": epoch, "target": copy.deepcopy(target.state_dict()),
                    "predictor": copy.deepcopy(predictor.state_dict())}
        if verbose and (epoch == 1 or epoch % 5 == 0 or epoch in {s_ for s_, _ in j["curriculum"]}):
            print(f"  epoch {epoch:3d}  K={k}  pred {row['train_pred']:.5f}  var {row['train_var']:.4f}  "
                  f"cov {row['train_cov']:.4f}  val snap@1 {row['val_snap_1']:.1%}  val snap@{h} {acc_h:.1%}")

    target.load_state_dict(best["target"])
    predictor.load_state_dict(best["predictor"])
    target.freeze()
    predictor.requires_grad_(False).eval()

    # v1-format pieces: identity standardisation (latents are already unit-scale by the variance term)
    with torch.no_grad():
        table = target(frames)
    codebook = table[cb_ids]
    latents = {"z_obs": table[torch.as_tensor(obs_id)].numpy(), "z_next": table[torch.as_tensor(next_id)].numpy()}
    metrics = evaluate(predictor, data, splits, latents, codebook, j.get("eval_horizon", 10))
    val_one = _windows(data, splits["val"], 1, held, obs_id, next_id)
    with torch.no_grad():
        err = torch.linalg.norm(predictor(table[val_one["obs"]], val_one["action"][:, 0]) - table[val_one["next"][:, 0]],
                                dim=-1)
    cells = CellIndex()
    cb = codebook.numpy()
    metrics.update(
        best_epoch=best["epoch"], best_val_snap=best["key"][0], best_val_mse=best["key"][1], select_horizon=h,
        median_one_step_error=float(err.median()), history=history,
        n_distinct_frames=int(len(frames_np)),
        latent_geometry={"coordinate_r2_top3_pcs": coordinate_r2(cb, cells.cells),
                         "effective_rank": effective_rank(cb),
                         "min_dim_std": float(cb.std(0).min()), "mean_dim_std": float(cb.std(0).mean())},
    )
    return target, predictor, {**metrics, "codebook": codebook}


def save(target: Encoder, predictor: Predictor, metrics: dict, cfg: dict) -> tuple[Path, Path]:
    j = cfg["jepa"]
    cells = CellIndex()
    enc_path, pred_path = resolve(cfg["encoder"]["checkpoint"]), resolve(cfg["predictor"]["checkpoint"])
    enc_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"state_dict": target.state_dict(), "latent_dim": target.latent_dim,
                "input_shape": list(target.input_shape), "codebook": metrics["codebook"],
                "codebook_cells": torch.as_tensor(cells.cells), "robot_weight": None,
                "best_epoch": metrics["best_epoch"], "gate_passed": True, "seed": cfg["seed"],
                "trained_by": "joint JEPA (EMA target encoder)"}, enc_path)
    torch.save({"state_dict": predictor.state_dict(), "latent_dim": predictor.latent_dim,
                "n_actions": predictor.n_actions, "hidden": list(j["hidden"]),
                "latent_space": "JEPA target-encoder latents (identity standardisation)",
                "median_one_step_error": metrics["median_one_step_error"], "best_epoch": metrics["best_epoch"],
                "seed": cfg["seed"]}, pred_path)
    return enc_path, pred_path


def ablate_latent_dim(cfg: dict, data: dict, splits: dict, dims: list[int]) -> list[dict]:
    """Train one model per latent size (in memory, nothing saved) and compare fit, generalization, geometry."""
    rows = []
    for d in dims:
        c = {**cfg, "jepa": {**cfg["jepa"], "latent_dim": d}}
        _, _, m = train(c, data, splits, verbose=False)
        p = m["pairs"]
        trained = p["normal moves"]["correct"] + p["collisions"]["correct"]
        rows.append({"latent_dim": d, "trained_pairs": trained,
                     "heldout_moves": p["held-out moves"]["correct"],
                     "heldout_collisions": p["held-out collisions"]["correct"],
                     "val_snap_5": m["best_val_snap"], **m["latent_geometry"],
                     "rollout_all_10": m["rollout_all_windows"]["snap_acc"][-1]})
        r = rows[-1]
        print(f"  D={d:>2}: trained {r['trained_pairs']}/90, held-out moves {r['heldout_moves']}/7, bumps "
              f"{r['heldout_collisions']}/3, (x,y) R^2 {r['coordinate_r2_top3_pcs']:.2f}, eff. rank "
              f"{r['effective_rank']:.1f}, all-window snap@10 {r['rollout_all_10']:.0%}", flush=True)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Joint JEPA training (v2 experiment 1).")
    parser.add_argument("--config", type=Path, default=None, help="config file (use config_v2.yaml)")
    parser.add_argument("--ablate-latent-dim", default=None, metavar="2,4,8",
                        help="instead of training the main model, compare these latent sizes (nothing saved but a JSON)")
    args = parser.parse_args()
    cfg = load_config(args.config)
    if "jepa" not in cfg:
        raise SystemExit("this config has no `jepa:` section; run with --config config_v2.yaml")
    j = cfg["jepa"]
    data = load_transitions(resolve(cfg["data"]["path"]))
    splits = load_splits(resolve(cfg["data"]["splits_path"]))
    if args.ablate_latent_dim:
        dims = [int(v) for v in args.ablate_latent_dim.split(",")]
        print(f"Latent-size ablation: {dims}")
        rows = ablate_latent_dim(cfg, data, splits, dims)
        out = resolve(j["metrics"]).with_name("latent_dim_ablation.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(rows, indent=1) + "\n")
        print(f"Saved {out}")
        return
    print(f"Joint JEPA: latent {j['latent_dim']}, EMA tau {j['ema_tau']}, weights pred/var/cov "
          f"{j['pred_weight']}/{j['var_weight']}/{j['cov_weight']}, {j['epochs']} epochs, seed {cfg['seed']}")

    target, predictor, metrics = train(cfg, data, splits)
    print_report(metrics)
    g = metrics["latent_geometry"]
    print(f"\nLatent geometry: (x, y) from top-3 PCs R^2 {g['coordinate_r2_top3_pcs']:.3f}, effective rank "
          f"{g['effective_rank']:.1f}, per-dim std min {g['min_dim_std']:.2f} / mean {g['mean_dim_std']:.2f}")

    enc_path, pred_path = save(target, predictor, metrics, cfg)
    out = {k: v for k, v in metrics.items() if k != "codebook"}
    mpath = resolve(j["metrics"])
    mpath.write_text(json.dumps({**out, "done_checks": done_checks(metrics)}, indent=1) + "\n")
    resolve(cfg["predictor"]["metrics"]).write_text(json.dumps(out, indent=1) + "\n")
    print(f"\nSaved {enc_path}\n      {pred_path}\n      {mpath}")


if __name__ == "__main__":
    main()
