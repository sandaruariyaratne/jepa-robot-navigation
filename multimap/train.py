"""Train the v1 model on the 70 training maps: `python -m multimap.train --config configs/multimap.yaml`.

Stage 1  autoencoder (v1 recipe) on the distinct frames of the training maps.
         Gate, on the *validation* maps (layouts never trained on): a linear probe
         finds the robot's cell from the latent, and the decoder draws the robot in
         the right cell. Checked at gate_epoch; on failure, retrain with robot pixels
         weighted 10x. Robot pixels come from the data: each map's background is the
         per-pixel median of its frames.
Stage 2  residual predictor z + f(z, a) on frozen, standardised latents, rollout
         curriculum K = 1 -> 2 -> 4, checkpoint chosen by 5-step snap accuracy on
         the validation maps. Snapping uses the codebook of the map the robot is on
         (its ~25 frames, from that map's own observations).

Cells are indexed absolutely here (id = y * cols + x, 30 ids) because the set of
free cells differs from map to map.
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
from environment import COLORS, save_png
from evaluation.probes import probe_kwargs, probe_report
from models import Decoder, Encoder, Predictor
from training.train_encoder import recon_loss
from training.train_world_model import k_for_epoch

from .collect import load
from .maps import load_maps

COLS, ROWS = 6, 5               # set from the data's frame size by set_grid (multimap.collect.load calls it)
N_CELLS = COLS * ROWS


def set_grid(cols: int, rows: int) -> None:
    """Grid size for the absolute cell ids below (6 x 5 for every experiment before Level C, 10 x 10 there)."""
    global COLS, ROWS, N_CELLS
    COLS, ROWS, N_CELLS = cols, rows, cols * rows


def set_grid_from_frames(frames, cell_px: int = 8) -> None:
    _, h, w = frames.shape[1:]
    set_grid(w // cell_px, h // cell_px)


def cell_ids(pos: np.ndarray) -> np.ndarray:
    pos = np.asarray(pos)
    return pos[..., 1] * COLS + pos[..., 0]


# --- data helpers ------------------------------------------------------------------------
def frame_split(data: dict, map_ids) -> np.ndarray:
    return np.flatnonzero(np.isin(data["frame_map"], list(map_ids)))


def map_backgrounds(data: dict, n_maps: int) -> np.ndarray:
    """Per-map background: per-pixel median of that map's frames (the robot is on one cell per frame)."""
    return np.stack([np.median(data["frames"][data["frame_map"] == m], axis=0).astype(np.uint8)
                     for m in range(n_maps)])


def decoded_robot_cells(decoded: np.ndarray, maps, frame_map: np.ndarray, cell_px: int = 8):
    """For each decoded frame: (predicted robot cell id, margin on the true cell is computed by the caller).

    Returns (pred_cell [N], robot_dist [N, 30], bg_dist [N, 30]); wall cells get inf robot distance.
    """
    img = np.asarray(decoded) * 255.0
    robot = np.array(COLORS["robot"], float)
    means = np.zeros((len(img), N_CELLS, 3))
    for y in range(ROWS):
        for x in range(COLS):
            means[:, y * COLS + x] = img[:, :, y * cell_px + 1:(y + 1) * cell_px, x * cell_px + 1:(x + 1) * cell_px].mean((2, 3))
    d_robot = np.linalg.norm(means - robot, axis=-1)
    bg = np.empty((len(img), N_CELLS, 3))
    for i, m in enumerate(frame_map):
        grid = maps[m]
        for y in range(ROWS):
            for x in range(COLS):
                c = y * COLS + x
                if (x, y) in grid.walls:
                    d_robot[i, c] = np.inf
                    bg[i, c] = COLORS["wall"]
                else:
                    bg[i, c] = COLORS["goal"] if (x, y) == grid.goal else COLORS["floor"]
    d_bg = np.linalg.norm(means - bg, axis=-1)
    return d_robot.argmin(1), d_robot, d_bg, means


