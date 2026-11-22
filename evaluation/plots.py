"""Step 9 plots (matplotlib, static PNG). Colours: the validated categorical palette, fixed slot order.

Every plot has a table view in results.md (several slots sit below 3:1 contrast on
the light surface, so the numbers are always available as text too).
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_2 = "#52514e"
GRID = "#e4e3df"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
REFERENCE = "#8f8e89"  # neutral ink for baselines (persistence), not a series hue


def _style(ax, title: str, xlabel: str, ylabel: str) -> None:
    ax.set_facecolor(SURFACE)
    ax.set_title(title, loc="left", fontsize=11.5, color=TEXT, pad=10, fontweight="bold")
    ax.set_xlabel(xlabel, color=TEXT_2, fontsize=9.5)
    ax.set_ylabel(ylabel, color=TEXT_2, fontsize=9.5)
    ax.tick_params(colors=TEXT_2, labelsize=9, length=0)
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)


def _legend(ax, **kw) -> None:
    leg = ax.legend(frameon=False, fontsize=9, labelcolor=TEXT_2, **kw)
    return leg


def _save(fig, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)
    return path


def plot_horizons(curves: dict, path: Path) -> Path:
    """Two panels: accuracy vs imagined steps, and latent MSE vs imagined steps (log scale)."""
    ks = list(range(1, len(curves["trained"]["snap_acc"]) + 1))
    fig, (a, b) = plt.subplots(1, 2, figsize=(11.5, 4.2), facecolor=SURFACE)

    # colour = which windows, line style = which read-out
    for (name, label), color in zip((("trained", "trained-pair windows"), ("all", "all windows")), SERIES):
        a.plot(ks, [100 * v for v in curves[name]["snap_acc"]], color=color, lw=2, marker="o", ms=8,
               markeredgecolor=SURFACE, markeredgewidth=2, label=f"snap, {label}")
        a.plot(ks, [100 * v for v in curves[name]["probe_acc"]], color=color, lw=2, ls=(0, (4, 3)),
               marker="s", ms=6, markeredgecolor=SURFACE, markeredgewidth=1.5, label=f"probe, {label}")
    _style(a, "Where does the imagined robot end up?", "imagined steps", "correct cell (%)")
    a.set_ylim(0, 105)
    a.set_xticks(ks)
    _legend(a, loc="lower left")

    for (name, label), color in zip((("trained", "model, trained-pair windows"), ("all", "model, all windows")), SERIES):
        b.plot(ks, curves[name]["mse"], color=color, lw=2, marker="o", ms=8, markeredgecolor=SURFACE,
               markeredgewidth=2, label=label)
    b.plot(ks, curves["all"]["mse_persistence"], color=REFERENCE, lw=2, ls=(0, (2, 2)),
           label="persistence (z_k = z_0), all windows")
    b.set_yscale("log")
    _style(b, "Latent error vs imagined steps", "imagined steps", "latent MSE (standardised, log)")
    b.set_xticks(ks)
    _legend(b, loc="center right")
    fig.tight_layout(w_pad=3)
    return _save(fig, path)


def plot_success_by_distance(nav: dict, path: Path) -> Path:
    fig, ax = plt.subplots(figsize=(8.5, 4.4), facecolor=SURFACE)
    for (label, s), color in zip(nav.items(), SERIES):
        ds = sorted(s["by_distance"])
        ys = [100 * s["by_distance"][d]["success"] / s["by_distance"][d]["total"] for d in ds]
        if label == "Oracle":  # upper bound: a wide band underneath, so planners that match it stay visible
            ax.plot(ds, ys, color=color, lw=9, alpha=0.3, solid_capstyle="round", label="Oracle (upper bound)",
                    zorder=1)
            continue
        ax.plot(ds, ys, color=color, lw=2, marker="o", ms=8, markeredgecolor=SURFACE, markeredgewidth=2,
                label=label, zorder=3)
    _style(ax, "Success by start distance (120 episodes per planner)", "optimal path length from start",
           "episodes reaching the goal (%)")
    ax.set_ylim(-3, 105)
    ax.set_xticks(sorted({d for s in nav.values() for d in s["by_distance"]}))
    _legend(ax, loc="center left", bbox_to_anchor=(1.01, 0.5))
    return _save(fig, path)


def plot_ladder(ladder: dict, path: Path) -> Path:
    rungs = [r["label"] for r in ladder["rungs"]]
    desc = {r["label"]: (f"{r['label']}: {r['dynamics']} dynamics, {r['cost']} cost"
                         if r["dynamics"] not in ("-",) and r["label"] != "Oracle" else
                         ("Oracle: A* on the true map" if r["label"] == "Oracle" else "Random policy"))
            for r in ladder["rungs"]}
    s = ladder["summaries"]
    fig, ax = plt.subplots(figsize=(9, 4.3), facecolor=SURFACE)
    h = 0.36
    for j, (key, label, color) in enumerate((("success", "reached goal", SERIES[0]),
                                             ("optimal", "reached goal optimally", SERIES[1]))):
        vals = [100 * s[r][key] / s[r]["episodes"] for r in rungs]
        ys = [i + (j - 0.5) * (h + 0.04) for i in range(len(rungs))]  # small surface gap between the pair
        ax.barh(ys, vals, height=h, color=color, label=label)
        if key == "success":
            for y, v in zip(ys, vals):
                ax.text(v + 1.2, y, f"{v:.0f}%", va="center", fontsize=8.5, color=TEXT_2)
    ax.set_yticks(range(len(rungs)), [desc[r] for r in rungs])
    ax.invert_yaxis()
    _style(ax, "Diagnostic ladder (P2 on D1-Full; 120 episodes per rung)", "episodes (%)", "")
    ax.set_xlim(0, 108)
    ax.grid(axis="y", visible=False)
    _legend(ax, loc="lower right")
    return _save(fig, path)
