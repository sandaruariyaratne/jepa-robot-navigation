"""The simulator dressed up as a world model (build plan step 8, and ladder rungs in step 9).

Same interface as planning.imagination.WorldModel -- encode, step, rollout,
imagine, snap, codebook -- but latents are one-hot cells and steps follow the
true rules. Plugging it into a planner separates planner bugs from model
errors: with true dynamics and the true cost, P2 must be optimal.
"""

from __future__ import annotations

import numpy as np
import torch

from environment import ACTIONS, GridMap, GridWorld
from evaluation.probes import CellIndex

from .imagination import Snapped


class TrueModel:
    def __init__(self, grid_map: GridMap | None = None, cell_px: int = 8) -> None:
        self.map = grid_map if grid_map is not None else GridMap()
        self.cells = CellIndex(self.map)
        renderer = GridWorld(self.map, cell_px=cell_px).renderer
        self._frame_to_cell = {renderer.render(tuple(int(v) for v in c)).tobytes(): i
                               for i, c in enumerate(self.cells.cells)}
        self.next = torch.tensor([[int(self.cells.ids(np.array(self.map.transition(tuple(int(v) for v in c), a)[0])))
                                   for a in ACTIONS] for c in self.cells.cells])  # [C, A]
        self.codebook = torch.eye(len(self.cells))
        self.median_one_step_error = 0.0
        self.unknown_factor = 3.0
        self.unknown_threshold = 1e-6

    @property
    def n_entries(self) -> int:
        return len(self.cells)

    @property
    def n_actions(self) -> int:
        return len(ACTIONS)

    def _ids(self, z: torch.Tensor) -> torch.Tensor:
        return z.argmax(-1)

    def _onehot(self, ids: torch.Tensor) -> torch.Tensor:
        return self.codebook[ids]

    def encode(self, frames) -> torch.Tensor:
        x = np.asarray(frames)
        single = x.ndim == 3
        ids = [self._frame_to_cell[f.tobytes()] for f in (x[None] if single else x)]
        z = self._onehot(torch.tensor(ids))
        return z[0] if single else z

    def step(self, z: torch.Tensor, action) -> torch.Tensor:
        return self._onehot(self.next[self._ids(z), torch.as_tensor(action)])

    def rollout(self, z0: torch.Tensor, actions: torch.Tensor) -> torch.Tensor:
        ids, out = self._ids(z0), []
        actions = torch.as_tensor(actions)
        for k in range(actions.shape[1]):
            ids = self.next[ids, actions[:, k]]
            out.append(ids)
        return self._onehot(torch.stack(out, dim=1))

    def imagine(self, z0: torch.Tensor, sequences: torch.Tensor) -> torch.Tensor:
        single = z0.ndim == 1
        z0 = z0[None] if single else z0
        b, s = len(z0), len(sequences)
        flat = self.rollout(z0.repeat_interleave(s, dim=0), sequences.repeat(b, 1))
        out = flat.view(b, s, *flat.shape[1:])
        return out[0] if single else out

    def snap(self, z: torch.Tensor) -> Snapped:
        flat = z.reshape(-1, z.shape[-1])
        d = torch.cdist(flat, self.codebook)
        dist, idx = d.min(-1)
        dist, idx = dist.reshape(z.shape[:-1]), idx.reshape(z.shape[:-1])
        return Snapped(idx, dist, dist <= self.unknown_threshold)
