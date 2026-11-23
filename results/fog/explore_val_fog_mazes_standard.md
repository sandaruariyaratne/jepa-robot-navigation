# Planning without privileged pictures: validation mazes (10 x 10, fog)

50 maps, 10 random free start cells per map, seeds as configured. Snapped P2, threshold 6.93 (same / new node and unknown rule), at most 250 nodes. Budget: 100 moves, third visit to a cell = loop failure.

| | Picture of every cell (as before) | A: imagine from start + goal pictures | B: imagine, then correct while walking | Oracle explorer (true walls once seen) |
|---|---|---|---|---|
| navigation success | 688/1000 (68.8%) | 46/1000 (4.6%) | 80/1000 (8.0%) | 806/1000 (80.6%) |
| shortest path | 659/1000 (65.9%) | 43/1000 (4.3%) | 55/1000 (5.5%) | 332/1000 (33.2%) |
| loop failures | 312 | 954 | 920 | 194 |
| extra moves per successful episode | 0.10 | 0.17 | 2.52 | 6.52 |
| collisions per action | 3.63% | 27.30% | 8.42% | 0.00% |
| map rebuilds per episode | 0.00 | 0.00 | 6.50 | 0.00 |
| plans heading for unexplored cells (no route seen) | 0.00% | 0.00% | 65.44% | 0.00% |
| plans with nothing known (latent fallback) | 24.44% | 95.56% | 32.36% | 0.00% |

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
| 2 | 24 | 100% / 100% | 54% / 54% | 79% / 79% | 100% / 100% |
| 3 | 24 | 100% / 100% | 21% / 17% | 42% / 29% | 100% / 100% |
| 4 | 28 | 93% / 93% | 11% / 7% | 21% / 7% | 100% / 86% |
| 5 | 30 | 93% / 93% | 17% / 17% | 27% / 20% | 100% / 93% |
| 6 | 38 | 89% / 87% | 0% / 0% | 16% / 11% | 100% / 95% |
| 7 | 20 | 80% / 70% | 10% / 10% | 20% / 5% | 100% / 90% |
| 8 | 42 | 71% / 71% | 5% / 2% | 2% / 0% | 100% / 90% |
| 9 | 36 | 72% / 72% | 0% / 0% | 8% / 0% | 94% / 50% |
| 10 | 20 | 80% / 80% | 0% / 0% | 20% / 0% | 100% / 80% |
| 11 | 30 | 67% / 53% | 0% / 0% | 3% / 0% | 93% / 47% |
| 12 | 34 | 65% / 59% | 0% / 0% | 0% / 0% | 94% / 35% |
| 13 | 28 | 71% / 71% | 0% / 0% | 4% / 0% | 86% / 50% |
| 14 | 20 | 70% / 60% | 0% / 0% | 5% / 0% | 100% / 50% |
| 15 | 42 | 76% / 76% | 0% / 0% | 0% / 0% | 71% / 29% |
| 16 | 46 | 59% / 52% | 0% / 0% | 0% / 0% | 87% / 13% |
| 17 | 40 | 65% / 60% | 0% / 0% | 0% / 0% | 80% / 10% |
| 18 | 38 | 55% / 47% | 0% / 0% | 0% / 0% | 53% / 5% |
| 19 | 50 | 76% / 68% | 0% / 0% | 0% / 0% | 72% / 8% |
| 20 | 70 | 57% / 54% | 0% / 0% | 0% / 0% | 80% / 6% |
| 21 | 26 | 46% / 38% | 0% / 0% | 0% / 0% | 62% / 8% |
| 22 | 56 | 61% / 57% | 0% / 0% | 0% / 0% | 68% / 0% |
| 23 | 46 | 65% / 65% | 0% / 0% | 0% / 0% | 65% / 0% |
| 24 | 34 | 65% / 65% | 0% / 0% | 0% / 0% | 59% / 0% |
| 25 | 54 | 63% / 63% | 0% / 0% | 0% / 0% | 59% / 0% |
| 26 | 20 | 20% / 20% | 0% / 0% | 0% / 0% | 60% / 10% |
| 27 | 26 | 58% / 58% | 0% / 0% | 0% / 0% | 69% / 0% |
| 28 | 18 | 78% / 78% | 0% / 0% | 0% / 0% | 56% / 0% |
| 29 | 10 | 60% / 60% | 0% / 0% | 0% / 0% | 80% / 20% |
| 30 | 14 | 43% / 43% | 0% / 0% | 0% / 0% | 71% / 0% |
| 31 | 8 | 50% / 50% | 0% / 0% | 0% / 0% | 100% / 0% |
| 32 | 6 | 100% / 100% | 0% / 0% | 0% / 0% | 100% / 33% |
| 33 | 4 | 25% / 25% | 0% / 0% | 0% / 0% | 50% / 0% |
| 34 | 2 | 0% / 0% | 0% / 0% | 0% / 0% | 100% / 0% |
