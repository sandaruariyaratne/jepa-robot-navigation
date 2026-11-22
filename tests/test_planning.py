"""Step 8 (planners + MPC loop) checks."""

import numpy as np
import pytest
import torch

from config import load_config
from environment import DOWN, RIGHT, UP, GridWorld, distances_to_goal
from planning.latent_graph import build_graph, steps_to_goal
from planning.mpc import Episode, done_checks, prepare, run_all, run_episode, summarize
from planning.planner import P0, P1, P2, Plan, PlanContext, _entries, _pick, make_planners
from planning.true_model import TrueModel
from tests.helpers import CELLS, GRID, TRUE_NEXT, cell_frames, cell_id, held_overrides, make_world

CFG = load_config()
P = CFG["planning"]


@pytest.fixture(scope="module")
def frames():
    return cell_frames()


@pytest.fixture(scope="module")
def true_model():
    return TrueModel()


# --- the true simulator as a model ---------------------------------------------------
def test_true_model_matches_simulator(true_model, frames):
    z = true_model.encode(frames[0])
    assert torch.equal(z, torch.eye(25))
    for a in range(4):
        nxt = true_model.step(z, torch.full((25,), a))
        assert nxt.argmax(-1).tolist() == TRUE_NEXT[:, a].tolist()
    s = true_model.snap(z)
    assert s.known.all() and s.index.tolist() == list(range(25))


def test_true_model_graph_gives_true_distances(true_model, frames):
    d = steps_to_goal(build_graph(true_model), cell_id(5, 0))
    truth = distances_to_goal(GRID)
    assert d.tolist() == [int(truth[y, x]) for x, y in CELLS.cells]


# --- done-when ------------------------------------------------------------------------
def test_p2_with_true_model_is_optimal_from_all_24_starts(true_model, frames):
    eps = run_all(true_model, [P2(3)], CFG, frames[1])["P2"]
    assert len(eps) == 24
    assert all(e.success and e.steps == e.optimal for e in eps)
    assert done_checks({"true": {"P2": eps}}) ["P2 with the true simulator reaches the goal optimally from all 24 starts"]


def test_every_planner_runs_full_episodes(true_model, frames):
    world = make_world(frames, held_overrides())
    for model in (true_model, world):
        results = run_all(model, make_planners(CFG), CFG, frames[1])
        assert set(results) == {"P0", "P1", "P2"}
        for eps in results.values():
            assert len(eps) == 24
            for e in eps:
                assert e.steps > 0 and len(e.path) == e.steps + 1 and len(e.plans) == e.steps
                assert e.success or e.loop_failure or e.timeout
                assert e.steps <= P["max_actions"]


def test_p2_routes_around_unknown_moves(frames):
    """Held-out edges unknown -> P2 never counts paths through them, yet stays optimal (D is exact here)."""
    world = make_world(frames, held_overrides())
    eps = run_all(world, [P2(3)], CFG, frames[1])["P2"]
    assert all(e.success and e.steps == e.optimal for e in eps)


def test_unknown_step_poisons_the_rest_of_the_sequence(frames):
    # (4,0) RIGHT is the only 1-step route to the goal; make it unknown.
    world = make_world(frames, {(cell_id(4, 0), RIGHT): "far"})
    mctx = prepare(world, frames[1])
    ep = run_episode(GridWorld(terminate_on_goal=True), world, P2(3), mctx, (4, 0), seed=0)
    assert ep.success and ep.actions[0] != RIGHT and ep.steps == 3  # around via (4,1) -> (5,1) -> (5,0)
    # After the unknown first step, later steps snap to real entries again but must stay untrusted.
    z = world.encode(frames[0][cell_id(4, 0)])
    traj = world.imagine(z, torch.tensor([[RIGHT, DOWN, UP]]))[0]
    assert world.snap(traj).known.tolist() == [False, True, True]
    assert _entries(world, traj) == [-1, -1, -1]


# --- loop mechanics --------------------------------------------------------------------
class Fixed:
    """A planner that always returns the same action."""

    def __init__(self, action):
        self.name, self.action = "fixed", action

    def plan(self, model, z, ctx):
        return Plan(self.action, [self.action], 0.0, [], 1)


def test_third_visit_is_a_loop_failure(true_model, frames):
    mctx = prepare(true_model, frames[1])
    ep = run_episode(GridWorld(terminate_on_goal=True), true_model, Fixed(UP), mctx, (0, 0), seed=0)
    assert ep.loop_failure and not ep.success and ep.steps == 2 and ep.collisions == 2


def test_timeout(true_model, frames):
    mctx = prepare(true_model, frames[1])
    ep = run_episode(GridWorld(terminate_on_goal=True), true_model, Fixed(DOWN), mctx, (0, 0), seed=0,
                     max_actions=2)
    assert ep.timeout and ep.steps == 2 and ep.path == [(0, 0), (0, 1), (0, 2)]


def test_revisit_penalty_discourages_bumping(true_model, frames):
    mctx = prepare(true_model, frames[1])
    z = true_model.encode(frames[0][cell_id(0, 0)])
    here = cell_id(0, 0)
    with_pen = PlanContext(mctx.z_goal, mctx.d_table, {here: 1}, 0.5, np.random.default_rng(0))
    # From (0,0) the optimal move is RIGHT; UP / LEFT bump in place and must cost at least 0.5 more.
    plan = P2(3).plan(true_model, z, with_pen)
    assert plan.action == RIGHT and plan.cost == 5.0


def test_seeded_tie_breaks_are_reproducible():
    costs = np.array([1.0, 0.0, 0.0, 0.0, 2.0])
    picks = {_pick(costs, np.random.default_rng(s)) for s in range(20)}
    assert picks <= {1, 2, 3} and len(picks) > 1
    assert _pick(costs, np.random.default_rng(7)) == _pick(costs, np.random.default_rng(7))
    assert _pick(np.array([np.inf, np.inf]), np.random.default_rng(0)) in (0, 1)


def test_same_seed_same_episode(frames):
    world = make_world(frames, held_overrides())
    a = run_all(world, [P1(12, 64)], CFG, frames[1])["P1"]
    b = run_all(world, [P1(12, 64)], CFG, frames[1])["P1"]
    assert [e.actions for e in a] == [e.actions for e in b]


# --- planner internals -----------------------------------------------------------------
def test_planner_search_sizes(true_model, frames):
    mctx = prepare(true_model, frames[1])
    ctx = PlanContext(mctx.z_goal, mctx.d_table, {}, 0.5, np.random.default_rng(0))
    z = true_model.encode(frames[0][cell_id(0, 4)])
    assert P0(5).plan(true_model, z, ctx).n_candidates == 1024
    assert P2(3).plan(true_model, z, ctx).n_candidates == 64
    p1 = P1(12, 64).plan(true_model, z, ctx)
    assert p1.n_candidates == 4 + 16 + 64 + 256 * 9  # beam capped at 64
    assert len(p1.sequence) == 12


def test_p0_reaches_goal_when_within_horizon(true_model, frames):
    mctx = prepare(true_model, frames[1])
    for start in [(4, 0), (3, 0), (5, 2)]:
        ep = run_episode(GridWorld(terminate_on_goal=True), true_model, P0(5), mctx, start, seed=0)
        assert ep.success


def test_summary_fields():
    e = Episode("P2", (0, 4), 0, True, 9, 9, 0, False, False, [(0, 4)] * 10, [0] * 9,
                [{"ms": 1.0}] * 9)
    s = summarize([e])
    assert s["success"] == 1 and s["optimal"] == 1 and s["mean_path_ratio"] == 1.0
