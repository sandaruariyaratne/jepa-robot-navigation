"""Split-aware access to the transition file (build plan step 2).

TransitionWindows(data, episodes, k=None)  -> single transitions
TransitionWindows(data, episodes, k=K)     -> K-step windows inside one episode

Map-style (len / getitem), so a torch DataLoader can wrap it later; `batch`
gathers many items at once with numpy indexing, which is much faster.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path

import numpy as np

from config import load_config, resolve

from .splits import load_splits, pair_mask

# Dataset contract (spec section 02 + build plan step 2). pos / next_pos are the
# true cells, for probes, splitting and evaluation only -- never model inputs.
FIELDS = ("obs", "action", "next_obs", "episode_id", "step", "collision", "pos", "next_pos")


def load_transitions(path: str | Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as z:
        missing = set(FIELDS) - set(z.files)
        if missing:
            raise ValueError(f"{path} is missing fields: {sorted(missing)}")
        return {k: z[k] for k in FIELDS}


class TransitionWindows:
    """Transitions (k=None) or K-step windows (k>=1) from the given episodes.

    A window is K consecutive steps of one episode. With exclude_pairs, any
    window containing one of those (state, action) pairs is dropped -- use the
    held-out pairs here for predictor training.

    Single item (k=None):  obs [3,H,W], action (), next_obs [3,H,W], pos [2], next_pos [2], collision ()
    Window item (k=K):     obs [3,H,W] (first frame), action [K], next_obs [K,3,H,W],
                           pos [2] (first cell), next_pos [K,2], collision [K]
    Both also carry episode_id and step (of the first transition).
    """

    def __init__(
        self,
        data: dict[str, np.ndarray],
        episode_ids: Iterable[int],
        k: int | None = None,
        exclude_pairs: Iterable[Sequence[int]] = (),
    ) -> None:
        if k is not None and k < 1:
            raise ValueError(f"k must be >= 1 or None, got {k}")
        self.data = data
        self.k = k
        span = 1 if k is None else k
        ep, step = data["episode_id"], data["step"]
        n = len(ep)

        ok = np.isin(ep, np.asarray(list(episode_ids), dtype=np.int64)) & ~pair_mask(data["pos"], data["action"], exclude_pairs)
        valid = ok.copy()
        for j in range(1, span):  # transition i + j must continue the same episode
            nxt = np.zeros(n, dtype=bool)
            nxt[: n - j] = ok[j:] & (ep[j:] == ep[: n - j]) & (step[j:] == step[: n - j] + j)
            valid &= nxt
        self.starts = np.flatnonzero(valid)

    def __len__(self) -> int:
        return len(self.starts)

    def __getitem__(self, i: int) -> dict[str, np.ndarray]:
        if not -len(self) <= i < len(self):
            raise IndexError(i)
        return {key: v[0] for key, v in self.batch(np.array([i])).items()}

    def batch(self, idx: np.ndarray | slice | None = None) -> dict[str, np.ndarray]:
        """Stacked items for an array (or slice) of dataset indices; None = every item."""
        if idx is None:
            idx = slice(None)
        first = self.starts[idx if isinstance(idx, slice) else np.asarray(idx)]
        d = self.data
        if self.k is None:
            return {key: d[key][first] for key in
                    ("obs", "action", "next_obs", "pos", "next_pos", "collision", "episode_id", "step")}
        rows = first[:, None] + np.arange(self.k)  # [B, K]
        return {
            "obs": d["obs"][first],
            "action": d["action"][rows],
            "next_obs": d["next_obs"][rows],
            "pos": d["pos"][first],
            "next_pos": d["next_pos"][rows],
            "collision": d["collision"][rows],
            "episode_id": d["episode_id"][first],
            "step": d["step"][first],
        }


def load_split(
    split: str,
    k: int | None = None,
    drop_heldout: bool = False,
    cfg: dict | None = None,
    data: dict[str, np.ndarray] | None = None,
) -> TransitionWindows:
    """Dataset for 'train' / 'val' / 'test' from the files named in config.yaml.

    drop_heldout=True removes windows touching the held-out pairs (predictor training).
    """
    cfg = cfg or load_config()
    if data is None:
        data = load_transitions(resolve(cfg["data"]["path"]))
    splits = load_splits(resolve(cfg["data"]["splits_path"]))
    if split not in ("train", "val", "test"):
        raise ValueError(f"split must be train, val or test, got {split!r}")
    exclude = splits["heldout_pairs"] if drop_heldout else ()
    return TransitionWindows(data, splits[split], k=k, exclude_pairs=exclude)
