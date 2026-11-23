"""Joint JEPA (v2) on the 70 training maps: `python -m multimap.train_jepa --config configs/multimap_jepa.yaml`.

Same objective as training/train_jepa.py (online encoder + EMA target encoder +
residual predictor, VICReg variance / covariance terms), same data, split,
per-map codebooks and checkpoint selection as the multi-map v1 run
(multimap/train.py), so `python -m multimap.evaluate` compares the two directly.

What changes for 100 maps: there are ~1,770 distinct training-map frames, not
25, so encoding the whole frame table every step (the single-map trick) is too
slow. Each step instead picks `maps_per_step` training maps, encodes their
~25 frames each once (online and target), and takes `windows_per_step` windows
from those maps. The variance / covariance terms use the same frames, so they
see several layouts at once. Training is counted in steps; the curriculum
K = 1 -> 2 -> 4 switches at the given steps.
"""

from __future__ import annotations

import argparse
import copy
import json
import time
from pathlib import Path

import numpy as np
import torch
from torch.nn import functional as F

from config import load_config, resolve
from evaluation.probes import probe_kwargs, probe_report
from models import Decoder, Encoder, Predictor
from training.train_encoder import recon_loss
from training.train_jepa import effective_rank, ema_update, vicreg_terms
from training.train_world_model import k_for_epoch

from .collect import load
from .maps import load_maps
from . import train as T
from .train import cell_ids, codebooks, encode, frame_split, map_backgrounds, rollout_scores, set_grid_from_frames, windows


@torch.no_grad()
def full_table(encoder: Encoder, frames: torch.Tensor, batch: int = 1024) -> torch.Tensor:
    encoder.eval()
    return torch.cat([encoder(frames[i:i + batch]) for i in range(0, len(frames), batch)])


def by_map(t: dict, map_ids) -> dict[int, np.ndarray]:
    m = t["map"].numpy()
    return {int(i): np.flatnonzero(m == i) for i in map_ids}


