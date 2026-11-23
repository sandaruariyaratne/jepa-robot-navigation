"""Planners P0, P1, P2 (build plan step 8).

Each takes a model (WorldModel or TrueModel), the current latent and a
PlanContext, imagines candidate action sequences, and returns the best one.
Only the first action is executed; the MPC loop then re-observes and replans.

  P0  all 4^5 = 1,024 sequences of 5 steps; cost = ||z_5 - z_goal||^2 (v1.0, kept as ablation)
  P1  beam search, 12 steps, width 64; cost = closest ||z_k - z_goal|| along the way
  P2  all 4^3 = 64 sequences of 3 steps; cost = min over k of [k + D(snap(z_k))] (primary)

Every cost adds revisit_penalty x (times the real robot has already been in the
state the sequence's first step leads to). Exact ties are broken with the
episode's seeded RNG.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import torch

from .imagination import all_action_sequences

INF = float("inf")


@dataclass
class PlanContext:
    z_goal: torch.Tensor                 # latent of the goal image
    d_table: np.ndarray | None           # D(c) per codebook entry (-1 = unreachable); P2 only
    visits: dict[int, int]               # codebook entry -> real visits so far this episode
    revisit_penalty: float
    rng: np.random.Generator


@dataclass
class Plan:
    action: int
    sequence: list[int]
    cost: float
    imagined_entries: list[int]          # snapped entry per imagined step, -1 = unknown
    n_candidates: int
    note: str = ""
    extra: dict = field(default_factory=dict)


def _pick(costs: np.ndarray, rng: np.random.Generator) -> int:
    """Index of the lowest cost; exact ties broken at random with the seeded RNG."""
    best = costs.min()
    ties = np.flatnonzero(costs == best) if np.isfinite(best) else np.arange(len(costs))
    return int(ties[0] if len(ties) == 1 else rng.choice(ties))


def _revisit(model, first_states: torch.Tensor, ctx: PlanContext) -> np.ndarray:
    s = model.snap(first_states)
    counts = np.array([ctx.visits.get(int(i), 0) for i in s.index.reshape(-1).tolist()], dtype=np.float64)
    return ctx.revisit_penalty * counts * s.known.reshape(-1).numpy()


def _per_first_action(first: torch.Tensor, cost: np.ndarray, n_actions: int) -> list[float]:
    """Best cost among candidates starting with each action (inf if none survive)."""
    first = np.asarray(first)
    return [float(cost[first == a].min()) if (first == a).any() else INF for a in range(n_actions)]


def _entries(model, states: torch.Tensor) -> list[int]:
    s = model.snap(states)
    known = torch.cumprod(s.known.long(), dim=-1).bool()  # once unknown, later steps can't be trusted
    return torch.where(known, s.index, torch.full_like(s.index, -1)).tolist()


class P0:
    """Exhaustive 5-step search, cost = final squared latent distance to the goal."""

    name = "P0"

    def __init__(self, horizon: int = 5) -> None:
        self.horizon = horizon

    def plan(self, model, z: torch.Tensor, ctx: PlanContext) -> Plan:
        seqs = all_action_sequences(self.horizon, model.n_actions)
        traj = model.imagine(z, seqs)  # [S, H, D]
        cost = ((traj[:, -1] - ctx.z_goal) ** 2).sum(-1).numpy() + _revisit(model, traj[:, 0], ctx)
        i = _pick(cost, ctx.rng)
        return Plan(int(seqs[i, 0]), seqs[i].tolist(), float(cost[i]), _entries(model, traj[i]), len(seqs),
                    extra={"first_action_costs": _per_first_action(seqs[:, 0], cost, model.n_actions),
                           "imagined": traj[i]})


class P1:
    """Beam search: keep the `width` sequences whose imagined path came closest to the goal."""

    name = "P1"

    def __init__(self, horizon: int = 12, beam_width: int = 64) -> None:
        self.horizon = horizon
        self.width = beam_width

    def plan(self, model, z: torch.Tensor, ctx: PlanContext) -> Plan:
        a = model.n_actions
        one = all_action_sequences(1, a)
        seqs = torch.zeros((1, 0), dtype=torch.int64)
        states = z[None]
        paths = torch.zeros((1, 0, z.shape[-1]))
        closest = np.array([INF])
        penalty = np.zeros(1)
        expanded = 0
        for depth in range(self.horizon):
            b = len(states)
            nxt = model.imagine(states, one)[:, :, 0].reshape(b * a, -1)  # every beam x every action
            expanded += len(nxt)
            seqs = torch.cat([seqs.repeat_interleave(a, 0), torch.arange(a).repeat(b)[:, None]], dim=1)
            paths = torch.cat([paths.repeat_interleave(a, 0), nxt[:, None]], dim=1)
            dist = torch.linalg.norm(nxt - ctx.z_goal, dim=-1).numpy()
            closest = np.minimum(closest.repeat(a), dist)
            penalty = _revisit(model, nxt, ctx) if depth == 0 else penalty.repeat(a)
            key = closest + penalty
            perm = ctx.rng.permutation(len(key))  # random order first, then a stable sort = seeded tie-break
            keep = perm[np.argsort(key[perm], kind="stable")[: self.width]]
            seqs, states, paths = seqs[keep], nxt[keep], paths[keep]
            closest, penalty = closest[keep], penalty[keep]
        cost = closest + penalty
        i = _pick(cost, ctx.rng)
        return Plan(int(seqs[i, 0]), seqs[i].tolist(), float(cost[i]), _entries(model, paths[i]), expanded,
                    extra={"first_action_costs": _per_first_action(seqs[:, 0], cost, a), "imagined": paths[i]})


def snapped_rollout(model, z: torch.Tensor, seqs: torch.Tensor) -> torch.Tensor:
    """Imagine every sequence, continuing each step from the codebook entry the last prediction snapped to.

    Returns the raw one-step predictions [S, H, D]; snapping them gives the same entries and unknown flags
    as walking the imagined graph (build_graph), because every prediction starts from an exact codebook
    latent. Drift cannot accumulate, so the unknown threshold only ever judges one-step predictions.
    """
    states = z.expand(len(seqs), -1) if z.ndim == 1 else z
    out = []
    for k in range(seqs.shape[1]):
        nxt = model.step(states, seqs[:, k])
        out.append(nxt)
        states = model.codebook[model.snap(nxt).index]
    return torch.stack(out, dim=1)


class P2:
    """Exhaustive 3-step search scored with the imagined steps-to-goal table D(c).

    snap_each_step=False (the default, as evaluated in steps 8-12): each sequence is rolled out on the raw
    latents. True: every imagined step is snapped to the codebook before the next one (snapped_rollout).
    """

    def __init__(self, horizon: int = 3, snap_each_step: bool = False) -> None:
        self.horizon = horizon
        self.snap_each_step = snap_each_step
        self.name = "P2s" if snap_each_step else "P2"

    def plan(self, model, z: torch.Tensor, ctx: PlanContext) -> Plan:
        if ctx.d_table is None:
            raise ValueError("P2 needs the D(c) table")
        seqs = all_action_sequences(self.horizon, model.n_actions)
        traj = snapped_rollout(model, z, seqs) if self.snap_each_step else model.imagine(z, seqs)  # [S, H, D]
        s = model.snap(traj)
        known = torch.cumprod(s.known.long(), dim=-1).bool().numpy()  # after an unknown step, stop trusting
        d = np.asarray(ctx.d_table)[s.index.numpy()]
        valid = known & (d >= 0)
        steps = np.arange(1, self.horizon + 1)[None, :]
        cost_k = np.where(valid, steps + d, INF)
        cost = cost_k.min(1) + _revisit(model, traj[:, 0], ctx)
        note = ""
        if not np.isfinite(cost).any():  # nothing known reaches the goal: fall back to latent distance
            cost = ((traj[:, -1] - ctx.z_goal) ** 2).sum(-1).numpy() + _revisit(model, traj[:, 0], ctx)
            note = "fallback: no known path to the goal, used latent distance"
        i = _pick(cost, ctx.rng)
        entries = np.where(known[i], s.index[i].numpy(), -1).tolist()
        return Plan(int(seqs[i, 0]), seqs[i].tolist(), float(cost[i]), entries, len(seqs), note,
                    extra={"first_action_costs": _per_first_action(seqs[:, 0], cost, model.n_actions),
                           "imagined": traj[i]})


def make_planners(cfg: dict) -> list:
    p = cfg["planning"]
    return [P0(p["p0"]["horizon"]), P1(p["p1"]["horizon"], p["p1"]["beam_width"]), P2(p["p2"]["horizon"])]
