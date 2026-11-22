"""Step 5 (autoencoder) checks. Training here runs on a small slice of the data;
the full run and its gate are `python -m training.train_encoder`."""

import numpy as np
import pytest
import torch

from config import load_config
from data.collect_data import collect_from_config, splits_from_config
from environment import GridMap, GridWorld
from evaluation.probes import CellIndex
from models import Decoder, Encoder
from models.decoder import load_decoder
from models.encoder import load_encoder
from training.train_encoder import (
    background_frame,
    codebook_frames,
    decode_mosaic,
    decoded_robot_cells,
    encode,
    prepare_sets,
    recon_loss,
    robot_mask,
    save_checkpoints,
    train,
    train_attempt,
)

CFG = load_config()
CELLS = CellIndex()


@pytest.fixture(scope="module")
def data():
    return collect_from_config(CFG)


@pytest.fixture(scope="module")
def splits(data):
    return splits_from_config(CFG, 200)


@pytest.fixture(scope="module")
def small(splits):
    """30 train / 5 val episodes and 2 epochs: enough to exercise every code path quickly."""
    s = {**splits, "train": splits["train"][:30], "val": splits["val"][:5]}
    cfg = {**CFG, "encoder": {**CFG["encoder"], "epochs": 2, "gate_epoch": 1}}
    return cfg, s


@pytest.fixture(scope="module")
def renderer():
    return GridWorld().renderer


# --- architecture (spec section 03-A) -----------------------------------------
def test_encoder_layer_shapes_match_spec():
    enc = Encoder(32)
    h = torch.zeros(2, 3, 40, 48)
    shapes = []
    for layer in enc.conv:
        h = layer(h)
        if isinstance(layer, torch.nn.ReLU):
            shapes.append(tuple(h.shape[1:]))
    assert shapes == [(16, 20, 24), (32, 10, 12), (64, 5, 6)]
    assert enc.fc.in_features == 1920 and enc.fc.out_features == 32


def test_uint8_and_float_inputs_agree():
    enc = Encoder(32)
    x = torch.randint(0, 256, (3, 3, 40, 48), dtype=torch.uint8)
    assert torch.allclose(enc(x), enc(x.float() / 255.0))


def test_decoder_output_shape_and_range():
    out = Decoder(32)(torch.randn(4, 32) * 5)
    assert out.shape == (4, 3, 40, 48)
    assert out.min() >= 0 and out.max() <= 1
    with pytest.raises(ValueError):
        Decoder(32, (3, 41, 48))


def test_standardize_round_trip():
    enc = Encoder(4)
    enc.z_mean.copy_(torch.tensor([1.0, -2.0, 0.5, 3.0]))
    enc.z_std.copy_(torch.tensor([2.0, 0.5, 1.0, 4.0]))
    z = torch.randn(5, 4)
    assert torch.allclose(enc.unstandardize(enc.standardize(z)), z, atol=1e-6)


# --- robot pixels, loss and decode check ---------------------------------------
def test_background_is_the_robotless_map(data, splits, renderer):
    sets = prepare_sets(data, {**splits, "train": splits["train"][:40]})
    expected = renderer._background.transpose(2, 0, 1)
    assert np.array_equal(sets["background"], expected)


def test_robot_mask_covers_exactly_the_robot(data, renderer):
    frames = torch.as_tensor(data["obs"][:200])
    bg = torch.as_tensor(np.ascontiguousarray(renderer._background.transpose(2, 0, 1)))
    mask = robot_mask(frames, bg)
    assert mask.shape == (200, 1, 40, 48)
    assert (mask.sum(dim=(1, 2, 3)) == 49).all()  # 7 x 7 interior, also on the goal cell


def test_recon_loss_weighting():
    target = torch.zeros(1, 3, 4, 4)
    recon = torch.zeros(1, 3, 4, 4)
    recon[..., 0, 0] = 1.0  # error only on one "robot" pixel
    mask = torch.zeros(1, 1, 4, 4, dtype=torch.bool)
    mask[..., 0, 0] = True
    plain = recon_loss(recon, target, mask, 1.0)
    weighted = recon_loss(recon, target, mask, 10.0)
    assert plain == pytest.approx(3 / 48)
    assert weighted == pytest.approx(30 / (25 * 3))  # weight 10 of total weight 15 + 10 = 25 per channel
    assert weighted > plain