def wall_accuracy(means: np.ndarray, maps, frame_map: np.ndarray) -> float:
    """Fraction of cells whose decoded colour is nearest the right kind (wall vs not wall)."""
    palette = np.array([COLORS["wall"], COLORS["floor"], COLORS["goal"], COLORS["robot"]], float)
    kind = np.linalg.norm(means[:, :, None] - palette, axis=-1).argmin(-1) == 0  # nearest is wall colour
    truth = np.zeros_like(kind)
    for i, m in enumerate(frame_map):
        for (x, y) in maps[m].walls:
            truth[i, y * COLS + x] = True
    return float((kind == truth).mean())


# --- stage 1: autoencoder ------------------------------------------------------------------
@torch.no_grad()
def encode(encoder: Encoder, frames, batch: int = 1024) -> np.ndarray:
    encoder.eval()
    x = torch.as_tensor(frames)
    return torch.cat([encoder(x[i:i + batch]) for i in range(0, len(x), batch)]).numpy()


@torch.no_grad()
def ae_gate(encoder, decoder, data, maps, tr, va, cfg) -> dict:
    e = cfg["multimap"]["encoder"]
    z_tr, z_va = encode(encoder, data["frames"][tr]), encode(encoder, data["frames"][va])
    y_tr, y_va = cell_ids(data["frame_pos"][tr]), cell_ids(data["frame_pos"][va])
    _, rep = probe_report(z_tr, y_tr, z_va, y_va, N_CELLS, **probe_kwargs(cfg))
    decoder.eval()
    dec = decoder(torch.as_tensor(z_va)).numpy()
    pred, d_robot, d_bg, means = decoded_robot_cells(dec, maps, data["frame_map"][va])
    own = np.arange(len(va))
    ok = (pred == y_va) & (d_bg[own, y_va] - d_robot[own, y_va] > 0)
    out = {"probe_val_accuracy": rep["accuracy"], "probe_train_accuracy": rep["train_accuracy"],
           "robot_decode_val": float(ok.mean()), "wall_decode_val": wall_accuracy(means, maps, data["frame_map"][va])}
    out["passed"] = bool(out["probe_val_accuracy"] >= e["gate_probe_accuracy"] and
                         out["robot_decode_val"] >= e["gate_robot_decode"])
    return out


