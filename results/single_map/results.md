# Mini-JEPA results

Regenerate with `python -m evaluation` (seed 0, planning seeds [0, 1, 2, 3, 4]). Fit = episode split (test episodes, trained pairs); generalization = held-out (state, action) pairs.

## World model (test split)

| One-step latent MSE | model | persistence (z_hat = z) |
|---|---|---|
| trained transitions | 0.00000 | 1.20554 |
| held-out (all) transitions | 1.52465 | 1.12769 |

| (cell, action) pairs | latent predictor | numerical baseline (step 3) |
|---|---|---|
| normal moves | 59/59 | 59/59 |
| collisions | 31/31 | 31/31 |
| held-out moves | 0/7 | 7/7 |
| held-out collisions | 1/3 | 2/3 |
| held-out (all) | 1/10 | 9/10 |

| Imagined steps | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| snap, trained-pair windows (n=248) | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| snap, all windows (n=820) | 91% | 83% | 77% | 72% | 67% | 62% | 58% | 55% | 52% | 49% |
| probe, trained-pair windows | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| probe, all windows | 91% | 84% | 78% | 73% | 68% | 63% | 60% | 57% | 53% | 50% |

Imagined graph: **93/100 edges correct** (trained 90/90, held-out 3/10), 10 unknown -> self-loops, 0 wrong but trusted. D(c) exact for **25/25** cells (over 0, under 0, unreachable 0).

## Navigation (5 seeds x 24 starts = 120 episodes each, learned model)

| | success | optimal | path ratio | collision rate | loop failures | timeouts |
|---|---|---|---|---|---|---|
| Oracle | 120/120 (100%) | 120/120 (100%) | 1.00 | 0.0% | 0 | 0 |
| P0 | 80/120 (67%) | 50/120 (42%) | 1.45 | 0.0% | 40 | 0 |
| P1 | 115/120 (96%) | 65/120 (54%) | 1.32 | 0.0% | 5 | 0 |
| P2 | 120/120 (100%) | 120/120 (100%) | 1.00 | 0.0% | 0 | 0 |
| Random | 13/120 (11%) | 7/120 (6%) | 1.65 | 33.1% | 107 | 0 |

Success by start distance (optimal path length):

| | d=1 | d=2 | d=3 | d=4 | d=5 | d=6 | d=7 | d=8 | d=9 |
|---|---|---|---|---|---|---|---|---|---|
| Oracle | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| P0 | 100% | 100% | 100% | 100% | 100% | 33% | 0% | 0% | 0% |
| P1 | 100% | 100% | 100% | 100% | 100% | 100% | 67% | 100% | 100% |
| P2 | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| Random | 40% | 27% | 25% | 0% | 0% | 0% | 0% | 0% | 0% |

## Diagnostic ladder (planner P2 on every rung except Oracle / Random)

| | dynamics | cost | success | optimal | path ratio | collision rate | loop failures | timeouts |
|---|---|---|---|---|---|---|---|---|
| Oracle | true | A* | 120/120 (100%) | 120/120 (100%) | 1.00 | 0.0% | 0 | 0 |
| D1 | true | true | 120/120 (100%) | 120/120 (100%) | 1.00 | 0.0% | 0 | 0 |
| D2 | true | learned | 120/120 (100%) | 120/120 (100%) | 1.00 | 0.0% | 0 | 0 |
| D3 | learned | true | 120/120 (100%) | 120/120 (100%) | 1.00 | 0.0% | 0 | 0 |
| Full | learned | learned | 120/120 (100%) | 120/120 (100%) | 1.00 | 0.0% | 0 | 0 |
| Random | - | - | 13/120 (11%) | 7/120 (6%) | 1.65 | 33.1% | 107 | 0 |

Reading:

- D1 = 100% optimal: the planner and control loop are correct.
- D2 matches D1: the learned cost D(c) costs nothing.
- D3 matches D1: the learned dynamics costs nothing.
- Full (100% optimal) is no worse than the weaker of D2 / D3: no compounding.
- Random reaches the goal in 11% of episodes (lower bound); Oracle in 100%.

Plots: `prediction_horizons.png`, `success_by_distance.png`, `ladder.png`.
