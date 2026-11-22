"""Stage 1: train the autoencoder, check the gate, freeze the encoder (build plan step 5).

    python -m training.train_encoder

Gate (build plan): a linear probe on validation latents scores >= 99%, and the
decoder draws the robot in the right cell for all 25 positions. Checked at
epoch 30; if it fails, training restarts with robot pixels weighted 10x.

Robot pixels are found from the data, not the renderer: the background is the
per-pixel median of the training frames, and a robot pixel is any pixel that
differs from it. After training, the encoder is frozen and saved with the
per-dimension mean / std of its training latents and a codebook (the latents
of the 25 distinct frames, one per cell).
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

import numpy as np
import torch

from config import load_config, resolve
from data import TransitionWindows, load_splits, load_transitions
from environment import COLORS, GridMap, save_png
from evaluation.probes import CellIndex, probe_kwargs, probe_report
from models import Decoder, Encoder

GAP_COLOR = (40, 44, 52)


# --- data ----------------------------------------------------------------------
def split_frames(data: dict, episodes, cells: CellIndex) -> tuple[np.ndarray, np.ndarray]:
    """obs of every transition in these episodes, with the robot's cell id."""
    b = TransitionWindows(data, episodes).batch()
    return b["obs"], cells.ids(b["pos"])


def background_frame(frames: np.ndarray) -> np.ndarray:
    """Per-pixel median: the robot covers any one pixel in only a few % of frames."""
    return np.median(frames, axis=0).astype(np.uint8)


def robot_mask(frames: torch.Tensor, background: torch.Tensor) -> torch.Tensor:
    """[B, 1, H, W] True where a frame differs from the background."""
    return (frames != background).any(dim=1, keepdim=True)


def codebook_frames(frames: np.ndarray, cell_ids: np.ndarray, n_cells: int) -> np.ndarray:
    """One frame per cell id (0..n_cells-1), taken from the given (training) frames."""
    out = []
    for i in range(n_cells):
        idx = np.flatnonzero(cell_ids == i)
        if len(idx) == 0:
            raise ValueError(f"cell {i} never appears in the training frames")
        out.append(frames[idx[0]])
    return np.stack(out)


# --- loss ----------------------------------------------------------------------
def recon_loss(recon: torch.Tensor, target: torch.Tensor, mask: torch.Tensor, robot_weight: float) -> torch.Tensor:
    """Pixel MSE; robot pixels count robot_weight times (normalised by total weight)."""
    se = (recon - target) ** 2
    if robot_weight == 1.0:
        return se.mean()
    w = 1.0 + (robot_weight - 1.0) * mask.float()
    return (se * w).sum() / (w.sum() * se.shape[1])


# --- gate ----------------------------------------------------------------------
@torch.no_grad()
def encode(encoder: Encoder, frames: np.ndarray | torch.Tensor, batch: int = 1024) -> np.ndarray:
    encoder.eval()
    frames = torch.as_tensor(frames)
    return torch.cat([encoder(frames[i:i + batch]) for i in range(0, len(frames), batch)]).numpy()


def decoded_robot_cells(decoded: np.ndarray, cells: CellIndex, cell_px: int) -> tuple[np.ndarray, np.ndarray]:
    """Where does each decoded frame show the robot?

    decoded: [N, 3, H, W] floats in [0, 1]. For every free cell, the mean colour
    of its interior is compared with the robot colour; the closest cell is the
    predicted robot cell. Also returns, per cell, the distance-to-robot and
    distance-to-own-background so callers can check the robot is clearly drawn.
    Returns (robot_cell_ids [N], margin [N, n_cells]): margin > 0 means a cell
    looks more like robot than like its own background.
    """
    img = np.asarray(decoded) * 255.0
    robot = np.array(COLORS["robot"], dtype=np.float64)
    goal = cells.map.goal
    means, bgs = [], []
    for x, y in cells.cells:
        ys, xs = slice(y * cell_px + 1, (y + 1) * cell_px), slice(x * cell_px + 1, (x + 1) * cell_px)
        means.append(img[:, :, ys, xs].mean(axis=(2, 3)))  # [N, 3]
        bgs.append(COLORS["goal"] if (x, y) == goal else COLORS["floor"])
    means = np.stack(means, axis=1)  # [N, n_cells, 3]
    d_robot = np.linalg.norm(means - robot, axis=-1)
    d_bg = np.linalg.norm(means - np.array(bgs, dtype=np.float64), axis=-1)
    return d_robot.argmin(axis=1), d_bg - d_robot


