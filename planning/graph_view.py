"""Draw the imagined graph and D(c): `python -m planning.graph_view`.

Reads checkpoints/single_map/graph_metrics.json (written by `python -m planning.latent_graph`) and writes:

latent_graph.png -- node-link graph (matplotlib). One node per codebook entry,
columns = imagined steps-to-goal D(c), arrows = imagined moves, dashed orange =
unknown moves (drawn to their true target; a self-loop in the graph).

latent_graph_grid.png -- the same graph drawn on the map (pygame):

  * big number in a cell     imagined steps-to-goal D(c); a small "true N" appears if it differs
  * dark arrow               imagined move that matches the simulator
  * red arrow                imagined move that is wrong but was trusted (known)
  * grey bar at a cell edge  imagined bump (self-loop) that matches the simulator
  * orange "?" at an edge    unknown move, turned into a self-loop
  * orange ring              that (cell, action) is a held-out pair
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import numpy as np

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame  # noqa: E402

from environment import ACTION_DELTAS, ACTIONS, GridMap  # noqa: E402
from evaluation.probes import CellIndex  # noqa: E402

CELL = 120
PAD = 20
LEGEND_H = 120
C = {
    "bg": (246, 248, 250), "floor": (227, 233, 239), "wall": (127, 138, 150), "goal": (13, 122, 112),
    "line": (200, 208, 216), "text": (33, 41, 52), "dim": (110, 120, 132), "ok": (52, 64, 84),
    "wrong": (200, 40, 40), "bump": (150, 158, 170), "unknown": (226, 132, 20),
}


def _arrow(surf, color, start, end, width=3, head=9):
    pygame.draw.line(surf, color, start, end, width)
    dx, dy = end[0] - start[0], end[1] - start[1]
    n = max((dx * dx + dy * dy) ** 0.5, 1e-6)
    ux, uy = dx / n, dy / n
    px, py = -uy, ux
    tip = end
    left = (end[0] - ux * head + px * head * 0.6, end[1] - uy * head + py * head * 0.6)
    right = (end[0] - ux * head - px * head * 0.6, end[1] - uy * head - py * head * 0.6)
    pygame.draw.polygon(surf, color, [tip, left, right])


def render(metrics: dict, heldout_pairs, path: str | Path) -> Path:
    pygame.font.init()
    grid, cells = GridMap(), CellIndex()
    held = {tuple(p) for p in heldout_pairs}
    nxt, known = metrics["next"], metrics["known"]
    d_im, d_true = metrics["d_imagined"], metrics["d_true"]

    w, h = PAD * 2 + grid.cols * CELL, PAD * 2 + grid.rows * CELL + LEGEND_H
    surf = pygame.Surface((w, h))
    surf.fill(C["bg"])
    big, small = pygame.font.Font(None, 46), pygame.font.Font(None, 22)

    def origin(x, y):
        return PAD + x * CELL, PAD + y * CELL

    def center(x, y):
        ox, oy = origin(x, y)
        return ox + CELL // 2, oy + CELL // 2

    # cells
    for y in range(grid.rows):
        for x in range(grid.cols):
            ox, oy = origin(x, y)
            rect = pygame.Rect(ox + 2, oy + 2, CELL - 4, CELL - 4)
            color = C["wall"] if (x, y) in grid.walls else C["floor"]
            pygame.draw.rect(surf, color, rect, border_radius=6)
            if (x, y) == grid.goal:
                pygame.draw.rect(surf, C["goal"], rect, width=5, border_radius=6)

    # edges
    for i, (x, y) in enumerate(cells.cells):
        x, y = int(x), int(y)
        cx, cy = center(x, y)
        for a in ACTIONS:
            dx, dy = ACTION_DELTAS[a]
            true_pos, _ = grid.transition((x, y), a)
            true_idx = int(cells.ids(np.array(true_pos)))
            j, is_known = nxt[i][a], known[i][a]
            edge = (cx + dx * (CELL // 2 - 14), cy + dy * (CELL // 2 - 14))  # point near the cell edge
            if (x, y, a) in held:
                pygame.draw.circle(surf, C["unknown"], edge, 13, width=2)
            if not is_known:
                q = small.render("?", True, C["unknown"])
                pygame.draw.circle(surf, C["bg"], edge, 10)
                pygame.draw.circle(surf, C["unknown"], edge, 10, width=2)
                surf.blit(q, q.get_rect(center=edge))
            elif j == i:
                color = C["bump"] if j == true_idx else C["wrong"]
                px, py = -dy, dx  # perpendicular
                pygame.draw.line(surf, color, (edge[0] + px * 12, edge[1] + py * 12),
                                 (edge[0] - px * 12, edge[1] - py * 12), 4)
            else:
                tx, ty = (int(v) for v in cells.cells[j])
                tcx, tcy = center(tx, ty)
                off = 7  # keep the two directions of a neighbour pair apart
                ox_, oy_ = (-dy * off, dx * off)
                start = (cx + dx * 26 + ox_, cy + dy * 26 + oy_)
                end = (tcx - dx * 26 + ox_, tcy - dy * 26 + oy_) if j == true_idx else (tcx + ox_, tcy + oy_)
                _arrow(surf, C["ok"] if j == true_idx else C["wrong"], start, end, width=2 if j == true_idx else 3)

        # D(c)
        label = "?" if d_im[i] < 0 else str(d_im[i])
        t = big.render(label, True, C["text"])
        surf.blit(t, t.get_rect(center=(cx, cy)))
        if d_im[i] != d_true[i]:
            s = small.render(f"true {d_true[i]}", True, C["wrong"])
            surf.blit(s, s.get_rect(center=(cx, cy + 26)))

    # legend
    ly = PAD * 2 + grid.rows * CELL
    e = metrics["edges"]["all"]
    title = (f"Imagined graph: {e['correct']}/100 edges correct, {e['unknown']} unknown, "
             f"{e['wrong_known']} wrong-but-trusted.  D(c) exact for {metrics['d_exact']}/25 cells.")
    surf.blit(small.render(title, True, C["text"]), (PAD, ly))
    items = [
        ("ok", "arrow", "imagined move = simulator"), ("wrong", "arrow", "wrong move, trusted"),
        ("bump", "bar", "imagined bump = simulator"), ("unknown", "?", "unknown -> self-loop"),
        ("unknown", "ring", "held-out pair"), ("goal", "box", "goal cell"),
    ]
    for k, (color, kind, text) in enumerate(items):
        x0, y0 = PAD + (k % 3) * 240, ly + 34 + (k // 3) * 34
        mid = (x0 + 16, y0 + 10)
        if kind == "arrow":
            _arrow(surf, C[color], (x0, y0 + 10), (x0 + 32, y0 + 10), width=2)
        elif kind == "bar":
            pygame.draw.line(surf, C[color], (x0 + 16, y0), (x0 + 16, y0 + 20), 4)
        elif kind == "?":
            pygame.draw.circle(surf, C[color], mid, 10, width=2)
            q = small.render("?", True, C[color])
            surf.blit(q, q.get_rect(center=mid))
        elif kind == "ring":
            pygame.draw.circle(surf, C[color], mid, 12, width=2)
        else:
            pygame.draw.rect(surf, C[color], (x0 + 2, y0, 28, 20), width=4, border_radius=4)
        surf.blit(small.render(text, True, C["dim"]), (x0 + 42, y0 + 3))

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pygame.image.save(surf, str(path))
    return path


def _true_next(grid: GridMap, cells: CellIndex) -> np.ndarray:
    return np.array([[int(cells.ids(np.array(grid.transition((int(x), int(y)), a)[0]))) for a in ACTIONS]
                     for x, y in cells.cells])


def _layer_order(layer: np.ndarray, adj: list[set[int]], cells: CellIndex, sweeps: int = 8) -> dict[int, float]:
    """Vertical position inside each layer; barycentre sweeps reduce edge crossings."""
    n_layers = int(layer.max()) + 1
    order = {L: sorted(np.flatnonzero(layer == L).tolist(), key=lambda i: (cells.cells[i][1], cells.cells[i][0]))
             for L in range(n_layers)}
    y: dict[int, float] = {}

    def assign():
        for nodes in order.values():
            for r, i in enumerate(nodes):
                y[i] = (len(nodes) - 1) / 2 - r

    assign()
    for sweep in range(sweeps):
        forward = sweep % 2 == 0
        for L in (range(1, n_layers) if forward else range(n_layers - 2, -1, -1)):
            ref = L - 1 if forward else L + 1

            def bary(i):
                nb = [y[j] for j in adj[i] if layer[j] == ref]
                return -float(np.mean(nb)) if nb else -y[i]

            order[L] = sorted(order[L], key=bary)
            assign()
    return y


def render_layered(metrics: dict, heldout_pairs, path: str | Path) -> Path:
    """Node-link drawing: one node per codebook entry, columns = imagined steps-to-goal D(c)."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.patches import Circle, FancyArrowPatch

    grid, cells = GridMap(), CellIndex()
    n = len(cells)
    nxt, known = np.array(metrics["next"]), np.array(metrics["known"], dtype=bool)
    d_im, d_true = np.array(metrics["d_imagined"]), np.array(metrics["d_true"])
    true_next = _true_next(grid, cells)
    held = {tuple(p) for p in heldout_pairs}
    goal = int(cells.ids(np.array(grid.goal)))

    layer = np.where(d_im >= 0, d_im, d_im.max() + 1)  # unreachable entries get a last column
    adj: list[set[int]] = [set() for _ in range(n)]
    for u in range(n):
        for a in ACTIONS:
            for v in (int(nxt[u, a]), int(true_next[u, a])):
                if v != u:
                    adj[u].add(v)
                    adj[v].add(u)
    ys = _layer_order(layer, adj, cells)
    XS, YS, R = 2.0, 1.35, 0.36
    pos = {i: np.array([layer[i] * XS, ys[i] * YS]) for i in range(n)}

    fig, ax = plt.subplots(figsize=(17, 7.6), dpi=150)
    ax.set_aspect("equal")
    ax.axis("off")
    col = {"ok": "#344054", "wrong": "#c62828", "unknown": "#e2841a", "bump": "#8a94a3",
           "node": "#e3e9ef", "edge": "#9aa6b2", "goal": "#0d7a70"}

    def arrow(u, v, style, color, lw=1.6, ls="-", rad=0.0, z=2):
        pu, pv = pos[u], pos[v]
        d = (pv - pu) / max(np.linalg.norm(pv - pu), 1e-9)
        ax.add_patch(FancyArrowPatch(tuple(pu + d * R), tuple(pv - d * R), arrowstyle=style, mutation_scale=13,
                                     color=color, lw=lw, linestyle=ls, connectionstyle=f"arc3,rad={rad}",
                                     zorder=z, shrinkA=0, shrinkB=0))

    correct = {(u, int(nxt[u, a])) for u in range(n) for a in ACTIONS
               if known[u, a] and nxt[u, a] == true_next[u, a] and nxt[u, a] != u}
    done = set()
    for u, v in sorted(correct):
        if (v, u) in done:
            continue
        both = (v, u) in correct
        arrow(u, v, "<|-|>" if both else "-|>", col["ok"])
        done.add((u, v))

    bumps = np.zeros(n, dtype=int)
    loop_slot = np.zeros(n, dtype=int)
    for u in range(n):
        for a in ACTIONS:
            v, t, k = int(nxt[u, a]), int(true_next[u, a]), bool(known[u, a])
            if k and v == t == u:
                bumps[u] += 1
            elif not k and t != u:  # missing move: dashed to where it should go
                arrow(u, t, "-|>", col["unknown"], lw=1.6, ls=(0, (4, 3)), rad=0.28, z=3)
                mid = (pos[u] + pos[t]) / 2
                perp = np.array([-(pos[t] - pos[u])[1], (pos[t] - pos[u])[0]])
                perp = perp / max(np.linalg.norm(perp), 1e-9)
                ax.text(*(mid - perp * 0.38), "?", color=col["unknown"], fontsize=11, fontweight="bold",
                        ha="center", va="center", zorder=4)
            elif not k:  # unknown bump: dashed self-loop
                cx, cy = pos[u] + np.array([0.42, 0.42 - 0.34 * loop_slot[u]])
                loop_slot[u] += 1
                ax.add_patch(Circle((cx, cy), 0.15, fill=False, ec=col["unknown"], lw=1.5, ls=(0, (3, 2)), zorder=3))
                ax.text(cx, cy, "?", color=col["unknown"], fontsize=8, fontweight="bold", ha="center", va="center")
            elif v != t:  # trusted but wrong
                if v == u:
                    ax.add_patch(Circle(tuple(pos[u] + np.array([0.42, -0.42])), 0.15, fill=False,
                                        ec=col["wrong"], lw=2, zorder=3))
                else:
                    arrow(u, v, "-|>", col["wrong"], lw=2.2, rad=0.35, z=3)

    for i in range(n):
        x, y = (int(c) for c in cells.cells[i])
        is_goal = i == goal
        mismatch = d_im[i] != d_true[i]
        ax.add_patch(Circle(tuple(pos[i]), R, fc=col["goal"] if is_goal else col["node"],
                            ec=col["wrong"] if mismatch else (col["goal"] if is_goal else col["edge"]),
                            lw=2.4 if mismatch else 1.2, zorder=5))
        ax.text(*pos[i], f"{x},{y}", ha="center", va="center", fontsize=10.5, fontweight="bold",
                color="white" if is_goal else "#212934", zorder=6)
        if bumps[i]:
            ax.text(pos[i][0], pos[i][1] - R - 0.17, f"↺{bumps[i]}", ha="center", va="center",
                    fontsize=8.5, color=col["bump"], zorder=6)
        if mismatch:
            ax.text(pos[i][0], pos[i][1] + R + 0.17, f"true {d_true[i]}", ha="center", fontsize=8,
                    color=col["wrong"], zorder=6)

    top = max(p[1] for p in pos.values()) + 0.95
    for L in range(int(layer.max()) + 1):
        label = f"D = {L}" if L <= d_im.max() else "unreachable"
        ax.text(L * XS, top, label, ha="center", va="bottom", fontsize=11, color="#5b6573")

    e = metrics["edges"]["all"]
    ax.set_title(f"Imagined latent graph: 25 codebook entries (labelled by their cell x,y), columns = imagined "
                 f"steps-to-goal D(c)\n{e['correct']}/100 edges correct · {e['unknown']} unknown "
                 f"(= the {len(held)} held-out pairs) · {e['wrong_known']} wrong-but-trusted · "
                 f"D(c) exact for {metrics['d_exact']}/25", fontsize=12, color="#212934", pad=14)
    handles = [
        Line2D([], [], color=col["ok"], lw=1.6, marker=">", markersize=6, label="imagined move = simulator"),
        Line2D([], [], color=col["unknown"], lw=1.6, ls=(0, (4, 3)), label="unknown move (true target shown), self-loop in the graph"),
        Line2D([], [], color=col["wrong"], lw=2.2, label="wrong move the model trusted"),
        Line2D([], [], color=col["bump"], lw=0, marker="$↺$", markersize=9, label="↺n = n correct bump self-loops"),
        Line2D([], [], color=col["goal"], lw=0, marker="o", markersize=11, label="goal entry"),
    ]
    ax.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, -0.09), ncol=3, frameon=False, fontsize=9.5)
    xs = [p[0] for p in pos.values()]
    yv = [p[1] for p in pos.values()]
    ax.set_xlim(min(xs) - 0.8, max(xs) + 0.9)
    ax.set_ylim(min(yv) - 0.9, top + 0.5)

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def render_all(metrics: dict, heldout_pairs, directory: str | Path) -> tuple[Path, Path]:
    """latent_graph.png (node-link) and latent_graph_grid.png (drawn on the map)."""
    directory = Path(directory)
    return (render_layered(metrics, heldout_pairs, directory / "latent_graph.png"),
            render(metrics, heldout_pairs, directory / "latent_graph_grid.png"))


def main() -> None:
    from config import load_config, resolve
    from data import load_splits

    parser = argparse.ArgumentParser(description="Draw the imagined graph as a PNG.")
    parser.add_argument("--config", type=Path, default=None, help="config file (default: configs/single_map.yaml)")
    parser.add_argument("--out-dir", type=Path, default=None, help="output folder (default: next to the metrics)")
    args = parser.parse_args()
    cfg = load_config(args.config)
    mpath = resolve(cfg["imagination"]["metrics"])
    if not mpath.exists():
        raise SystemExit(f"{mpath} not found: run `python -m planning.latent_graph` first")
    metrics = json.loads(mpath.read_text())
    held = load_splits(resolve(cfg["data"]["splits_path"]))["heldout_pairs"]
    for p in render_all(metrics, held, args.out_dir or mpath.parent):
        print(f"Saved {p}")


if __name__ == "__main__":
    main()
