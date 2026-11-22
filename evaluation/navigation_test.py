"""Navigation evaluation (build plan step 9): 24 starts x 5 seeds = 120 episodes per planner.

Rows: Oracle (A* on the true map), the three planners with the learned model
(P0, P1, P2) and a random policy -- all through the same MPC loop, stopping
rules and seeds. Reports success, optimal episodes, path ratio, collision
rate, loop failures, timeouts and success by start distance.
"""

from __future__ import annotations

import heapq

import numpy as np

from environment import ACTION_DELTAS, ACTIONS, GridMap, GridWorld, distances_to_goal
from evaluation.probes import CellIndex
from planning.mpc import Episode, ModelContext, run_episode, summarize
from planning.planner import Plan, PlanContext


def astar(grid_map: GridMap, start: tuple[int, int], goal: tuple[int, int],
          rng: np.random.Generator | None = None) -> list[int]:
    """Shortest action sequence by A* with the Manhattan heuristic; random tie-break among equal f."""
    rng = rng if rng is not None else np.random.default_rng(0)
    h = lambda p: abs(p[0] - goal[0]) + abs(p[1] - goal[1])  # noqa: E731
    frontier = [(h(start), 0, float(rng.random()), start)]
    came: dict = {start: None}
    g = {start: 0}
    while frontier:
        _, gc, _, cur = heapq.heappop(frontier)
        if cur == goal:
            break
        if gc > g[cur]:
            continue
        for a in ACTIONS:
            nxt, collision = grid_map.transition(cur, a)
            if collision:
                continue
            if nxt not in g or gc + 1 < g[nxt]:
                g[nxt] = gc + 1
                came[nxt] = (cur, a)
                heapq.heappush(frontier, (gc + 1 + h(nxt), gc + 1, float(rng.random()), nxt))
    if goal not in came:
        raise ValueError(f"goal {goal} unreachable from {start}")
    actions, node = [], goal
    while came[node] is not None:
        node, a = came[node]
        actions.append(a)
    return actions[::-1]


class Oracle:
    """A* on the true map (needs a TrueModel to read the current cell)."""

    name = "Oracle"

    def __init__(self, grid_map: GridMap | None = None) -> None:
        self.map = grid_map if grid_map is not None else GridMap()
        self.cells = CellIndex(self.map)
        self._dist = distances_to_goal(self.map)

    def plan(self, model, z, ctx: PlanContext) -> Plan:
        x, y = (int(v) for v in self.cells.positions(int(z.argmax())))
        path = astar(self.map, (x, y), self.map.goal, ctx.rng)
        cells, pos = [], (x, y)
        for a in path:
            pos, _ = self.map.transition(pos, a)
            cells.append(int(self.cells.ids(np.array(pos))))
        first_costs = []
        for a in ACTIONS:  # 1 step + true distance from where that action lands
            nxt, _ = self.map.transition((x, y), a)
            first_costs.append(float(1 + self._dist[nxt[1], nxt[0]]))
        return Plan(path[0], path, float(len(path)), cells, 1, extra={"first_action_costs": first_costs})


class RandomPolicy:
    name = "Random"

    def plan(self, model, z, ctx: PlanContext) -> Plan:
        a = int(ctx.rng.integers(len(ACTION_DELTAS)))
        return Plan(a, [a], 0.0, [], 1)


def episode_seed(seed: int, start_index: int) -> int:
    """Same formula as planning.mpc.run_all, so seed 0 reproduces step 8's episodes."""
    return int(np.random.SeedSequence([seed, start_index]).generate_state(1)[0])


def run_seeds(model, planner, mctx: ModelContext, cfg: dict, seeds) -> list[Episode]:
    p = cfg["planning"]
    env = GridWorld(terminate_on_goal=True)
    return [
        run_episode(env, model, planner, mctx, start, episode_seed(seed, i),
                    max_actions=p["max_actions"], max_visits=p["max_visits"], revisit_penalty=p["revisit_penalty"])
        for seed in seeds
        for i, start in enumerate(env.map.start_cells())
    ]


def by_distance(episodes: list[Episode]) -> dict[int, dict]:
    out: dict[int, dict] = {}
    for e in episodes:
        d = out.setdefault(e.optimal, {"success": 0, "optimal": 0, "total": 0})
        d["total"] += 1
        d["success"] += int(e.success)
        d["optimal"] += int(e.success and e.steps == e.optimal)
    return dict(sorted(out.items()))


def report(episodes: list[Episode]) -> dict:
    return {**summarize(episodes), "by_distance": by_distance(episodes)}