@torch.no_grad()
def check_gate(encoder: Encoder, decoder: Decoder, sets: dict, cfg: dict) -> dict:
    """Probe accuracy on validation latents + robot placement in the 25 decodes."""
    ecfg = cfg["encoder"]
    z_tr, z_va = encode(encoder, sets["train_x"]), encode(encoder, sets["val_x"])
    _, rep = probe_report(z_tr, sets["train_y"], z_va, sets["val_y"], len(sets["cells"]), **probe_kwargs(cfg))
    decoder.eval()
    decoded = decoder(torch.as_tensor(encode(encoder, sets["codebook_x"]))).numpy()
    pred, margin = decoded_robot_cells(decoded, sets["cells"], cfg["data"]["cell_px"])
    true = np.arange(len(sets["cells"]))
    own_margin = margin[true, true]
    decode_ok = (pred == true) & (own_margin > 0)
    return {
        "probe_val_accuracy": rep["accuracy"],
        "probe_train_accuracy": rep["train_accuracy"],
        "probe_per_cell": [None if np.isnan(v) else float(v) for v in rep["per_cell"]],
        "decodes_correct": int(decode_ok.sum()),
        "decode_ok": decode_ok.tolist(),
        "decode_pred_cell": pred.tolist(),
        "decode_margin": [round(float(v), 1) for v in own_margin],
        "passed": bool(rep["accuracy"] >= ecfg["gate_probe_accuracy"] and decode_ok.all()),
        "_decoded": decoded,
    }


def _public(gate: dict) -> dict:
    return {k: v for k, v in gate.items() if not k.startswith("_")}


# --- training ------------------------------------------------------------------
def prepare_sets(data: dict, splits: dict) -> dict:
    cells = CellIndex()
    train_x, train_y = split_frames(data, splits["train"], cells)
    val_x, val_y = split_frames(data, splits["val"], cells)
    return {
        "cells": cells,
        "train_x": train_x, "train_y": train_y,
        "val_x": val_x, "val_y": val_y,
        "background": background_frame(train_x),  # training split only
        "codebook_x": codebook_frames(train_x, train_y, len(cells)),
    }


@torch.no_grad()
def _val_losses(encoder, decoder, val, bg, robot_weight, batch=1000) -> dict:
    encoder.eval()
    decoder.eval()
    tot = {"weighted": 0.0, "mse": 0.0, "robot_mse": 0.0}
    robot_px = 0
    for i in range(0, len(val), batch):
        x = val[i:i + batch]
        target = x.float() / 255.0
        recon = decoder(encoder(x))
        mask = robot_mask(x, bg)
        se = (recon - target) ** 2
        tot["weighted"] += recon_loss(recon, target, mask, robot_weight).item() * len(x)
        tot["mse"] += se.mean().item() * len(x)
        tot["robot_mse"] += (se * mask).sum().item()
        robot_px += mask.sum().item() * se.shape[1]
    n = len(val)
    return {"weighted": tot["weighted"] / n, "mse": tot["mse"] / n, "robot_mse": tot["robot_mse"] / max(robot_px, 1)}


