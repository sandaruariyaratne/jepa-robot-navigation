"""Train the Stage 0 numerical baseline (build plan step 3): `python -m training.train_numerical`.

Trains on the train split with the held-out (state, action) pairs removed,
picks the epoch with the lowest validation loss (validation also excludes the
held-out pairs, so selection never peeks at them), then reports exact-cell
accuracy separately for normal moves, collisions and held-out pairs.
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
from models import NumericalModel



def _tensors(ds: TransitionWindows) -> dict[str, torch.Tensor]:
    b = ds.batch(np.arange(len(ds)))
    return {
        "pos": torch.as_tensor(b["pos"], dtype=torch.float32),
        "action": torch.as_tensor(b["action"]),
        "next_pos": torch.as_tensor(b["next_pos"], dtype=torch.float32),
    }


def training_sets(data: dict, splits: dict) -> tuple[dict, dict]:
    """Train / val tensors, both without the held-out pairs."""
    held = splits["heldout_pairs"]
    train = _tensors(TransitionWindows(data, splits["train"], exclude_pairs=held))
    val = _tensors(TransitionWindows(data, splits["val"], exclude_pairs=held))
    return train, val


def _loss(model: NumericalModel, t: dict[str, torch.Tensor]) -> torch.Tensor:
    return F.mse_loss(model(t["pos"], t["action"]), model.normalize(t["next_pos"]))


@torch.no_grad()
def evaluate(model: NumericalModel, data: dict, splits: dict) -> dict:
    """Exact-cell accuracy by category, on val / test transitions and on every distinct pair."""
    model.eval()
    held = splits["heldout_pairs"]
    metrics: dict = {}
    for split in ("val", "test"):
        b = TransitionWindows(data, splits[split]).batch(np.arange(len(TransitionWindows(data, splits[split]))))
        pred = model.predict_cell(torch.as_tensor(b["pos"]), torch.as_tensor(b["action"])).numpy()
        correct = (pred == b["next_pos"]).all(axis=1)
        metrics[split] = score(correct, category_masks(b["pos"], b["action"], b["collision"], held))

    p = unique_pairs(data)
    raw = model.predict(torch.as_tensor(p["pos"]), torch.as_tensor(p["action"])).numpy()
    pred = np.round(raw).astype(np.int64)
    correct = (pred == p["next_pos"]).all(axis=1)
    masks = category_masks(p["pos"], p["action"], p["collision"], held)
    metrics["pairs"] = score(correct, masks)
    held_mask = masks["held-out (all)"]
    metrics["pair_details"] = [
        {
            "pair": [int(p["pos"][i, 0]), int(p["pos"][i, 1]), int(p["action"][i])],
            "heldout": bool(held_mask[i]),
            "collision": bool(p["collision"][i]),
            "true": p["next_pos"][i].tolist(),
            "pred": pred[i].tolist(),
            "pred_raw": [round(float(v), 3) for v in raw[i]],
            "correct": bool(correct[i]),
        }
        for i in range(len(correct))
        if held_mask[i] or not correct[i]  # every held-out pair, plus any trained pair it gets wrong
    ]
    return metrics


def train(cfg: dict, data: dict, splits: dict, verbose: bool = True) -> tuple[NumericalModel, dict]:
    ncfg = cfg["numerical"]
    seed = cfg["seed"]
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)

    tr, va = training_sets(data, splits)
    model = NumericalModel(ncfg["hidden"])
    model.set_normalization(tr["pos"].mean(0), tr["pos"].std(0))  # training split only
    opt = torch.optim.Adam(model.parameters(), lr=ncfg["lr"])
    n, bs = len(tr["action"]), ncfg["batch_size"]

    best_loss, best_state, best_epoch = float("inf"), None, 0
    history = []
    for epoch in range(1, ncfg["epochs"] + 1):
        model.train()
        perm = torch.as_tensor(rng.permutation(n))
        total = 0.0
        for s in range(0, n, bs):
            idx = perm[s:s + bs]
            loss = _loss(model, {k: v[idx] for k, v in tr.items()})
            opt.zero_grad()
            loss.backward()
            opt.step()
            total += loss.item() * len(idx)
        model.eval()
        with torch.no_grad():
            val_loss = _loss(model, va).item()
            val_acc = (model.predict_cell(va["pos"], va["action"]) == va["next_pos"].long()).all(1).float().mean().item()
        history.append({"epoch": epoch, "train_loss": total / n, "val_loss": val_loss, "val_acc": val_acc})
        if val_loss < best_loss:
            best_loss, best_state, best_epoch = val_loss, copy.deepcopy(model.state_dict()), epoch
        if verbose and (epoch == 1 or epoch % 10 == 0):
            print(f"  epoch {epoch:3d}  train {total / n:.5f}  val {val_loss:.5f}  val exact-cell {val_acc:.1%}")

    model.load_state_dict(best_state)
    metrics = evaluate(model, data, splits)
    metrics.update(best_epoch=best_epoch, best_val_loss=best_loss, history=history,
                   n_train=n, n_val=len(va["action"]))
    return model, metrics


def save_checkpoint(model: NumericalModel, cfg: dict, metrics: dict, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"state_dict": model.state_dict(), "hidden": list(cfg["numerical"]["hidden"]),
                "best_epoch": metrics["best_epoch"], "seed": cfg["seed"]}, path)
    return path


def load_checkpoint(path: str | Path) -> NumericalModel:
    ckpt = torch.load(path, map_location="cpu", weights_only=True)
    model = NumericalModel(ckpt["hidden"])
    model.load_state_dict(ckpt["state_dict"])
    return model.eval()


def print_report(metrics: dict) -> None:
    print(f"\nBest epoch {metrics['best_epoch']} (val loss {metrics['best_val_loss']:.6f}), "
          f"{metrics['n_train']} training transitions")
    print(f"\n{'Exact-cell accuracy':<22}{'test transitions':>17}{'val transitions':>18}{'distinct pairs':>18}")
    for name in CATEGORIES:
        print(f"  {name:<20}{fmt_score(metrics['test'][name]):>17}{fmt_score(metrics['val'][name]):>18}{fmt_score(metrics['pairs'][name]):>18}")
    print("\nHeld-out pairs (never trained on), and any trained pair it gets wrong:")
    for d in metrics["pair_details"]:
        x, y, a = d["pair"]
        tag = "held-out" if d["heldout"] else "TRAINED "
        kind = "collision" if d["collision"] else "move"
        mark = "ok   " if d["correct"] else "WRONG"
        print(f"  {mark} {tag} ({x},{y}) {ACTION_NAMES[a]:<5} {kind:<9} true {tuple(d['true'])}  "
              f"pred {tuple(d['pred'])}  raw ({d['pred_raw'][0]:.2f}, {d['pred_raw'][1]:.2f})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the numerical (x, y, a) -> next (x, y) baseline.")
    parser.add_argument("--config", type=Path, default=None, help="config file (default: configs/single_map.yaml)")
    args = parser.parse_args()
    cfg = load_config(args.config)
    data = load_transitions(resolve(cfg["data"]["path"]))
    splits = load_splits(resolve(cfg["data"]["splits_path"]))

    print(f"Training numerical baseline: hidden {cfg['numerical']['hidden']}, lr {cfg['numerical']['lr']}, "
          f"batch {cfg['numerical']['batch_size']}, {cfg['numerical']['epochs']} epochs, seed {cfg['seed']}")
    model, metrics = train(cfg, data, splits)
    print_report(metrics)

    ckpt = save_checkpoint(model, cfg, metrics, resolve(cfg["numerical"]["checkpoint"]))
    mpath = resolve(cfg["numerical"]["metrics"])
    mpath.write_text(json.dumps(metrics, indent=1) + "\n")
    print(f"\nSaved {ckpt}\n      {mpath}")


if __name__ == "__main__":
    main()
