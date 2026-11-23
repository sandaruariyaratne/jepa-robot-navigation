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


@torch.no_grad()
def grow(encoder, predictor, anchors: torch.Tensor, threshold: float, max_nodes: int = 60) -> tuple[torch.Tensor, bool]:
    """Nodes reachable in imagination from the anchors [K, D]; anchors stay at indices 0..K-1."""
    nodes = [z for z in anchors]
    frontier = list(range(len(nodes)))
    acts = torch.arange(predictor.n_actions)
    overflow = False
    while frontier:
        z = torch.stack([nodes[u] for u in frontier])
        pred = predictor(z.repeat_interleave(len(acts), 0), acts.repeat(len(frontier)))
        nxt = []
        for p in pred:
            if torch.linalg.norm(torch.stack(nodes) - p, dim=-1).min() <= threshold:
                continue                                       # an existing node (or a blocked move)
            if len(nodes) >= max_nodes:
                overflow = True
                continue
            nodes.append(p)
            nxt.append(len(nodes) - 1)
        frontier = nxt
    return torch.stack(nodes), overflow


def imagined_map(encoder, predictor, anchors: torch.Tensor, goal: int, threshold: float,
                 max_nodes: int = 60) -> ImaginedMap:
    nodes, overflow = grow(encoder, predictor, anchors, threshold, max_nodes)
    return graph_map(WorldModel(encoder, predictor, nodes, threshold, 1.0), len(anchors), goal, overflow)


def graph_map(world: WorldModel, n_anchors: int, goal: int, overflow: bool = False) -> ImaginedMap:
    g = build_graph(world)                                             # unknown threshold = threshold
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
        world = WorldModel(encoder, predictor, privileged, threshold, 1.0)
        m = graph_map(world, len(privileged), int(world.snap(z_goal).index))
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


# --- evaluation over a map set ---------------------------------------------------------------
def evaluate(cfg: dict, set_key: str, modes=MODES, threshold: float | None = None, max_nodes: int = 60,
             limit: int | None = None, verbose: bool = True) -> dict:
    mm, nm = cfg["multimap"], cfg["multimap"][set_key]
    maps, _ = load_maps(resolve(nm["maps_path"]))
    maps = maps[:limit] if limit else maps
    encoder, _ = load_encoder(resolve(mm["encoder"]["checkpoint"]))
    predictor, _ = load_predictor(resolve(mm["predictor"]["checkpoint"]))
    encoder.eval(), predictor.eval()
    if threshold is None:
        from .calibrate import load_threshold
        threshold = load_threshold(cfg)["threshold"]
    tot = {m: Counter() for m in modes}
    quality = {m: Counter() for m in modes if m != "privileged"}
    by_len = {m: defaultdict(Counter) for m in modes}
    t0 = time.perf_counter()
    for k, grid in enumerate(maps):
        env = GridWorld(grid, terminate_on_goal=True)
        cells = CellIndex(grid).cells
        frames = np.stack([env.render((int(x), int(y))) for x, y in cells])
        with torch.no_grad():
            cell_latents = encoder.standardize(encoder(torch.as_tensor(frames)))
        goal_frame = env.render(grid.goal)
        index = {(int(x), int(y)): i for i, (x, y) in enumerate(cells)}
        for i, start in enumerate(grid.start_cells()):
            for seed in nm["nav_seeds"]:
                s = int(np.random.SeedSequence([seed, i]).generate_state(1)[0])
                for mode in modes:
                    e = run(mode, env, encoder, predictor, goal_frame, start, s, cfg, threshold, cell_latents, max_nodes)
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
            print(f"  {k + 1} maps ({time.perf_counter() - t0:.0f}s): success/shortest {line}", flush=True)
    return {"set": set_key, "title": nm.get("title", set_key), "n_maps": len(maps), "threshold": threshold,
            "max_nodes": max_nodes, "modes": list(modes),
            "navigation": {m: dict(v) for m, v in tot.items()},
            "first_map_quality": {m: dict(v) for m, v in quality.items()},
            "by_path_length": {m: {int(k): dict(v) for k, v in sorted(d.items())} for m, d in by_len.items()},
            "seconds": round(time.perf_counter() - t0)}


LABELS = {"privileged": "Picture of every cell (as before)", "imagine": "A: imagine from start + goal pictures",
          "explore": "B: imagine, then correct while walking"}


def _pct(c, t):
    return f"{c}/{t} ({100 * c / t:.1f}%)" if t else "n/a"


def render(res: dict) -> str:
    nav, q = res["navigation"], res["first_map_quality"]
    modes = res["modes"]
    out = [f"# Planning without privileged pictures: {res['title']}", "",
           f"{res['n_maps']} maps, every free start cell, seeds as configured. Snapped P2, threshold "
           f"{res['threshold']:.2f} (same / new node and unknown rule), at most {res['max_nodes']} nodes. "
           + ("Budget: 30 moves, third visit to a cell = loop failure (as every other run)."
              if res.get("budget", {}).get("name", "standard") == "standard"
              else f"Explorer's budget: {res['budget']['max_actions']} moves, no loop rule."), "",
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
    parser.add_argument("--modes", default=",".join(MODES))
    parser.add_argument("--threshold", type=float, default=None, help="default: the calibrated unknown threshold")
    parser.add_argument("--max-nodes", type=int, default=60)
    parser.add_argument("--limit", type=int, default=None, help="first N maps only")
    parser.add_argument("--name", default=None, help="output name (default: explore_<set>)")
    parser.add_argument("--budget", choices=["standard", "explorer"], default="standard",
                        help="standard: 30 moves, 3rd visit = loop (as every other run); explorer: 60 moves, no loop rule")
    parser.add_argument("--threads", type=int, default=2)
    args = parser.parse_args()
    cfg = load_config(args.config)
    torch.set_num_threads(args.threads)
    if args.budget == "explorer":
        cfg["planning"]["max_actions"], cfg["planning"]["max_visits"] = 60, 10 ** 6
    res = evaluate(cfg, args.set, tuple(args.modes.split(",")), args.threshold, args.max_nodes, args.limit)
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
