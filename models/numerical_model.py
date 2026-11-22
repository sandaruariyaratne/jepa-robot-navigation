"""Stage 0 numerical baseline (build plan step 3).

A small MLP on normalised (x, y) + one-hot action -> next (x, y). It learns the
transition rule from coordinates alone, so later image-based models have a
reference for how hard the dynamics are -- and for how much a plain MLP
generalizes to (state, action) pairs it never saw.
"""

from __future__ import annotations

from collections.abc import Sequence

import torch
from torch import nn
from torch.nn import functional as F


class NumericalModel(nn.Module):
    def __init__(self, hidden: Sequence[int] = (64, 64), n_actions: int = 4) -> None:
        super().__init__()
        self.n_actions = n_actions
        dims = [2 + n_actions, *hidden]
        layers: list[nn.Module] = []
        for a, b in zip(dims[:-1], dims[1:]):
            layers += [nn.Linear(a, b), nn.ReLU()]
        layers.append(nn.Linear(dims[-1], 2))
        self.net = nn.Sequential(*layers)
        # Normalisation statistics, fit on the training split and saved with the weights.
        self.register_buffer("pos_mean", torch.zeros(2))
        self.register_buffer("pos_std", torch.ones(2))

    def set_normalization(self, mean: torch.Tensor, std: torch.Tensor) -> None:
        self.pos_mean.copy_(torch.as_tensor(mean, dtype=torch.float32))
        self.pos_std.copy_(torch.as_tensor(std, dtype=torch.float32).clamp_min(1e-6))

    def normalize(self, pos: torch.Tensor) -> torch.Tensor:
        return (pos.float() - self.pos_mean) / self.pos_std

    def forward(self, pos: torch.Tensor, action: torch.Tensor) -> torch.Tensor:
        """Predicted next position in normalised units. pos [B, 2] in cells, action [B] ints."""
        inp = torch.cat([self.normalize(pos), F.one_hot(action.long(), self.n_actions).float()], dim=-1)
        return self.net(inp)

    def predict(self, pos: torch.Tensor, action: torch.Tensor) -> torch.Tensor:
        """Predicted next position in cell units (float)."""
        return self.forward(pos, action) * self.pos_std + self.pos_mean

    @torch.no_grad()
    def predict_cell(self, pos: torch.Tensor, action: torch.Tensor) -> torch.Tensor:
        """Prediction rounded to the nearest cell (int64 [B, 2])."""
        return torch.round(self.predict(pos, action)).long()
