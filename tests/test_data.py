"""Step 2 (data collection) checks from the build plan."""

import numpy as np
import pytest

from config import load_config
from data import FIELDS, TransitionWindows, all_pairs, load_split, load_transitions, pair_counts, pair_mask
from data.collect_data import collect, collect_from_config, save_npz, splits_from_config
from data.splits import is_collision_pair, load_splits, save_splits
from environment import GridMap, GridWorld

CFG = load_config()
MAP = GridMap()


@pytest.fixture(scope="module")
def data():
    return collect_from_config(CFG)


@pytest.fixture(scope="module")
def splits(data):
    return splits_from_config(CFG, int(data["episode_id"].max()) + 1, MAP)


# --- config ------------------------------------------------------------------
def test_config_matches_build_plan():
    d = CFG["data"]
    assert CFG["seed"] == 0
    assert (d["episodes"], d["steps_per_episode"]) == (200, 50)
    assert d["terminate_on_goal"] is False
    assert d["split_fractions"] == [0.8, 0.1, 0.1]
    assert (d["heldout_pairs"], d["heldout_min_collisions"]) == (10, 2)


# --- collection --------------------------------------------------------------
def test_contract_shapes_and_dtypes(data):
    n = 10_000
    assert set(data) == set(FIELDS)
    assert data["obs"].shape == data["next_obs"].shape == (n, 3, 40, 48)
    assert data["obs"].dtype == data["next_obs"].dtype == np.uint8
    for key in ("action", "episode_id", "step"):
        assert data[key].shape == (n,) and data[key].dtype == np.int64
    assert data["collision"].dtype == bool
    assert data["pos"].shape == data["next_pos"].shape == (n, 2)
    assert set(np.unique(data["action"])) == {0, 1, 2, 3}
    assert np.array_equal(np.bincount(data["episode_id"]), np.full(200, 50))
    assert np.array_equal(data["step"], np.tile(np.arange(50), 200))


def test_records_agree_with_simulator(data):
    renderer = GridWorld().renderer
    for i in range(0, len(data["action"]), 97):
        pos, a = tuple(data["pos"][i]), int(data["action"][i])
        nxt, collision = MAP.transition(pos, a)
        assert tuple(data["next_pos"][i]) == nxt
        assert bool(data["collision"][i]) == collision
        assert np.array_equal(data["obs"][i], renderer.render(pos))
        assert np.array_equal(data["next_obs"][i], renderer.render(nxt))


def test_episodes_are_continuous(data):
    same_ep = data["episode_id"][1:] == data["episode_id"][:-1]
    assert np.array_equal(data["next_obs"][:-1][same_ep], data["obs"][1:][same_ep])
    assert np.array_equal(data["next_pos"][:-1][same_ep], data["pos"][1:][same_ep])
    first = data["step"] == 0
    assert not any(tuple(p) == MAP.goal for p in data["pos"][first])  # random starts exclude the goal


def test_goal_transitions_are_recorded(data):
    at_goal = (data["pos"] == MAP.goal).all(axis=1)
    assert at_goal.any()  # terminate_on_goal=False keeps stepping through the goal


def test_all_100_pairs_covered(data):
    counts = pair_counts(data, MAP)
    assert len(counts) == 100
    assert min(counts.values()) > 0


def test_same_seed_gives_identical_file(tmp_path):
    a = save_npz(collect(20, 50, seed=0), tmp_path / "a.npz")
    b = save_npz(collect(20, 50, seed=0), tmp_path / "b.npz")
    assert a.read_bytes() == b.read_bytes()
    c = collect(20, 50, seed=1)
    assert not np.array_equal(c["action"], load_transitions(a)["action"])


def test_npz_round_trip(tmp_path, data):
    small = {k: v[:300] for k, v in data.items()}
    loaded = load_transitions(save_npz(small, tmp_path / "t.npz"))
    for k in FIELDS:
        assert loaded[k].dtype == small[k].dtype
        assert np.array_equal(loaded[k], small[k])


# --- splits ------------------------------------------------------------------
def test_episode_split_80_10_10(splits):
    tr, va, te = (set(splits[s]) for s in ("train", "val", "test"))
    assert (len(tr), len(va), len(te)) == (160, 20, 20)
    assert not (tr & va or tr & te or va & te)
    assert tr | va | te == set(range(200))


