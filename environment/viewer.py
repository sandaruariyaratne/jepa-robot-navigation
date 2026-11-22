"""Interactive pygame viewer for the grid world: `python -m environment.viewer`.

Shows the exact frame the model sees (the Renderer output), scaled up with
nearest-neighbour so every pixel stays visible.

Keys:
  arrows / WASD   move the robot
  space           play / pause the BFS optimal path from the current cell
  T               toggle the BFS distance-to-goal overlay
  R               reset to the reference start
  N               reset to a random start
  mouse click     put the robot on the clicked cell
  Esc / Q         quit
"""

from __future__ import annotations

import argparse

try:
    import pygame
except ImportError as exc:  # pragma: no cover
    raise SystemExit("pygame is not installed: run `pip install pygame`") from exc

from .bfs import UNREACHABLE, distances_to_goal, shortest_path
from .grid_world import ACTION_NAMES, DOWN, LEFT, REFERENCE_START, RIGHT, UP, GridWorld, Pos
from .renderer import to_hwc

KEY_ACTIONS = {
    pygame.K_UP: UP, pygame.K_w: UP,
    pygame.K_DOWN: DOWN, pygame.K_s: DOWN,
    pygame.K_LEFT: LEFT, pygame.K_a: LEFT,
    pygame.K_RIGHT: RIGHT, pygame.K_d: RIGHT,
}
TOGGLE_DIST_KEY = pygame.K_t  # not D: that key is RIGHT in WASD
HUD_H = 84
HUD_BG = (24, 28, 34)
HUD_TEXT = (230, 235, 240)
HUD_DIM = (140, 150, 162)
PLAN_DOT = (240, 176, 64)
CELL_TEXT_DARK = (60, 70, 82)
CELL_TEXT_LIGHT = (245, 248, 250)


