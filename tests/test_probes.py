"""Step 4 (probe utilities) checks from the build plan."""

import numpy as np
import pytest
import torch

from config import load_config
from data.collect_data import collect_from_config, splits_from_config
from environment import GridMap
from evaluation.probes import CellIndex, LinearProbe, probe_kwargs, probe_report, run_sanity_checks, sanity_features

CFG = load_config()


@pytest.fixture(scope="module")
def sanity():
    data = collect_from_config(CFG)
    return run_sanity_checks(CFG, data, splits_from_config(CFG, 200))


# --- cell index ----------------------------------------------------------------
def test_cell_index_round_trip():
    cells = CellIndex()
    free = np.array(GridMap().free_cells())
    assert len(cells) == 25
    assert np.array_equal(cells.ids(free), np.arange(25))
    assert np.array_equal(cells.positions(np.arange(25)), free)
    assert cells.ids(np.array([5, 0])) == 5  # top-right goal, row-major
    assert cells.ids(np.array([[0, 4], [5, 4]])).tolist() == [20, 24]


@pytest.mark.parametrize("pos", [(2, 1), (4, 4), (6, 0), (0, -1)])
def test_cell_index_rejects_walls_and_outside(pos):
    with pytest.raises(ValueError):
        CellIndex().ids(np.array(pos))


# --- sanity checks from the build plan --------------------------------------
def test_onehot_positions_score_100(sanity):
    assert sanity["onehot"]["accuracy"] == 1.0
    assert sanity["onehot"]["train_accuracy"] == 1.0


def test_noise_scores_near_chance(sanity):
    r = sanity["noise"]
    assert r["chance"] == pytest.approx(0.04)
    assert r["accuracy"] < 0.10


# --- probe mechanics -----------------------------------------------------------
def _toy(n=600, dim=8, seed=0):
    rng = np.random.default_rng(seed)
    y = rng.integers(0, 25, n)
    x = sanity_features(y, "onehot", dim=32)[:, :25] * 3 + 0.1 * rng.standard_normal((n, 25))
    return x[:, :dim] if dim < 25 else x.astype(np.float32), y


def test_fit_is_deterministic_and_leaves_global_rng_alone():
    x, y = _toy(dim=25)
    torch.manual_seed(123)
    expected_next = torch.rand(1)
    torch.manual_seed(123)
    a = LinearProbe(25).fit(x, y, steps=50, seed=0)
    assert torch.equal(torch.rand(1), expected_next)
    b = LinearProbe(25).fit(x, y, steps=50, seed=0)
    assert torch.equal(a.linear.weight, b.linear.weight)


def test_constant_columns_do_not_break_standardisation():
    x, y = _toy(dim=25)
    x = np.concatenate([x, np.ones((len(x), 7), dtype=np.float32)], axis=1)  # 32-D, 7 constant
    probe = LinearProbe(32).fit(x, y, steps=200)
    assert torch.isfinite(probe.linear.weight).all()
    assert probe.score(x, y) > 0.95


def test_report_fields():
    x, y = _toy(dim=25)
    keep = y != 7  # cell 7 absent from eval
    _, r = probe_report(x, y, x[keep], y[keep], **probe_kwargs(CFG))
    assert r["confusion"].shape == (25, 25)
    assert r["confusion"].sum() == keep.sum()
    assert np.isnan(r["per_cell"][7])
    assert 0.0 <= r["accuracy"] <= 1.0 and 0.0 <= r["majority"] <= 1.0


def test_state_dict_round_trip_keeps_standardisation():
    x, y = _toy(dim=25)
    a = LinearProbe(25).fit(x + 5.0, y, steps=50)
    b = LinearProbe(25)
    b.load_state_dict(a.state_dict())
    assert torch.allclose(b.mean, a.mean)
    assert np.array_equal(a.predict(x + 5.0), b.predict(x + 5.0))


def test_fit_works_under_no_grad():
    x, y = _toy(dim=25)
    with torch.no_grad():
        probe = LinearProbe(25).fit(x, y, steps=100)
    assert probe.score(x, y) > 0.95


def test_shape_mismatch_rejected():
    with pytest.raises(ValueError):
        LinearProbe(4).fit(np.zeros((10, 4)), np.zeros(9, dtype=np.int64))
