"""Step 6 (latent predictor) checks. Uses synthetic latents (a fixed random vector
per cell) so the tests don't depend on a trained encoder checkpoint."""

import numpy as np
import pytest
import torch

from config import load_config
from data import TransitionWindows, pair_mask
from data.collect_data import collect_from_config, splits_from_config
from evaluation.probes import CellIndex
from models import Predictor, snap
from models.predictor import load_predictor
from training.train_world_model import done_checks, k_for_epoch, save_checkpoint, train, window_tensors

CFG = load_config()
CELLS = CellIndex()


@pytest.fixture(scope="module")
def data():
    return collect_from_config(CFG)


@pytest.fixture(scope="module")
def splits(data):
    return splits_from_config(CFG, 200)


@pytest.fixture(scope="module")
def synthetic(data):
    table = np.random.default_rng(0).standard_normal((25, 32)).astype(np.float32)
    latents = {"z_obs": table[CELLS.ids(data["pos"])], "z_next": table[CELLS.ids(data["next_pos"])]}
    return latents, torch.as_tensor(table)


@pytest.fixture(scope="module")
def trained(data, splits, synthetic):
    latents, codebook = synthetic
    return train(CFG, data, splits, latents, codebook, verbose=False)


# --- model ---------------------------------------------------------------------
def test_starts_as_persistence_and_matches_spec_shape():
    m = Predictor(32, 4, (128, 128), 1e-3)
    sizes = [(l.in_features, l.out_features) for l in m.f if isinstance(l, torch.nn.Linear)]
    assert sizes == [(36, 128), (128, 128), (128, 32)]
    z = torch.randn(16, 32)
    a = torch.randint(0, 4, (16,))
    assert (m(z, a) - z).abs().max() < 0.01  # near-zero last layer -> z_hat ~ z


def test_rollout_feeds_predictions_back():
    m = Predictor(8, 4, (16,), 1.0)
    z0 = torch.randn(3, 8)
    acts = torch.randint(0, 4, (3, 5))
    out = m.rollout(z0, acts)
    assert out.shape == (3, 5, 8)
    z = z0
    for k in range(5):
        z = m(z, acts[:, k])
        assert torch.allclose(out[:, k], z)


def test_snap_finds_nearest_entry():
    cb = torch.tensor([[0.0, 0.0], [10.0, 0.0], [0.0, 10.0]])
    idx, dist = snap(torch.tensor([[[9.0, 1.0], [1.0, 1.0]]]), cb)
    assert idx.tolist() == [[1, 0]]
    assert dist.shape == (1, 2)


@pytest.mark.parametrize("epoch,k", [(1, 1), (10, 1), (11, 2), (20, 2), (21, 4), (50, 4)])
def test_curriculum(epoch, k):
    assert k_for_epoch(CFG["predictor"]["curriculum"], epoch) == k


# --- data plumbing ---------------------------------------------------------------
def test_window_tensors_and_heldout_exclusion(data, splits, synthetic):
    latents, _ = synthetic
    ds = TransitionWindows(data, splits["train"], k=4, exclude_pairs=splits["heldout_pairs"])
    t = window_tensors(ds, latents, CELLS)
    assert t["z0"].shape == (len(ds), 32) and t["target"].shape == (len(ds), 4, 32)
    assert t["action"].shape == t["next_cell"].shape == (len(ds), 4)
    # rebuild each step's start cell and check no held-out pair is in any training window
    start_cells = torch.cat([t["cell"][:, None], t["next_cell"][:, :-1]], dim=1)
    pos = CELLS.positions(start_cells.numpy()).reshape(-1, 2)
    assert not pair_mask(pos, t["action"].reshape(-1).numpy(), splits["heldout_pairs"]).any()
    # targets are the latents of the next frames
    assert torch.equal(t["target"][:, 0], torch.as_tensor(latents["z_next"][ds.starts]))


# --- training ----------------------------------------------------------------------
def test_done_when_checks_on_synthetic_latents(trained):
    _, metrics = trained
    checks = done_checks(metrics)
    assert all(checks.values()), checks
    assert metrics["rollout_trained_windows"]["snap_acc"][4] >= 0.99  # 5 imagined steps
    assert metrics["pairs"]["held-out (all)"]["total"] == 10
    assert len(metrics["pair_details"]) >= 10
    assert metrics["median_one_step_error"] > 0


def test_selection_uses_multi_step_snap_accuracy(trained):
    _, metrics = trained
    h = metrics["select_horizon"]
    best = max(metrics["history"], key=lambda r: (r[f"val_snap_{h}"], -r[f"val_mse_{h}"]))
    assert best["epoch"] == metrics["best_epoch"]


def test_training_is_reproducible(data, splits, synthetic):
    latents, codebook = synthetic
    cfg = {**CFG, "predictor": {**CFG["predictor"], "epochs": 3, "curriculum": [[1, 1], [2, 2], [3, 4]]}}
    a, _ = train(cfg, data, splits, latents, codebook, verbose=False)
    b, _ = train(cfg, data, splits, latents, codebook, verbose=False)
    for va, vb in zip(a.state_dict().values(), b.state_dict().values()):
        assert torch.equal(va, vb)


def test_checkpoint_round_trip(tmp_path, trained, synthetic):
    model, metrics = trained
    _, codebook = synthetic
    loaded, ckpt = load_predictor(save_checkpoint(model, CFG, metrics, tmp_path / "p.pt"))
    a = torch.arange(25) % 4
    assert torch.equal(loaded(codebook, a), model(codebook, a))
    assert ckpt["median_one_step_error"] == metrics["median_one_step_error"]
    assert not any(p.requires_grad for p in loaded.parameters())
