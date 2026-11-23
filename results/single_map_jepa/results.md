# Mini-JEPA results

Regenerate with `python -m evaluation` (seed 0, planning seeds [0, 1, 2, 3, 4]). Fit = episode split (test episodes, trained pairs); generalization = held-out (state, action) pairs.

## World model (test split)

| One-step latent MSE | model | persistence (z_hat = z) |
|---|---|---|
| trained transitions | 0.00015 | 0.99694 |
| held-out (all) transitions | 1.39475 | 1.47041 |

| (cell, action) pairs | latent predictor | numerical baseline (step 3) |
|---|---|---|
| normal moves | 59/59 | 59/59 |
| collisions | 31/31 | 31/31 |
| held-out moves | 0/7 | 7/7 |
| held-out collisions | 2/3 | 2/3 |
| held-out (all) | 2/10 | 9/10 |

| Imagined steps | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| snap, trained-pair windows (n=248) | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| snap, all windows (n=820) | 92% | 86% | 80% | 76% | 71% | 66% | 62% | 57% | 53% | 50% |
| probe, trained-pair windows | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| probe, all windows | 92% | 86% | 80% | 75% | 71% | 65% | 61% | 56% | 53% | 49% |

Imagined graph: **88/100 edges correct** (trained 85/90, held-out 3/10), 15 unknown -> self-loops, 0 wrong but trusted. D(c) exact for **24/25** cells (over 0, under 0, unreachable 1).

## Navigation (5 seeds x 24 starts = 120 episodes each, learned model)

| | success | optimal | path ratio | collision rate | loop failures | timeouts |
|---|---|---|---|---|---|---|
| Oracle | 120/120 (100%) | 120/120 (100%) | 1.00 | 0.0% | 0 | 0 |
| P0 | 110/120 (92%) | 0/120 (0%) | 4.37 | 0.0% | 10 | 0 |
| P1 | 120/120 (100%) | 58/120 (48%) | 1.32 | 0.0% | 0 | 0 |
| P2 | 120/120 (100%) | 120/120 (100%) | 1.00 | 0.0% | 0 | 0 |
| Random | 13/120 (11%) | 7/120 (6%) | 1.65 | 33.1% | 107 | 0 |

Success by start distance (optimal path length):

| | d=1 | d=2 | d=3 | d=4 | d=5 | d=6 | d=7 | d=8 | d=9 |
|---|---|---|---|---|---|---|---|---|---|
| Oracle | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| P0 | 100% | 100% | 100% | 100% | 100% | 100% | 67% | 50% | 100% |
| P1 | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| P2 | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| Random | 40% | 27% | 25% | 0% | 0% | 0% | 0% | 0% | 0% |

## Diagnostic ladder (planner P2 on every rung except Oracle / Random)

| | dynamics | cost | success | optimal | path ratio | collision rate | loop failures | timeouts |
|---|---|---|---|---|---|---|---|---|
| Oracle | true | A* | 120/120 (100%) | 120/120 (100%) | 1.00 | 0.0% | 0 | 0 |
| D1 | true | true | 120/120 (100%) | 120/120 (100%) | 1.00 | 0.0% | 0 | 0 |
| D2 | true | learned | 120/120 (100%) | 120/120 (100%) | 1.00 | 0.0% | 0 | 0 |
| D3 | learned | true | 115/120 (96%) | 115/120 (96%) | 1.00 | 1.9% | 5 | 0 |
| Full | learned | learned | 120/120 (100%) | 120/120 (100%) | 1.00 | 0.0% | 0 | 0 |
| Random | - | - | 13/120 (11%) | 7/120 (6%) | 1.65 | 33.1% | 107 | 0 |

Reading:

- D1 = 100% optimal: the planner and control loop are correct.
- D2 matches D1: the learned cost D(c) costs nothing.
- D3 vs D1: the learned dynamics costs 4% success and 4% optimal episodes.
- Full (100% optimal) is no worse than the weaker of D2 / D3: no compounding.
- Random reaches the goal in 11% of episodes (lower bound); Oracle in 100%.

Plots: `prediction_horizons.png`, `success_by_distance.png`, `ladder.png`.
