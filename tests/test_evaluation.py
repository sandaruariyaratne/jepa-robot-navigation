"""Step 9 (evaluation + diagnostic ladder) checks."""

import subprocess
import sys

import numpy as np
import pytest
import yaml

from config import ROOT, load_config, resolve
from environment import GridMap, distances_to_goal
from evaluation.ladder import build_rungs, diagnose
from evaluation.navigation_test import Oracle, RandomPolicy, astar, by_distance, episode_seed, report, run_seeds
from evaluation.plots import plot_horizons, plot_ladder, plot_success_by_distance
from planning.mpc import prepare
from planning.true_model import TrueModel
from tests.helpers import cell_frames, held_overrides, make_world

CFG = load_config()
GRID = GridMap()


@pytest.fixture(scope="module")
def frames():
    return cell_frames()


@pytest.fixture(scope="module")
def true_model():
    return TrueModel()


# --- oracle and random ---------------------------------------------------------------
def test_astar_is_optimal_from_every_start():
    d = distances_to_goal(GRID)
    for start in GRID.start_cells():
        path = astar(GRID, start, GRID.goal, np.random.default_rng(0))
        assert len(path) == d[start[1], start[0]]
        pos = start
        for a in path:
            pos, collision = GRID.transition(pos, a)
            assert not collision
        assert pos == GRID.goal


def test_astar_ties_are_seeded():
    paths = {tuple(astar(GRID, (0, 4), GRID.goal, np.random.default_rng(s))) for s in range(30)}
    assert len(paths) > 1 and all(len(p) == 9 for p in paths)


def test_oracle_and_random_episodes(true_model, frames):
    ctx = prepare(true_model, frames[1])
    oracle = run_seeds(true_model, Oracle(), ctx, CFG, [0, 1])
    assert len(oracle) == 48 and all(e.success and e.steps == e.optimal for e in oracle)
    r1 = run_seeds(true_model, RandomPolicy(), ctx, CFG, [3])
    r2 = run_seeds(true_model, RandomPolicy(), ctx, CFG, [3])
    assert [e.actions for e in r1] == [e.actions for e in r2]
    assert sum(e.success for e in r1) < 24


def test_seed_zero_matches_step_8():
    from planning.mpc import run_all  # noqa: F401  (same seed formula)
    assert episode_seed(0, 5) == int(np.random.SeedSequence([0, 5]).generate_state(1)[0])


def test_by_distance_and_report(true_model, frames):
    eps = run_seeds(true_model, Oracle(), prepare(true_model, frames[1]), CFG, [0])
    bd = by_distance(eps)
    assert sum(v["total"] for v in bd.values()) == 24
    assert bd[9] == {"success": 1, "optimal": 1, "total": 1}  # only the reference start is 9 away
    assert report(eps)["success"] == 24


# --- ladder ------------------------------------------------------------------------------
def test_ladder_rungs_with_unknown_edges(true_model, frames):
    world = make_world(frames, held_overrides())
    rungs = build_rungs(true_model, world, frames[1])
    assert [r.label for r in rungs] == ["Oracle", "D1", "D2", "D3", "Full", "Random"]
    summaries = {r.label: report(run_seeds(r.model, r.planner, r.mctx, CFG, [0])) for r in rungs}
    for label in ("Oracle", "D1", "D2", "D3", "Full"):
        assert summaries[label]["optimal"] == 24, label
    lines = diagnose(summaries)
    assert lines[0].startswith("D1 = 100% optimal")
    assert "costs nothing" in lines[1] and "costs nothing" in lines[2]


def test_ladder_blames_the_broken_part(true_model, frames):
    # A confidently wrong edge breaks the learned cost D(c) and the learned dynamics.
    from tests.helpers import cell_id

    world = make_world(frames, {(cell_id(0, 4), 3): cell_id(4, 0)})
    rungs = {r.label: r for r in build_rungs(true_model, world, frames[1])}
    assert rungs["D2"].mctx.d_table[cell_id(0, 4)] == 2  # learned D(c) thinks the start is 2 away
    s = {k: report(run_seeds(r.model, r.planner, r.mctx, CFG, [0])) for k, r in rungs.items()}
    assert s["D1"]["optimal"] == 24
    assert s["D2"]["optimal"] < 24 or s["D3"]["optimal"] < 24 or s["Full"]["optimal"] < 24
    text = " ".join(diagnose(s))
    assert "costs" in text


def test_diagnose_flags_planner_bug():
    base = {"episodes": 120, "success": 120, "optimal": 120}
    s = {k: dict(base) for k in ("Oracle", "D1", "D2", "D3", "Full", "Random")}
    s["D1"] = {"episodes": 120, "success": 100, "optimal": 90}
    s["Full"] = {"episodes": 120, "success": 60, "optimal": 30}
    s["D2"] = {"episodes": 120, "success": 110, "optimal": 100}
    s["D3"] = {"episodes": 120, "success": 110, "optimal": 100}
    lines = diagnose(s)
    assert "bug" in lines[0] and "compound" in lines[3]


# --- plots and the one command -------------------------------------------------------
def test_plots_render(tmp_path):
    curve = {"n": 5, "snap_acc": [1.0, 0.9], "probe_acc": [1.0, 0.8], "mse": [1e-4, 1e-3],
             "mse_persistence": [1.0, 1.2]}
    bd = {1: {"success": 1, "optimal": 1, "total": 1}, 2: {"success": 0, "optimal": 0, "total": 1}}
    summ = {"episodes": 2, "success": 1, "optimal": 1, "by_distance": bd}
    ladder = {"rungs": [{"label": k, "dynamics": "true", "cost": "true"} for k in ("Oracle", "D1")],
              "summaries": {"Oracle": summ, "D1": summ}}
    for p in (plot_horizons({"trained": curve, "all": curve}, tmp_path / "h.png"),
              plot_success_by_distance({"Oracle": summ, "P2": summ}, tmp_path / "s.png"),
              plot_ladder(ladder, tmp_path / "l.png")):
        assert p.exists() and p.stat().st_size > 1000


@pytest.mark.skipif(not all(resolve(CFG[k]["checkpoint"]).exists() for k in ("encoder", "predictor")),
                    reason="needs the trained encoder and predictor checkpoints")
def test_one_command_regenerates_everything(tmp_path):
    cfg = yaml.safe_load((ROOT / "configs" / "single_map.yaml").read_text())
    cfg["evaluation"]["seeds"] = [0]
    cfg["evaluation"]["results_dir"] = str(tmp_path / "results")
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg))
    run = subprocess.run([sys.executable, "-m", "evaluation", "--config", str(cfg_path)], cwd=ROOT,
                         capture_output=True, text=True, timeout=300)
    assert run.returncode == 0, run.stderr
    out = tmp_path / "results"
    for name in ("results.md", "results.json", "prediction_horizons.png", "success_by_distance.png", "ladder.png"):
        assert (out / name).exists(), name
    md = (out / "results.md").read_text()
    assert "## Diagnostic ladder" in md and "| D3 | learned | true |" in md