def train(cfg: dict, data: dict, splits: dict, n_maps: int, verbose: bool = True):
    j = cfg["multimap"]["jepa"]
    seed = cfg["seed"]
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    set_grid_from_frames(data["frames"])
    frames = torch.as_tensor(data["frames"])
    frames_of = {m: np.flatnonzero(data["frame_map"] == m) for m in range(n_maps)}

    objective = j.get("objective", "jepa")      # jepa: predict target latents; pixel: predict frames via a decoder
    target_kind = j.get("target", "ema")        # ema: slow copy of the online encoder; online: the online encoder, stop-grad
    if objective not in ("jepa", "pixel") or target_kind not in ("ema", "online"):
        raise ValueError(f"unknown objective / target: {objective} / {target_kind}")
    online = Encoder(j["latent_dim"], tuple(data["frames"].shape[1:]))
    target = copy.deepcopy(online).requires_grad_(False)
    predictor = Predictor(j["latent_dim"], 4, j["hidden"], j["last_layer_init"])
    params = [*online.parameters(), *predictor.parameters()]
    if objective == "pixel":
        decoder = Decoder(j["latent_dim"])
        params += list(decoder.parameters())
        bgs = torch.as_tensor(map_backgrounds(data, n_maps))
        fmap = torch.as_tensor(data["frame_map"])
        rw = j.get("recon_robot_weight", 10.0)
    opt = torch.optim.Adam(params, lr=j["lr"])
    use_ema = objective == "jepa" and target_kind == "ema"
    enc_eval = target if use_ema else online      # the encoder that is evaluated, selected and saved

    train_maps = list(splits["train"])
    ks = sorted({k for _, k in j["curriculum"]})
    sets = {k: windows(data, train_maps, k) for k in ks}
    rows_of = {k: by_map(sets[k], train_maps) for k in ks}
    h = j["select_horizon"]
    val_sel, val_one = windows(data, splits["val"], h), windows(data, splits["val"], 1)

    best, history = {"key": (-1.0, float("inf")), "step": 0}, []
    queue: list[int] = []
    tot = {"loss": 0.0, "pred": 0.0, "var": 0.0, "cov": 0.0}
    t0 = time.perf_counter()
    for step in range(1, j["steps"] + 1):
        k = k_for_epoch(j["curriculum"], step)
        t = sets[k]
        if len(queue) < j["maps_per_step"]:
            queue += rng.permutation(train_maps).tolist()
        group, queue = queue[: j["maps_per_step"]], queue[j["maps_per_step"]:]

        fids = np.concatenate([frames_of[m] for m in group])           # frames of these maps, global ids
        local = torch.full((len(frames),), -1, dtype=torch.long)
        local[torch.as_tensor(fids)] = torch.arange(len(fids))
        pool = np.concatenate([rows_of[k][m] for m in group])
        idx = torch.as_tensor(rng.choice(pool, size=min(j["windows_per_step"], len(pool)), replace=False))

        online.train()
        predictor.train()
        x = frames[torch.as_tensor(fids)]
        z = online(x)
        pred = predictor.rollout(z[local[t["obs"][idx]]], t["action"][idx])
        if objective == "jepa":
            if use_ema:
                with torch.no_grad():
                    z_tgt = target(x)
            else:
                z_tgt = z.detach()
            l_pred = F.mse_loss(pred, z_tgt[local[t["next"][idx]]])
            l_var, l_cov = vicreg_terms(z)
            loss = j["pred_weight"] * l_pred + j["var_weight"] * l_var + j["cov_weight"] * l_cov
        else:
            # generative baseline: reconstruct the frames and decode every imagined step into the next frame
            gids = torch.as_tensor(fids)
            l_rec = recon_loss(decoder(z), x.float() / 255.0, (x != bgs[fmap[gids]]).any(1, keepdim=True), rw)
            nxt = t["next"][idx].reshape(-1)
            xn = frames[nxt]
            l_pred = recon_loss(decoder(pred.reshape(-1, pred.shape[-1])), xn.float() / 255.0,
                                (xn != bgs[fmap[nxt]]).any(1, keepdim=True), rw)
            with torch.no_grad():
                l_var, l_cov = vicreg_terms(z)          # logged only
            loss = l_rec + j["pred_weight"] * l_pred
        opt.zero_grad()
        loss.backward()
        opt.step()
        if use_ema:
            ema_update(target, online, j["ema_tau"])
        for name, v in (("loss", loss), ("pred", l_pred), ("var", l_var), ("cov", l_cov)):
            tot[name] += v.item()

        if step % j["eval_every"] == 0 or step == j["steps"]:
            n = j["eval_every"] if step % j["eval_every"] == 0 else step % j["eval_every"]
            predictor.eval()
            table = full_table(enc_eval, frames)
            cb, mask = codebooks(table, data, n_maps)
            acc, mse, _ = rollout_scores(predictor, table, val_sel, cb, mask)
            acc1, _, _ = rollout_scores(predictor, table, val_one, cb, mask)
            row = {"step": step, "k": k, **{f"train_{n_}": v / n for n_, v in tot.items()},
                   "val_snap_1": float(acc1[0]), f"val_snap_{h}": float(acc[-1]), f"val_mse_{h}": float(mse[-1])}
            history.append(row)
            key = (row[f"val_snap_{h}"], row[f"val_mse_{h}"])
            if key[0] > best["key"][0] or (key[0] == best["key"][0] and key[1] < best["key"][1]):
                best = {"key": key, "step": step, "target": copy.deepcopy(enc_eval.state_dict()),
                        "predictor": copy.deepcopy(predictor.state_dict())}
            if verbose:
                print(f"  step {step:5d}  K={k}  pred {row['train_pred']:.4f}  var {row['train_var']:.3f}  "
                      f"cov {row['train_cov']:.3f}  val snap@1 {row['val_snap_1']:.1%}  val snap@{h} {key[0]:.1%}  "
                      f"({time.perf_counter() - t0:.0f}s)", flush=True)
            tot = dict.fromkeys(tot, 0.0)

    target.load_state_dict(best["target"])         # always returned as `target`, whichever encoder it came from
    predictor.load_state_dict(best["predictor"])
    target.freeze()
    predictor.requires_grad_(False).eval()

    table = full_table(target, frames)
    with torch.no_grad():
        err = torch.linalg.norm(predictor(table[val_one["obs"]], val_one["action"][:, 0]) - table[val_one["next"][:, 0]],
                                dim=-1)
    tr, va = frame_split(data, splits["train"]), frame_split(data, splits["val"])
    _, rep = probe_report(encode(target, data["frames"][tr]), cell_ids(data["frame_pos"][tr]),
                          encode(target, data["frames"][va]), cell_ids(data["frame_pos"][va]), T.N_CELLS,
                          **probe_kwargs(cfg))
    tb = table.numpy()
    return target, predictor, {
        "best_step": best["step"], "best_val_snap": best["key"][0], "best_val_mse": best["key"][1],
        "select_horizon": h, "median_one_step_error": float(err.median()),
        "probe_val_accuracy": rep["accuracy"], "probe_train_accuracy": rep["train_accuracy"],
        "latent_geometry": {"effective_rank": effective_rank(tb[tr]), "min_dim_std": float(tb[tr].std(0).min()),
                            "mean_dim_std": float(tb[tr].std(0).mean())},
        "history": history,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Joint JEPA on the training maps.")
    parser.add_argument("--config", type=Path, default=None, help="use configs/multimap_jepa.yaml")
    args = parser.parse_args()
    cfg = load_config(args.config)
    mm = cfg["multimap"]
    if "jepa" not in mm:
        raise SystemExit("this config has no `multimap.jepa:` section; run with --config configs/multimap_jepa.yaml")
    j = mm["jepa"]
    maps, splits = load_maps(resolve(mm["maps_path"]))
    data = load(resolve(mm["data_path"]))
    print(f"Joint JEPA on {len(splits['train'])} training maps: latent {j['latent_dim']}, {j['steps']} steps of "
          f"{j['maps_per_step']} maps / {j['windows_per_step']} windows, EMA tau {j['ema_tau']}, weights pred/var/cov "
          f"{j['pred_weight']}/{j['var_weight']}/{j['cov_weight']}, seed {cfg['seed']}")

    target, predictor, m = train(cfg, data, splits, len(maps))
    g = m["latent_geometry"]
    print(f"\nBest step {m['best_step']}: val-map snap@{m['select_horizon']} {m['best_val_snap']:.1%}, median one-step "
          f"error {m['median_one_step_error']:.4f}")
    print(f"Robot cell from the latent (linear probe, train maps -> unseen val maps): {m['probe_val_accuracy']:.1%}")
    print(f"Latent: effective rank {g['effective_rank']:.1f}, per-dim std min {g['min_dim_std']:.2f} / "
          f"mean {g['mean_dim_std']:.2f}")

    e, p = mm["encoder"], mm["predictor"]
    resolve(e["checkpoint"]).parent.mkdir(parents=True, exist_ok=True)
    torch.save({"state_dict": target.state_dict(), "latent_dim": target.latent_dim,
                "input_shape": list(target.input_shape), "gate_passed": True, "best_epoch": m["best_step"],
                "seed": cfg["seed"], "trained_by": "joint JEPA (EMA target encoder), identity standardisation"},
               resolve(e["checkpoint"]))
    torch.save({"state_dict": predictor.state_dict(), "latent_dim": predictor.latent_dim,
                "n_actions": predictor.n_actions, "hidden": list(j["hidden"]),
                "median_one_step_error": m["median_one_step_error"], "best_epoch": m["best_step"],
                "seed": cfg["seed"]}, resolve(p["checkpoint"]))
    resolve(j["metrics"]).write_text(json.dumps(m, indent=1) + "\n")
    print(f"Saved {resolve(e['checkpoint'])}, predictor and metrics in {resolve(p['checkpoint']).parent}")


if __name__ == "__main__":
    main()
