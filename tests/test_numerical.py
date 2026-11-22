"""Step 3 (numerical baseline) checks from the build plan."""

import numpy as np
import pytest
import torch

from config import load_config
from data import pair_mask
from data.collect_data import collect_from_config, splits_from_config
from models import NumericalModel
from training.train_numerical import CATEGORIES, load_checkpoint, save_checkpoint, train, training_sets

CFG = load_config()


@pytest.fixture(scope="module")
def data():
    return collect_from_config(CFG)


@pytest.fixture(scope="module")
def splits(data):
    return splits_from_config(CFG, 200)


@pytest.fixture(scope="module")
def trained(data, splits):
    return train(CFG, data, splits, verbose=False)


def test_model_shapes_and_normalization():
    m = NumericalModel((16, 16))
    m.set_normalization(torch.tensor([2.5, 2.0]), torch.tensor([1.7, 1.4]))
    pos = torch.tensor([[0, 4], [5, 0]])
    act = torch.tensor([0, 3])
    assert m(pos, act).shape == (2, 2)
    assert m.predict_cell(pos, act).dtype == torch.int64
    assert torch.allclose(m.predict(pos, act), m(pos, act) * m.pos_std + m.pos_mean)
    assert {"pos_mean", "pos_std"} <= set(m.state_dict())  # stats travel with the weights


def test_training_sets_exclude_heldout_pairs(data, splits):
    tr, va = training_sets(data, splits)
    for t in (tr, va):
        assert not pair_mask(t["pos"].long().numpy(), t["action"].numpy(), splits["heldout_pairs"]).any()
    assert len(tr["action"]) == 7175


def test_trained_pairs_near_perfect(trained):
    _, metrics = trained
    for name in ("normal moves", "collisions"):
        assert metrics["pairs"][name]["accuracy"] >= 0.99, name
        assert metrics["test"][name]["accuracy"] >= 0.99, name


def test_categories_reported_separately(trained, splits):
    _, metrics = trained
    for scope in ("val", "test", "pairs"):
        assert set(metrics[scope]) == set(CATEGORIES)
    p = metrics["pairs"]
    assert p["held-out (all)"]["total"] == 10
    assert p["held-out moves"]["total"] + p["held-out collisions"]["total"] == 10
    assert sum(p[c]["total"] for c in ("normal moves", "collisions", "held-out (all)")) == 100
    details = {tuple(d["pair"]) for d in metrics["pair_details"] if d["heldout"]}
    assert details == {tuple(x) for x in splits["heldout_pairs"]}


def test_training_is_reproducible(data, splits):
    cfg = {**CFG, "numerical": {**CFG["numerical"], "epochs": 2}}
    a, _ = train(cfg, data, splits, verbose=False)
    b, _ = train(cfg, data, splits, verbose=False)
    for (ka, va), (kb, vb) in zip(a.state_dict().items(), b.state_dict().items()):
        assert ka == kb and torch.equal(va, vb)


def test_checkpoint_round_trip(tmp_path, trained):
    model, metrics = trained
    loaded = load_checkpoint(save_checkpoint(model, CFG, metrics, tmp_path / "n.pt"))
    pos = torch.tensor(np.array([[0, 4], [3, 1], [5, 3]]))
    act = torch.tensor([0, 0, 1])
    assert torch.equal(loaded.predict_cell(pos, act), model.predict_cell(pos, act))
