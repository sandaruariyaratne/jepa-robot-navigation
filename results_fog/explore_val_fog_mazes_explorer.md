# Planning without privileged pictures: validation mazes (10 x 10, fog)

50 maps, 10 random free start cells per map, seeds as configured. Snapped P2, threshold 6.93 (same / new node and unknown rule), at most 250 nodes. Budget: 300 moves, no loop rule.

| | Picture of every cell (as before) | A: imagine from start + goal pictures | B: imagine, then correct while walking | Oracle explorer (true walls once seen) |
|---|---|---|---|---|
| navigation success | 738/1000 (73.8%) | 98/1000 (9.8%) | 217/1000 (21.7%) | 1000/1000 (100.0%) |
| shortest path | 659/1000 (65.9%) | 43/1000 (4.3%) | 55/1000 (5.5%) | 332/1000 (33.2%) |
| loop failures | 0 | 0 | 0 | 0 |
| extra moves per successful episode | 6.57 | 62.08 | 57.45 | 9.51 |
| collisions per action | 19.48% | 75.66% | 22.18% | 0.00% |
| map rebuilds per episode | 0.00 | 0.00 | 22.96 | 0.00 |
| plans heading for unexplored cells (no route seen) | 0.00% | 0.00% | 7.61% | 0.00% |
| plans with nothing known (latent fallback) | 82.25% | 84.40% | 92.16% | 0.00% |

Imagined map before the first move (one per start cell; A and B start identically):

| | value |
|---|---|
| maps exactly right (one node per cell, every edge right) | 0/500 (0.0%) |
| nodes / true cells | 5.7 / 71.3 |
| cells found | 2557/35670 (7.2%) |
| duplicate nodes (a cell imagined twice) | 2 |
| spurious nodes (match no real cell) | 288 |
| edges right (nodes matching a real cell) | 6972/10236 (68.1%) |
| steps-to-goal from the start exact | 15/500 (3.0%) |
| goal unreachable from the start in imagination | 474 |
| growth hit the node cap | 0 |

By shortest-path length (success / shortest path):

| length | episodes | privileged | imagine | explore | oracle |
|---|---|---|---|---|---|
| 1 | 16 | 100% / 100% | 100% / 100% | 100% / 100% | 100% / 100% |
| 2 | 24 | 100% / 100% | 67% / 54% | 96% / 79% | 100% / 100% |
| 3 | 24 | 100% / 100% | 50% / 17% | 79% / 29% | 100% / 100% |
| 4 | 28 | 93% / 93% | 29% / 7% | 68% / 7% | 100% / 86% |
| 5 | 30 | 100% / 93% | 30% / 17% | 63% / 20% | 100% / 93% |
| 6 | 38 | 89% / 87% | 26% / 0% | 63% / 11% | 100% / 95% |
| 7 | 20 | 80% / 70% | 20% / 10% | 60% / 5% | 100% / 90% |
| 8 | 42 | 76% / 71% | 10% / 2% | 62% / 0% | 100% / 90% |
| 9 | 36 | 78% / 72% | 6% / 0% | 42% / 0% | 100% / 50% |
| 10 | 20 | 80% / 80% | 5% / 0% | 40% / 0% | 100% / 80% |
| 11 | 30 | 73% / 53% | 20% / 0% | 27% / 0% | 100% / 47% |
| 12 | 34 | 74% / 59% | 0% / 0% | 9% / 0% | 100% / 35% |
| 13 | 28 | 71% / 71% | 11% / 0% | 14% / 0% | 100% / 50% |
| 14 | 20 | 80% / 60% | 0% / 0% | 30% / 0% | 100% / 50% |
| 15 | 42 | 83% / 76% | 0% / 0% | 7% / 0% | 100% / 29% |
| 16 | 46 | 61% / 52% | 4% / 0% | 2% / 0% | 100% / 13% |
| 17 | 40 | 65% / 60% | 2% / 0% | 10% / 0% | 100% / 10% |
| 18 | 38 | 68% / 47% | 3% / 0% | 5% / 0% | 100% / 5% |
| 19 | 50 | 84% / 68% | 0% / 0% | 2% / 0% | 100% / 8% |
| 20 | 70 | 59% / 54% | 0% / 0% | 1% / 0% | 100% / 6% |
| 21 | 26 | 50% / 38% | 0% / 0% | 4% / 0% | 100% / 8% |
| 22 | 56 | 64% / 57% | 2% / 0% | 0% / 0% | 100% / 0% |
| 23 | 46 | 76% / 65% | 2% / 0% | 2% / 0% | 100% / 0% |
| 24 | 34 | 71% / 65% | 0% / 0% | 0% / 0% | 100% / 0% |
| 25 | 54 | 72% / 63% | 2% / 0% | 0% / 0% | 100% / 0% |
| 26 | 20 | 40% / 20% | 0% / 0% | 0% / 0% | 100% / 10% |
| 27 | 26 | 69% / 58% | 0% / 0% | 0% / 0% | 100% / 0% |
| 28 | 18 | 78% / 78% | 0% / 0% | 6% / 0% | 100% / 0% |
| 29 | 10 | 60% / 60% | 0% / 0% | 0% / 0% | 100% / 20% |
| 30 | 14 | 43% / 43% | 0% / 0% | 0% / 0% | 100% / 0% |
| 31 | 8 | 50% / 50% | 0% / 0% | 0% / 0% | 100% / 0% |
| 32 | 6 | 100% / 100% | 0% / 0% | 0% / 0% | 100% / 33% |
| 33 | 4 | 50% / 25% | 0% / 0% | 0% / 0% | 100% / 0% |
| 34 | 2 | 0% / 0% | 0% / 0% | 0% / 0% | 100% / 0% |
