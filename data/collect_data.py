"""Collect random-action transitions (build plan step 2): `python -m data.collect_data`.

Writes one .npz with the dataset contract fields, then the episode split and
the held-out (state, action) pairs. Re-running with the same config gives a
byte-identical file.
"""

from __future__ import annotations

import argparse
import hashlib
import zipfile
from pathlib import Path

import numpy as np

from config import load_config, resolve
from environment import ACTION_NAMES, GridMap, GridWorld

from .dataset import TransitionWindows
from .splits import make_splits, pair_counts, pair_mask, save_splits

_ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)  # fixed timestamp so the file bytes are reproducible


def collect(
    episodes: int,
    steps_per_episode: int,
    seed: int,
    terminate_on_goal: bool = False,
    cell_px: int = 8,
    grid_map: GridMap | None = None,
) -> dict[str, np.ndarray]:
    """Run `episodes` random-start episodes of uniformly random actions."""
    env = GridWorld(grid_map, cell_px=cell_px, terminate_on_goal=terminate_on_goal, seed=seed)
    n = episodes * steps_per_episode
    c, h, w = env.obs_shape
    out = {
        "obs": np.empty((n, c, h, w), dtype=np.uint8),
        "action": np.empty(n, dtype=np.int64),
        "next_obs": np.empty((n, c, h, w), dtype=np.uint8),
        "episode_id": np.empty(n, dtype=np.int64),
        "step": np.empty(n, dtype=np.int64),
        "collision": np.empty(n, dtype=bool),
        "pos": np.empty((n, 2), dtype=np.int64),
        "next_pos": np.empty((n, 2), dtype=np.int64),
    }
    i = 0
    for ep in range(episodes):
        obs = env.reset()
        for t in range(steps_per_episode):
            pos = env.pos
            action = env.sample_action()
            r = env.step(action)
            out["obs"][i] = obs
            out["action"][i] = action
            out["next_obs"][i] = r.obs
            out["episode_id"][i] = ep
            out["step"][i] = t
            out["collision"][i] = r.collision
            out["pos"][i] = pos
            out["next_pos"][i] = r.pos
            obs = r.obs
            i += 1
            if r.done:  # only with terminate_on_goal=True
                break
    return {k: v[:i] for k, v in out.items()}


def save_npz(arrays: dict[str, np.ndarray], path: str | Path) -> Path:
    """Compressed .npz readable by np.load, with fixed zip timestamps (np.savez stamps the current time)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with zipfile.ZipFile(tmp, "w") as zf:
        for name, arr in arrays.items():
            info = zipfile.ZipInfo(f"{name}.npy", date_time=_ZIP_EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            with zf.open(info, "w", force_zip64=True) as f:
                np.lib.format.write_array(f, np.ascontiguousarray(arr), allow_pickle=False)
    tmp.replace(path)
    return path


def collect_from_config(cfg: dict) -> dict[str, np.ndarray]:
    d = cfg["data"]
    return collect(
        episodes=d["episodes"],
        steps_per_episode=d["steps_per_episode"],
        seed=cfg["seed"],
        terminate_on_goal=d["terminate_on_goal"],
        cell_px=d["cell_px"],
    )


def splits_from_config(cfg: dict, n_episodes: int, grid_map: GridMap | None = None) -> dict:
    d = cfg["data"]
    return make_splits(
        n_episodes=n_episodes,
        fractions=d["split_fractions"],
        n_heldout=d["heldout_pairs"],
        min_collisions=d["heldout_min_collisions"],
        seed=cfg["seed"],
        grid_map=grid_map or GridMap(),
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect the random-transition dataset.")
    parser.add_argument("--config", type=Path, default=None, help="config file (default: configs/single_map.yaml)")
    args = parser.parse_args()
    cfg = load_config(args.config)
    grid_map = GridMap()

    data = collect_from_config(cfg)
    data_path = save_npz(data, resolve(cfg["data"]["path"]))
    n_eps = int(data["episode_id"].max()) + 1
    splits = splits_from_config(cfg, n_eps, grid_map)
    splits_path = save_splits(splits, resolve(cfg["data"]["splits_path"]))

    n = len(data["action"])
    print(f"Collected {n} transitions from {n_eps} episodes (seed {cfg['seed']})")
    print(f"  obs {data['obs'].dtype} {list(data['obs'].shape[1:])}, collisions {data['collision'].mean():.1%}")
    print(f"  {data_path}  {data_path.stat().st_size / 1e6:.1f} MB  sha256 {_sha256(data_path)[:16]}")

    counts = pair_counts(data, grid_map)
    seen = sum(v > 0 for v in counts.values())
    vals = np.array(list(counts.values()))
    print(f"\nCoverage: {seen}/{len(counts)} (state, action) pairs seen; "
          f"count min {vals.min()}, median {int(np.median(vals))}, max {vals.max()}")
    rare = sorted(counts.items(), key=lambda kv: kv[1])[:3]
    print("  rarest: " + ", ".join(f"({x},{y}) {ACTION_NAMES[a]} x{c}" for (x, y, a), c in rare))

    print(f"\nSplit by episode: train {len(splits['train'])}, val {len(splits['val'])}, test {len(splits['test'])}"
          f"  -> {splits_path}")
    held = [tuple(p) for p in splits["heldout_pairs"]]
    in_split = {s: np.isin(data["episode_id"], splits[s]) for s in ("train", "val", "test")}
    print(f"Held-out pairs ({len(held)}, {sum(splits['heldout_collision'])} collisions)   occurrences train/val/test:")
    for p, coll in zip(held, splits["heldout_collision"]):
        m = pair_mask(data["pos"], data["action"], [p])
        occ = "/".join(str(int((m & in_split[s]).sum())) for s in ("train", "val", "test"))
        print(f"  ({p[0]},{p[1]}) {ACTION_NAMES[p[2]]:<5} {'collision' if coll else 'move':<9}  {occ}")

    print("\nPredictor training windows (train split):")
    for k in (1, 2, 4):
        full = len(TransitionWindows(data, splits["train"], k=k))
        kept = len(TransitionWindows(data, splits["train"], k=k, exclude_pairs=held))
        print(f"  K={k}: {kept} of {full} kept after dropping held-out pairs")

    if seen < len(counts):
        missing = [p for p, c in counts.items() if c == 0]
        raise SystemExit(f"\nFAIL: {len(missing)} pairs never visited: {missing}")


if __name__ == "__main__":
    main()
