"""Deterministic grid world for Mini-JEPA (spec v1.1, section 02).

Coordinates are (x, y) = (column, row) with row 0 at the top.
The simulator is the source of truth: models never read these rules.
The true position is exposed only for probes, diagnostics and evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .renderer import Renderer

Pos = tuple[int, int]

UP, DOWN, LEFT, RIGHT = 0, 1, 2, 3
ACTIONS: tuple[int, ...] = (UP, DOWN, LEFT, RIGHT)
ACTION_NAMES: tuple[str, ...] = ("UP", "DOWN", "LEFT", "RIGHT")
ACTION_DELTAS: dict[int, Pos] = {UP: (0, -1), DOWN: (0, 1), LEFT: (-1, 0), RIGHT: (1, 0)}

DEFAULT_COLS = 6
DEFAULT_ROWS = 5
DEFAULT_WALLS: frozenset[Pos] = frozenset({(2, 1), (2, 2), (2, 3), (4, 3), (4, 4)})
DEFAULT_GOAL: Pos = (5, 0)
REFERENCE_START: Pos = (0, 4)


@dataclass(frozen=True)
class GridMap:
    """Static layout: size, walls and goal. Holds the transition rules.

    view_radius: None = the robot sees the whole grid (every experiment up to REPORT section 11).
    r = fog of war: every cell more than r cells from the robot (Chebyshev distance) is drawn as fog.
    """

    cols: int = DEFAULT_COLS
    rows: int = DEFAULT_ROWS
    walls: frozenset[Pos] = field(default_factory=lambda: DEFAULT_WALLS)
    goal: Pos = DEFAULT_GOAL
    view_radius: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "walls", frozenset(tuple(w) for w in self.walls))
        object.__setattr__(self, "goal", tuple(self.goal))
        if self.cols < 1 or self.rows < 1:
            raise ValueError(f"grid must be at least 1x1, got {self.cols}x{self.rows}")
        for w in self.walls:
            if not self.in_bounds(w):
                raise ValueError(f"wall {w} is outside the {self.cols}x{self.rows} grid")
        if not self.in_bounds(self.goal):
            raise ValueError(f"goal {self.goal} is outside the grid")
        if self.goal in self.walls:
            raise ValueError(f"goal {self.goal} is on a wall")
        if self.view_radius is not None and self.view_radius < 0:
            raise ValueError(f"view_radius must be >= 0 or None, got {self.view_radius}")

    def in_bounds(self, pos: Pos) -> bool:
        x, y = pos
        return 0 <= x < self.cols and 0 <= y < self.rows

    def is_free(self, pos: Pos) -> bool:
        return self.in_bounds(pos) and pos not in self.walls

    def free_cells(self) -> list[Pos]:
        """All non-wall cells, in row-major order (top row first)."""
        return [(x, y) for y in range(self.rows) for x in range(self.cols) if (x, y) not in self.walls]

    def start_cells(self) -> list[Pos]:
        """Free cells other than the goal."""
        return [c for c in self.free_cells() if c != self.goal]

    def transition(self, pos: Pos, action: int) -> tuple[Pos, bool]:
        """Apply one action. Returns (next_pos, collision).

        A move into a wall or the border leaves the robot in place.
        """
        if action not in ACTION_DELTAS:
            raise ValueError(f"action must be one of {ACTIONS}, got {action!r}")
        if not self.is_free(pos):
            raise ValueError(f"position {pos} is not a free cell")
        dx, dy = ACTION_DELTAS[action]
        nxt = (pos[0] + dx, pos[1] + dy)
        if self.is_free(nxt):
            return nxt, False
        return pos, True


@dataclass(frozen=True)
class StepResult:
    obs: np.ndarray  # uint8 [3, H, W]
    pos: Pos  # true position after the step (probes / evaluation only)
    collision: bool
    at_goal: bool
    terminated: bool  # reached the goal with terminate_on_goal=True
    truncated: bool  # hit max_steps

    @property
    def done(self) -> bool:
        return self.terminated or self.truncated


class GridWorld:
    """Episode wrapper around a GridMap with RGB observations.

    Args:
        grid_map: layout; defaults to the v1.1 reference map.
        cell_px: pixels per cell side (8 gives a 3 x 40 x 48 frame).
        max_steps: truncate the episode after this many actions (None = never).
        terminate_on_goal: end the episode when the robot reaches the goal.
            Data collection uses False so goal-cell transitions are recorded.
        seed: seed for random starts.
    """

    def __init__(
        self,
        grid_map: GridMap | None = None,
        cell_px: int = 8,
        max_steps: int | None = None,
        terminate_on_goal: bool = True,
        seed: int | None = None,
    ) -> None:
        self.map = grid_map if grid_map is not None else GridMap()
        if not self.map.start_cells():
            raise ValueError("map has no free start cell besides the goal")
        if max_steps is not None and max_steps < 1:
            raise ValueError(f"max_steps must be >= 1 or None, got {max_steps}")
        self.renderer = Renderer(self.map, cell_px=cell_px)
        self.max_steps = max_steps
        self.terminate_on_goal = terminate_on_goal
        self.rng = np.random.default_rng(seed)
        self._pos: Pos | None = None
        self._steps = 0
        self._done = False

    # --- properties -------------------------------------------------------
    @property
    def pos(self) -> Pos:
        if self._pos is None:
            raise RuntimeError("call reset() before reading the position")
        return self._pos

    @property
    def steps(self) -> int:
        return self._steps

    @property
    def done(self) -> bool:
        return self._done

    @property
    def obs_shape(self) -> tuple[int, int, int]:
        return self.renderer.shape

    @property
    def num_actions(self) -> int:
        return len(ACTIONS)

    # --- episode API ------------------------------------------------------
    def reset(self, start: Pos | None = None) -> np.ndarray:
        """Start an episode. A random free non-goal cell is used if start is None."""
        if start is None:
            cells = self.map.start_cells()
            start = cells[int(self.rng.integers(len(cells)))]
        else:
            start = (int(start[0]), int(start[1]))
            if not self.map.is_free(start):
                raise ValueError(f"start {start} is not a free cell")
        self._pos = start
        self._steps = 0
        self._done = False
        return self.render()

    def step(self, action: int) -> StepResult:
        if self._pos is None:
            raise RuntimeError("call reset() before step()")
        if self._done:
            raise RuntimeError("episode is over; call reset()")
        action = int(action)
        self._pos, collision = self.map.transition(self._pos, action)
        self._steps += 1
        at_goal = self._pos == self.map.goal
        terminated = self.terminate_on_goal and at_goal
        truncated = (not terminated) and self.max_steps is not None and self._steps >= self.max_steps
        self._done = terminated or truncated
        return StepResult(self.render(), self._pos, collision, at_goal, terminated, truncated)

    def sample_action(self) -> int:
        return int(self.rng.integers(len(ACTIONS)))

    # --- rendering --------------------------------------------------------
    def render(self, pos: Pos | None = None) -> np.ndarray:
        """RGB frame (uint8, CHW) with the robot at pos (default: current position)."""
        return self.renderer.render(self.pos if pos is None else pos)

    def goal_obs(self) -> np.ndarray:
        """The goal frame used for z_goal: the robot standing on the goal cell."""
        return self.renderer.render(self.map.goal)

    def render_ascii(self, pos: Pos | None = None) -> str:
        """Text view: R robot, G goal, # wall, . floor."""
        robot = pos if pos is not None else self._pos
        lines = []
        for y in range(self.map.rows):
            row = []
            for x in range(self.map.cols):
                c = (x, y)
                if c == robot:
                    row.append("R")
                elif c in self.map.walls:
                    row.append("#")
                elif c == self.map.goal:
                    row.append("G")
                else:
                    row.append(".")
            lines.append(" ".join(row))
        return "\n".join(lines)