def train_attempt(cfg: dict, sets: dict, robot_weight: float, abort_on_gate: bool, verbose: bool) -> dict:
    ecfg = cfg["encoder"]
    seed = cfg["seed"]
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    encoder, decoder = Encoder(ecfg["latent_dim"]), Decoder(ecfg["latent_dim"])
    opt = torch.optim.Adam([*encoder.parameters(), *decoder.parameters()], lr=ecfg["lr"])

    train_x = torch.as_tensor(sets["train_x"])
    val_x = torch.as_tensor(sets["val_x"])
    bg = torch.as_tensor(sets["background"])
    n, bs = len(train_x), ecfg["batch_size"]

    best = {"loss": float("inf"), "epoch": 0, "enc": None, "dec": None}
    history, gate_check = [], None
    for epoch in range(1, ecfg["epochs"] + 1):
        encoder.train()
        decoder.train()
        perm = torch.as_tensor(rng.permutation(n))
        total = 0.0
        for s in range(0, n, bs):
            x = train_x[perm[s:s + bs]]
            loss = recon_loss(decoder(encoder(x)), x.float() / 255.0, robot_mask(x, bg), robot_weight)
            opt.zero_grad()
            loss.backward()
            opt.step()
            total += loss.item() * len(x)
        val = _val_losses(encoder, decoder, val_x, bg, robot_weight)
        history.append({"epoch": epoch, "train_loss": total / n, **{f"val_{k}": v for k, v in val.items()}})
        if val["weighted"] < best["loss"]:
            best = {"loss": val["weighted"], "epoch": epoch,
                    "enc": copy.deepcopy(encoder.state_dict()), "dec": copy.deepcopy(decoder.state_dict())}
        if verbose and (epoch == 1 or epoch % 5 == 0):
            print(f"  epoch {epoch:3d}  train {total / n:.6f}  val mse {val['mse']:.6f}  "
                  f"val robot-pixel mse {val['robot_mse']:.4f}")
        if epoch == ecfg["gate_epoch"]:
            gate_check = check_gate(encoder, decoder, sets, cfg)
            if verbose:
                print(f"  gate @ epoch {epoch}: probe val {gate_check['probe_val_accuracy']:.1%}, "
                      f"decodes {gate_check['decodes_correct']}/{len(sets['cells'])} -> "
                      f"{'PASS' if gate_check['passed'] else 'FAIL'}")
            if abort_on_gate and not gate_check["passed"]:
                return {"encoder": encoder, "decoder": decoder, "aborted": True, "robot_weight": robot_weight,
                        "history": history, "gate_check": _public(gate_check), "best_epoch": None}

    encoder.load_state_dict(best["enc"])
    decoder.load_state_dict(best["dec"])
    return {"encoder": encoder, "decoder": decoder, "aborted": False, "robot_weight": robot_weight,
            "history": history, "gate_check": _public(gate_check) if gate_check else None,
            "best_epoch": best["epoch"]}


def train(cfg: dict, data: dict, splits: dict, verbose: bool = True) -> tuple[Encoder, Decoder, dict, np.ndarray]:
    """Returns (frozen encoder with stats, decoder, metrics, decoded codebook frames)."""
    ecfg = cfg["encoder"]
    sets = prepare_sets(data, splits)
    weights = [ecfg["robot_weight"]]
    if ecfg["fallback_robot_weight"] != ecfg["robot_weight"]:
        weights.append(ecfg["fallback_robot_weight"])

    attempts = []
    for i, rw in enumerate(weights):
        if verbose:
            print(f"Attempt {i + 1}: robot pixel weight {rw:g}")
        result = train_attempt(cfg, sets, rw, abort_on_gate=i < len(weights) - 1, verbose=verbose)
        attempts.append({k: result[k] for k in ("robot_weight", "aborted", "best_epoch", "gate_check", "history")})
        if not result["aborted"]:
            break
        if verbose:
            print(f"  gate not met after {ecfg['gate_epoch']} epochs: retraining with robot pixels weighted "
                  f"{weights[i + 1]:g}x\n")

    encoder, decoder = result["encoder"], result["decoder"]
    gate = check_gate(encoder, decoder, sets, cfg)
    decoded = gate.pop("_decoded")

    # Freeze, then attach training-latent statistics and the codebook.
    z_train = torch.as_tensor(encode(encoder, sets["train_x"]))
    encoder.z_mean.copy_(z_train.mean(0))
    encoder.z_std.copy_(z_train.std(0).clamp_min(1e-6))
    encoder.freeze()
    decoder.requires_grad_(False).eval()
    codebook = encode(encoder, sets["codebook_x"])
    final_val = _val_losses(encoder, decoder, torch.as_tensor(sets["val_x"]),
                            torch.as_tensor(sets["background"]), result["robot_weight"])

    metrics = {
        "passed": gate["passed"],
        "robot_weight": result["robot_weight"],
        "best_epoch": result["best_epoch"],
        "gate": gate,
        "val_mse": final_val["mse"],
        "val_robot_pixel_mse": final_val["robot_mse"],
        "attempts": attempts,
        "n_train_frames": int(len(sets["train_x"])),
        "n_val_frames": int(len(sets["val_x"])),
        "codebook": codebook,
        "codebook_frames": sets["codebook_x"],
    }
    return encoder, decoder, metrics, decoded


