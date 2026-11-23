# Planning without privileged pictures: test mazes (10 x 10, fog)

100 maps, 10 random free start cells per map, seeds as configured. Snapped P2, threshold every-cell pictures: 6.93 (same / new node and unknown rule); A and B: stay 3.53 / merge 4.47 (fog: blocked vs same / new node), at most 250 nodes. Budget: 300 moves, no loop rule.

| | Picture of every cell (as before) | A: imagine from start + goal pictures | B: imagine, then correct while walking | Oracle explorer (true walls once seen) |
|---|---|---|---|---|
| navigation success | 1620/2000 (81.0%) | 280/2000 (14.0%) | 1955/2000 (97.8%) | 2000/2000 (100.0%) |
| shortest path | 1406/2000 (70.3%) | 248/2000 (12.4%) | 293/2000 (14.7%) | 680/2000 (34.0%) |
| loop failures | 0 | 0 | 0 | 0 |
| extra moves per successful episode | 5.35 | 0.54 | 71.56 | 10.02 |
| collisions per action | 22.84% | 90.42% | 3.48% | 0.00% |
| map rebuilds per episode | 0.00 | 0.00 | 39.86 | 0.00 |
| plans heading for unexplored cells (no route seen) | 0.00% | 0.00% | 26.86% | 0.00% |
| plans with nothing known (latent fallback) | 82.91% | 9.91% | 6.07% | 0.00% |

Imagined map before the first move (one per start cell; A and B start identically):

| | value |
|---|---|
| maps exactly right (one node per cell, every edge right) | 0/1000 (0.0%) |
| nodes / true cells | 212.7 / 70.7 |
| cells found | 17137/70710 (24.2%) |
| duplicate nodes (a cell imagined twice) | 1497 |
| spurious nodes (match no real cell) | 194017 |
| edges right (nodes matching a real cell) | 41098/74536 (55.1%) |
| steps-to-goal from the start exact | 137/1000 (13.7%) |
| goal unreachable from the start in imagination | 123 |
| growth hit the node cap | 623 |

By shortest-path length (success / shortest path):

| length | episodes | privileged | imagine | explore | oracle |
|---|---|---|---|---|---|
| 1 | 46 | 100% / 100% | 100% / 100% | 100% / 100% | 100% / 100% |
| 2 | 50 | 100% / 100% | 86% / 86% | 100% / 76% | 100% / 100% |
| 3 | 66 | 97% / 97% | 88% / 88% | 100% / 86% | 100% / 100% |
| 4 | 58 | 97% / 90% | 59% / 50% | 100% / 52% | 100% / 97% |
| 5 | 48 | 96% / 92% | 48% / 46% | 100% / 58% | 100% / 92% |
| 6 | 52 | 100% / 87% | 35% / 25% | 100% / 33% | 100% / 77% |
| 7 | 46 | 91% / 80% | 48% / 37% | 100% / 48% | 100% / 70% |
| 8 | 68 | 93% / 85% | 15% / 6% | 100% / 24% | 100% / 79% |
| 9 | 66 | 91% / 68% | 17% / 8% | 100% / 18% | 100% / 76% |
| 10 | 50 | 92% / 68% | 10% / 8% | 100% / 14% | 100% / 72% |
| 11 | 68 | 90% / 79% | 13% / 10% | 100% / 21% | 100% / 74% |
| 12 | 62 | 68% / 50% | 0% / 0% | 98% / 0% | 100% / 55% |
| 13 | 64 | 88% / 78% | 2% / 0% | 98% / 5% | 100% / 44% |
| 14 | 72 | 92% / 75% | 0% / 0% | 99% / 1% | 100% / 44% |
| 15 | 44 | 77% / 59% | 0% / 0% | 89% / 5% | 100% / 9% |
| 16 | 54 | 80% / 63% | 0% / 0% | 98% / 0% | 100% / 22% |
| 17 | 80 | 71% / 60% | 0% / 0% | 99% / 0% | 100% / 15% |
| 18 | 92 | 76% / 61% | 0% / 0% | 96% / 0% | 100% / 7% |
| 19 | 96 | 75% / 75% | 0% / 0% | 100% / 0% | 100% / 15% |
| 20 | 92 | 78% / 61% | 0% / 0% | 98% / 0% | 100% / 4% |
| 21 | 106 | 77% / 70% | 0% / 0% | 98% / 0% | 100% / 6% |
| 22 | 104 | 75% / 64% | 0% / 0% | 94% / 0% | 100% / 2% |
| 23 | 74 | 78% / 68% | 0% / 0% | 96% / 0% | 100% / 0% |
| 24 | 80 | 74% / 68% | 0% / 0% | 92% / 0% | 100% / 0% |
| 25 | 52 | 65% / 54% | 0% / 0% | 96% / 0% | 100% / 0% |
| 26 | 64 | 81% / 69% | 0% / 0% | 97% / 0% | 100% / 0% |
| 27 | 66 | 68% / 56% | 0% / 0% | 97% / 0% | 100% / 0% |
| 28 | 56 | 68% / 59% | 0% / 0% | 98% / 0% | 100% / 0% |
| 29 | 52 | 62% / 48% | 0% / 0% | 96% / 0% | 100% / 0% |
| 30 | 24 | 50% / 50% | 0% / 0% | 92% / 0% | 100% / 0% |
| 31 | 26 | 62% / 62% | 0% / 0% | 96% / 0% | 100% / 8% |
| 32 | 12 | 83% / 67% | 0% / 0% | 100% / 0% | 100% / 0% |
| 33 | 6 | 33% / 0% | 0% / 0% | 100% / 0% | 100% / 0% |
| 34 | 2 | 100% / 0% | 0% / 0% | 100% / 0% | 100% / 0% |
| 35 | 2 | 100% / 100% | 0% / 0% | 100% / 0% | 100% / 0% |
