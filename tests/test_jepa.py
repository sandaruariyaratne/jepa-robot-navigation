"""Step 12 / v2 experiment 1 (joint JEPA) checks."""

import numpy as np
import pytest
import torch

from config import ROOT, load_config
from data import TransitionWindows, pair_mask
from data.collect_data import collect_from_config, splits_from_config
from evaluation.probes import CellIndex
from models import Encoder
from training.train_jepa import (
    _windows,
    codebook_ids,
    coordinate_r2,
    ema_update,
    frame_table,
    save,
    train,
    vicreg_terms,
)

CFG2 = load_config(ROOT / "config_v2.yaml")
CELLS = CellIndex()


@pytest.fixture(scope="module")
def data():
    return collect_from_config(CFG2)


@pytest.fixture(scope="module")
def splits(data):
    return splits_from_config(CFG2, 200)


def test_v2_config_extends_v1():
    base = load_config()
    assert CFG2["data"] == base["data"]
    assert {k: v for k, v in CFG2["planning"].items() if k != "metrics"} == \
        {k: v for k, v in base["planning"].items() if k != "metrics"}
    assert CFG2["encoder"]["checkpoint"] == "checkpoints_v2/encoder.pt"
    assert CFG2["encoder"]["latent_dim"] == base["encoder"]["latent_dim"]  # untouched keys survive the merge
    assert CFG2["jepa"]["ema_tau"] == 0.99 and CFG2["evaluation"]["results_dir"] == "results_v2"
    assert "extends" not in CFG2


def test_frame_table_has_the_25_distinct_frames(data):
    frames, obs_id, next_id = frame_table(data)
    assert len(frames) == 25
    for i in (0, 123, 9999):
        assert np.array_equal(frames[obs_id[i]], data["obs"][i])
        assert np.array_equal(frames[next_id[i]], data["next_obs"][i])


def test_codebook_entry_i_is_cell_i(data, splits):
    frames, obs_id, _ = frame_table(data)
    ids = codebook_ids(data, splits, obs_id)
    from environment import GridWorld

    r = GridWorld().renderer
    for i, (x, y) in enumerate(CELLS.cells):
        assert np.array_equal(frames[ids[i]], r.render((int(x), int(y))))


def test_vicreg_terms():
    collapsed = torch.ones(25, 8)
    v, c = (float(t) for t in vicreg_terms(collapsed))
    assert v == pytest.approx(1.0, abs=0.02) and c == pytest.approx(0.0)
    spread = torch.randn(1000, 8, generator=torch.Generator().manual_seed(0)) * 3
    v, c_independent = (float(t) for t in vicreg_terms(spread))
    assert v == pytest.approx(0.0)
    corr = torch.randn(1000, 1, generator=torch.Generator().manual_seed(1)).repeat(1, 8) * 2
    c_correlated = float(vicreg_terms(corr)[1])
    assert c_correlated > 10 and c_independent < c_correlated / 10


def test_ema_update():
    a, b = Encoder(4), Encoder(4)
    before = [p.clone() for p in a.parameters()]
    ema_update(a, b, 0.5)
    for p, q, r in zip(a.parameters(), b.parameters(), before):
        assert torch.allclose(p, 0.5 * r + 0.5 * q)


def test_coordinate_r2():
    w = np.random.default_rng(0).standard_normal((2, 32))
    linear = CELLS.cells @ w
    assert coordinate_r2(linear, CELLS.cells) == pytest.approx(1.0)
    noise = np.random.default_rng(1).standard_normal((25, 32))
    assert coordinate_r2(noise, CELLS.cells) < 0.6


def test_training_windows_exclude_heldout(data, splits):
    _, obs_id, next_id = frame_table(data)
    t = _windows(data, splits["train"], 4, splits["heldout_pairs"], obs_id, next_id)
    ds = TransitionWindows(data, splits["train"], k=4, exclude_pairs=splits["heldout_pairs"])
    rows = ds.starts[:, None] + np.arange(4)
    assert len(t["obs"]) == len(ds)
    assert not pair_mask(data["pos"][rows].reshape(-1, 2), data["action"][rows].reshape(-1),
                         splits["heldout_pairs"]).any()


@pytest.fixture(scope="module")
def short_run(data, splits):
    cfg = {**CFG2, "jepa": {**CFG2["jepa"], "epochs": 3, "curriculum": [[1, 1], [2, 2], [3, 4]]}}
    return cfg, train(cfg, data, splits, verbose=False)


def test_short_run_outputs(short_run):
    _, (target, predictor, metrics) = short_run
    assert not any(p.requires_grad for p in target.parameters())
    assert not any(p.requires_grad for p in predictor.parameters())
    assert metrics["codebook"].shape == (25, 32)
    assert metrics["pairs"]["held-out (all)"]["total"] == 10
    assert {"coordinate_r2_top3_pcs", "effective_rank", "min_dim_std"} <= set(metrics["latent_geometry"])


def test_training_is_reproducible(data, splits, short_run):
    cfg, (target, _, _) = short_run
    again, _, _ = train(cfg, data, splits, verbose=False)
    for a, b in zip(target.state_dict().values(), again.state_dict().values()):
        assert torch.equal(a, b)


def test_checkpoints_plug_into_the_v1_pipeline(short_run, tmp_path):
    cfg, (target, predictor, metrics) = short_run
    cfg = {**cfg, "encoder": {**cfg["encoder"], "checkpoint": str(tmp_path / "e.pt")},
           "predictor": {**cfg["predictor"], "checkpoint": str(tmp_path / "p.pt")}}
    enc_path, pred_path = save(target, predictor, metrics, cfg)
    from planning.imagination import WorldModel
    from planning.latent_graph import build_graph

    world = WorldModel.from_checkpoints(enc_path, pred_path)
    assert torch.allclose(world.codebook, metrics["codebook"])  # identity standardisation
    assert build_graph(world).next.shape == (25, 4)
