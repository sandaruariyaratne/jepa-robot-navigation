"""RGB renderer for the grid world (spec v1.1, section 02).

Each cell is cell_px x cell_px pixels: a 1 px grid line on its top and left
edges and a (cell_px - 1) square interior. Walls and the goal are static.
The robot fills its cell's interior and is drawn on top of the goal.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from .grid_world import GridMap, Pos

COLORS: dict[str, tuple[int, int, int]] = {
    "line": (200, 208, 216),
    "floor": (227, 233, 239),
    "wall": (127, 138, 150),
    "goal": (13, 122, 112),
    "robot": (42, 94, 168),
    "fog": (52, 58, 68),       # cells outside the robot's view (GridMap.view_radius)
}


class Renderer:
    def __init__(self, grid_map: "GridMap", cell_px: int = 8) -> None:
        if cell_px < 2:
            raise ValueError(f"cell_px must be >= 2, got {cell_px}")
        self.map = grid_map
        self.cell_px = cell_px
        self.height = grid_map.rows * cell_px
        self.width = grid_map.cols * cell_px
        self._background = self._draw_background()
        self._cache: dict[Pos, np.ndarray] = {}

    @property
    def shape(self) -> tuple[int, int, int]:
        return (3, self.height, self.width)

    def _interior(self, pos: "Pos") -> tuple[slice, slice]:
        x, y = pos
        p = self.cell_px
        return slice(y * p + 1, (y + 1) * p), slice(x * p + 1, (x + 1) * p)

    def _draw_background(self) -> np.ndarray:
        img = np.empty((self.height, self.width, 3), dtype=np.uint8)
        img[:] = COLORS["line"]
        for y in range(self.map.rows):
            for x in range(self.map.cols):
                c = (x, y)
                if c in self.map.walls:
                    color = COLORS["wall"]
                elif c == self.map.goal:
                    color = COLORS["goal"]
                else:
                    color = COLORS["floor"]
                img[self._interior(c)] = color
        return img

    def render(self, pos: "Pos") -> np.ndarray:
        """Frame with the robot at pos, as uint8 CHW. Returns a fresh copy."""
        pos = (int(pos[0]), int(pos[1]))
        frame = self._cache.get(pos)
        if frame is None:
            if not self.map.is_free(pos):
                raise ValueError(f"cannot render robot at {pos}: not a free cell")
            hwc = self._background.copy()
            r = self.map.view_radius
            if r is not None:                                   # fog of war around the robot
                for y in range(self.map.rows):
                    for x in range(self.map.cols):
                        if max(abs(x - pos[0]), abs(y - pos[1])) > r:
                            hwc[self._interior((x, y))] = COLORS["fog"]
            hwc[self._interior(pos)] = COLORS["robot"]
            frame = np.ascontiguousarray(hwc.transpose(2, 0, 1))
            frame.flags.writeable = False
            self._cache[pos] = frame
        return frame.copy()


def to_hwc(frame: np.ndarray) -> np.ndarray:
    """CHW -> HWC, for plotting."""
    return np.ascontiguousarray(np.asarray(frame).transpose(1, 2, 0))


def save_png(frame: np.ndarray, path: str | Path, scale: int = 1) -> Path:
    """Write a uint8 CHW or HWC RGB frame to PNG without extra dependencies."""
    img = np.asarray(frame)
    if img.ndim != 3:
        raise ValueError(f"expected a 3-D RGB array, got shape {img.shape}")
    if img.shape[0] == 3 and img.shape[-1] != 3:
        img = img.transpose(1, 2, 0)
    if img.dtype != np.uint8:
        raise ValueError(f"expected uint8, got {img.dtype}")
    if scale > 1:
        img = img.repeat(scale, axis=0).repeat(scale, axis=1)
    h, w, _ = img.shape
    raw = b"".join(b"\x00" + img[r].tobytes() for r in range(h))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )
    path = Path(path)
    path.write_bytes(png)
    return path
