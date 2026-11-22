"""Shared test helpers: a small synthetic WorldModel whose edges can be made exact, unknown or wrong."""

import numpy as np
import torch

from environment import ACTIONS, GridMap, GridWorld
from evaluation.probes import CellIndex
from models import Encoder, Predictor
from planning.imagination import WorldModel

CELLS = CellIndex()
GRID = GridMap()
HELD = [(0, 1, 0), (0, 2, 1), (0, 4, 0), (1, 2, 2), (1, 4, 3), (3, 1, 0), (4, 2, 1), (5, 0, 3), (5, 1, 3), (5, 3, 1)]
TRUE_NEXT = np.array([[CELLS.ids(np.array(GRID.transition(tuple(map(int, c)), a)[0])) for a in ACTIONS]
                      for c in CELLS.cells])


def cell_id(x: int, y: int) -> int:
    return int(CELLS.ids(np.array([x, y])))


class TablePredictor(Predictor):
    """Exact dynamics on codebook latents, with overrides: {(cell_id, action): 'far' | target_cell_id}."""

    def __init__(self, codebook: torch.Tensor, overrides: dict) -> None:
        super().__init__(codebook.shape[1], 4, (8,))
        self.table = codebook
        self.overrides = overrides

    def forward(self, z, action):
        src = torch.cdist(z, self.table).argmin(-1)
        out = []
        for s, a in zip(src.tolist(), action.tolist()):
            o = self.overrides.get((s, a))
            if o == "far":
                out.append(self.table[TRUE_NEXT[s, a]] + 10.0)
            else:
                out.append(self.table[TRUE_NEXT[s, a] if o is None else o])
        return torch.stack(out)


def cell_frames() -> tuple[np.ndarray, np.ndarray]:
    """(frames of all 25 cells in cell-id order, goal frame)."""
    r = GridWorld().renderer
    return np.stack([r.render(tuple(map(int, c))) for c in CELLS.cells]), GridWorld().goal_obs()


def make_world(frames, overrides=None) -> WorldModel:
    torch.manual_seed(0)
    enc = Encoder(32).freeze()
    with torch.no_grad():
        z = enc(torch.as_tensor(frames[0]))
    enc.z_mean.copy_(z.mean(0))
    enc.z_std.copy_(z.std(0))
    codebook = enc.standardize(z)
    return WorldModel(enc, TablePredictor(codebook, overrides or {}), codebook, median_one_step_error=0.01)


def held_overrides() -> dict:
    return {(cell_id(*p[:2]), p[2]): "far" for p in HELD}