def test_heldout_pairs(splits):
    held = [tuple(p) for p in splits["heldout_pairs"]]
    assert len(set(held)) == 10
    assert set(held) <= set(all_pairs(MAP))
    n_collide = sum(is_collision_pair(MAP, p) for p in held)
    assert n_collide >= 2
    assert splits["heldout_collision"] == [is_collision_pair(MAP, p) for p in held]
    assert len({p[:2] for p in held}) == 10  # at most one per cell


def test_heldout_pairs_measurable_outside_training(data, splits):
    held = splits["heldout_pairs"]
    eval_eps = np.isin(data["episode_id"], splits["val"] + splits["test"])
    for p in held:
        assert (pair_mask(data["pos"], data["action"], [p]) & eval_eps).any(), p


def test_splits_reproducible_and_saved(tmp_path, splits, data):
    again = splits_from_config(CFG, 200, MAP)
    assert again == splits
    loaded = load_splits(save_splits(splits, tmp_path / "s.json"))
    assert loaded["heldout_pairs"] == [tuple(p) for p in splits["heldout_pairs"]]
    assert loaded["train"] == splits["train"]


# --- dataset -----------------------------------------------------------------
@pytest.mark.parametrize("k", [None, 1, 2, 4])
def test_heldout_pairs_absent_from_training_windows(data, splits, k):
    ds = TransitionWindows(data, splits["train"], k=k, exclude_pairs=splits["heldout_pairs"])
    b = ds.batch(np.arange(len(ds)))
    pos, act = b["pos"], b["action"]
    if k is not None:  # cell before each step of the window
        pos = np.concatenate([b["pos"][:, None], b["next_pos"][:, :-1]], axis=1).reshape(-1, 2)
        act = act.reshape(-1)
    assert len(ds) > 0
    assert not pair_mask(pos, act, splits["heldout_pairs"]).any()
    assert np.isin(b["episode_id"], splits["train"]).all()


@pytest.mark.parametrize("k", [1, 2, 4])
def test_window_counts_without_exclusion(data, splits, k):
    ds = TransitionWindows(data, splits["val"], k=k)
    assert len(ds) == len(splits["val"]) * (50 - k + 1)


def test_windows_are_consecutive_steps(data, splits):
    ds = TransitionWindows(data, splits["train"], k=4, exclude_pairs=splits["heldout_pairs"])
    b = ds.batch(np.arange(len(ds)))
    assert b["action"].shape == (len(ds), 4)
    assert b["next_obs"].shape == (len(ds), 4, 3, 40, 48)
    assert (b["step"] <= 46).all()
    for i in range(0, len(ds), 211):
        x = b["pos"][i]
        for j in range(4):  # replay the window through the true rules
            x, collision = MAP.transition(tuple(x), int(b["action"][i, j]))
            assert tuple(b["next_pos"][i, j]) == x
            assert bool(b["collision"][i, j]) == collision
        assert np.array_equal(b["obs"][i], data["obs"][ds.starts[i]])


def test_single_item_shapes(data, splits):
    one = TransitionWindows(data, splits["test"])[0]
    assert one["obs"].shape == one["next_obs"].shape == (3, 40, 48)
    assert one["action"].shape == () and one["pos"].shape == (2,)
    win = TransitionWindows(data, splits["test"], k=3)[-1]
    assert win["action"].shape == (3,) and win["next_obs"].shape == (3, 3, 40, 48)
    with pytest.raises(IndexError):
        TransitionWindows(data, splits["test"])[10_000]
    with pytest.raises(ValueError):
        TransitionWindows(data, splits["test"], k=0)


def test_load_split_from_config_files(tmp_path, data, splits):
    cfg = {**CFG, "data": {**CFG["data"], "path": str(tmp_path / "t.npz"), "splits_path": str(tmp_path / "s.json")}}
    save_splits(splits, cfg["data"]["splits_path"])
    ds = load_split("train", k=2, drop_heldout=True, cfg=cfg, data=data)
    assert len(ds) == len(TransitionWindows(data, splits["train"], k=2, exclude_pairs=splits["heldout_pairs"]))
    with pytest.raises(ValueError):
        load_split("dev", cfg=cfg, data=data)
