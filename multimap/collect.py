"""Collect random-action data on every map: `python -m multimap.collect --config config_multimap.yaml`.

Each map has only ~25 distinct frames (the robot on each free cell), so frames
are stored once in a table and transitions refer to them by index:

    frames [F, 3, 40, 48] uint8    frame_map [F]   frame_pos [F, 2]
    per transition: map_id, episode_id (global), step, action, obs_id, next_id,
                    pos, next_pos, collision, wall_bump (blocked by an interior wall, not the border)

pos / next_pos / collision / wall_bump are labels for evaluation only.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from config import load_config, resolve
from data.collect_data import save_npz
from environment import ACTION_DELTAS, GridWorld

from .maps import generate_maps, load_maps, save_maps, split_maps

FIELDS = ("frames", "frame_map", "frame_pos", "map_id", "episode_id", "step", "action", "obs_id", "next_id",
          "pos", "next_pos", "collision", "wall_bump")


def collect(maps, episodes_per_map: int, steps: int, seed: int, cell_px: int = 8) -> dict[str, np.ndarray]:
    index: dict[bytes, int] = {}
    frames, frame_map, frame_pos = [], [], []
    rows = {k: [] for k in FIELDS[3:]}

    def fid(obs, m, pos):
        key = obs.tobytes()
        if key not in index:
            index[key] = len(frames)
            frames.append(obs)
            frame_map.append(m)
            frame_pos.append(pos)
        return index[key]

    ep_global = 0
    for m, grid in enumerate(maps):
        env = GridWorld(grid, cell_px=cell_px, terminate_on_goal=False,
                        seed=int(np.random.SeedSequence([seed, m]).generate_state(1)[0]))
        for _ in range(episodes_per_map):
            obs = env.reset()
            for t in range(steps):
                pos, a = env.pos, env.sample_action()
                r = env.step(a)
                dx, dy = ACTION_DELTAS[a]
                intended = (pos[0] + dx, pos[1] + dy)
                wall_bump = r.collision and grid.in_bounds(intended)
                for k, v in (("map_id", m), ("episode_id", ep_global), ("step", t), ("action", a),
                             ("obs_id", fid(obs, m, pos)), ("next_id", fid(r.obs, m, r.pos)), ("pos", pos),
                             ("next_pos", r.pos), ("collision", r.collision), ("wall_bump", wall_bump)):
                    rows[k].append(v)
                obs = r.obs
            ep_global += 1

    out = {"frames": np.stack(frames), "frame_map": np.array(frame_map, dtype=np.int64),
           "frame_pos": np.array(frame_pos, dtype=np.int64)}
    for k, v in rows.items():
        dtype = bool if k in ("collision", "wall_bump") else np.int64
        out[k] = np.array(v, dtype=dtype)
    return out


def load(path: str | Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as z:
        return {k: z[k] for k in FIELDS}


def coverage(data: dict, maps) -> dict:
    """Per map: free cells with a frame (needed for its codebook) and (cell, action) pairs seen."""
    out = []
    for m, grid in enumerate(maps):
        cells = {tuple(p) for p in data["frame_pos"][data["frame_map"] == m]}
        sel = data["map_id"] == m
        pairs = {(int(x), int(y), int(a)) for (x, y), a in zip(data["pos"][sel], data["action"][sel])}
        out.append({"free": len(grid.free_cells()), "frames": len(cells), "pairs": len(pairs),
                    "all_pairs": 4 * len(grid.free_cells())})
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the maps and collect multi-map data.")
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args()
    cfg = load_config(args.config)
    mm = cfg["multimap"]
    maps = generate_maps(mm["n_maps"], cfg["seed"], mm["min_walls"], mm["max_walls"])
    splits = split_maps(len(maps), mm["split_fractions"], cfg["seed"])
    maps_path = save_maps(maps, splits, resolve(mm["maps_path"]))
    maps, splits = load_maps(maps_path)

    data = collect(maps, mm["episodes_per_map"], mm["steps_per_episode"], cfg["seed"], cfg["data"]["cell_px"])
    path = save_npz(data, resolve(mm["data_path"]))
    cov = coverage(data, maps)
    n = len(data["action"])
    print(f"{len(maps)} maps ({', '.join(f'{k} {len(v)}' for k, v in splits.items())}) -> {maps_path}")
    print(f"{n} transitions, {len(data['frames'])} distinct frames, collisions {data['collision'].mean():.1%} "
          f"(interior walls {data['wall_bump'].mean():.1%}) -> {path} ({path.stat().st_size / 1e6:.1f} MB)")
    full_frames = sum(c["frames"] == c["free"] for c in cov)
    full_pairs = sum(c["pairs"] == c["all_pairs"] for c in cov)
    print(f"maps with every free cell seen: {full_frames}/{len(maps)}; with every (cell, action) seen: "
          f"{full_pairs}/{len(maps)} (min {min(c['pairs'] / c['all_pairs'] for c in cov):.0%})")
    if full_frames < len(maps):
        raise SystemExit("some map is missing a frame for a free cell; its codebook would be incomplete")


if __name__ == "__main__":
    main()
