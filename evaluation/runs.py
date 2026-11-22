"""Every evaluation run, by label, built one way for both `python -m evaluation` and the dashboard.

    Oracle, P0, P1, P2, Random       navigation rows (planners use the learned model)
    D1, D2, D3, Full                 ladder rungs (P2 with true / learned dynamics and cost)

An episode is identified by (label, seed, start); everything is seeded, so
re-running one reproduces the evaluation episode exactly.
"""

from __future__ import annotations

from dataclasses import dataclass

from config import resolve
from environment import GridWorld
from planning.imagination import WorldModel
from planning.mpc import Episode, ModelContext, prepare, run_episode
from planning.planner import make_planners
from planning.true_model import TrueModel

from .ladder import build_rungs
from .navigation_test import Oracle, RandomPolicy, episode_seed

NAVIGATION = ("Oracle", "P0", "P1", "P2", "Random")
LADDER = ("Oracle", "D1", "D2", "D3", "Full", "Random")


@dataclass
class Run:
    label: str
    model: object
    planner: object
    mctx: ModelContext
    dynamics: str  # "true" | "learned" | "-"
    cost: str


def load_world(cfg: dict) -> WorldModel:
    return WorldModel.from_checkpoints(resolve(cfg["encoder"]["checkpoint"]), resolve(cfg["predictor"]["checkpoint"]),
                                       cfg["imagination"]["unknown_factor"])


def build_runs(cfg: dict, true_model=None, world=None, goal_frame=None) -> dict[str, Run]:
    true_model = true_model if true_model is not None else TrueModel()
    world = world if world is not None else load_world(cfg)
    goal_frame = goal_frame if goal_frame is not None else GridWorld().goal_obs()
    learned_ctx = prepare(world, goal_frame)
    true_ctx = prepare(true_model, goal_frame)

    runs = {"Oracle": Run("Oracle", true_model, Oracle(), true_ctx, "true", "A*")}
    for p in make_planners(cfg):
        cost = "learned D(c)" if p.name == "P2" else "latent distance"
        runs[p.name] = Run(p.name, world, p, learned_ctx, "learned", cost)
    runs["Random"] = Run("Random", world, RandomPolicy(), learned_ctx, "-", "-")
    for r in build_rungs(true_model, world, goal_frame, cfg["planning"]["p2"]["horizon"]):
        if r.label in ("D1", "D2", "D3"):
            runs[r.label] = Run(r.label, r.model, r.planner, r.mctx, r.dynamics, r.cost)
    full = runs["P2"]
    runs["Full"] = Run("Full", full.model, full.planner, full.mctx, "learned", "learned")
    return runs


def replay(run: Run, cfg: dict, seed: int, start: tuple[int, int], record: bool = True) -> Episode:
    """Re-run one evaluation episode (same seed formula as evaluation.navigation_test.run_seeds)."""
    env = GridWorld(terminate_on_goal=True)
    starts = env.map.start_cells()
    if tuple(start) not in starts:
        raise ValueError(f"start {start} is not one of the 24 start cells")
    p = cfg["planning"]
    return run_episode(env, run.model, run.planner, run.mctx, tuple(start), episode_seed(seed, starts.index(tuple(start))),
                       max_actions=p["max_actions"], max_visits=p["max_visits"], revisit_penalty=p["revisit_penalty"],
                       record=record)
