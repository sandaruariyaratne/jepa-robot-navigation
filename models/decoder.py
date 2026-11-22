"""Mirrored decoder (spec section 03-A, build plan step 5).

    Linear + ReLU       32 -> 1920, reshape     64 x 5 x 6
    Upsample 2x + Conv  64 -> 32, k3 p1, ReLU   32 x 10 x 12
    Upsample 2x + Conv  32 -> 16, k3 p1, ReLU   16 x 20 x 24
    Upsample 2x + Conv  16 -> 3,  k3 p1         3 x 40 x 48
    Sigmoid                                     RGB in [0, 1]

Only used to pretrain the encoder and to visualise imagined latents. It is
not part of the controller.
"""

from __future__ import annotations

import torch
from torch import nn

from .encoder import conv_out


class Decoder(nn.Module):
    def __init__(self, latent_dim: int = 32, output_shape: tuple[int, int, int] = (3, 40, 48)) -> None:
        super().__init__()
        c, h, w = output_shape
        if conv_out(h) * 8 != h or conv_out(w) * 8 != w:
            raise ValueError(f"output height and width must be multiples of 8, got {h} x {w}")
        self.output_shape = tuple(output_shape)
        self.feature_shape = (64, h // 8, w // 8)
        self.fc = nn.Sequential(nn.Linear(latent_dim, 64 * (h // 8) * (w // 8)), nn.ReLU())
        up = lambda: nn.Upsample(scale_factor=2, mode="nearest")  # noqa: E731
        self.deconv = nn.Sequential(
            up(), nn.Conv2d(64, 32, 3, padding=1), nn.ReLU(),
            up(), nn.Conv2d(32, 16, 3, padding=1), nn.ReLU(),
            up(), nn.Conv2d(16, c, 3, padding=1),
            nn.Sigmoid(),
        )

    def forward(self, z: torch.Tensor) -> torch.Tensor:
        """Latents [B, latent_dim] -> frames [B, 3, H, W] in [0, 1]."""
        return self.deconv(self.fc(z).view(-1, *self.feature_shape))


def load_decoder(path) -> Decoder:
    ckpt = torch.load(path, map_location="cpu", weights_only=True)
    decoder = Decoder(ckpt["latent_dim"], tuple(ckpt["output_shape"]))
    decoder.load_state_dict(ckpt["state_dict"])
    decoder.requires_grad_(False)
    return decoder.eval()
