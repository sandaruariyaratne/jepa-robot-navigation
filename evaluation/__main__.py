"""Regenerate every step 9 result from config.yaml: `python -m evaluation`.

Writes <results_dir>/results.md (the table), results.json (everything) and
three plots: prediction_horizons.png, success_by_distance.png, ladder.png.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from config import load_config, resolve
from data import load_splits, load_transitions
from evaluation.ladder import diagnose
from evaluation.metrics import CATEGORIES
from evaluation.navigation_test import report, run_seeds
from evaluation.plots import plot_horizons, plot_ladder, plot_success_by_distance
from evaluation.prediction_accuracy import model_metrics
from evaluation.runs import LADDER, NAVIGATION, build_runs


def _pct(n, d):
    return f"{n}/{d} ({n / d:.0%})" if d else "-"


def _acc(s):
    return f"{s['correct']}/{s['total']}" if s["total"] else "-"


def render_markdown(cfg: dict, model: dict, nav: dict, ladder: dict, diagnosis: list[str]) -> str:
    seeds = cfg["evaluation"]["seeds"]
    o = model["one_step"]
    L = []
    L.append("# Mini-JEPA results\n")
    L.append(f"Regenerate with `python -m evaluation` (seed {cfg['seed']}, planning seeds {seeds}). "
             "Fit = episode split (test episodes, trained pairs); generalization = held-out (state, action) pairs.\n")

    L.append("## World model (test split)\n")
    L.append("| One-step latent MSE | model | persistence (z_hat = z) |\n|---|---|---|")
    for k in ("trained", "held-out (all)"):
        L.append(f"| {k} transitions | {o['mse_model'][k]:.5f} | {o['mse_persistence'][k]:.5f} |")
    L.append("")
    nb = model["numerical_baseline"]
    L.append("| (cell, action) pairs | latent predictor | numerical baseline (step 3) |\n|---|---|---|")
    for c in CATEGORIES:
        L.append(f"| {c} | {_acc(model['pairs'][c])} | {_acc(nb['pairs'][c]) if nb else '-'} |")
    L.append("")
    cur = model["curves"]
    hdr = " | ".join(str(k + 1) for k in range(len(cur["trained"]["snap_acc"])))
    L.append(f"| Imagined steps | {hdr} |\n|---|" + "---|" * len(cur["trained"]["snap_acc"]))
    for name, key, label in (("trained", "snap_acc", f"snap, trained-pair windows (n={cur['trained']['n']})"),
                             ("all", "snap_acc", f"snap, all windows (n={cur['all']['n']})"),
                             ("trained", "probe_acc", "probe, trained-pair windows"),
                             ("all", "probe_acc", "probe, all windows")):
        L.append(f"| {label} | " + " | ".join(f"{v:.0%}" for v in cur[name][key]) + " |")
    L.append("")
    e = model["graph"]["edges"]
    L.append(f"Imagined graph: **{e['all']['correct']}/100 edges correct** (trained {e['trained']['correct']}/"
             f"{e['trained']['total']}, held-out {e['held-out']['correct']}/{e['held-out']['total']}), "
             f"{e['all']['unknown']} unknown -> self-loops, {e['all']['wrong_known']} wrong but trusted. "
             f"D(c) exact for **{model['graph']['d_exact']}/25** cells "
             f"(over {model['graph']['d_over']}, under {model['graph']['d_under']}, "
             f"unreachable {model['graph']['d_unreachable']}).\n")

    def nav_table(rows: dict, title: str, extra=None):
        L.append(title + "\n")
        cols = "| | success | optimal | path ratio | collision rate | loop failures | timeouts |"
        if extra:
            cols = "| | dynamics | cost " + cols[2:]
        L.append(cols + "\n|" + "---|" * (cols.count("|") - 1))
        for label, s in rows.items():
            ratio = f"{s['mean_path_ratio']:.2f}" if s["mean_path_ratio"] is not None else "-"
            pre = f"| {label} | " + (" | ".join(extra[label]) + " | " if extra else "")
            L.append(f"{pre}{_pct(s['success'], s['episodes'])} | {_pct(s['optimal'], s['episodes'])} | {ratio} | "
                     f"{s['collision_rate']:.1%} | {s['loop_failures']} | {s['timeouts']} |")
        L.append("")

    nav_table(nav, f"## Navigation ({len(seeds)} seeds x 24 starts = {24 * len(seeds)} episodes each, learned model)")
    dists = sorted({d for s in nav.values() for d in s["by_distance"]})
    L.append("Success by start distance (optimal path length):\n")
    L.append("| | " + " | ".join(f"d={d}" for d in dists) + " |\n|---" + "|---" * len(dists) + "|")
    for label, s in nav.items():
        bd = s["by_distance"]
        L.append(f"| {label} | " + " | ".join(f"{bd[d]['success'] / bd[d]['total']:.0%}" for d in dists) + " |")
    L.append("")
    nav_table(ladder["summaries"], "## Diagnostic ladder (planner P2 on every rung except Oracle / Random)",
              extra={r["label"]: (r["dynamics"], r["cost"]) for r in ladder["rungs"]})
    L.append("Reading:\n")
    L.extend(f"- {line}" for line in diagnosis)
    L.append("\nPlots: `prediction_horizons.png`, `success_by_distance.png`, `ladder.png`.")
    return "\n".join(L) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Regenerate the step 9 results table and plots.")
    parser.add_argument("--config", type=Path, default=None, help="config file (default: config.yaml)")
    args = parser.parse_args()
    cfg = load_config(args.config)
    seeds = cfg["evaluation"]["seeds"]
    out_dir = resolve(cfg["evaluation"]["results_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()

    data = load_transitions(resolve(cfg["data"]["path"]))
    splits = load_splits(resolve(cfg["data"]["splits_path"]))
    print("Model metrics ...")
    model = model_metrics(cfg, data, splits)

    runs = build_runs(cfg)

    print("Navigation ...")
    episodes = {k: run_seeds(runs[k].model, runs[k].planner, runs[k].mctx, cfg, seeds) for k in NAVIGATION}
    nav = {k: report(v) for k, v in episodes.items()}

    print("Ladder ...")
    reuse = {"Oracle": "Oracle", "Full": "P2", "Random": "Random"}  # identical runs already done above
    ladder_eps = {k: episodes[reuse[k]] if k in reuse else run_seeds(runs[k].model, runs[k].planner, runs[k].mctx,
                                                                      cfg, seeds) for k in LADDER}
    ladder = {"rungs": [{"label": k, "dynamics": runs[k].dynamics, "cost": runs[k].cost} for k in LADDER],
              "summaries": {k: report(v) for k, v in ladder_eps.items()}}
    diagnosis = diagnose(ladder["summaries"])

    md = render_markdown(cfg, model, nav, ladder, diagnosis)
    (out_dir / "results.md").write_text(md)
    (out_dir / "results.json").write_text(json.dumps(
        {"model": model, "navigation": nav, "ladder": ladder, "diagnosis": diagnosis}, indent=1, default=str) + "\n")
    plots = [plot_horizons(model["curves"], out_dir / "prediction_horizons.png"),
             plot_success_by_distance(nav, out_dir / "success_by_distance.png"),
             plot_ladder(ladder, out_dir / "ladder.png")]

    print("\n" + md)
    print(f"Wrote {out_dir / 'results.md'}, results.json and {len(plots)} plots in {time.perf_counter() - t0:.1f}s")


if __name__ == "__main__":
    main()
