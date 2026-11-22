"""Mini-JEPA: one entry point for the whole pipeline (build plan step 11).

    python main.py all                 everything below, in order (~10 min on a laptop CPU)
    python main.py collect             step 2   data/transitions.npz + data/splits.json
    python main.py train-numerical     step 3   checkpoints/numerical.pt
    python main.py train-encoder       step 5   checkpoints/encoder.pt, decoder.pt (gate checked)
    python main.py train-world         step 6   checkpoints/predictor.pt
    python main.py eval                steps 4, 7-9   probe sanity check, latent graph, planners,
                                                      results/results.md + plots
    python main.py fingerprint         hashes of every deterministic output, to compare two runs

Every stage reads config.yaml (or --config) and its fixed seed. Each stage
runs as its own process and the pipeline stops at the first failure (e.g. the
encoder gate).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent

STAGES: dict[str, list[tuple[str, str]]] = {
    "collect": [("data.collect_data", "collect 10,000 transitions, splits, held-out pairs")],
    "train-numerical": [("training.train_numerical", "numerical (x, y, a) -> next (x, y) baseline")],
    "train-encoder": [("training.train_encoder", "autoencoder, gate, frozen encoder + codebook")],
    "train-world": [("training.train_world_model", "residual latent predictor")],
    "eval": [
        ("evaluation.probes", "probe sanity checks"),
        ("planning.latent_graph", "imagined graph and D(c)"),
        ("planning.mpc", "planners with true and learned models"),
        ("evaluation", "results table, ladder and plots"),
    ],
}
ORDER = ["collect", "train-numerical", "train-encoder", "train-world", "eval"]


def run_stage(name: str, config: Path | None) -> None:
    for module, what in STAGES[name]:
        cmd = [sys.executable, "-m", module] + (["--config", str(config)] if config else [])
        print(f"\n=== {name}: {what}  ({' '.join(cmd[1:])})", flush=True)
        t0 = time.perf_counter()
        result = subprocess.run(cmd, cwd=ROOT)
        if result.returncode != 0:
            raise SystemExit(f"\n{module} failed with exit code {result.returncode}; stopping.")
        print(f"=== {module} done in {time.perf_counter() - t0:.1f}s", flush=True)


# --- fingerprint ------------------------------------------------------------------------
TIMING_KEYS = {"ms", "mean_plan_ms"}


def _strip_timing(obj):
    """Drop wall-clock fields so only deterministic content is hashed."""
    if isinstance(obj, dict):
        return {k: _strip_timing(v) for k, v in obj.items() if k not in TIMING_KEYS}
    if isinstance(obj, list):
        return [_strip_timing(v) for v in obj]
    return obj


def _hash_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()[:16]


def _hash_checkpoint(path: Path) -> str:
    """Hash of every tensor's values (not the pickle bytes), in key order."""
    import torch

    ckpt = torch.load(path, map_location="cpu", weights_only=True)
    h = hashlib.sha256()

    def feed(prefix, v):
        if isinstance(v, torch.Tensor):
            h.update(prefix.encode())
            h.update(v.detach().contiguous().numpy().tobytes())
        elif isinstance(v, dict):
            for k in sorted(v):
                feed(f"{prefix}/{k}", v[k])
        else:
            h.update(f"{prefix}={v!r}".encode())

    feed("", ckpt)
    return h.hexdigest()[:16]


def fingerprint(config: Path | None) -> dict[str, str]:
    sys.path.insert(0, str(ROOT))
    from config import load_config, resolve

    cfg = load_config(config)
    files: dict[str, str] = {}
    raw = [cfg["data"]["path"], cfg["data"]["splits_path"], f"{cfg['evaluation']['results_dir']}/results.md"]
    ckpts = [cfg[k]["checkpoint"] for k in ("numerical", "encoder", "predictor")] + [cfg["encoder"]["decoder_checkpoint"]]
    jsons = [cfg["numerical"]["metrics"], cfg["encoder"]["metrics"], cfg["predictor"]["metrics"],
             cfg["imagination"]["metrics"], cfg["planning"]["metrics"], f"{cfg['evaluation']['results_dir']}/results.json"]
    for rel in raw:
        p = resolve(rel)
        files[rel] = _hash_bytes(p.read_bytes()) if p.exists() else "missing"
    for rel in ckpts:
        p = resolve(rel)
        files[rel] = _hash_checkpoint(p) if p.exists() else "missing"
    for rel in jsons:
        p = resolve(rel)
        files[rel] = (_hash_bytes(json.dumps(_strip_timing(json.loads(p.read_text())), sort_keys=True).encode())
                      if p.exists() else "missing")
    return files


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=[*ORDER, "all", "fingerprint"])
    parser.add_argument("--config", type=Path, default=None, help="config file (default: config.yaml)")
    args = parser.parse_args()
    config = args.config.resolve() if args.config else None

    if args.command == "fingerprint":
        for name, h in fingerprint(config).items():
            print(f"{h}  {name}")
        return
    t0 = time.perf_counter()
    for stage in (ORDER if args.command == "all" else [args.command]):
        run_stage(stage, config)
    print(f"\nDone: {args.command} in {(time.perf_counter() - t0) / 60:.1f} min")


if __name__ == "__main__":
    main()