def train_autoencoder(cfg, data, maps, splits, verbose=True):
    e = cfg["multimap"]["encoder"]
    tr, va = frame_split(data, splits["train"]), frame_split(data, splits["val"])
    bgs = torch.as_tensor(map_backgrounds(data, len(maps)))
    frames = torch.as_tensor(data["frames"])
    fmap = torch.as_tensor(data["frame_map"])
    weights = [e["robot_weight"]] + ([e["fallback_robot_weight"]] if e["fallback_robot_weight"] != e["robot_weight"] else [])
    attempts = []
    for attempt, rw in enumerate(weights):
        torch.manual_seed(cfg["seed"])
        rng = np.random.default_rng(cfg["seed"])
        enc, dec = Encoder(e["latent_dim"]), Decoder(e["latent_dim"])
        opt = torch.optim.Adam([*enc.parameters(), *dec.parameters()], lr=e["lr"])
        best = {"loss": float("inf")}
        history, gate_at, aborted = [], None, False
        if verbose:
            print(f"Autoencoder attempt {attempt + 1}: robot pixel weight {rw:g}, {len(tr)} training-map frames")
        for epoch in range(1, e["epochs"] + 1):
            enc.train()
            dec.train()
            order = torch.as_tensor(tr[rng.permutation(len(tr))])
            for s in range(0, len(tr), e["batch_size"]):
                idx = order[s:s + e["batch_size"]]
                x = frames[idx]
                mask = (x != bgs[fmap[idx]]).any(1, keepdim=True)
                loss = recon_loss(dec(enc(x)), x.float() / 255.0, mask, rw)
                opt.zero_grad()
                loss.backward()
                opt.step()
            if epoch % e["eval_every"] == 0 or epoch == e["epochs"]:
                enc.eval()
                dec.eval()
                with torch.no_grad():
                    x = frames[torch.as_tensor(va)]
                    rec = dec(enc(x))
                    mask = (x != bgs[fmap[torch.as_tensor(va)]]).any(1, keepdim=True)
                    tgt = x.float() / 255.0
                    vl = recon_loss(rec, tgt, mask, rw).item()
                    se = (rec - tgt) ** 2
                    robot_mse = ((se * mask).sum() / (mask.sum() * 3)).item()
                history.append({"epoch": epoch, "val_loss": vl, "val_mse": se.mean().item(), "val_robot_mse": robot_mse})
                if vl < best["loss"]:
                    best = {"loss": vl, "epoch": epoch, "enc": copy.deepcopy(enc.state_dict()),
                            "dec": copy.deepcopy(dec.state_dict())}
                if verbose and epoch % (e["eval_every"] * 3) == 0:
                    print(f"  epoch {epoch:4d}  val mse {se.mean().item():.6f}  val robot-pixel mse {robot_mse:.4f}",
                          flush=True)
            if epoch == e["gate_epoch"]:
                gate_at = ae_gate(enc, dec, data, maps, tr, va, cfg)
                if verbose:
                    print(f"  gate @ epoch {epoch}: probe val {gate_at['probe_val_accuracy']:.1%}, robot decodes "
                          f"{gate_at['robot_decode_val']:.1%}, walls {gate_at['wall_decode_val']:.1%} -> "
                          f"{'PASS' if gate_at['passed'] else 'FAIL'}", flush=True)
                if not gate_at["passed"] and attempt < len(weights) - 1:
                    aborted = True
                    break
        attempts.append({"robot_weight": rw, "aborted": aborted, "gate_at_gate_epoch": gate_at,
                         "best_epoch": None if aborted else best["epoch"], "history": history})
        if not aborted:
            break
    enc.load_state_dict(best["enc"])
    dec.load_state_dict(best["dec"])
    gate = ae_gate(enc, dec, data, maps, tr, va, cfg)
    z_tr = torch.as_tensor(encode(enc, data["frames"][tr]))
    enc.z_mean.copy_(z_tr.mean(0))
    enc.z_std.copy_(z_tr.std(0).clamp_min(1e-6))
    enc.freeze()
    dec.requires_grad_(False).eval()
    return enc, dec, {"gate": gate, "robot_weight": rw, "best_epoch": best["epoch"], "attempts": attempts}


def decode_examples(encoder, decoder, data, map_ids, per_map: int = 4, pad: int = 3) -> np.ndarray:
    """Rows of [original | decoded] pairs for a few frames of each given map."""
    rows = []
    for m in map_ids:
        idx = np.flatnonzero(data["frame_map"] == m)[:per_map]
        x = torch.as_tensor(data["frames"][idx])
        with torch.no_grad():
            dec = (decoder(encoder(x)).numpy() * 255).round().clip(0, 255).astype(np.uint8)
        tiles = []
        for o, d in zip(data["frames"][idx], dec):
            tiles += [o.transpose(1, 2, 0), np.full((40, 2, 3), 255, np.uint8), d.transpose(1, 2, 0),
                      np.full((40, pad * 3, 3), (40, 44, 52), np.uint8)]
        rows += [np.concatenate(tiles, 1), np.full((pad * 2, sum(t.shape[1] for t in tiles), 3), (40, 44, 52), np.uint8)]
    return np.concatenate(rows, 0)


# --- stage 2: predictor ----------------------------------------------------------------------
def latent_table(encoder: Encoder, data: dict) -> torch.Tensor:
    with torch.no_grad():
        return encoder.standardize(torch.as_tensor(encode(encoder, data["frames"])))


