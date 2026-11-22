"""Step 7 (imagination + latent graph) checks.

Uses a small synthetic world model: an untrained encoder (its 25 latents are
the codebook) and a predictor that looks up the true next cell, except for
chosen pairs that are pushed far away (-> unknown) or redirected (-> wrong).
"""

import numpy as np
import pytest
import torch

import environment
import environment.bfs
import environment.grid_world
import environment.renderer
from environment import REFERENCE_START, distances_to_goal
from models import Encoder, Predictor
from planning import imagination as imagination_module
from planning.imagination import WorldModel, all_action_sequences
from planning.latent_graph import UNREACHABLE, LatentGraph, build_graph, evaluate, goal_entry, steps_to_goal
from tests.helpers import CELLS, GRID, HELD, TRUE_NEXT, cell_frames, held_overrides, make_world


@pytest.fixture(scope="module")
def frames():
    return cell_frames()


# --- rollouts ----------------------------------------------------------------------
def test_all_action_sequences():
    s = all_action_sequences(3)
    assert s.shape == (64, 3)
    assert len({tuple(r) for r in s.tolist()}) == 64
    assert s[0].tolist() == [0, 0, 0] and s[-1].tolist() == [3, 3, 3]
    assert all_action_sequences(5).shape == (1024, 5)


def test_imagine_is_batched_rollout():
    torch.manual_seed(0)
    p = Predictor(8, 4, (16,), 1.0)
    world = WorldModel(Encoder(8), p, torch.randn(25, 8), 0.01)
    z0 = torch.randn(3, 8)
    seqs = all_action_sequences(2)
    out = world.imagine(z0, seqs)
    assert out.shape == (3, 16, 2, 8)
    assert torch.allclose(out[2, 7], p.rollout(z0[2:3], seqs[7:8])[0])
    assert world.imagine(z0[0], seqs).shape == (16, 2, 8)


def test_imagination_module_does_not_import_the_simulator():
    src = open(imagination_module.__file__).read()
    assert "environment" not in src.replace("`environment`", "")
    assert not any(v is environment for v in vars(imagination_module).values())


def test_rollouts_make_no_simulator_calls(frames, monkeypatch):
    world = make_world(frames)

    def forbidden(*args, **kwargs):
        raise AssertionError("simulator called during imagination")

    for mod, names in (
        (environment.grid_world.GridMap, ["transition", "is_free", "in_bounds", "free_cells"]),
        (environment.grid_world.GridWorld, ["step", "reset", "render", "goal_obs"]),
        (environment.renderer.Renderer, ["render"]),
    ):
        for name in names:
            monkeypatch.setattr(mod, name, forbidden)
    for mod in (environment.bfs, environment):
        monkeypatch.setattr(mod, "distances_to_goal", forbidden)
        monkeypatch.setattr(mod, "shortest_path", forbidden)

    start_frame, goal_frame = frames[0][int(CELLS.ids(np.array(REFERENCE_START)))], frames[1]
    z0 = world.encode(start_frame)
    imagined = world.imagine(z0, all_action_sequences(5))  # all 1,024 five-step plans
    snapped = world.snap(imagined)
    graph = build_graph(world)
    goal, known = goal_entry(world, goal_frame)
    d = steps_to_goal(graph, goal)
    assert imagined.shape == (1024, 5, 32) and snapped.known.all()
    assert known and goal == 5 and d[20] == 9  # reference start is 9 steps out


# --- graph and D(c) ----------------------------------------------------------------------
def test_exact_model_recovers_true_graph_and_distances(frames):
    world = make_world(frames)
    graph = build_graph(world)
    assert np.array_equal(graph.next, TRUE_NEXT) and graph.known.all()
    ev = evaluate(graph, steps_to_goal(graph, 5), HELD)
    assert ev["edges"]["all"]["correct"] == 100
    assert ev["d_exact"] == 25


def test_unknown_moves_become_self_loops(frames):
    world = make_world(frames, held_overrides())
    graph = build_graph(world)
    ev = evaluate(graph, steps_to_goal(graph, 5), HELD)
    e = ev["edges"]
    assert e["trained"]["correct"] == 90 and e["held-out"]["unknown"] == 10 and e["all"]["wrong_known"] == 0
    assert e["held-out"]["correct"] == 3  # the three held-out collisions: a self-loop is the truth
    for x, y, a in HELD:
        i = int(CELLS.ids(np.array([x, y])))
        assert graph.next[i, a] == i and not graph.known[i, a]
    assert ev["d_exact"] == 25  # every cell keeps another optimal route


def test_confidently_wrong_edge_shortcuts_distances(frames):
    start = int(CELLS.ids(np.array(REFERENCE_START)))
    world = make_world(frames, {(start, 3): int(CELLS.ids(np.array([4, 0])))})  # RIGHT "teleports" next to goal
    graph = build_graph(world)
    ev = evaluate(graph, steps_to_goal(graph, 5), HELD)
    assert ev["edges"]["all"]["wrong_known"] == 1
    assert ev["d_imagined"][start] == 2 and ev["d_true"][start] == 9
    assert ev["d_under"] >= 1


def test_graph_png(frames, tmp_path):
    import pygame

    from planning.graph_view import render_all

    start = int(CELLS.ids(np.array(REFERENCE_START)))
    overrides = {**held_overrides(), (start, 3): int(CELLS.ids(np.array([4, 0])))}  # plus one wrong edge
    world = make_world(frames, overrides)
    graph = build_graph(world)
    ev = evaluate(graph, steps_to_goal(graph, 5), HELD)
    metrics = {"next": graph.next.tolist(), "known": graph.known.tolist(), **ev}
    layered, on_grid = render_all(metrics, HELD, tmp_path)
    assert pygame.image.load(str(on_grid)).get_size() == (760, 760)
    w, h = pygame.image.load(str(layered)).get_size()
    assert w > 1000 and h > 400


def test_steps_to_goal_bfs():
    # chain 0 -> 1 -> 2 (goal), 3 only self-loops
    nxt = np.array([[1, 0], [2, 1], [2, 2], [3, 3]])
    g = LatentGraph(nxt, nxt, np.ones_like(nxt, dtype=bool), np.zeros(nxt.shape))
    assert steps_to_goal(g, 2).tolist() == [2, 1, 0, UNREACHABLE]


def test_distance_table_shape_matches_oracle():
    d = distances_to_goal(GRID)
    assert d[4, 0] == 9  # sanity link between oracle grid indexing and cell ids used above


def test_world_model_from_checkpoints(tmp_path, frames):
    world = make_world(frames)
    pred = Predictor(32, 4, (16,), 1e-3)
    torch.save({"state_dict": world.encoder.state_dict(), "latent_dim": 32, "input_shape": [3, 40, 48],
                "codebook": world.encoder.unstandardize(world.codebook)}, tmp_path / "e.pt")
    torch.save({"state_dict": pred.state_dict(), "latent_dim": 32, "n_actions": 4, "hidden": [16],
                "median_one_step_error": 0.02}, tmp_path / "p.pt")
    loaded = WorldModel.from_checkpoints(tmp_path / "e.pt", tmp_path / "p.pt", unknown_factor=3.0)
    assert loaded.unknown_threshold == pytest.approx(0.06)
    assert torch.allclose(loaded.codebook, world.codebook, atol=1e-5)
    assert torch.allclose(loaded.encode(frames[0][:3]), world.encode(frames[0][:3]), atol=1e-5)
