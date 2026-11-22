"""Breadth-first-search oracle on the true map (spec v1.1, sections 05-06).

Used for evaluation only (optimal path length, the diagnostic ladder and
"success by distance"). Never used by the learned models or planners.
"""

from __future__ import annotations

from collections import deque

import numpy as np

from .grid_world import ACTIONS, GridMap, Pos

UNREACHABLE = -1


def distances_to_goal(grid_map: GridMap, goal: Pos | None = None) -> np.ndarray:
    """Shortest number of actions from every cell to the goal.

    Returns an int array of shape (rows, cols), indexed [y, x].
    Walls and cells that cannot reach the goal are UNREACHABLE (-1).
    Built from the transition rules, so it stays correct for any layout.
    """
    goal = grid_map.goal if goal is None else (int(goal[0]), int(goal[1]))
    if not grid_map.is_free(goal):
        raise ValueError(f"goal {goal} is not a free cell")

    predecessors: dict[Pos, list[Pos]] = {c: [] for c in grid_map.free_cells()}
    for c in grid_map.free_cells():
        for a in ACTIONS:
            nxt, _ = grid_map.transition(c, a)
            if nxt != c:
                predecessors[nxt].append(c)

    dist = np.full((grid_map.rows, grid_map.cols), UNREACHABLE, dtype=np.int64)
    dist[goal[1], goal[0]] = 0
    queue: deque[Pos] = deque([goal])
    while queue:
        cur = queue.popleft()
        d = dist[cur[1], cur[0]]
        for prev in predecessors[cur]:
            if dist[prev[1], prev[0]] == UNREACHABLE:
                dist[prev[1], prev[0]] = d + 1
                queue.append(prev)
    return dist


def shortest_path(grid_map: GridMap, start: Pos, goal: Pos | None = None) -> list[int]:
    """One optimal action sequence from start to goal (ties go to the lowest action id)."""
    goal = grid_map.goal if goal is None else (int(goal[0]), int(goal[1]))
    dist = distances_to_goal(grid_map, goal)
    pos = (int(start[0]), int(start[1]))
    if not grid_map.is_free(pos):
        raise ValueError(f"start {pos} is not a free cell")
    if dist[pos[1], pos[0]] == UNREACHABLE:
        raise ValueError(f"goal {goal} is unreachable from {pos}")

    actions: list[int] = []
    while pos != goal:
        d = dist[pos[1], pos[0]]
        for a in ACTIONS:
            nxt, _ = grid_map.transition(pos, a)
            if dist[nxt[1], nxt[0]] == d - 1:
                actions.append(a)
                pos = nxt
                break
    return actions
