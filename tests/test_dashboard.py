"""Step 10 (replay dashboard) checks: any evaluation episode can be replayed step by step."""

import subprocess
import sys

import matplotlib

matplotlib.use("Agg")

import numpy as np  # noqa: E402
import pytest  # noqa: E402

from config import ROOT, load_config, resolve  # noqa: E402
from environment import GridWorld  # noqa: E402
from evaluation.navigation_test import run_seeds  # noqa: E402
from evaluation.runs import LADDER, NAVIGATION, build_runs, replay  # noqa: E402
from models import Decoder  # noqa: E402
from planning.mpc import run_episode  # noqa: E402
from planning.true_model import TrueModel  # noqa: E402
from tests.helpers import cell_frames, held_overrides, make_world  # noqa: E402
from visualization.dashboard import Dashboard, Replay  # noqa: E402

CFG = load_config()


@pytest.fixture(scope="module")
def runs():
    frames = cell_frames()
    return build_runs(CFG, TrueModel(), make_world(frames, held_overrides()), frames[1])


def test_every_run_label_is_available(runs):
    assert set(NAVIGATION) | set(LADDER) == set(runs)


@pytest.mark.parametrize("label", ["Oracle", "P0", "P1", "P2", "Random", "D2", "D3"])
def test_replay_reproduces_the_evaluation_episode(runs, label):
    run = runs[label]
    seeds = [0, 3]
    evaluated = run_seeds(run.model, run.planner, run.mctx, CFG, seeds)
    starts = GridWorld().map.start_cells()
    for k in (0, 7, 23, 24 + 5, 24 + 20):
        seed, start = seeds[k // 24], starts[k % 24]
        again = replay(run, CFG, seed, start)
        assert again.actions == evaluated[k].actions and again.path == evaluated[k].path


def test_recording_does_not_change_the_episode(runs):
    run = runs["P1"]
    env = GridWorld(terminate_on_goal=True)
    a = run_episode(env, run.model, run.planner, run.mctx, (0, 4), seed=11)
    b = run_episode(env, run.model, run.planner, run.mctx, (0, 4), seed=11, record=True)
    assert a.actions == b.actions and a.frames is None
    assert len(b.frames) == b.steps + 1
    assert np.array_equal(b.frames[0], env.renderer.render((0, 4)))
    assert all("extra" in p for p in b.plans) and all("extra" not in p for p in a.plans)


def test_recorded_costs_explain_the_choice(runs):
    for label in ("P0", "P1", "P2", "Oracle"):
        ep = replay(runs[label], CFG, 0, (0, 4))
        for p in ep.plans:
            costs = np.array(p["extra"]["first_action_costs"])
            assert costs.shape == (4,)
            assert costs[p["action"]] == pytest.approx(costs.min())
    oracle = replay(runs["Oracle"], CFG, 0, (0, 4))
    assert min(oracle.plans[0]["extra"]["first_action_costs"]) == 9.0


def test_unknown_first_move_has_no_known_path(runs):
    ep = replay(runs["P2"], CFG, 0, (0, 4))  # (0,4) UP is held out -> unknown
    assert np.isinf(ep.plans[0]["extra"]["first_action_costs"][0])


@pytest.mark.parametrize("label", ["P2", "P1", "Oracle", "Random", "D1"])
def test_dashboard_draws_every_step(runs, label):
    decoder = Decoder(32).eval()
    r = Replay(replay(runs[label], CFG, 1, (0, 1)), runs[label], decoder, eval_seed=1)
    dash = Dashboard(r)
    for t in range(r.n_states):
        dash.draw(t)
        assert dash.t == t
    dash.draw(999)
    assert dash.t == r.n_states - 1  # clamped
    if label in ("P2", "P1"):
        frame, _ = r.imagined[0][0]
        assert frame.shape == (40, 48, 3)  # decoded imagined frame
    import matplotlib.pyplot as plt
    plt.close(dash.fig)


def test_export_writes_one_png_per_step_and_a_gif(runs, tmp_path):
    r = Replay(replay(runs["P2"], CFG, 0, (3, 4)), runs["P2"], None, eval_seed=0)
    files = Dashboard(r).export(tmp_path)
    assert len(files) == r.n_states + 1
    assert files[-1].name == "replay.gif" and files[-1].stat().st_size > 1000


@pytest.mark.skipif(not all(resolve(CFG[k]["checkpoint"]).exists() for k in ("encoder", "predictor")),
                    reason="needs the trained encoder and predictor checkpoints")
def test_cli_export(tmp_path):
    run = subprocess.run([sys.executable, "-m", "visualization.dashboard", "--run", "P0", "--seed", "0",
                          "--start", "0,1", "--export", str(tmp_path)], cwd=ROOT, capture_output=True, text=True,
                         timeout=300)
    assert run.returncode == 0, run.stderr
    assert (tmp_path / "replay.gif").exists() and (tmp_path / "step_00.png").exists()
