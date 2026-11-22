"""Multi-map experiment checks: maps, split by map, collection, per-map snapping and evaluation helpers."""

import numpy as np
import pytest
import torch

from config import ROOT, load_config
from environment import DEFAULT_WALLS, GridWorld, distances_to_goal
from multimap.collect import collect, coverage
from multimap.evaluate import graph_metrics, navigate
from multimap.maps import generate_maps, is_valid, load_maps, save_maps, split_maps
from multimap.train import cell_ids, codebooks, decoded_robot_cells, snap_in_map, wall_accuracy, windows
from planning.true_model import TrueModel

CFG = load_config(ROOT / "config_multimap.yaml")


@pytest.fixture(scope="module")
def maps():
    return generate_maps(100, 0)


@pytest.fixture(scope="module")
def small(maps):
    sub = maps[:3]
    return sub, collect(sub, episodes_per_map=4, steps=30, seed=0)


def test_maps_are_distinct_valid_and_exclude_the_reference(maps):
    walls = [m.walls for m in maps]
    assert len(set(walls)) == 100 and frozenset(DEFAULT_WALLS) not in set(walls)
    for m in maps:
        assert is_valid(m) and m.goal == (5, 0) and 3 <= len(m.walls) <= 7
        assert (distances_to_goal(m) >= 0).sum() == len(m.free_cells())
    assert [m.walls for m in generate_maps(100, 0)] == walls  # seeded


def test_split_by_map(tmp_path, maps):
    s = split_maps(100, [0.7, 0.15, 0.15], 0)
    assert [len(s[k]) for k in ("train", "val", "test")] == [70, 15, 15]
    assert set(s["train"]) | set(s["val"]) | set(s["test"]) == set(range(100))
    assert not set(s["train"]) & set(s["test"])
    loaded, s2 = load_maps(save_maps(maps, s, tmp_path / "m.json"))
    assert s2 == s and [m.walls for m in loaded] == [m.walls for m in maps]


def test_collection_frame_table(small):
    sub, data = small
    n = 3 * 4 * 30
    assert len(data["action"]) == n
    for i in (0, 77, n - 1):
        m = data["map_id"][i]
        r = GridWorld(sub[m]).renderer
        assert np.array_equal(data["frames"][data["obs_id"][i]], r.render(tuple(data["pos"][i])))
        assert np.array_equal(data["frames"][data["next_id"][i]], r.render(tuple(data["next_pos"][i])))
        assert data["frame_map"][data["obs_id"][i]] == m
    assert (data["wall_bump"] <= data["collision"]).all()  # wall bumps are a kind of collision
    for i in np.flatnonzero(data["wall_bump"])[:20]:
        assert (data["pos"][i] == data["next_pos"][i]).all()
    assert all(c["frames"] <= c["free"] for c in coverage(data, sub))


def test_collection_is_seeded(small):
    sub, data = small
    again = collect(sub, episodes_per_map=4, steps=30, seed=0)
    assert all(np.array_equal(data[k], again[k]) for k in data)


def test_windows_stay_inside_one_episode_and_map(small):
    _, data = small
    t = windows(data, [1, 2], 4)
    starts = t["obs"].numpy()
    assert set(t["map"].tolist()) <= {1, 2}
    assert t["next"].shape[1] == 4 and len(starts) == 2 * 4 * (30 - 3)


def test_snap_is_restricted_to_the_robots_map():
    cb = torch.zeros(2, 30, 2)
    mask = torch.zeros(2, 30, dtype=torch.bool)
    cb[0, 3], mask[0, 3] = torch.tensor([1.0, 0.0]), True
    cb[1, 7], mask[1, 7] = torch.tensor([0.9, 0.0]), True  # nearer, but on another map
    cb[0, 9], mask[0, 9] = torch.tensor([5.0, 5.0]), True
    cell, _ = snap_in_map(torch.tensor([[0.9, 0.0]]), torch.tensor([0]), cb, mask)
    assert cell.item() == 3


def test_codebook_mask_matches_seen_cells(small):
    sub, data = small
    table = torch.randn(len(data["frames"]), 8)
    cb, mask = codebooks(table, data, len(sub))
    for m in range(len(sub)):
        seen = set(cell_ids(data["frame_pos"][data["frame_map"] == m]).tolist())
        assert set(np.flatnonzero(mask[m].numpy()).tolist()) == seen