# --- outputs -------------------------------------------------------------------
def decode_mosaic(originals: np.ndarray, decoded: np.ndarray, cells: CellIndex, pad: int = 4) -> np.ndarray:
    """HWC uint8 image laid out like the grid: each free cell shows [original | decoded]."""
    _, h, w = originals.shape[1:]
    tile_w = 2 * w + 2
    rows, cols = cells.map.rows, cells.map.cols
    canvas = np.empty((pad + rows * (h + pad), pad + cols * (tile_w + pad), 3), dtype=np.uint8)
    canvas[:] = GAP_COLOR
    dec = np.clip(np.round(np.asarray(decoded) * 255.0), 0, 255).astype(np.uint8)
    for i, (x, y) in enumerate(cells.cells):
        top, left = pad + y * (h + pad), pad + x * (tile_w + pad)
        canvas[top:top + h, left:left + w] = originals[i].transpose(1, 2, 0)
        canvas[top:top + h, left + w + 2:left + tile_w] = dec[i].transpose(1, 2, 0)
    return canvas


def save_checkpoints(encoder: Encoder, decoder: Decoder, metrics: dict, cfg: dict) -> tuple[Path, Path]:
    ecfg = cfg["encoder"]
    enc_path, dec_path = resolve(ecfg["checkpoint"]), resolve(ecfg["decoder_checkpoint"])
    enc_path.parent.mkdir(parents=True, exist_ok=True)
    cells = CellIndex()
    torch.save({
        "state_dict": encoder.state_dict(),  # includes z_mean / z_std
        "latent_dim": encoder.latent_dim,
        "input_shape": list(encoder.input_shape),
        "codebook": torch.as_tensor(metrics["codebook"]),       # [25, latent_dim], raw latents
        "codebook_cells": torch.as_tensor(cells.cells),          # [25, 2] (x, y), for evaluation only
        "robot_weight": metrics["robot_weight"],
        "best_epoch": metrics["best_epoch"],
        "gate_passed": metrics["passed"],
        "seed": cfg["seed"],
    }, enc_path)
    torch.save({"state_dict": decoder.state_dict(), "latent_dim": encoder.latent_dim,
                "output_shape": list(decoder.output_shape)}, dec_path)
    return enc_path, dec_path


def print_report(metrics: dict, cells: CellIndex) -> None:
    g = metrics["gate"]
    print(f"\nSelected: robot weight {metrics['robot_weight']:g}, best epoch {metrics['best_epoch']}")
    print(f"  val pixel MSE {metrics['val_mse']:.6f}, robot-pixel MSE {metrics['val_robot_pixel_mse']:.4f}")
    print(f"  probe accuracy: val {g['probe_val_accuracy']:.2%}, train {g['probe_train_accuracy']:.2%} "
          f"(gate >= 99%)")
    print(f"  decodes with the robot in the right cell: {g['decodes_correct']}/{len(cells)}")
    bad = [i for i, ok in enumerate(g["decode_ok"]) if not ok]
    for i in bad:
        x, y = cells.cells[i]
        px, py = cells.cells[g["decode_pred_cell"][i]]
        print(f"    cell ({x},{y}): robot drawn nearest ({px},{py}), margin {g['decode_margin'][i]}")
    print(f"  weakest decode margin: {min(g['decode_margin']):.1f} (colour distance; > 0 means visible)")
    print(f"\nGate: {'PASS' if metrics['passed'] else 'FAIL'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Train and freeze the autoencoder (Stage 1).")
    parser.add_argument("--config", type=Path, default=None, help="config file (default: config.yaml)")
    args = parser.parse_args()
    cfg = load_config(args.config)
    ecfg = cfg["encoder"]
    data = load_transitions(resolve(cfg["data"]["path"]))
    splits = load_splits(resolve(cfg["data"]["splits_path"]))
    print(f"Training autoencoder: latent {ecfg['latent_dim']}, lr {ecfg['lr']}, batch {ecfg['batch_size']}, "
          f"up to {ecfg['epochs']} epochs, gate checked at epoch {ecfg['gate_epoch']}, seed {cfg['seed']}")

    encoder, decoder, metrics, decoded = train(cfg, data, splits)
    cells = CellIndex(GridMap())
    print_report(metrics, cells)

    enc_path, dec_path = save_checkpoints(encoder, decoder, metrics, cfg)
    png = save_png(decode_mosaic(metrics["codebook_frames"], decoded, cells), resolve(ecfg["decodes_png"]), scale=3)
    out = {k: v for k, v in metrics.items() if k not in ("codebook", "codebook_frames")}
    mpath = resolve(ecfg["metrics"])
    mpath.write_text(json.dumps(out, indent=1) + "\n")
    print(f"\nSaved {enc_path}\n      {dec_path}\n      {mpath}\n      {png}")
    if not metrics["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
