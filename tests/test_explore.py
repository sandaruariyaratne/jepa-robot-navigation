"""Planning without privileged pictures (multimap/explore.py): growth, experience, graph planner, episodes."""

import numpy as np
import pytest
import torch

from config import ROOT, load_config
from environment import GridWorld
from evaluation.probes import CellIndex
from models import Encoder, Predictor
from multimap.explore import GraphP2, grow, graph_map, run, with_experience, _frontier
from multimap.maps import generate_maps
from planning.imagination import WorldModel
from planning.latent_graph import build_graph, goal_entry, steps_to_goal
from planning.planner import P2, PlanContext

CFG = load_config(ROOT / "config_multimap_jepa.yaml")


class Shift(torch.nn.Module):
    """Fake predictor: z + shift[action]."""

    n_actions = 4

    def __init__(self, shift):
        super().__init__()
        self.shift = torch.as_tensor(shift, dtype=torch.float32)

    def forward(self, z, a):
        return z + self.shift[a]


@pytest.fixture(scope="module")
def setup():
    grid = generate_maps(5, 3)[2]
    torch.manual_seed(0)
    enc, pred = Encoder(8).freeze(), Predictor(8, 4, [16], 0.5).eval()
    env = GridWorld(grid, terminate_on_goal=True)
    cells = CellIndex(grid).cells
    with torch.no_grad():
        cb = enc.standardize(enc(torch.as_tensor(np.stack([env.render((int(x), int(y))) for x, y in cells]))))
    return grid, enc, pred, env, cb


def test_growth_stops_when_every_move_is_blocked():
    anchors = torch.tensor([[0.0, 0.0], [10.0, 0.0]])
    nodes, overflow = grow(None, Shift(np.zeros((4, 2))), anchors, threshold=1.0)
    assert torch.equal(nodes, anchors) and not overflow


def test_growth_adds_imagined_nodes_and_respects_the_cap():
    anchors = torch.tensor([[0.0, 0.0]])
    right_only = np.array([[0, 0], [0, 0], [0, 0], [5.0, 0]])           # only "right" moves
    nodes, overflow = grow(None, Shift(right_only), anchors, threshold=1.0, max_nodes=6)
    assert len(nodes) == 6 and overflow
    assert torch.allclose(nodes[:, 0], torch.arange(6) * 5.0)           # a chain, anchors first


def test_experience_overrides_imagined_edges(setup):
    grid, enc, pred, env, cb = setup
    world = WorldModel(enc, pred, cb, 1e-6, 1.0)                        # every move unknown -> self-loops
    goal, _ = goal_entry(world, env.render(grid.goal))
    m = graph_map(world, len(cb), goal)
    assert (m.d[np.arange(len(cb)) != goal] < 0).all()
    other = (goal + 1) % len(cb)
    m2 = with_experience(m, {(other, 0): goal})
    assert m2.next[other, 0] == goal and m2.known[other, 0] and m2.d[other] == 1
    assert m.next[other, 0] == other                                    # the original is untouched


def test_frontier_distances(setup):
    grid, enc, pred, env, cb = setup
    world = WorldModel(enc, pred, cb, 1e6, 1.0)
    m = _frontier(graph_map(world, len(cb) - 3, 0))                     # last 3 entries count as imagined
    assert (m.d_frontier[len(cb) - 3:] == 0).all() and (m.d_frontier[: len(cb) - 3] != 0).all()


def test_graph_planner_equals_snapped_p2_from_a_node(setup):
    grid, enc, pred, env, cb = setup
    world = WorldModel(enc, pred, cb, 0.5, 3.0)
    goal, _ = goal_entry(world, env.render(grid.goal))
    m = graph_map(world, len(cb), goal)
    d = steps_to_goal(build_graph(world), goal)
    z_goal = world.encode(env.render(grid.goal))
    for node in range(len(cb)):
        ctx = PlanContext(z_goal, d, {node: 1}, 0.5, np.random.default_rng(7))
        want = P2(3, snap_each_step=True).plan(world, cb[node], ctx)
        got, how = GraphP2(3).plan(m, node, z_goal, {node: 1}, 0.5, np.random.default_rng(7))
        if not want.note:
            assert got == want.action and how == "goal"


@pytest.mark.parametrize("mode", ["privileged", "imagine", "explore"])
def test_episodes_run(setup, mode):
    grid, enc, pred, env, cb = setup
    e = run(mode, env, enc, pred, env.render(grid.goal), grid.start_cells()[0], 0, CFG, 0.5, cb)
    assert set(e) >= {"success", "steps", "optimal", "loop", "rebuilds", "first_map"}
    assert 1 <= e["steps"] <= CFG["planning"]["max_actions"]
    if mode != "explore":
        assert e["rebuilds"] == 0
    if mode != "privileged":
        assert e["first_map"].n_anchors == 2
