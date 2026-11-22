# Mini-JEPA evaluation report

A small action-conditioned latent world model on a 6 × 5 grid: a frozen CNN
encoder maps each RGB frame to a 32-D latent, a residual MLP predicts how an
action changes that latent, and planners search over imagined rollouts. Every
number below comes from `python main.py all` with seed 0 (config.yaml); the
full tables are in [results/results.md](results/results.md).

**Bottom line.** On the one fixed map it was trained on, the system navigates
perfectly: the primary planner (P2) reaches the goal by a shortest path in
120/120 episodes. That is a statement about **fit**. On the only real
**generalization** test, (state, action) pairs never seen in training, the
learned dynamics fail: 1 of 10 held-out pairs predicted correctly, against 9 of
10 for a plain MLP on coordinates. Navigation stays perfect only because the
model flags all 10 of those predictions as unknown and the map has enough
alternative shortest routes to avoid them.

## 1. Setup

| | |
|---|---|
| World | 6 × 5 grid, 5 fixed walls, fixed goal (5,0), 25 free cells, 4 actions; blocked moves stay in place |
| Observation | 3 × 40 × 48 RGB frame; only 25 distinct frames exist |
| Data | 200 episodes × 50 uniformly random actions = 10,000 transitions, random non-goal starts |
| Fit split | train / val / test = 160 / 20 / 20 **episodes** |
| Generalization split | 10 of the 100 (cell, action) pairs held out of all predictor training and model selection (7 moves, 3 bumps; at most one per cell) |
| Encoder | 3 stride-2 convs + linear → 32-D, trained as an autoencoder (pixel MSE), then frozen |
| Predictor | ẑ = z + f(z, a), f = MLP 36 → 128 → 128 → 32, rollout curriculum K = 1 → 2 → 4, checkpoint chosen by 5-step validation snap accuracy |
| Snap | nearest of the 25 codebook latents; **unknown** if farther than 3 × the median one-step error (0.0089) |
| Planners | P0: 1,024 five-step plans, final latent distance. P1: beam search 12 × 64, closest latent distance. P2: 64 three-step plans, min_k [k + D(snap(ẑ_k))], with D(c) from BFS on the imagined graph |

Why two splits: on a fixed map every (cell, action) pair recurs in every
episode, so test episodes contain the same transitions as training episodes.
The episode split therefore measures fit only. Held-out pairs are the one place
the model must predict something it has never seen.

## 2. Fit (test episodes, trained pairs)

| Measure | Result |
|---|---|
| Encoder gate: linear probe on validation latents | 100% (gate ≥ 99%) |
| Encoder gate: robot drawn in the right cell, 25 decodes | 25/25 |
| One-step latent MSE, model vs persistence (ẑ = z) | 0.00000 vs 1.206 |
| Snap accuracy, trained pairs (all 90) | 90/90 |
| Imagined rollouts on trained-pair windows, steps 1–10 | 100% at every step |
| Imagined graph, trained edges | 90/90 correct, none wrong |
| Imagined steps-to-goal D(c) vs true distance | exact for 25/25 cells |
| P2, 120 episodes | 120 success, 120 optimal, path ratio 1.00 |

The diagnostic ladder runs P2 with each part swapped for the truth. All four
model rungs are 100% optimal, so on this map neither the learned cost nor the
learned dynamics costs anything:

| Rung | Dynamics | Cost | Optimal episodes |
|---|---|---|---|
| Oracle (A*) | true | true | 120/120 |
| D1 | true | true D(c) | 120/120 |
| D2 | true | learned D(c) | 120/120 |
| D3 | learned | true D(c) | 120/120 |
| Full | learned | learned D(c) | 120/120 |
| Random policy | – | – | 7/120 (13 reach the goal) |

## 3. Generalization (held-out pairs)

| Held-out pairs (one step) | Latent predictor | Numerical baseline (x, y, a → next x, y) |
|---|---|---|
| moves | 0/7 | 7/7 |
| bumps | 1/3 | 2/3 |
| **all** | **1/10** | **9/10** |

- The latent predictor learned the 90 training transitions by heart; it did not
  learn "UP moves the robot one cell up" as a rule it can apply elsewhere.
  Several held-out moves are predicted as the *opposite* move. The numerical
  baseline, given coordinates, generalizes 9/10 (its one miss is an interior
  wall it has no way to know about).
- The encoder was trained only to reconstruct pixels, so its 25 latents carry
  no grid geometry for the predictor to exploit. Freezing it prevents collapse
  but does not provide useful structure, as the spec anticipated.
- Errors compound: over all test windows (which include held-out pairs) snap
  accuracy falls from 91% after one imagined step to 49% after ten. A linear
  position probe on the imagined latents tracks snapping within 1–2 points.
- **What saves planning is calibration, not generalization.** All 10 held-out
  predictions land 1.8–5.5 units from any codebook entry (threshold 0.0089), so
  all 10 are flagged unknown and become self-loops; none is trusted while
  wrong. Every affected cell still has another shortest route, so D(c) stays
  exact. A test with one injected confidently wrong edge shows the failure mode
  this avoids: D(reference start) drops from 9 to 2.

## 4. Planners

| Planner (learned model, 120 episodes) | Success | Optimal | Path ratio | Loop failures |
|---|---|---|---|---|
| P0 (latent distance, 5 steps) | 80 | 50 | 1.45 | 40 |
| P1 (latent distance, beam 12 × 64) | 115 | 65 | 1.32 | 5 |
| P2 (imagined steps-to-goal, 3 steps) | 120 | 120 | 1.00 | 0 |

Latent distance is a weak cost here: with the true model (one-hot latents) P0
and P1 are still only 9/24 and 15/24 optimal, because distance to the goal
latent says "at the goal or not", not "how far". P0 succeeds only within its
5-step horizon (100% up to distance 5, 0% from 7 on). Replays show P0 also
trusting plans that start with a held-out move, whose decoded rollouts lose the
robot entirely. The cost built from the imagined graph (P2) is what makes
planning reliable.

## 5. What these results do not show

- **Anything about other maps.** One layout, one goal, 25 distinct frames.
  Perfect navigation here is fit to this map. Unseen layouts were not tested.
- **That the model learned the dynamics.** It reproduces the transitions it was
  trained on; on new pairs it fails (1/10).
- **That navigation would survive a less redundant map.** P2 is optimal because
  every cell has a second shortest route around each unknown move. On a map
  where a held-out move is the only shortest route, paths would get longer,
  and where it is the only route at all, the goal would become unreachable.
- **Statistical strength.** One training seed; a single draw of 10 held-out
  pairs; navigation varies only the planner's tie-breaking seeds (5).
- **A strong encoder gate.** Any 25 distinct points in 32-D are linearly
  separable, so the ≥ 99% probe gate mostly rules out collapse; the 25 decodes
  are the stricter half.

## 6. Reproducing

```
python main.py all           # ~10 min on a laptop CPU; stops at the first failed gate
python main.py fingerprint   # hashes of every deterministic output
```

A clean copy (no data, checkpoints or results) re-run with `main.py all`
(9.4 min) produced fingerprints identical to the run reported here for all 13
outputs: data, splits, the four checkpoints' tensors, every metrics file and
the results table. Wall-clock planning times are the only fields excluded.

## 7. Next steps

In the order the build plan gives: joint JEPA training (EMA target encoder,
τ = 0.99, variance / covariance penalties), which is the direct attack on the
held-out failure because it lets prediction shape the latent space; then
random goals; many layouts with held-out layouts; a learned goal-distance head;
then moving obstacles, partial observability and stochastic dynamics.
