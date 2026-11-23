"""The shared control loop (build plan step 8): `python -m planning.mpc`.

    observe -> encode -> plan (imagination only) -> execute the first action -> repeat

Stops when the robot reaches the goal, after max_actions, or on the third
visit to the same cell (a loop failure). The planner sees only the model, the
current observation and the goal image; the simulator is used solely to
execute actions and, by the harness, to score the episode.

The CLI runs P0, P1 and P2 from all 24 starts with two models:
  true     -- the simulator as the model (TrueModel): checks the planners themselves
  learned  -- frozen encoder + predictor + codebook (WorldModel)
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import torch

from environment import ACTION_NAMES, GridWorld, distances_to_goal

from .latent_graph import build_graph, goal_entry, steps_to_goal
from .planner import PlanContext, make_planners


@dataclass
class ModelContext:
    """Per-model things computed once: goal latent, goal entry and D(c)."""

    z_goal: torch.Tensor
    goal_entry: int
    d_table: np.ndarray


def prepare(model, goal_frame: np.ndarray) -> ModelContext:
    goal, _ = goal_entry(model, goal_frame)
    return ModelContext(model.encode(goal_frame), goal, steps_to_goal(build_graph(model), goal))


@dataclass
class Episode:
    planner: str
    start: tuple[int, int]
    seed: int
    success: bool
    steps: int
    optimal: int
    collisions: int
    loop_failure: bool
    timeout: bool
    path: list[tuple[int, int]]
    actions: list[int]
    plans: list[dict] = field(default_factory=list)
    frames: list[np.ndarray] | None = None  # observations, only when recorded (for replay)

    @property
    def path_ratio(self) -> float | None:
        return self.steps / self.optimal if self.success else None


def run_episode(env: GridWorld, model, planner, mctx: ModelContext, start: tuple[int, int], seed: int,
                max_actions: int = 30, max_visits: int = 3, revisit_penalty: float = 0.5,
                record: bool = False) -> Episode:
    """One episode. record=True also keeps every observation and each plan's `extra`
    (per-action costs, imagined latents) for replay; it does not change what happens."""
    rng = np.random.default_rng(seed)
    obs = env.reset(start=start)
    frames = [obs] if record else None
    optimal = int(distances_to_goal(env.map)[start[1], start[0]])  # harness scoring only
    cell_visits = Counter({env.pos: 1})   # harness: loop detection on true cells
    entry_visits: Counter = Counter()     # agent: visits by snapped codebook entry, for the revisit penalty
    path, actions, plans = [env.pos], [], []
    collisions, success, loop_failure = 0, False, False

    def note_visit(z):
        s = model.snap(z)
        if bool(s.known):
            entry_visits[int(s.index)] += 1

    z = model.encode(obs)
    note_visit(z)
    for _ in range(max_actions):
        ctx = PlanContext(mctx.z_goal, mctx.d_table, dict(entry_visits), revisit_penalty, rng)
        t0 = time.perf_counter()
        plan = planner.plan(model, z, ctx)
        entry = {"action": plan.action, "sequence": plan.sequence, "cost": plan.cost,
                 "imagined_entries": plan.imagined_entries, "note": plan.note,
                 "ms": round(1000 * (time.perf_counter() - t0), 2)}
        if record:
            entry["extra"] = plan.extra
            entry["visits"] = dict(entry_visits)
        plans.append(entry)
        r = env.step(plan.action)
        if record:
            frames.append(r.obs)
        actions.append(plan.action)
        path.append(r.pos)
        collisions += int(r.collision)
        cell_visits[r.pos] += 1
        z = model.encode(r.obs)  # re-observe
        note_visit(z)
        if r.terminated:
            success = True
            break
        if cell_visits[r.pos] >= max_visits:
            loop_failure = True
            break
    timeout = not success and not loop_failure
    return Episode(planner.name, tuple(start), seed, success, len(actions), optimal, collisions,
                   loop_failure, timeout, path, actions, plans, frames)


def summarize(episodes: list[Episode]) -> dict:
    n = len(episodes)
    ok = [e for e in episodes if e.success]
    acts = sum(e.steps for e in episodes)
    return {
        "episodes": n,
        "success": len(ok),
        "optimal": sum(e.success and e.steps == e.optimal for e in episodes),
        "mean_path_ratio": float(np.mean([e.path_ratio for e in ok])) if ok else None,
        "collision_rate": sum(e.collisions for e in episodes) / acts if acts else 0.0,
        "loop_failures": sum(e.loop_failure for e in episodes),
        "timeouts": sum(e.timeout for e in episodes),
        "mean_plan_ms": float(np.mean([p["ms"] for e in episodes for p in e.plans])) if acts else 0.0,
    }


def run_all(model, planners, cfg: dict, goal_frame: np.ndarray, seed: int | None = None) -> dict[str, list[Episode]]:
    p = cfg["planning"]
    seed = cfg["seed"] if seed is None else seed
    env = GridWorld(terminate_on_goal=True)
    mctx = prepare(model, goal_frame)
    out = {}
    for planner in planners:
        out[planner.name] = [
            run_episode(env, model, planner, mctx, start, seed=int(np.random.SeedSequence([seed, i]).generate_state(1)[0]),
                        max_actions=p["max_actions"], max_visits=p["max_visits"], revisit_penalty=p["revisit_penalty"])
            for i, start in enumerate(env.map.start_cells())
        ]
    return out


def done_checks(results: dict[str, dict[str, list[Episode]]]) -> dict[str, bool]:
    every = all(len(eps) == 24 and all(e.steps > 0 for e in eps)
                for per_model in results.values() for eps in per_model.values())
    p2 = results["true"]["P2"]
    return {
        "every planner runs full episodes": every,
        "P2 with the true simulator reaches the goal optimally from all 24 starts":
            all(e.success and e.steps == e.optimal for e in p2),
    }


def print_report(results: dict[str, dict[str, list[Episode]]]) -> None:
    print(f"\n{'model':<9}{'planner':<9}{'success':>9}{'optimal':>9}{'path ratio':>12}{'collisions':>12}"
          f"{'loops':>7}{'timeouts':>10}{'ms/plan':>9}")
    for model_name, per_planner in results.items():
        for name, eps in per_planner.items():
            s = summarize(eps)
            ratio = f"{s['mean_path_ratio']:.2f}" if s["mean_path_ratio"] is not None else "-"
            print(f"{model_name:<9}{name:<9}{s['success']:>6}/24{s['optimal']:>6}/24{ratio:>12}"
                  f"{s['collision_rate']:>11.1%}{s['loop_failures']:>7}{s['timeouts']:>10}{s['mean_plan_ms']:>9.1f}")
    for model_name, per_planner in results.items():
        for name, eps in per_planner.items():
            bad = [e for e in eps if not (e.success and e.steps == e.optimal)]
            if bad and model_name == "learned":
                print(f"\n{model_name} {name}: {len(bad)} episodes not optimal")
                for e in bad[:6]:
                    how = "loop" if e.loop_failure else "timeout" if e.timeout else f"{e.steps} steps (optimal {e.optimal})"
                    print(f"  start {e.start}: {how}  " + " ".join(ACTION_NAMES[a][0] for a in e.actions))
                if len(bad) > 6:
                    print(f"  ... {len(bad) - 6} more")
    print()
    for name, ok in done_checks(results).items():
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")


def main() -> None:
    from config import load_config, resolve

    from .imagination import WorldModel
    from .true_model import TrueModel

    parser = argparse.ArgumentParser(description="Run P0, P1 and P2 from every start with the true and learned models.")
    parser.add_argument("--config", type=Path, default=None, help="config file (default: configs/single_map.yaml)")
    args = parser.parse_args()
    cfg = load_config(args.config)
    planners = make_planners(cfg)
    goal_frame = GridWorld().goal_obs()
    models = {
        "true": TrueModel(),
        "learned": WorldModel.from_checkpoints(resolve(cfg["encoder"]["checkpoint"]),
                                               resolve(cfg["predictor"]["checkpoint"]),
                                               cfg["imagination"]["unknown_factor"]),
    }
    results = {}
    for name, model in models.items():
        t0 = time.perf_counter()
        results[name] = run_all(model, planners, cfg, goal_frame)
        print(f"{name} model: {sum(len(v) for v in results[name].values())} episodes in {time.perf_counter() - t0:.1f}s")
    print_report(results)

    out = resolve(cfg["planning"]["metrics"])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "done_checks": done_checks(results),
        "summary": {m: {p: summarize(e) for p, e in per.items()} for m, per in results.items()},
        "episodes": {m: {p: [asdict(e) for e in eps] for p, eps in per.items()} for m, per in results.items()},
    }, indent=1) + "\n")
    print(f"\nSaved {out}")
    if not all(done_checks(results).values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
