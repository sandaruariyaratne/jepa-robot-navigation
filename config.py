"""Load config.yaml, the single source of settings for every script."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = ROOT / "config.yaml"


def _merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in over.items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Load a config. `extends: other.yaml` (relative to this file) loads that first and deep-merges on top."""
    path = Path(path) if path is not None else DEFAULT_CONFIG
    with open(path) as f:
        cfg = yaml.safe_load(f)
    if not isinstance(cfg, dict):
        raise ValueError(f"{path} does not contain a mapping")
    parent = cfg.pop("extends", None)
    if parent is not None:
        cfg = _merge(load_config(path.parent / parent), cfg)
    return cfg


def resolve(path: str | Path) -> Path:
    """Paths in config.yaml are relative to the project root."""
    p = Path(path)
    return p if p.is_absolute() else ROOT / p