class Viewer:
    def __init__(self, env: GridWorld, scale: int = 12, step_ms: int = 250) -> None:
        self.env = env
        self.scale = scale
        self.step_ms = step_ms
        self.dist = distances_to_goal(env.map)
        _, h, w = env.obs_shape
        self.cell = env.renderer.cell_px * scale
        self.grid_w, self.grid_h = w * scale, h * scale
        self.screen = pygame.display.set_mode((self.grid_w, self.grid_h + HUD_H))
        pygame.display.set_caption("Mini-JEPA grid world")
        self.font = pygame.font.Font(None, 22)
        self.cell_font = pygame.font.Font(None, max(18, self.cell // 2))
        self.show_dist = False
        self.reset(REFERENCE_START)

    # --- state ------------------------------------------------------------
    def reset(self, start: Pos | None = None) -> None:
        self.env.reset(start)
        self.plan: list[int] = []
        self.next_auto = 0
        self.status = f"start at {self.env.pos}"

    def act(self, action: int) -> None:
        if self.env.done:
            self.status = "episode over - press R or N to reset"
            return
        r = self.env.step(action)
        name = ACTION_NAMES[action]
        if r.terminated:
            self.status = f"{name}: reached the goal in {self.env.steps} steps (R/N to reset)"
            self.plan = []
        elif r.collision:
            self.status = f"{name}: blocked by a wall or the border"
        else:
            self.status = name

    def toggle_play(self) -> None:
        if self.plan:
            self.plan = []
            self.status = "paused"
            return
        if self.env.done:
            self.status = "episode over - press R or N to reset"
            return
        pos = self.env.pos
        if self.dist[pos[1], pos[0]] == UNREACHABLE:
            self.status = "goal is unreachable from here"
            return
        self.plan = shortest_path(self.env.map, pos)
        if not self.plan:
            self.status = "already on the goal"
            return
        self.next_auto = pygame.time.get_ticks()
        self.status = f"playing BFS optimal path ({len(self.plan)} steps)"

    def update(self) -> None:
        if self.plan and pygame.time.get_ticks() >= self.next_auto:
            self.act(self.plan.pop(0))
            self.next_auto += self.step_ms

    def handle(self, event: pygame.event.Event) -> bool:
        """Process one event. Returns False to quit."""
        if event.type == pygame.QUIT:
            return False
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_q):
                return False
            if event.key in KEY_ACTIONS:
                self.plan = []
                self.act(KEY_ACTIONS[event.key])
            elif event.key == pygame.K_SPACE:
                self.toggle_play()
            elif event.key == TOGGLE_DIST_KEY:
                self.show_dist = not self.show_dist
            elif event.key == pygame.K_r:
                self.reset(REFERENCE_START)
            elif event.key == pygame.K_n:
                self.reset(None)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            if my < self.grid_h:
                cell = (mx // self.cell, my // self.cell)
                if self.env.map.is_free(cell):
                    self.reset(cell)
                else:
                    self.status = f"{cell} is a wall"
        return True

    # --- drawing ----------------------------------------------------------
    def _cell_center(self, pos: Pos) -> tuple[int, int]:
        # The 1 px grid line sits on the top/left edge, so the interior is offset by one scaled pixel.
        x, y = pos
        off = (self.cell + self.scale) // 2
        return x * self.cell + off, y * self.cell + off

    def draw(self) -> None:
        frame = to_hwc(self.env.render())  # H, W, 3 -- the model's observation
        surf = pygame.surfarray.make_surface(frame.transpose(1, 0, 2))
        self.screen.blit(pygame.transform.scale(surf, (self.grid_w, self.grid_h)), (0, 0))

        if self.plan:
            pos = self.env.pos
            for a in self.plan:
                pos, _ = self.env.map.transition(pos, a)
                cx, cy = self._cell_center(pos)
                if self.show_dist:  # sit below the distance number instead of on top of it
                    cy += self.cell * 3 // 10
                pygame.draw.circle(self.screen, PLAN_DOT, (cx, cy), max(3, self.cell // 12))

        if self.show_dist:
            for c in self.env.map.free_cells():
                d = self.dist[c[1], c[0]]
                dark_bg = c == self.env.pos or c == self.env.map.goal
                txt = self.cell_font.render("-" if d == UNREACHABLE else str(d), True,
                                            CELL_TEXT_LIGHT if dark_bg else CELL_TEXT_DARK)
                self.screen.blit(txt, txt.get_rect(center=self._cell_center(c)))

        pygame.draw.rect(self.screen, HUD_BG, (0, self.grid_h, self.grid_w, HUD_H))
        pos = self.env.pos
        info = f"pos {pos}   steps {self.env.steps}   BFS dist {self.dist[pos[1], pos[0]]}   obs {list(self.env.obs_shape)}"
        lines = [
            (info, HUD_TEXT),
            (self.status, HUD_TEXT),
            ("arrows/WASD move  space play BFS  T distances", HUD_DIM),
            ("R reset  N random  click place  Esc quit", HUD_DIM),
        ]
        for i, (text, color) in enumerate(lines):
            self.screen.blit(self.font.render(text, True, color), (8, self.grid_h + 6 + i * 19))
        pygame.display.flip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Interactive pygame viewer for the grid world.")
    parser.add_argument("--scale", type=int, default=12, help="screen pixels per observation pixel (default 12)")
    parser.add_argument("--step-ms", type=int, default=250, help="autoplay delay between steps in ms (default 250)")
    parser.add_argument("--seed", type=int, default=None, help="seed for random starts")
    args = parser.parse_args()

    pygame.init()
    viewer = Viewer(GridWorld(terminate_on_goal=True, seed=args.seed), scale=args.scale, step_ms=args.step_ms)
    clock = pygame.time.Clock()
    running = True
    while running:
        for event in pygame.event.get():
            if not viewer.handle(event):
                running = False
                break
        viewer.update()
        viewer.draw()
        clock.tick(60)
    pygame.quit()


if __name__ == "__main__":
    main()
