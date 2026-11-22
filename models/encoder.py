"""CNN encoder (spec section 03-A, build plan step 5).

    Input            RGB / 255             3 x 40 x 48
    Conv2d + ReLU    3 -> 16, k3 s2 p1     16 x 20 x 24
    Conv2d + ReLU    16 -> 32, k3 s2 p1    32 x 10 x 12
    Conv2d + ReLU    32 -> 64, k3 s2 p1    64 x 5 x 6
    Flatten + Linear 1920 -> 32            32

Trained with the decoder (Stage 1), then frozen. The checkpoint also carries
the per-dimension mean / std of training latents and the codebook: the
latents of the 25 distinct frames, used for snapping from step 6 on.
"""

from __future__ import annotations

import torch
from torch import nn


def conv_out(n: int, stages: int = 3) -> int:
    """Spatial size after `stages` stride-2, k3, p1 convolutions."""
    for _ in range(stages):
        n = (n + 1) // 2
    return n


class Encoder(nn.Module):
    def __init__(self, latent_dim: int = 32, input_shape: tuple[int, int, int] = (3, 40, 48)) -> None:
        super().__init__()
        c, h, w = input_shape
        self.latent_dim = latent_dim
        self.input_shape = tuple(input_shape)
        self.feature_shape = (64, conv_out(h), conv_out(w))  # 64 x 5 x 6
        self.conv = nn.Sequential(
            nn.Conv2d(c, 16, 3, stride=2, padding=1), nn.ReLU(),
            nn.Conv2d(16, 32, 3, stride=2, padding=1), nn.ReLU(),
            nn.Conv2d(32, 64, 3, stride=2, padding=1), nn.ReLU(),
        )
        self.fc = nn.Linear(64 * self.feature_shape[1] * self.feature_shape[2], latent_dim)  # 1920 -> 32
        # Per-dimension statistics of training latents, filled in after training.
        self.register_buffer("z_mean", torch.zeros(latent_dim))
        self.register_buffer("z_std", torch.ones(latent_dim))

    @staticmethod
    def prepare(x: torch.Tensor) -> torch.Tensor:
        """uint8 frames -> float in [0, 1]; float input is assumed already scaled."""
        return x.float() / 255.0 if x.dtype == torch.uint8 else x.float()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Frames [B, 3, H, W] (uint8 or float in [0, 1]) -> latents [B, latent_dim]."""
        return self.fc(self.conv(self.prepare(x)).flatten(1))

    def standardize(self, z: torch.Tensor) -> torch.Tensor:
        return (z - self.z_mean) / self.z_std

    def unstandardize(self, z: torch.Tensor) -> torch.Tensor:
        return z * self.z_std + self.z_mean

    def freeze(self) -> "Encoder":
        self.requires_grad_(False)
        return self.eval()


def load_encoder(path) -> tuple[Encoder, dict]:
    """Frozen encoder (with z_mean / z_std) and the raw checkpoint dict (codebook, codebook_cells, ...)."""
    ckpt = torch.load(path, map_location="cpu", weights_only=True)
    encoder = Encoder(ckpt["latent_dim"], tuple(ckpt["input_shape"]))
    encoder.load_state_dict(ckpt["state_dict"])
    return encoder.freeze(), ckpt
