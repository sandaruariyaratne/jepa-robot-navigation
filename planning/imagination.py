"""Imagination: batched latent rollouts with the frozen encoder + predictor (build plan step 7).

Nothing here touches the simulator. The only inputs are frames (the current
observation and the goal image), the trained networks and the codebook. This
module deliberately does not import `environment`; a test runs it with every
simulator entry point patched to raise.

Latents are standardised (encoder z_mean / z_std) throughout, matching the
space the predictor was trained in.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch

from models import Predictor, snap
from models.encoder import Encoder, load_encoder
from models.predictor import load_predictor


def all_action_sequences(horizon: int, n_actions: int = 4) -> torch.Tensor:
    """Every action sequence of the given length, lexicographic: [n_actions ** horizon, horizon]."""
    return torch.tensor(list(itertools.product(range(n_actions), repeat=horizon)), dtype=torch.int64)


@dataclass(frozen=True)
class Snapped:
    index: torch.Tensor     # nearest codebook entry
    distance: torch.Tensor  # distance to it
    known: torch.Tensor     # distance <= unknown threshold


class WorldModel:
    """Frozen encoder + predictor + codebook, with the 'unknown' snapping rule."""

    def __init__(self, encoder: Encoder, predictor: Predictor, codebook: torch.Tensor,
                 median_one_step_error: float, unknown_factor: float = 3.0) -> None:
        self.encoder = encoder.eval()
        self.predictor = predictor.eval()
        self.codebook = codebook.float()  # standardised, [C, D]; entry i is the frame of cell i
        self.median_one_step_error = float(median_one_step_error)
        self.unknown_factor = float(unknown_factor)

    @classmethod
    def from_checkpoints(cls, encoder_path: str | Path, predictor_path: str | Path,
                         unknown_factor: float = 3.0) -> "WorldModel":
        encoder, enc_ckpt = load_encoder(encoder_path)
        predictor, pred_ckpt = load_predictor(predictor_path)
        codebook = encoder.standardize(enc_ckpt["codebook"].float())
        return cls(encoder, predictor, codebook, pred_ckpt["median_one_step_error"], unknown_factor)

    @property
    def n_entries(self) -> int:
        return len(self.codebook)

    @property
    def n_actions(self) -> int:
        return self.predictor.n_actions

    @property
    def unknown_threshold(self) -> float:
        return self.unknown_factor * self.median_one_step_error

    # --- encoding and stepping --------------------------------------------------------
    @torch.no_grad()
    def encode(self, frames: np.ndarray | torch.Tensor) -> torch.Tensor:
        """Frames [B, 3, H, W] or [3, H, W] (uint8) -> standardised latents [B, D] or [D]."""
        x = torch.as_tensor(frames)
        single = x.ndim == 3
        z = self.encoder.standardize(self.encoder(x[None] if single else x))
        return z[0] if single else z

    @torch.no_grad()
    def step(self, z: torch.Tensor, action: torch.Tensor) -> torch.Tensor:
        return self.predictor(z, torch.as_tensor(action))

    @torch.no_grad()
    def rollout(self, z0: torch.Tensor, actions: torch.Tensor) -> torch.Tensor:
        """z0 [B, D], actions [B, K] -> imagined latents [B, K, D]."""
        return self.predictor.rollout(z0, torch.as_tensor(actions))

    @torch.no_grad()
    def imagine(self, z0: torch.Tensor, sequences: torch.Tensor) -> torch.Tensor:
        """Roll every sequence out from every start, in one batch.

        z0 [D] or [B, D], sequences [S, K] -> [S, K, D] or [B, S, K, D].
        """
        single = z0.ndim == 1
        z0 = z0[None] if single else z0
        b, s = len(z0), len(sequences)
        flat = self.predictor.rollout(z0.repeat_interleave(s, dim=0), sequences.repeat(b, 1))
        out = flat.view(b, s, *flat.shape[1:])
        return out[0] if single else out

    # --- snapping --------------------------------------------------------------------------
    @torch.no_grad()
    def snap(self, z: torch.Tensor) -> Snapped:
        idx, dist = snap(z, self.codebook)
        return Snapped(idx, dist, dist <= self.unknown_threshold)