def test_decode_check_on_true_frames(renderer):
    frames = np.stack([renderer.render(tuple(c)) for c in CELLS.cells]) / 255.0
    pred, margin = decoded_robot_cells(frames, CELLS, 8)
    assert np.array_equal(pred, np.arange(25))
    assert (margin[np.arange(25), np.arange(25)] > 0).all()
    empty = renderer._background.transpose(2, 0, 1)[None] / 255.0
    _, m = decoded_robot_cells(empty, CELLS, 8)
    assert (m < 0).all()  # no robot anywhere


def test_codebook_frames_one_per_cell(data, splits, renderer):
    sets = prepare_sets(data, splits)
    cb = codebook_frames(sets["train_x"], sets["train_y"], 25)
    for i, c in enumerate(CELLS.cells):
        assert np.array_equal(cb[i], renderer.render(tuple(c)))
    with pytest.raises(ValueError):
        codebook_frames(sets["train_x"][:1], sets["train_y"][:1], 25)


def test_mosaic_shape(renderer):
    frames = np.stack([renderer.render(tuple(c)) for c in CELLS.cells])
    img = decode_mosaic(frames, frames / 255.0, CELLS)
    assert img.dtype == np.uint8 and img.shape == (4 + 5 * 44, 4 + 6 * (98 + 4), 3)


# --- training loop ---------------------------------------------------------------
def test_training_is_reproducible(data, small):
    cfg, s = small
    sets = prepare_sets(data, s)
    a = train_attempt(cfg, sets, 1.0, abort_on_gate=False, verbose=False)
    b = train_attempt(cfg, sets, 1.0, abort_on_gate=False, verbose=False)
    for va, vb in zip(a["encoder"].state_dict().values(), b["encoder"].state_dict().values()):
        assert torch.equal(va, vb)


def test_train_fallback_freeze_stats_and_codebook(data, small, tmp_path):
    cfg, s = small
    cfg = {**cfg, "encoder": {**cfg["encoder"], "gate_probe_accuracy": 1.01}}  # force the gate to fail
    encoder, decoder, metrics, decoded = train(cfg, data, s, verbose=False)

    # Gate failed at epoch 1 -> retrained with robot pixels weighted 10x.
    assert [a["robot_weight"] for a in metrics["attempts"]] == [1.0, 10.0]
    assert metrics["attempts"][0]["aborted"] and not metrics["attempts"][1]["aborted"]
    assert metrics["robot_weight"] == 10.0 and not metrics["passed"]

    # Frozen, with stats from training latents only.
    assert not any(p.requires_grad for p in encoder.parameters())
    sets = prepare_sets(data, s)
    z = torch.as_tensor(encode(encoder, sets["train_x"]))
    assert torch.allclose(encoder.z_mean, z.mean(0), atol=1e-5)
    assert torch.allclose(encoder.z_std, z.std(0), atol=1e-5)
    assert metrics["codebook"].shape == (25, 32) and decoded.shape == (25, 3, 40, 48)

    # Checkpoints round-trip.
    cfg_out = {**cfg, "encoder": {**cfg["encoder"], "checkpoint": str(tmp_path / "e.pt"),
                                  "decoder_checkpoint": str(tmp_path / "d.pt")}}
    enc_path, dec_path = save_checkpoints(encoder, decoder, metrics, cfg_out)
    enc2, ckpt = load_encoder(enc_path)
    dec2 = load_decoder(dec_path)
    x = torch.as_tensor(sets["codebook_x"])
    assert torch.equal(enc2(x), encoder(x))
    assert torch.equal(ckpt["codebook"], torch.as_tensor(metrics["codebook"]))
    assert ckpt["codebook_cells"].tolist() == CELLS.cells.tolist()
    assert torch.equal(enc2.z_std, encoder.z_std)
    assert torch.allclose(dec2(enc2(x)), decoder(encoder(x)))
    assert not any(p.requires_grad for p in enc2.parameters())
