"""Linear position probe (build plan step 4): `python -m evaluation.probes` runs the sanity checks.

Answers one question: does this vector know where the robot is? A softmax
regression from a feature vector (a 32-D latent, later) to the robot's cell,
one of the 25 free cells. It is linear on purpose: a deep probe could dig the
position out of almost anything, a linear one only finds it if it is plainly
there.

Used in step 5 (encoder gate: >= 99% on validation), step 6 (predicted
latents) and step 9 (multi-step rollouts). True positions are labels here,
which is allowed: probes are evaluation tools, never part of a model.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from config import load_config, resolve
from data import TransitionWindows, load_splits, load_transitions
from environment import GridMap


class CellIndex:
    """Free cell <-> class id (0..24), row-major like GridMap.free_cells()."""

    def __init__(self, grid_map: GridMap | None = None) -> None:
        self.map = grid_map if grid_map is not None else GridMap()
        self.cells = np.array(self.map.free_cells(), dtype=np.int64)  # [25, 2] as (x, y)
        self._lookup = np.full((self.map.rows, self.map.cols), -1, dtype=np.int64)
        for i, (x, y) in enumerate(self.cells):
            self._lookup[y, x] = i

    def __len__(self) -> int:
        return len(self.cells)

    def ids(self, pos: np.ndarray) -> np.ndarray:
        """Positions [..., 2] (x, y) -> class ids [...]."""
        pos = np.asarray(pos, dtype=np.int64)
        x, y = pos[..., 0], pos[..., 1]
        if ((x < 0) | (x >= self.map.cols) | (y < 0) | (y >= self.map.rows)).any():
            raise ValueError("position outside the grid")
        ids = self._lookup[y, x]
        if (ids < 0).any():
            raise ValueError("position on a wall")
        return ids

    def positions(self, ids: np.ndarray) -> np.ndarray:
        """Class ids [...] -> positions [..., 2]."""
        return self.cells[np.asarray(ids, dtype=np.int64)]


class LinearProbe(nn.Module):
    """Softmax regression on standardised features. Standardisation stats are fit with the weights."""

    def __init__(self, dim: int, n_classes: int = 25) -> None:
        super().__init__()
        with torch.random.fork_rng():  # fit() re-initialises with its own seed anyway
            self.linear = nn.Linear(dim, n_classes)
        self.register_buffer("mean", torch.zeros(dim))
        self.register_buffer("std", torch.ones(dim))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.linear((x.float() - self.mean) / self.std)

    def fit(
        self,
        x: np.ndarray | torch.Tensor,
        y: np.ndarray | torch.Tensor,
        steps: int = 500,
        lr: float = 0.05,
        weight_decay: float = 1e-4,
        seed: int = 0,
    ) -> "LinearProbe":
        x = torch.as_tensor(x, dtype=torch.float32)
        y = torch.as_tensor(y, dtype=torch.int64)
        if x.ndim != 2 or len(x) != len(y):
            raise ValueError(f"expected x [N, D] and y [N], got {tuple(x.shape)} and {tuple(y.shape)}")
        self.mean.copy_(x.mean(0))
        self.std.copy_(x.std(0).clamp_min(1e-6))  # constant columns standardise to 0
        with torch.random.fork_rng():  # seeded init without touching the caller's RNG
            torch.manual_seed(seed)
            self.linear.reset_parameters()
        opt = torch.optim.Adam(self.parameters(), lr=lr, weight_decay=weight_decay)
        self.train()
        with torch.enable_grad():  # callers often evaluate under torch.no_grad()
            for _ in range(steps):  # full batch: deterministic and fast at this size
                loss = F.cross_entropy(self(x), y)
                opt.zero_grad()
                loss.backward()
                opt.step()
        return self.eval()

    @torch.no_grad()
    def predict(self, x: np.ndarray | torch.Tensor) -> np.ndarray:
        return self(torch.as_tensor(x, dtype=torch.float32)).argmax(-1).numpy()

    def score(self, x: np.ndarray | torch.Tensor, y: np.ndarray) -> float:
        return float((self.predict(x) == np.asarray(y)).mean())


def probe_report(
    train_x: np.ndarray,
    train_y: np.ndarray,
    eval_x: np.ndarray,
    eval_y: np.ndarray,
    n_classes: int = 25,
    **fit_kwargs,
) -> tuple[LinearProbe, dict]:
    """Fit on (train_x, train_y), score on (eval_x, eval_y).

    Report: accuracy, train_accuracy, per_cell accuracy (NaN for cells absent
    from eval), confusion [true, pred], chance (1 / n_classes) and majority
    (accuracy of always guessing the most common training cell).
    """
    probe = LinearProbe(np.shape(train_x)[1], n_classes).fit(train_x, train_y, **fit_kwargs)
    eval_y = np.asarray(eval_y)
    pred = probe.predict(eval_x)
    confusion = np.zeros((n_classes, n_classes), dtype=np.int64)
    np.add.at(confusion, (eval_y, pred), 1)
    support = confusion.sum(1)
    with np.errstate(invalid="ignore", divide="ignore"):
        per_cell = np.where(support > 0, np.diag(confusion) / support, np.nan)
    majority = np.bincount(np.asarray(train_y), minlength=n_classes).argmax()
    report = {
        "accuracy": float((pred == eval_y).mean()),
        "train_accuracy": probe.score(train_x, train_y),
        "per_cell": per_cell,
        "confusion": confusion,
        "chance": 1.0 / n_classes,
        "majority": float((eval_y == majority).mean()),
    }
    return probe, report


def probe_kwargs(cfg: dict) -> dict:
    p = cfg["probe"]
    return {"steps": p["steps"], "lr": p["lr"], "weight_decay": p["weight_decay"], "seed": cfg["seed"]}


def sanity_features(labels: np.ndarray, kind: str, dim: int = 32, n_classes: int = 25,
                    rng: np.random.Generator | None = None) -> np.ndarray:
    """'onehot': one-hot cell padded with zeros to `dim`; 'noise': Gaussian noise unrelated to the cell."""
    if kind == "onehot":
        x = np.zeros((len(labels), dim), dtype=np.float32)
        x[np.arange(len(labels)), labels] = 1.0
        return x
    if kind == "noise":
        rng = rng if rng is not None else np.random.default_rng(0)
        return rng.standard_normal((len(labels), dim)).astype(np.float32)
    raise ValueError(f"unknown kind {kind!r}")


def run_sanity_checks(cfg: dict, data: dict, splits: dict) -> dict[str, dict]:
    cells = CellIndex()
    train_y = cells.ids(TransitionWindows(data, splits["train"]).batch()["pos"])
    val_y = cells.ids(TransitionWindows(data, splits["val"]).batch()["pos"])
    rng = np.random.default_rng(cfg["seed"])
    results = {}
    for kind in ("onehot", "noise"):
        tx = sanity_features(train_y, kind, rng=rng)
        vx = sanity_features(val_y, kind, rng=rng)
        _, results[kind] = probe_report(tx, train_y, vx, val_y, len(cells), **probe_kwargs(cfg))
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Sanity-check the linear position probe.")
    parser.add_argument("--config", type=Path, default=None, help="config file (default: configs/single_map.yaml)")
    args = parser.parse_args()
    cfg = load_config(args.config)
    data = load_transitions(resolve(cfg["data"]["path"]))
    splits = load_splits(resolve(cfg["data"]["splits_path"]))

    results = run_sanity_checks(cfg, data, splits)
    one, noise = results["onehot"], results["noise"]
    print("Linear probe sanity checks: 32-D features -> 25 cells, fit on train, scored on val")
    print(f"  {'features':<22}{'train':>8}{'val':>8}")
    print(f"  {'one-hot position':<22}{one['train_accuracy']:8.1%}{one['accuracy']:8.1%}")
    print(f"  {'Gaussian noise':<22}{noise['train_accuracy']:8.1%}{noise['accuracy']:8.1%}")
    print(f"  chance {one['chance']:.1%}, always-majority-cell {noise['majority']:.1%}")

    ok_one = one["accuracy"] == 1.0
    ok_noise = noise["accuracy"] < 2.5 * noise["chance"]
    print(f"\n  one-hot = 100%: {'PASS' if ok_one else 'FAIL'}    noise near chance: {'PASS' if ok_noise else 'FAIL'}")
    if not (ok_one and ok_noise):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
