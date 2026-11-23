"""Planning without a picture of every cell: `python -m multimap.explore --set val_maze_maps`.

Everywhere else the planner gets a per-map codebook: one rendered frame of the
robot on every free cell, encoded before the episode starts. That is privileged:
a real agent never sees itself in places it has not been. Here the agent gets
only real observations.

  anchors   latents of real pictures: the start observation and the goal image
            (the task specification); in level B also every observation so far
  grow      imagine all 4 moves from every node, breadth first from the anchors.
            A prediction within `threshold` of an existing node is that node
            (a blocked move lands on its own node); otherwise it becomes a new,
            imagined node and is expanded in turn. Stops when nothing new
            appears, or at `max_nodes`.
  plan      the grown nodes are the codebook: the imagined graph, D(c) and the
            snapped P2 planner are exactly those of the privileged setting.

  A (imagine)  grow once from the start and goal pictures, then act; each new
               observation is only snapped to the existing nodes.
  B (explore)  after every move to a cell not seen before, add its picture as an
               anchor and regrow: real pictures replace imagined ones as the
               robot walks, and their surroundings are re-imagined from them.
               Every move actually made (a blocked one included) overrides the
               imagined edge for that cell and action: experience beats imagination.

Planning walks the graph (GraphP2): every 3-move sequence from the current node,
cost = min_k [k + D(node_k)] + revisit penalty, steps after an unknown edge
untrusted. From a node this is the snapped P2 of the privileged setting, but it
can use edges that were experienced rather than imagined.

The simulator executes actions and scores episodes; map-quality metrics compare
nodes with the true cells' latents (harness only, never shown to the agent).
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch

from config import load_config, resolve
from environment import GridWorld, distances_to_goal
from evaluation.probes import CellIndex
from models.encoder import load_encoder
from models.predictor import load_predictor
from planning.imagination import WorldModel
from planning.latent_graph import build_graph, steps_to_goal
from planning.imagination import all_action_sequences
from planning.planner import _pick
from planning.true_model import TrueModel

from .maps import load_maps

MODES = ("privileged", "imagine", "explore")
ALL_MODES = (*MODES, "oracle")       # oracle: true walls once seen, unseen cells assumed free (fog-of-war baseline)


@dataclass
class ImaginedMap:
    world: WorldModel          # codebook = grown nodes (anchors first)
    n_anchors: int
    next: np.ndarray           # [nodes, A] successor node (self-loop where unknown or blocked)
    known: np.ndarray          # [nodes, A]
    d: np.ndarray              # imagined steps to the goal per node
    goal: int                  # node of the goal image (an anchor)
    overflow: bool             # growth stopped at max_nodes
    d_frontier: np.ndarray | None = None   # B: steps to the nearest node only imagined, never seen


def steps_to_any(nxt: np.ndarray, targets) -> np.ndarray:
    """Multi-source BFS backwards over the edges: steps from every node to the nearest target (-1 = none)."""
    g = type("G", (), {"next": nxt, "n_entries": len(nxt)})()
    best = np.full(len(nxt), -1)
    for t in targets:                                   # tiny graphs: one BFS per target is fine
        d = steps_to_goal(g, int(t))
        best = np.where((d >= 0) & ((best < 0) | (d < best)), d, best)
    return best


def _frontier(m: ImaginedMap) -> ImaginedMap:
    m.d_frontier = steps_to_any(m.next, range(m.n_anchors, len(m.next)))
    return m


def with_experience(m: ImaginedMap, experienced: dict[tuple[int, int], int]) -> ImaginedMap:
    """Replace imagined edges by the transitions actually observed (anchor -> anchor), recompute D."""
    nxt, known = m.next.copy(), m.known.copy()
    for (u, a), v in experienced.items():
        nxt[u, a], known[u, a] = v, True
    g = type("G", (), {"next": nxt, "n_entries": len(nxt)})()
    return ImaginedMap(m.world, m.n_anchors, nxt, known, steps_to_goal(g, m.goal), m.goal, m.overflow,
                       steps_to_any(nxt, range(m.n_anchors, len(nxt))))


class GraphP2:
    """Snapped P2 as a walk on the (possibly experience-corrected) graph."""

    def __init__(self, horizon: int = 3, n_actions: int = 4) -> None:
        self.seqs = all_action_sequences(horizon, n_actions).numpy()

    def plan(self, m: ImaginedMap, node: int, z_goal: torch.Tensor, visits: Counter, penalty: float, rng) -> tuple[int, str]:
        cost, cur, rev = self._score(m, m.d, node, visits, penalty)
        total, how = cost + rev, "goal"
        if not np.isfinite(total).any() and m.d_frontier is not None:   # B: no route seen; go and look
            cost, cur, rev = self._score(m, m.d_frontier, node, visits, penalty)
            total, how = cost + rev, "frontier"
        if not np.isfinite(total).any():                # nothing known: closest imagined end state to the goal
            total = ((m.world.codebook[torch.as_tensor(cur)] - z_goal) ** 2).sum(-1).numpy() + rev
            how = "fallback"
        return int(self.seqs[_pick(total, rng), 0]), how

    def _score(self, m: ImaginedMap, dist: np.ndarray, node: int, visits: Counter, penalty: float):
        s, h = self.seqs.shape
        cur = np.full(s, node)
        trusted = np.ones(s, bool)
        cost = np.full(s, np.inf)
        first = None
        for k in range(h):
            a = self.seqs[:, k]
            trusted &= m.known[cur, a]
            cur = m.next[cur, a]
            if k == 0:
                first, first_known = cur.copy(), trusted.copy()
            d = dist[cur]
            ok = trusted & (d >= 0)
            cost = np.where(ok, np.minimum(cost, k + 1 + d), cost)
        rev = penalty * np.array([visits.get(int(f), 0) for f in first]) * first_known
        return cost, cur, rev


def fog_thresholds(cfg: dict, verbose: bool = False) -> dict:
    """Stay and merge thresholds from the validation split of the training maps (saved next to the predictor).

    stay  = 99% quantile of |prediction - own cell| over blocked moves;
    merge = 1% quantile of |prediction - nearest wrong cell| over real moves (wrong merges <= ~1%).
    """
    mm = cfg["multimap"]
    path = resolve(mm["predictor"]["checkpoint"]).with_name("fog_thresholds.json")
    if path.exists():
        return json.loads(path.read_text())
    from planning.true_model import TrueModel
    maps, splits = load_maps(resolve(mm["maps_path"]))
    encoder, _ = load_encoder(resolve(mm["encoder"]["checkpoint"]))
    predictor, _ = load_predictor(resolve(mm["predictor"]["checkpoint"]))
    blocked, wrong, right = [], [], []
    with torch.no_grad():
        for m in splits["val"]:
            grid = maps[m]
            env, cells = GridWorld(grid), CellIndex(grid).cells
            z = encoder.standardize(encoder(torch.as_tensor(np.stack([env.render((int(x), int(y))) for x, y in cells]))))
            tn, n = TrueModel(grid).next.numpy(), len(cells)
            p = predictor(z.repeat_interleave(4, 0), torch.arange(4).repeat(n)).view(n, 4, -1)
            for i in range(n):
                for a in range(4):
                    d = torch.linalg.norm(z - p[i, a], dim=-1)
                    if tn[i, a] == i:
                        blocked.append(float(d[i]))
                    else:
                        right.append(float(d[tn[i, a]]))
                        d[[i, int(tn[i, a])]] = float("inf")
                        wrong.append(float(d.min()))
    out = {"stay": float(np.quantile(blocked, 0.99)), "merge": float(np.quantile(wrong, 0.01)),
           "rule": "stay: 99% quantile of |pred - own cell| (blocked moves); merge: 1% quantile of "
                   "|pred - nearest wrong cell| (real moves); validation split of the training maps",
           "blocked_moves": len(blocked), "real_moves": len(right),
           "real_moves_within_merge_of_true_cell": float(np.mean(np.array(right) <= np.quantile(wrong, 0.01)))}
    path.write_text(json.dumps(out, indent=1) + "\n")
    if verbose:
        print(out)
    return out


def split_threshold(threshold) -> tuple[float | None, float]:
    """One threshold (stay = merge, as on the 6 x 5 grid) or (stay, merge) for fog of war.

    stay:  a prediction this close to the node it came from is a blocked move.
    merge: otherwise, a prediction this close to another node is that node; farther = a new node.
    """
    return tuple(threshold) if isinstance(threshold, (tuple, list)) else (None, float(threshold))


@torch.no_grad()
def grow(encoder, predictor, anchors: torch.Tensor, threshold, max_nodes: int = 60) -> tuple[torch.Tensor, bool]:
    """Nodes reachable in imagination from the anchors [K, D]; anchors stay at indices 0..K-1."""
    stay, merge = split_threshold(threshold)
    nodes = anchors.clone()
    frontier = torch.arange(len(nodes))
    acts = torch.arange(predictor.n_actions)
    overflow = False
    while len(frontier):
        pred = predictor(nodes[frontier].repeat_interleave(len(acts), 0), acts.repeat(len(frontier)))
        d = torch.cdist(pred, nodes)
        if stay is None:
            far = d.min(1).values > merge                             # not an existing node (nor a blocked move)
        else:
            rows, src = torch.arange(len(pred)), frontier.repeat_interleave(len(acts))
            blocked = d[rows, src] <= stay
            d[rows, src] = float("inf")
            far = ~blocked & (d.min(1).values > merge)
        new: list[torch.Tensor] = []
        for p in pred[far]:                                           # in order, so new nodes can merge
            if new and torch.linalg.norm(torch.stack(new) - p, dim=-1).min() <= merge:
                continue
            if len(nodes) + len(new) >= max_nodes:
                overflow = True
                continue
            new.append(p)
        frontier = torch.arange(len(nodes), len(nodes) + len(new))
        if new:
            nodes = torch.cat([nodes, torch.stack(new)])
    return nodes, overflow


def imagined_map(encoder, predictor, anchors: torch.Tensor, goal: int, threshold,
                 max_nodes: int = 60) -> ImaginedMap:
    stay, merge = split_threshold(threshold)
    nodes, overflow = grow(encoder, predictor, anchors, threshold, max_nodes)
    return graph_map(WorldModel(encoder, predictor, nodes, merge, 1.0), len(anchors), goal, overflow, stay)


@torch.no_grad()
def two_threshold_graph(world: WorldModel, stay: float) -> "LatentGraph":
    """build_graph with a separate stay threshold: blocked if the prediction stays within `stay` of its own node;
    otherwise the nearest other node if within the merge (unknown) threshold, else unknown (self-loop)."""
    from planning.latent_graph import LatentGraph
    c, a = world.n_entries, world.n_actions
    p = world.step(world.codebook.repeat_interleave(a, dim=0), torch.arange(a).repeat(c))
    d = torch.cdist(p, world.codebook)
    rows, src = torch.arange(c * a), torch.arange(c).repeat_interleave(a)
    d_self = d[rows, src].clone()
    blocked = d_self <= stay
    d[rows, src] = float("inf")
    dist, idx = d.min(1)
    hit = ~blocked & (dist <= world.unknown_threshold)
    nxt = torch.where(hit, idx, src)
    return LatentGraph(nxt.view(c, a).numpy(), torch.where(blocked, src, idx).view(c, a).numpy(),
                       (blocked | hit).view(c, a).numpy(), torch.where(blocked, d_self, dist).view(c, a).numpy())


def graph_map(world: WorldModel, n_anchors: int, goal: int, overflow: bool = False,
              stay: float | None = None) -> ImaginedMap:
    g = build_graph(world) if stay is None else two_threshold_graph(world, stay)
    return ImaginedMap(world, n_anchors, g.next, g.known, steps_to_goal(g, goal), goal, overflow)


# --- harness: how good is the imagined map? ------------------------------------------------
@torch.no_grad()
def map_quality(m: ImaginedMap, cell_latents: torch.Tensor, cells: list, grid, start_node: int, start_cell) -> dict:
    """Match every node to its nearest true cell latent and compare graph and D(c) with the truth."""
    dist = torch.cdist(m.world.codebook, cell_latents)                 # [nodes, cells]
    near, cell_of = dist.min(1)
    real = near <= m.world.unknown_threshold
    cell_of = np.where(real.numpy(), cell_of.numpy(), -1)
    covered = set(cell_of[cell_of >= 0].tolist())
    true = TrueModel(grid)
    g = m
    edges = correct = 0
    for u in range(len(cell_of)):
        if cell_of[u] < 0:
            continue
        for a in range(4):
            edges += 1
            correct += int(cell_of[g.next[u, a]] == int(true.next[cell_of[u], a]))
    dt = distances_to_goal(grid)
    return {"nodes": len(cell_of), "cells": len(cells), "covered": len(covered),
            "duplicates": int((cell_of >= 0).sum() - len(covered)), "spurious": int((cell_of < 0).sum()),
            "edges": edges, "edges_correct": correct, "overflow": m.overflow,
            "d_start": int(m.d[start_node]), "d_start_true": int(dt[start_cell[1], start_cell[0]]),
            "exact": len(covered) == len(cells) and len(cell_of) == len(cells) and correct == edges}


# --- one episode ----------------------------------------------------------------------------
@torch.no_grad()
def run(mode: str, env: GridWorld, encoder, predictor, goal_frame, start, seed: int, cfg: dict, threshold: float,
        privileged: torch.Tensor | None = None, max_nodes: int = 60) -> dict:
    p = cfg["planning"]
    planner = GraphP2(p["p2"]["horizon"], predictor.n_actions)
    rng = np.random.default_rng(seed)
    obs = env.reset(start=start)
    enc = lambda f: encoder.standardize(encoder(torch.as_tensor(f)[None]))[0]   # noqa: E731
    z_goal, z = enc(goal_frame), enc(obs)
    if mode == "privileged":
        stay, merge = split_threshold(threshold)
        world = WorldModel(encoder, predictor, privileged, merge, 1.0)
        m = graph_map(world, len(privileged), int(world.snap(z_goal).index), stay=stay)
    else:
        m = imagined_map(encoder, predictor, torch.stack([z, z_goal]), 1, threshold, max_nodes)
    first_map = m
    if mode == "explore":
        m = _frontier(m)
    experienced: dict[tuple[int, int], int] = {}
    optimal = int(distances_to_goal(env.map)[start[1], start[0]])
    cell_visits, entry_visits = Counter({env.pos: 1}), Counter()
    node = int(m.world.snap(z).index)                    # an anchor in A and B (exact), a cell entry if privileged
    entry_visits[node] += 1
    steps = collisions = rebuilds = fallbacks = frontier = 0
    success = loop = False
    for _ in range(p["max_actions"]):
        action, how = planner.plan(m, node, z_goal, entry_visits, p["revisit_penalty"], rng)
        fallbacks += int(how == "fallback")
        frontier += int(how == "frontier")
        r = env.step(action)
        steps += 1
        collisions += int(r.collision)
        cell_visits[r.pos] += 1
        z = enc(r.obs)
        if mode == "explore":
            dist = torch.linalg.norm(m.world.codebook[: m.n_anchors] - z, dim=-1)
            if dist.min() > 1e-4:                         # a cell never seen before: new anchor, regrow
                anchors = torch.cat([m.world.codebook[: m.n_anchors], z[None]])
                m = imagined_map(encoder, predictor, anchors, m.goal, threshold, max_nodes)
                rebuilds += 1
                new = m.n_anchors - 1
            else:
                new = int(dist.argmin())
            experienced[(node, action)] = new
            m = with_experience(m, experienced)
            node = new
        else:
            node = int(m.world.snap(z).index)             # A: localise on the imagined map, no corrections
        entry_visits[node] += 1
        if r.terminated:
            success = True
            break
        if cell_visits[r.pos] >= p["max_visits"]:
            loop = True
            break
    return {"success": success, "steps": steps, "optimal": optimal, "loop": loop, "collisions": collisions,
            "rebuilds": rebuilds, "fallbacks": fallbacks, "frontier": frontier, "first_map": first_map}


def run_oracle(env: GridWorld, start, cfg: dict) -> dict:
    """Optimistic planning with perfect perception: walls are known exactly once inside the view radius,
    unseen cells are assumed free; follow a shortest path on that map and re-plan after every move.
    The cost of not seeing the map, with no model errors at all."""
    from environment import GridMap
    p, grid = cfg["planning"], env.map
    r = grid.view_radius
    env.reset(start=start)
    known: set = set()

    def reveal(pos):
        for y in range(grid.rows):
            for x in range(grid.cols):
                if (x, y) in grid.walls and (r is None or max(abs(x - pos[0]), abs(y - pos[1])) <= r):
                    known.add((x, y))

    pos = tuple(start)
    reveal(pos)
    optimal = int(distances_to_goal(grid)[start[1], start[0]])
    visits = Counter({pos: 1})
    steps = collisions = 0
    success = loop = False
    for _ in range(p["max_actions"]):
        d = distances_to_goal(GridMap(cols=grid.cols, rows=grid.rows, walls=frozenset(known), goal=grid.goal))
        best = min(range(4), key=lambda a: d[grid.transition(pos, a)[0][1], grid.transition(pos, a)[0][0]]
                   if grid.transition(pos, a)[0] != pos else 10 ** 9)
        res = env.step(best)
        steps += 1
        collisions += int(res.collision)
        pos = res.pos
        reveal(pos)
        visits[pos] += 1
        if res.terminated:
            success = True
            break
        if visits[pos] >= p["max_visits"]:
            loop = True
            break
    return {"success": success, "steps": steps, "optimal": optimal, "loop": loop, "collisions": collisions,
            "rebuilds": 0, "fallbacks": 0, "frontier": 0, "first_map": None}


# --- evaluation over a map set ---------------------------------------------------------------
def evaluate(cfg: dict, set_key: str, modes=MODES, threshold: float | None = None, max_nodes: int = 60,
             limit: int | None = None, verbose: bool = True, shard: tuple[int, int] = (0, 1)) -> dict:
    """shard (i, n): only maps k with k % n == i (start cells and seeds stay those of the whole run)."""
    mm, nm = cfg["multimap"], cfg["multimap"][set_key]
    if not resolve(nm["maps_path"]).exists():          # build the set (and its episodes) as multimap.new_maps does
        from .new_maps import new_maps_and_data
        new_maps_and_data(cfg, set_key)
    maps, _ = load_maps(resolve(nm["maps_path"]))
    maps = maps[:limit] if limit else maps
    if set(modes) == {"oracle"}:                       # the oracle needs no model
        return _evaluate_oracle(cfg, set_key, maps, limit, verbose)
    encoder, _ = load_encoder(resolve(mm["encoder"]["checkpoint"]))
    predictor, _ = load_predictor(resolve(mm["predictor"]["checkpoint"]))
    encoder.eval(), predictor.eval()
    if threshold is None:
        from .calibrate import load_threshold
        threshold = load_threshold(cfg)["threshold"]
    per_mode = {m: threshold for m in modes}
    if mm.get("explore", {}).get("two_thresholds") and not isinstance(threshold, (tuple, list)):
        # fog: imagined maps (A, B) need separate stay / merge thresholds; the full codebook keeps the
        # calibrated one, which did better there on validation (REPORT section 12)
        t = fog_thresholds(cfg)
        per_mode.update({m: (t["stay"], t["merge"]) for m in modes if m in ("imagine", "explore")})
    tot = {m: Counter() for m in modes}
    quality = {m: Counter() for m in modes if m in ("imagine", "explore")}
    by_len = {m: defaultdict(Counter) for m in modes}
    t0 = time.perf_counter()
    for k, grid in enumerate(maps):
        if k % shard[1] != shard[0]:
            continue
        env = GridWorld(grid, terminate_on_goal=True)
        cells = CellIndex(grid).cells
        frames = np.stack([env.render((int(x), int(y))) for x, y in cells])
        with torch.no_grad():
            cell_latents = encoder.standardize(encoder(torch.as_tensor(frames)))
        goal_frame = env.render(grid.goal)
        index = {(int(x), int(y)): i for i, (x, y) in enumerate(cells)}
        for i, start in _starts(grid, nm, k):
            for seed in nm["nav_seeds"]:
                s = int(np.random.SeedSequence([seed, i]).generate_state(1)[0])
                for mode in modes:
                    e = (run_oracle(env, start, cfg) if mode == "oracle" else
                         run(mode, env, encoder, predictor, goal_frame, start, s, cfg, per_mode[mode], cell_latents,
                             max_nodes))
                    opt = e["success"] and e["steps"] == e["optimal"]
                    t = tot[mode]
                    t.update(episodes=1, success=int(e["success"]), optimal=int(opt), loops=int(e["loop"]),
                             steps=e["steps"], collisions=e["collisions"], rebuilds=e["rebuilds"],
                             fallback_plans=e["fallbacks"], frontier_plans=e["frontier"], extra_steps=(e["steps"] - e["optimal"]) if e["success"] else 0)
                    b = by_len[mode][e["optimal"]]
                    b.update(episodes=1, success=int(e["success"]), optimal=int(opt))
                    if mode in quality and seed == nm["nav_seeds"][0]:      # the first map does not depend on the seed
                        q = map_quality(e["first_map"], cell_latents, cells, grid, 0, start)
                        quality[mode].update(maps=1, exact=int(q["exact"]), nodes=q["nodes"], cells=q["cells"],
                                             covered=q["covered"], duplicates=q["duplicates"], spurious=q["spurious"],
                                             edges=q["edges"], edges_correct=q["edges_correct"],
                                             overflow=int(q["overflow"]), d_start_exact=int(q["d_start"] == q["d_start_true"]),
                                             d_start_unreachable=int(q["d_start"] < 0))
        if verbose and ((k + 1) % 25 == 0 or k + 1 == len(maps)):
            line = ", ".join(f"{m} {tot[m]['success'] / tot[m]['episodes']:.1%}/{tot[m]['optimal'] / tot[m]['episodes']:.1%}"
                             for m in modes)
            who = f"[{shard[0] + 1}/{shard[1]}] " if shard[1] > 1 else ""
            print(f"  {who}{k + 1} maps ({time.perf_counter() - t0:.0f}s): success/shortest {line}", flush=True)
    return {"set": set_key, "title": nm.get("title", set_key), "n_maps": len(range(shard[0], len(maps), shard[1])),
            "threshold": per_mode if len({str(v) for v in per_mode.values()}) > 1 else threshold,
            "max_nodes": max_nodes, "modes": list(modes), "nav_starts": nm.get("nav_starts"),
            "navigation": {m: dict(v) for m, v in tot.items()},
            "first_map_quality": {m: dict(v) for m, v in quality.items()},
            "by_path_length": {m: {int(k): dict(v) for k, v in sorted(d.items())} for m, d in by_len.items()},
            "seconds": round(time.perf_counter() - t0)}


def _evaluate_shard(args):
    cfg, set_key, modes, threshold, max_nodes, limit, shard = args
    torch.set_num_threads(1)
    return evaluate(cfg, set_key, modes, threshold, max_nodes, limit, True, shard)


def evaluate_parallel(cfg: dict, set_key: str, modes=MODES, threshold=None, max_nodes: int = 60,
                      limit: int | None = None, workers: int = 1) -> dict:
    """evaluate() split over `workers` processes by map; counts are summed, so the result is the same."""
    if workers <= 1 or set(modes) == {"oracle"}:      # the oracle is fast and not sharded
        return evaluate(cfg, set_key, modes, threshold, max_nodes, limit)
    import multiprocessing as mp
    with mp.get_context("spawn").Pool(workers) as pool:
        parts = pool.map(_evaluate_shard, [(cfg, set_key, modes, threshold, max_nodes, limit, (i, workers))
                                           for i in range(workers)])
    return merge_results(parts)


def merge_results(parts: list[dict]) -> dict:
    def add(dicts):
        c = Counter()
        for d in dicts:
            c.update(d)
        return dict(c)
    out = dict(parts[0])
    out["n_maps"] = sum(p["n_maps"] for p in parts)
    out["navigation"] = {m: add(p["navigation"][m] for p in parts) for m in out["modes"]}
    out["first_map_quality"] = {m: add(p["first_map_quality"][m] for p in parts) for m in parts[0]["first_map_quality"]}
    out["by_path_length"] = {m: {L: add(p["by_path_length"][m].get(L, {}) for p in parts)
                                 for L in sorted({L for p in parts for L in p["by_path_length"][m]})}
                             for m in out["modes"]}
    out["seconds"] = max(p["seconds"] for p in parts)
    return out


def _starts(grid, nm: dict, k: int):
    starts = list(enumerate(grid.start_cells()))
    if nm.get("nav_starts") and nm["nav_starts"] < len(starts):       # a seeded subset of start cells
        pick = np.random.default_rng([nm["seed"], k]).choice(len(starts), nm["nav_starts"], replace=False)
        starts = [starts[j] for j in sorted(pick)]
    return starts


def _evaluate_oracle(cfg: dict, set_key: str, maps, limit, verbose) -> dict:
    nm = cfg["multimap"][set_key]
    tot, by_len = Counter(), defaultdict(Counter)
    for k, grid in enumerate(maps):
        env = GridWorld(grid, terminate_on_goal=True)
        for i, start in _starts(grid, nm, k):
            for _ in nm["nav_seeds"]:                  # deterministic; repeated so the episode counts match
                e = run_oracle(env, start, cfg)
                opt = e["success"] and e["steps"] == e["optimal"]
                tot.update(episodes=1, success=int(e["success"]), optimal=int(opt), loops=int(e["loop"]), steps=e["steps"],
                           collisions=e["collisions"], extra_steps=(e["steps"] - e["optimal"]) if e["success"] else 0)
                by_len[e["optimal"]].update(episodes=1, success=int(e["success"]), optimal=int(opt))
    return {"set": set_key, "title": nm.get("title", set_key), "n_maps": len(maps), "threshold": float("nan"), "nav_starts": nm.get("nav_starts"),
            "max_nodes": 0, "modes": ["oracle"], "navigation": {"oracle": dict(tot)}, "first_map_quality": {},
            "by_path_length": {"oracle": {int(k): dict(v) for k, v in sorted(by_len.items())}}, "seconds": 0}


LABELS = {"privileged": "Picture of every cell (as before)", "imagine": "A: imagine from start + goal pictures",
          "explore": "B: imagine, then correct while walking",
          "oracle": "Oracle explorer (true walls once seen)"}


def _threshold_text(t) -> str:
    if isinstance(t, dict):
        groups: dict[str, list[str]] = {}
        for m, v in t.items():
            if m == "oracle":                          # model-free, no threshold
                continue
            groups.setdefault(_threshold_text(v), []).append({"privileged": "every-cell pictures", "imagine": "A",
                                                             "explore": "B"}.get(m, m))
        return "; ".join(f"{' and '.join(ms)}: {txt}" for txt, ms in groups.items())
    if isinstance(t, (tuple, list)):
        return f"stay {t[0]:.2f} / merge {t[1]:.2f} (fog: blocked vs same / new node)"
    return f"{t:.2f} (same / new node and unknown rule)" if t == t else "no model"


def _budget_text(b: dict) -> str:
    loop = "third visit to a cell = loop failure" if b["max_visits"] == 3 else "no loop rule"
    usual = " (as every other run)" if b["max_visits"] == 3 and b["max_actions"] == 30 else ""
    return f"Budget: {b['max_actions']} moves, {loop}{usual}."


def _pct(c, t):
    return f"{c}/{t} ({100 * c / t:.1f}%)" if t else "n/a"


def render(res: dict) -> str:
    nav, q = res["navigation"], res["first_map_quality"]
    modes = res["modes"]
    out = [f"# Planning without privileged pictures: {res['title']}", "",
           f"{res['n_maps']} maps, " + (f"{res['nav_starts']} random free start cells per map" if res.get("nav_starts")
                                        else "every free start cell") + ", seeds as configured. Snapped P2, threshold "
           + _threshold_text(res['threshold']) + f", at most {res['max_nodes']} nodes. "
           + _budget_text(res.get("budget", {"max_actions": 30, "max_visits": 3})), "",
           "| | " + " | ".join(LABELS[m] for m in modes) + " |", "|---|" + "---|" * len(modes)]
    rows = [("navigation success", lambda t: _pct(t["success"], t["episodes"])),
            ("shortest path", lambda t: _pct(t["optimal"], t["episodes"])),
            ("loop failures", lambda t: str(t.get("loops", 0))),
            ("extra moves per successful episode", lambda t: f"{t.get('extra_steps', 0) / max(t['success'], 1):.2f}"),
            ("collisions per action", lambda t: f"{t.get('collisions', 0) / max(t['steps'], 1):.2%}"),
            ("map rebuilds per episode", lambda t: f"{t.get('rebuilds', 0) / t['episodes']:.2f}"),
            ("plans heading for unexplored cells (no route seen)", lambda t: f"{t.get('frontier_plans', 0) / max(t['steps'], 1):.2%}"),
            ("plans with nothing known (latent fallback)", lambda t: f"{t.get('fallback_plans', 0) / max(t['steps'], 1):.2%}")]
    for name, f in rows:
        out.append(f"| {name} | " + " | ".join(f(nav[m]) for m in modes) + " |")
    if q:
        out += ["", "Imagined map before the first move (one per start cell; A and B start identically):", "",
                "| | value |", "|---|---|"]
        v = q.get("imagine") or next(iter(q.values()))
        out += [f"| maps exactly right (one node per cell, every edge right) | {_pct(v['exact'], v['maps'])} |",
                f"| nodes / true cells | {v['nodes'] / v['maps']:.1f} / {v['cells'] / v['maps']:.1f} |",
                f"| cells found | {_pct(v['covered'], v['cells'])} |",
                f"| duplicate nodes (a cell imagined twice) | {v['duplicates']} |",
                f"| spurious nodes (match no real cell) | {v['spurious']} |",
                f"| edges right (nodes matching a real cell) | {_pct(v['edges_correct'], v['edges'])} |",
                f"| steps-to-goal from the start exact | {_pct(v['d_start_exact'], v['maps'])} |",
                f"| goal unreachable from the start in imagination | {v['d_start_unreachable']} |",
                f"| growth hit the node cap | {v['overflow']} |"]
    out += ["", "By shortest-path length (success / shortest path):", "",
            "| length | episodes | " + " | ".join(modes) + " |", "|---|---|" + "---|" * len(modes)]
    lens = sorted({k for m in modes for k in res["by_path_length"][m]})
    for L in lens:
        n = res["by_path_length"][modes[0]].get(L, {}).get("episodes", 0)
        cells = []
        for m in modes:
            b = res["by_path_length"][m].get(L, {})
            cells.append(f"{100 * b.get('success', 0) / max(n, 1):.0f}% / {100 * b.get('optimal', 0) / max(n, 1):.0f}%")
        out.append(f"| {L} | {n} | " + " | ".join(cells) + " |")
    return "\n".join(out) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Plan from real pictures only: imagine the map (A) and explore (B).")
    parser.add_argument("--config", type=Path, default=Path("config_multimap_jepa.yaml"))
    parser.add_argument("--set", default="val_maze_maps")
    parser.add_argument("--modes", default=",".join(MODES), help=f"any of {','.join(ALL_MODES)}")
    parser.add_argument("--threshold", type=float, default=None, help="default: the calibrated unknown threshold")
    parser.add_argument("--max-nodes", type=int, default=None, help="default: multimap.explore.max_nodes or 60")
    parser.add_argument("--limit", type=int, default=None, help="first N maps only")
    parser.add_argument("--name", default=None, help="output name (default: explore_<set>)")
    parser.add_argument("--budget", choices=["standard", "explorer"], default="standard",
                        help="standard: 30 moves, 3rd visit = loop (as every other run); explorer: 60 moves, no loop rule "
                             "(or multimap.explore.standard / explorer in the config)")
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--workers", type=int, default=1, help="processes, split by map (one thread each)")
    args = parser.parse_args()
    cfg = load_config(args.config)
    torch.set_num_threads(args.threads)
    ex = cfg["multimap"].get("explore", {})
    budget = ex.get(args.budget, {"max_actions": 30, "max_visits": 3} if args.budget == "standard"
                    else {"max_actions": 60, "max_visits": 10 ** 6})
    cfg["planning"]["max_actions"], cfg["planning"]["max_visits"] = budget["max_actions"], budget["max_visits"]
    max_nodes = args.max_nodes or ex.get("max_nodes", 60)
    res = evaluate_parallel(cfg, args.set, tuple(args.modes.split(",")), args.threshold, max_nodes, args.limit,
                            args.workers)
    out = resolve(cfg["multimap"]["evaluation"]["results_dir"])
    name = args.name or f"explore_{args.set}" + ("_budget" if args.budget == "explorer" else "")
    res["budget"] = {"name": args.budget, "max_actions": cfg["planning"]["max_actions"],
                     "max_visits": cfg["planning"]["max_visits"]}
    md = render(res)
    (out / f"{name}.md").write_text(md)
    (out / f"{name}.json").write_text(json.dumps(res, indent=1) + "\n")
    print("\n" + md + f"\nWrote {out / (name + '.md')}")


if __name__ == "__main__":
    main()