def codebooks(table: torch.Tensor, data: dict, n_maps: int) -> tuple[torch.Tensor, torch.Tensor]:
    """[M, 30, D] latent of each map's frame per cell, and [M, 30] mask of cells that have one."""
    cb = torch.zeros(n_maps, N_CELLS, table.shape[1])
    mask = torch.zeros(n_maps, N_CELLS, dtype=torch.bool)
    for f, (m, c) in enumerate(zip(data["frame_map"], cell_ids(data["frame_pos"]))):
        cb[m, c] = table[f]
        mask[m, c] = True
    return cb, mask


def snap_in_map(z: torch.Tensor, map_id: torch.Tensor, cb: torch.Tensor, mask: torch.Tensor):
    """Nearest codebook cell of each sample's own map. z [B, ..., D], map_id [B] -> (cell [B, ...], dist [B, ...])."""
    b = z.shape[0]
    flat = z.reshape(b, -1, z.shape[-1])
    d = torch.cdist(flat, cb[map_id])  # [B, K, 30]
    d = d.masked_fill(~mask[map_id][:, None, :], float("inf"))
    dist, idx = d.min(-1)
    return idx.reshape(z.shape[:-1]), dist.reshape(z.shape[:-1])


def windows(data: dict, map_ids, k: int) -> dict[str, torch.Tensor]:
    """K consecutive steps of one episode, from the given maps."""
    ok = np.isin(data["map_id"], list(map_ids))
    n = len(ok)
    ep, step = data["episode_id"], data["step"]
    valid = ok.copy()
    for j in range(1, k):
        nxt = np.zeros(n, bool)
        nxt[: n - j] = ok[j:] & (ep[j:] == ep[: n - j]) & (step[j:] == step[: n - j] + j)
        valid &= nxt
    starts = np.flatnonzero(valid)
    rows = starts[:, None] + np.arange(k)
    return {
        "obs": torch.as_tensor(data["obs_id"][starts]), "next": torch.as_tensor(data["next_id"][rows]),
        "action": torch.as_tensor(data["action"][rows]), "map": torch.as_tensor(data["map_id"][starts]),
        "next_cell": torch.as_tensor(cell_ids(data["next_pos"][rows])),
        "collision": torch.as_tensor(data["collision"][rows]), "wall_bump": torch.as_tensor(data["wall_bump"][rows]),
    }


@torch.no_grad()
def rollout_scores(predictor, table, t, cb, mask):
    pred = predictor.rollout(table[t["obs"]], t["action"])
    cell, _ = snap_in_map(pred, t["map"], cb, mask)
    return (cell == t["next_cell"]).float().mean(0), ((pred - table[t["next"]]) ** 2).mean(dim=(0, 2)), cell


