"""Episode replay dashboard (build plan step 10).

    python -m visualization.dashboard                          P2, seed 0, from the reference start (0,4)
    python -m visualization.dashboard --run P0 --seed 2 --start 0,1
    python -m visualization.dashboard --run P1 --episodes      list all 120 episodes of a run, to pick one
    python -m visualization.dashboard --run D2 --export out/   one PNG per step + replay.gif, no window

Runs: Oracle, P0, P1, P2, Random (navigation) and D1, D2, D3, Full (ladder).
Every evaluation episode is seeded, so (run, seed, start) replays it exactly.

Window keys:  right / left  step    home / end  first / last    space  play / pause    q  quit

Panels at each step t (the plan made after observing frame t):
  live grid      the real observation, the path so far, and the chosen plan's imagined cells (orange)
  D(c) heat map  the steps-to-goal table this run's planner uses; the robot's cell is outlined
  costs          best candidate cost for each first action; the chosen action is highlighted
  imagined       the chosen sequence decoded step by step (decoder for the learned model; for the
                 true model, the frame of the imagined cell); '?' marks an unknown snap
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import torch

from environment import ACTION_NAMES, GridMap, GridWorld

ARROWS = {0: "↑", 1: "↓", 2: "←", 3: "→"}
SURFACE, TEXT, TEXT_2, GRIDC = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
BLUE, ORANGE, NEUTRAL = "#2a78d6", "#eb6834", "#c9c7c0"
MAX_STRIP = 8


class Replay:
    """A recorded episode plus everything the panels need, precomputed per step."""

    def __init__(self, episode, run, decoder=None, cell_px: int = 8, eval_seed: int | None = None) -> None:
        from evaluation.probes import CellIndex
        from planning.true_model import TrueModel

        self.ep, self.run, self.cell_px = episode, run, cell_px
        self.eval_seed = eval_seed  # the --seed you'd pass to replay it (episode.seed is the derived one)
        self.map = GridMap()
        self.cells = CellIndex(self.map)
        self.renderer = GridWorld(self.map, cell_px=cell_px).renderer
        self.is_true = isinstance(run.model, TrueModel)
        self.decoder = decoder
        self.d_table = np.asarray(run.mctx.d_table)
        self.imagined = [self._decode(p) for p in episode.plans]

    @property
    def n_states(self) -> int:
        return self.ep.steps + 1

    def _cell_frame(self, idx: int) -> np.ndarray:
        x, y = (int(v) for v in self.cells.positions(idx))
        return self.renderer.render((x, y)).transpose(1, 2, 0) / 255.0

    @torch.no_grad()
    def _decode(self, plan: dict) -> list[tuple[np.ndarray | None, int]]:
        """[(frame HWC in [0,1] or None, snapped entry or -1)] for the chosen sequence."""
        entries = plan["imagined_entries"]
        z = plan.get("extra", {}).get("imagined")
        if z is None:  # Oracle (planned cells) or Random (nothing)
            return [(self._cell_frame(e), e) for e in entries]
        if self.is_true:
            return [(self._cell_frame(int(i)), e) for i, e in zip(z.argmax(-1).tolist(), entries)]
        if self.decoder is None:
            return [(None, e) for e in entries]
        frames = self.decoder(self.run.model.encoder.unstandardize(z)).numpy().transpose(0, 2, 3, 1)
        return list(zip(frames, entries))


class Dashboard:
    def __init__(self, replay: Replay, fig=None) -> None:
        import matplotlib.pyplot as plt
        from matplotlib.gridspec import GridSpec

        self.r = replay
        self.t = 0
        self.playing = False
        self.fig = fig or plt.figure(figsize=(15, 7.8), facecolor=SURFACE)
        gs = GridSpec(3, 8, figure=self.fig, height_ratios=[1, 1, 0.8], hspace=0.5, wspace=0.6,
                      left=0.03, right=0.97, top=0.94, bottom=0.03)
        self.ax_grid = self.fig.add_subplot(gs[0:2, 0:3])
        self.ax_heat = self.fig.add_subplot(gs[0:2, 3:6])
        self.ax_cost = self.fig.add_subplot(gs[0, 6:8])
        self.ax_info = self.fig.add_subplot(gs[1, 6:8])
        sub = gs[2, :].subgridspec(1, MAX_STRIP, wspace=0.15)
        self.ax_strip = [self.fig.add_subplot(sub[0, k]) for k in range(MAX_STRIP)]
        self.timer = None

    # --- drawing ----------------------------------------------------------------------
    def _center(self, idx: int) -> tuple[float, float]:
        x, y = (int(v) for v in self.r.cells.positions(idx))
        p = self.r.cell_px
        return x * p + p / 2, y * p + p / 2

    def _pos_center(self, pos) -> tuple[float, float]:
        p = self.r.cell_px
        return pos[0] * p + p / 2, pos[1] * p + p / 2

    def draw(self, t: int) -> None:
        self.t = t = int(np.clip(t, 0, self.r.n_states - 1))
        ep, r = self.r.ep, self.r
        plan = ep.plans[t] if t < ep.steps else None
        for ax in (self.ax_grid, self.ax_heat, self.ax_cost, self.ax_info, *self.ax_strip):
            ax.clear()

        # live grid
        ax = self.ax_grid
        ax.imshow(ep.frames[t].transpose(1, 2, 0), interpolation="nearest")
        path = np.array([self._pos_center(p) for p in ep.path[: t + 1]])
        if len(path) > 1:
            ax.plot(path[:, 0], path[:, 1], color=TEXT, lw=2, alpha=0.55, solid_capstyle="round", zorder=3)
        ax.plot(*self._pos_center(ep.path[0]), marker="o", ms=7, color=TEXT, alpha=0.55, zorder=3)
        if plan is not None and plan["imagined_entries"]:
            pts, unknown_at = [self._pos_center(ep.path[t])], None
            for e in plan["imagined_entries"]:
                if e < 0:
                    unknown_at = pts[-1]
                    break
                pts.append(self._center(e))
            pts = np.array(pts)
            ax.plot(pts[:, 0], pts[:, 1], color=ORANGE, lw=2, ls=(0, (3, 2)), marker="o", ms=5, zorder=4)
            if unknown_at is not None:
                ax.text(unknown_at[0] + 2.5, unknown_at[1] - 2.5, "?", color=ORANGE, fontsize=14,
                        fontweight="bold", zorder=5)
        status = ""
        if plan is not None:
            status = f"next action {ACTION_NAMES[plan['action']]} {ARROWS[plan['action']]}"
        else:
            status = ("reached the goal" if ep.success else "loop failure (3rd visit)" if ep.loop_failure
                      else "out of actions")
        ax.set_title(f"step {t}/{ep.steps}   robot at {ep.path[t]}   {status}", loc="left", fontsize=11,
                     color=TEXT, fontweight="bold")
        ax.set_xticks([])
        ax.set_yticks([])

        # D(c) heat map
        self._draw_heat(ep.path[t])

        # costs per first action
        ax = self.ax_cost
        costs = (plan or {}).get("extra", {}).get("first_action_costs")
        if plan is None or costs is None:
            ax.text(0.5, 0.5, "episode over" if plan is None else "random policy: no costs",
                    ha="center", va="center", color=TEXT_2, fontsize=10, transform=ax.transAxes)
            ax.axis("off")
        else:
            costs = np.array(costs, dtype=float)
            finite = np.isfinite(costs)
            top = costs[finite].max() if finite.any() else 1.0
            colors = [BLUE if a == plan["action"] else NEUTRAL for a in range(4)]
            ax.bar(range(4), np.where(finite, costs, 0), color=colors, width=0.7)
            for a in range(4):
                label = f"{costs[a]:.2f}".rstrip("0").rstrip(".") if finite[a] else "no known\npath"
                ax.text(a, (costs[a] if finite[a] else 0) + top * 0.03, label, ha="center", va="bottom",
                        fontsize=8.5, color=TEXT if a == plan["action"] else TEXT_2)
            ax.set_xticks(range(4), [f"{ARROWS[a]} {ACTION_NAMES[a]}" for a in range(4)], fontsize=9, color=TEXT_2)
            ax.set_ylim(0, top * 1.3 + 1e-9)
            ax.set_title("best cost per first action (lower wins)", loc="left", fontsize=10, color=TEXT)
            for side in ("top", "right", "left"):
                ax.spines[side].set_visible(False)
            ax.spines["bottom"].set_color(GRIDC)
            ax.tick_params(length=0, labelsize=8.5, colors=TEXT_2)
            ax.grid(axis="y", color=GRIDC)
            ax.set_axisbelow(True)

        # info
        ax = self.ax_info
        ax.axis("off")
        seed = r.eval_seed if r.eval_seed is not None else ep.seed
        lines = [f"run {r.run.label}: {r.run.dynamics} dynamics,",
                 f"  {r.run.cost} cost",
                 f"seed {seed}  start {ep.start}  optimal {ep.optimal}"]
        if plan is not None:
            seq = " ".join(ARROWS[a] for a in plan["sequence"])
            lines += [f"chosen plan: {seq}", f"cost {plan['cost']:.3f}   plan time {plan['ms']:.1f} ms"]
            if plan["note"]:
                lines.append(plan["note"])
        else:
            lines.append(f"outcome: {'success' if ep.success else 'failure'} in {ep.steps} actions, "
                         f"{ep.collisions} bumps")
        ax.text(0, 1, "\n".join(lines), va="top", ha="left", fontsize=9, color=TEXT, family="monospace",
                transform=ax.transAxes, linespacing=1.6)

        # imagined strip
        imagined = r.imagined[t] if plan is not None else []
        what = "planned cells (A*)" if r.run.label == "Oracle" else "imagined rollout of the chosen plan"
        for k, sax in enumerate(self.ax_strip):
            sax.axis("off")
            if k >= len(imagined):
                continue
            frame, entry = imagined[k]
            if frame is not None:
                sax.imshow(np.clip(frame, 0, 1), interpolation="nearest")
            name = "?" if entry < 0 else str(tuple(int(v) for v in r.cells.positions(entry)))
            sax.set_title(f"{k + 1}: {name}", fontsize=9, color=ORANGE if entry < 0 else TEXT_2)
        if imagined:
            extra = f"  (first {MAX_STRIP} of {len(imagined)})" if len(imagined) > MAX_STRIP else ""
            self.ax_strip[0].text(0, 1.45, what + extra, transform=self.ax_strip[0].transAxes, fontsize=10,
                                  color=TEXT, fontweight="bold")
        self.fig.canvas.draw_idle()

    def _draw_heat(self, robot) -> None:
        from matplotlib.patches import Rectangle

        ax, r = self.ax_heat, self.r
        grid = np.full((r.map.rows, r.map.cols), np.nan)
        for i, (x, y) in enumerate(r.cells.cells):
            grid[int(y), int(x)] = r.d_table[i] if r.d_table[i] >= 0 else np.nan
        vmax = max(1, np.nanmax(grid)) if np.isfinite(grid).any() else 1
        ax.imshow(np.where(np.isnan(grid), -1, grid), cmap="Blues", vmin=-1, vmax=vmax, interpolation="nearest")
        for y in range(r.map.rows):
            for x in range(r.map.cols):
                if (x, y) in r.map.walls:
                    ax.add_patch(Rectangle((x - 0.5, y - 0.5), 1, 1, color="#7f8a96"))
                    continue
                v = grid[y, x]
                txt = "?" if np.isnan(v) else f"{int(v)}"
                ax.text(x, y, txt, ha="center", va="center", fontsize=13, fontweight="bold",
                        color="white" if not np.isnan(v) and v > vmax * 0.55 else TEXT)
        ax.add_patch(Rectangle((robot[0] - 0.47, robot[1] - 0.47), 0.94, 0.94, fill=False, ec=ORANGE, lw=3))
        gx, gy = r.map.goal
        ax.text(gx + 0.34, gy - 0.3, "goal", ha="center", va="center", fontsize=7.5, color=TEXT_2)
        used = {"P0": "not used by P0", "P1": "not used by P1", "Random": "not used"}.get(r.run.label, "used by P2")
        source = "true BFS" if r.run.cost in ("true", "A*") else "imagined graph"
        ax.set_title(f"D(c) steps-to-goal from the {source} ({used})", loc="left", fontsize=10.5, color=TEXT)
        ax.set_xticks(range(r.map.cols))
        ax.set_yticks(range(r.map.rows))
        ax.tick_params(length=0, labelsize=8.5, colors=TEXT_2)
        for s in ax.spines.values():
            s.set_visible(False)

    # --- interaction ----------------------------------------------------------------------
    def _on_key(self, event) -> None:
        key = event.key
        if key in ("right", "n"):
            self.draw(self.t + 1)
        elif key in ("left", "p"):
            self.draw(self.t - 1)
        elif key == "home":
            self.draw(0)
        elif key == "end":
            self.draw(self.r.n_states - 1)
        elif key == " ":
            self.playing = not self.playing
            (self.timer.start if self.playing else self.timer.stop)()
        elif key == "q":
            import matplotlib.pyplot as plt
            plt.close(self.fig)

    def _tick(self) -> None:
        if self.t >= self.r.n_states - 1:
            self.playing = False
            self.timer.stop()
            return
        self.draw(self.t + 1)

    def show(self, interval_ms: int = 700) -> None:
        import matplotlib.pyplot as plt

        self.fig.canvas.mpl_connect("key_press_event", self._on_key)
        self.timer = self.fig.canvas.new_timer(interval=interval_ms)
        self.timer.add_callback(self._tick)
        self.draw(0)
        plt.show()

    def export(self, out_dir: str | Path, gif_ms: int = 800) -> list[Path]:
        from PIL import Image

        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        paths, images = [], []
        for t in range(self.r.n_states):
            self.draw(t)
            p = out_dir / f"step_{t:02d}.png"
            self.fig.savefig(p, dpi=110, facecolor=SURFACE)
            paths.append(p)
            images.append(Image.open(p).convert("RGB"))
        gif = out_dir / "replay.gif"
        images[0].save(gif, save_all=True, append_images=images[1:], duration=gif_ms, loop=0)
        return [*paths, gif]


# --- CLI ---------------------------------------------------------------------------------
def load_replay(cfg: dict, run_label: str, seed: int, start: tuple[int, int], runs=None) -> Replay:
    from config import resolve
    from evaluation.runs import build_runs, replay
    from models.decoder import load_decoder

    runs = runs or build_runs(cfg)
    if run_label not in runs:
        raise SystemExit(f"unknown run {run_label!r}; choose from {', '.join(runs)}")
    dec_path = resolve(cfg["encoder"]["decoder_checkpoint"])
    decoder = load_decoder(dec_path) if dec_path.exists() else None
    return Replay(replay(runs[run_label], cfg, seed, start), runs[run_label], decoder, cfg["data"]["cell_px"],
                  eval_seed=seed)


def list_episodes(cfg: dict, run_label: str) -> None:
    from evaluation.navigation_test import run_seeds
    from evaluation.runs import build_runs

    run = build_runs(cfg)[run_label]
    seeds = cfg["evaluation"]["seeds"]
    eps = run_seeds(run.model, run.planner, run.mctx, cfg, seeds)
    per_seed = len(eps) // len(seeds)  # run_seeds loops seeds outside, starts inside
    print(f"{run_label}: {len(eps)} episodes (seed, start -> outcome)")
    for i, e in enumerate(eps):
        how = ("optimal" if e.steps == e.optimal else f"{e.steps} steps (optimal {e.optimal})") if e.success else \
            ("loop failure" if e.loop_failure else "timeout")
        print(f"  --seed {seeds[i // per_seed]} --start {e.start[0]},{e.start[1]}   {how}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay any evaluation episode step by step.")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--run", default="P2", help="Oracle, P0, P1, P2, Random, D1, D2, D3 or Full")
    parser.add_argument("--seed", type=int, default=0, help="evaluation seed (0-4 by default)")
    parser.add_argument("--start", default="0,4", help="start cell as x,y (default: the reference start)")
    parser.add_argument("--episodes", action="store_true", help="list every episode of --run and exit")
    parser.add_argument("--export", type=Path, default=None, help="write step PNGs + replay.gif here, no window")
    args = parser.parse_args()

    import matplotlib
    if args.export or args.episodes:
        matplotlib.use("Agg")
    from config import load_config

    cfg = load_config(args.config)
    if args.episodes:
        list_episodes(cfg, args.run)
        return
    start = tuple(int(v) for v in args.start.split(","))
    replay = load_replay(cfg, args.run, args.seed, start)
    ep = replay.ep
    print(f"{args.run} seed {args.seed} from {start}: "
          f"{'success' if ep.success else 'failure'} in {ep.steps} actions (optimal {ep.optimal}): "
          + " ".join(ARROWS[a] for a in ep.actions))
    dash = Dashboard(replay)
    if args.export:
        files = dash.export(args.export)
        print(f"Wrote {len(files) - 1} step PNGs and {files[-1]}")
    else:
        print("keys: right/left step, home/end, space play/pause, q quit")
        dash.show()


if __name__ == "__main__":
    main()
