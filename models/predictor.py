"""Residual latent predictor (spec section 03-B, build plan step 6).

    z_hat_(t+1) = z_t + f(z_t, a_t)
    f: Linear 36 -> 128 + ReLU, Linear 128 -> 128 + ReLU, Linear 128 -> 32 (near-zero init)

Works on standardised latents (encoder z_mean / z_std), so every dimension
has unit scale. Starting f near zero means an untrained predictor is the
persistence baseline z_hat = z, and training only has to learn the change.
"""

from __future__ import annotations

from collections.abc import Sequence

import torch
from torch import nn
from torch.nn import functional as F


class Predictor(nn.Module):
    def __init__(self, latent_dim: int = 32, n_actions: int = 4, hidden: Sequence[int] = (128, 128),
                 last_layer_init: float = 1e-3) -> None:
        super().__init__()
        self.latent_dim = latent_dim
        self.n_actions = n_actions
        dims = [latent_dim + n_actions, *hidden]
        layers: list[nn.Module] = []
        for a, b in zip(dims[:-1], dims[1:]):
            layers += [nn.Linear(a, b), nn.ReLU()]
        last = nn.Linear(dims[-1], latent_dim)
        with torch.no_grad():
            last.weight.mul_(last_layer_init)
            last.bias.zero_()
        layers.append(last)
        self.f = nn.Sequential(*layers)

    def delta(self, z: torch.Tensor, action: torch.Tensor) -> torch.Tensor:
        return self.f(torch.cat([z, F.one_hot(action.long(), self.n_actions).float()], dim=-1))

    def forward(self, z: torch.Tensor, action: torch.Tensor) -> torch.Tensor:
        """One step: z [B, D], action [B] -> z_hat [B, D]."""
        return z + self.delta(z, action)

    def rollout(self, z0: torch.Tensor, actions: torch.Tensor) -> torch.Tensor:
        """Feed predictions back in: z0 [B, D], actions [B, K] -> [B, K, D] (no simulator involved)."""
        out, z = [], z0
        for k in range(actions.shape[1]):
            z = self(z, actions[:, k])
            out.append(z)
        return torch.stack(out, dim=1)


def snap(z: torch.Tensor, codebook: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    """Nearest codebook entry for each latent: z [..., D], codebook [C, D] -> (index [...], distance [...])."""
    flat = z.reshape(-1, z.shape[-1])
    d = torch.cdist(flat, codebook)
    dist, idx = d.min(dim=-1)
    return idx.reshape(z.shape[:-1]), dist.reshape(z.shape[:-1])


def load_predictor(path) -> tuple[Predictor, dict]:
    ckpt = torch.load(path, map_location="cpu", weights_only=True)
    model = Predictor(ckpt["latent_dim"], ckpt["n_actions"], ckpt["hidden"])
    model.load_state_dict(ckpt["state_dict"])
    model.requires_grad_(False)
    return model.eval(), ckpt