def train_predictor(cfg, data, splits, table, cb, mask, verbose=True):
    p = cfg["multimap"]["predictor"]
    torch.manual_seed(cfg["seed"])
    rng = np.random.default_rng(cfg["seed"])
    model = Predictor(table.shape[1], 4, p["hidden"], p["last_layer_init"])
    opt = torch.optim.Adam(model.parameters(), lr=p["lr"])
    ks = sorted({k for _, k in p["curriculum"]})
    sets = {k: windows(data, splits["train"], k) for k in ks}
    h = p["select_horizon"]
    val_sel, val_one = windows(data, splits["val"], h), windows(data, splits["val"], 1)
    best, history = {"key": (-1.0, float("inf"))}, []
    for epoch in range(1, p["epochs"] + 1):
        k = k_for_epoch(p["curriculum"], epoch)
        t = sets[k]
        n = len(t["obs"])
        perm = torch.as_tensor(rng.permutation(n))
        model.train()
        tot = 0.0
        for s in range(0, n, p["batch_size"]):
            idx = perm[s:s + p["batch_size"]]
            loss = F.mse_loss(model.rollout(table[t["obs"][idx]], t["action"][idx]), table[t["next"][idx]])
            opt.zero_grad()
            loss.backward()
            opt.step()
            tot += loss.item() * len(idx)
        model.eval()
        acc, mse, _ = rollout_scores(model, table, val_sel, cb, mask)
        acc1, _, _ = rollout_scores(model, table, val_one, cb, mask)
        key = (float(acc[-1]), float(mse[-1]))
        history.append({"epoch": epoch, "k": k, "train_loss": tot / n, "val_snap_1": float(acc1[0]),
                        f"val_snap_{h}": key[0], f"val_mse_{h}": key[1]})
        if key[0] > best["key"][0] or (key[0] == best["key"][0] and key[1] < best["key"][1]):
            best = {"key": key, "epoch": epoch, "state": copy.deepcopy(model.state_dict())}
        if verbose:
            print(f"  epoch {epoch:3d}  K={k}  train {tot / n:.5f}  val snap@1 {float(acc1[0]):.1%}  "
                  f"val snap@{h} {key[0]:.1%}", flush=True)
    model.load_state_dict(best["state"])
    model.requires_grad_(False).eval()
    with torch.no_grad():
        err = torch.linalg.norm(model(table[val_one["obs"]], val_one["action"][:, 0]) - table[val_one["next"][:, 0]], dim=-1)
    return model, {"best_epoch": best["epoch"], "best_val_snap": best["key"][0], "best_val_mse": best["key"][1],
                   "median_one_step_error": float(err.median()), "history": history}


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the v1 model on the training maps.")
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args()
    cfg = load_config(args.config)
    mm = cfg["multimap"]
    maps, splits = load_maps(resolve(mm["maps_path"]))
    data = load(resolve(mm["data_path"]))

    enc, dec, ae = train_autoencoder(cfg, data, maps, splits)
    g = ae["gate"]
    print(f"\nAutoencoder: best epoch {ae['best_epoch']}, robot weight {ae['robot_weight']:g}; on unseen validation maps: "
          f"probe {g['probe_val_accuracy']:.1%}, robot decodes {g['robot_decode_val']:.1%}, "
          f"walls {g['wall_decode_val']:.1%} -> gate {'PASS' if g['passed'] else 'FAIL'}")
    e = mm["encoder"]
    for path in (e["checkpoint"], e["decoder_checkpoint"]):
        resolve(path).parent.mkdir(parents=True, exist_ok=True)
    torch.save({"state_dict": enc.state_dict(), "latent_dim": enc.latent_dim, "input_shape": list(enc.input_shape),
                "gate_passed": g["passed"], "best_epoch": ae["best_epoch"], "seed": cfg["seed"]}, resolve(e["checkpoint"]))
    torch.save({"state_dict": dec.state_dict(), "latent_dim": enc.latent_dim, "output_shape": list(dec.output_shape)},
               resolve(e["decoder_checkpoint"]))
    save_png(decode_examples(enc, dec, data, splits["test"][:5]), resolve(e["decodes_png"]), scale=3)
    resolve(e["metrics"]).write_text(json.dumps(ae, indent=1) + "\n")
    if not g["passed"]:
        raise SystemExit("encoder gate failed on the validation maps; not training the predictor")

    print("\nPredictor on the training maps:")
    table = latent_table(enc, data)
    cb, mask = codebooks(table, data, len(maps))
    model, pm = train_predictor(cfg, data, splits, table, cb, mask)
    p = mm["predictor"]
    torch.save({"state_dict": model.state_dict(), "latent_dim": model.latent_dim, "n_actions": model.n_actions,
                "hidden": list(p["hidden"]), "median_one_step_error": pm["median_one_step_error"],
                "best_epoch": pm["best_epoch"], "seed": cfg["seed"]}, resolve(p["checkpoint"]))
    resolve(p["metrics"]).write_text(json.dumps(pm, indent=1) + "\n")
    print(f"\nPredictor: best epoch {pm['best_epoch']}, val-map snap@{p['select_horizon']} {pm['best_val_snap']:.1%}, "
          f"median one-step error {pm['median_one_step_error']:.4f}")
    print(f"Saved {resolve(e['checkpoint'])}, decoder, predictor and metrics in {resolve(p['checkpoint']).parent}")


if __name__ == "__main__":
    main()
