"""Load config.yaml, the single source of settings for every script."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = ROOT / "config.yaml"


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    path = Path(path) if path is not None else DEFAULT_CONFIG
    with open(path) as f:
        cfg = yaml.safe_load(f)
    if not isinstance(cfg, dict):
        raise ValueError(f"{path} does not contain a mapping")
    return cfg


def resolve(path: str | Path) -> Path:
    """Paths in config.yaml are relative to the project root."""
    p = Path(path)
    return p if p.is_absolute() else ROOT / p