def test_decode_checks_on_true_frames(maps):
    sub = maps[:4]
    frames, fmap, cells = [], [], []
    for m, g in enumerate(sub):
        r = GridWorld(g).renderer
        for c in g.free_cells()[:6]:
            frames.append(r.render(c) / 255.0)
            fmap.append(m)
            cells.append(c[1] * 6 + c[0])
    pred, d_robot, d_bg, means = decoded_robot_cells(np.stack(frames), sub, np.array(fmap))
    assert pred.tolist() == cells
    assert wall_accuracy(means, sub, np.array(fmap)) == 1.0


def test_true_model_graph_and_navigation_on_a_new_map(maps):
    grid = maps[42]
    true = TrueModel(grid)
    goal_frame = GridWorld(grid).goal_obs()
    gm = graph_metrics(true, grid, goal_frame)
    assert all(v["correct"] == v["total"] for v in gm["edges"].values())
    assert gm["d_exact"] == gm["d_cells"] and gm["goal_ok"]
    eps = navigate(true, grid, goal_frame, CFG, [0])
    for label in ("Oracle", "D1", "D2", "D3", "Full"):
        assert all(e.success and e.steps == e.optimal for e in eps[label]), label


def test_multimap_jepa_trains_and_selects_on_validation_maps(small):
    from multimap.train_jepa import train as train_jepa

    sub, data = small
    cfg = load_config(ROOT / "config_multimap_jepa.yaml")
    cfg["multimap"]["jepa"].update(latent_dim=8, hidden=[16], steps=4, eval_every=2, maps_per_step=2,
                                   windows_per_step=16, curriculum=[[1, 1], [3, 2]])
    cfg["probe"]["steps"] = 20
    target, predictor, m = train_jepa(cfg, data, {"train": [0, 1], "val": [2], "test": []}, len(sub), verbose=False)
    assert m["best_step"] in (2, 4) and [r["step"] for r in m["history"]] == [2, 4]
    assert np.isfinite(m["median_one_step_error"]) and 0.0 <= m["best_val_snap"] <= 1.0
    assert not target.training and not any(p.requires_grad for p in [*target.parameters(), *predictor.parameters()])


def test_new_maps_exclude_given_layouts_and_codebooks_are_completed(maps):
    from multimap.new_maps import complete_frames

    new = generate_maps(50, 1, exclude=[m.walls for m in maps])
    assert len({m.walls for m in new}) == 50 and not {m.walls for m in new} & {m.walls for m in maps}
    sub = new[:3]
    data = collect(sub, episodes_per_map=1, steps=5, seed=0)  # far too short to visit every cell
    added = complete_frames(data, sub)
    assert added > 0
    for m, g in enumerate(sub):
        sel = data["frame_map"] == m
        assert {tuple(p) for p in data["frame_pos"][sel]} == set(g.free_cells())
        r = GridWorld(g).renderer
        for f, p in zip(data["frames"][sel], data["frame_pos"][sel]):
            assert np.array_equal(f, r.render(tuple(p)))


def test_chunked_new_map_metrics_equal_the_unchunked_ones(small):
    from multimap.new_maps import chunked_metrics, collision_metrics
    from multimap.evaluate import prediction_metrics
    from models import Predictor

    sub, data = small
    torch.manual_seed(0)
    table = torch.randn(len(data["frames"]), 8)
    cb, mask = codebooks(table, data, len(sub))
    model = Predictor(8, 4, [16], 0.1).eval()
    whole = {"prediction": prediction_metrics(model, table, data, [0, 1, 2], cb, mask, 3),
             "collision": collision_metrics(model, table, data, [0, 1, 2], cb, mask)}
    parts = chunked_metrics(model, table, data, [0, 1, 2], cb, mask, 3, chunk=1)
    assert parts["prediction"]["one_step"] == whole["prediction"]["one_step"]
    assert np.allclose(parts["prediction"]["rollout"], whole["prediction"]["rollout"])
    assert parts["prediction"]["mse_model"] == pytest.approx(whole["prediction"]["mse_model"], rel=1e-5)
    assert parts["collision"]["accuracy"] == pytest.approx(whole["collision"]["accuracy"])
    assert parts["collision"]["precision"] == pytest.approx(whole["collision"]["precision"])
