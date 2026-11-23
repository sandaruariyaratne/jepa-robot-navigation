"""Diagnostic ladder (build plan step 9): when navigation fails, which part is at fault?

Every rung runs the same planner (P2, the primary one) through the same MPC
loop and seeds; only where the dynamics and the cost come from changes.

  Oracle  A* on the true map                              upper bound
  D1      true dynamics  + true cost  D(c) from true BFS  tests the planner + loop
  D2      true dynamics  + learned cost (imagined D(c))   tests the learned cost
  D3      learned dynamics + true cost                    tests the learned dynamics
  Full    learned dynamics + learned cost                 the real system
  Random  uniform random actions                          lower bound

Codebook entry i is cell i in both models, so a D(c) table from one model
indexes the other directly.
"""

from __future__ import annotations

from dataclasses import dataclass

from planning.mpc import ModelContext, prepare
from planning.planner import P2

from .navigation_test import Oracle, RandomPolicy


@dataclass
class Rung:
    label: str
    dynamics: str
    cost: str
    model: object
    planner: object
    mctx: ModelContext


def build_rungs(true_model, world, goal_frame, p2_horizon: int = 3, snap_each_step: bool = False) -> list[Rung]:
    true_ctx = prepare(true_model, goal_frame)
    learned_ctx = prepare(world, goal_frame)
    p2 = P2(p2_horizon, snap_each_step)
    return [
        Rung("Oracle", "true", "A*", true_model, Oracle(getattr(true_model, "map", None)), true_ctx),
        Rung("D1", "true", "true", true_model, p2, true_ctx),
        Rung("D2", "true", "learned", true_model, p2,
             ModelContext(true_ctx.z_goal, true_ctx.goal_entry, learned_ctx.d_table)),
        Rung("D3", "learned", "true", world, p2,
             ModelContext(learned_ctx.z_goal, learned_ctx.goal_entry, true_ctx.d_table)),
        Rung("Full", "learned", "learned", world, p2, learned_ctx),
        Rung("Random", "-", "-", world, RandomPolicy(), learned_ctx),
    ]


def diagnose(summaries: dict[str, dict]) -> list[str]:
    """Plain-language reading of the ladder, from success and optimal-episode rates."""
    def rate(label, key):
        s = summaries[label]
        return s[key] / s["episodes"]

    lines = []
    d1s, d1o = rate("D1", "success"), rate("D1", "optimal")
    if d1o < 1.0:
        lines.append(f"D1 is {d1o:.0%} optimal with true dynamics and true cost: the planner or loop has a bug.")
    else:
        lines.append("D1 = 100% optimal: the planner and control loop are correct.")
    for rung, part in (("D2", "learned cost D(c)"), ("D3", "learned dynamics")):
        gs, go = d1s - rate(rung, "success"), d1o - rate(rung, "optimal")
        if gs <= 0 and go <= 0:
            lines.append(f"{rung} matches D1: the {part} costs nothing.")
        else:
            lines.append(f"{rung} vs D1: the {part} costs {gs:.0%} success and {go:.0%} optimal episodes.")
    worst_single = min(rate("D2", "optimal"), rate("D3", "optimal"))
    full_o = rate("Full", "optimal")
    if full_o < worst_single:
        lines.append(f"Full ({full_o:.0%} optimal) is below both D2 and D3: the two errors compound.")
    else:
        lines.append(f"Full ({full_o:.0%} optimal) is no worse than the weaker of D2 / D3: no compounding.")
    lines.append(f"Random reaches the goal in {rate('Random', 'success'):.0%} of episodes (lower bound); "
                 f"Oracle in {rate('Oracle', 'success'):.0%}.")
    return lines
