# Planning without privileged pictures: test mazes (10 x 10, fog)

100 maps, 10 random free start cells per map, seeds as configured. Snapped P2, threshold every-cell pictures: 6.93 (same / new node and unknown rule); A and B: stay 3.53 / merge 4.47 (fog: blocked vs same / new node), at most 250 nodes. Budget: 100 moves, third visit to a cell = loop failure.

| | Picture of every cell (as before) | A: imagine from start + goal pictures | B: imagine, then correct while walking | Oracle explorer (true walls once seen) |
|---|---|---|---|---|
| navigation success | 1517/2000 (75.8%) | 265/2000 (13.2%) | 434/2000 (21.7%) | 1576/2000 (78.8%) |
| shortest path | 1406/2000 (70.3%) | 248/2000 (12.4%) | 293/2000 (14.7%) | 680/2000 (34.0%) |
| loop failures | 483 | 1735 | 1566 | 424 |
| extra moves per successful episode | 0.37 | 0.08 | 1.48 | 6.91 |
| collisions per action | 2.72% | 32.39% | 1.07% | 0.00% |
| map rebuilds per episode | 0.00 | 0.00 | 8.62 | 0.00 |
| plans heading for unexplored cells (no route seen) | 0.00% | 0.00% | 14.07% | 0.00% |
| plans with nothing known (latent fallback) | 19.33% | 10.56% | 0.32% | 0.00% |

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
| 3 | 66 | 97% / 97% | 88% / 88% | 89% / 86% | 100% / 100% |
| 4 | 58 | 90% / 90% | 55% / 50% | 71% / 52% | 100% / 97% |
| 5 | 48 | 92% / 92% | 48% / 46% | 81% / 58% | 100% / 92% |
| 6 | 52 | 92% / 87% | 29% / 25% | 50% / 33% | 100% / 77% |
| 7 | 46 | 80% / 80% | 46% / 37% | 67% / 48% | 100% / 70% |
| 8 | 68 | 88% / 85% | 12% / 6% | 40% / 24% | 97% / 79% |
| 9 | 66 | 79% / 68% | 12% / 8% | 39% / 18% | 100% / 76% |
| 10 | 50 | 76% / 68% | 8% / 8% | 26% / 14% | 100% / 72% |
| 11 | 68 | 79% / 79% | 10% / 10% | 35% / 21% | 100% / 74% |
| 12 | 62 | 58% / 50% | 0% / 0% | 18% / 0% | 97% / 55% |
| 13 | 64 | 78% / 78% | 0% / 0% | 17% / 5% | 88% / 44% |
| 14 | 72 | 88% / 75% | 0% / 0% | 14% / 1% | 94% / 44% |
| 15 | 44 | 66% / 59% | 0% / 0% | 14% / 5% | 68% / 9% |
| 16 | 54 | 70% / 63% | 0% / 0% | 7% / 0% | 63% / 22% |
| 17 | 80 | 66% / 60% | 0% / 0% | 0% / 0% | 72% / 15% |
| 18 | 92 | 72% / 61% | 0% / 0% | 4% / 0% | 78% / 7% |
| 19 | 96 | 75% / 75% | 0% / 0% | 1% / 0% | 62% / 15% |
| 20 | 92 | 76% / 61% | 0% / 0% | 2% / 0% | 57% / 4% |
| 21 | 106 | 76% / 70% | 0% / 0% | 2% / 0% | 58% / 6% |
| 22 | 104 | 70% / 64% | 0% / 0% | 0% / 0% | 63% / 2% |
| 23 | 74 | 78% / 68% | 0% / 0% | 0% / 0% | 57% / 0% |
| 24 | 80 | 70% / 68% | 0% / 0% | 0% / 0% | 55% / 0% |
| 25 | 52 | 63% / 54% | 0% / 0% | 0% / 0% | 69% / 0% |
| 26 | 64 | 75% / 69% | 0% / 0% | 0% / 0% | 72% / 0% |
| 27 | 66 | 65% / 56% | 0% / 0% | 0% / 0% | 70% / 0% |
| 28 | 56 | 62% / 59% | 0% / 0% | 0% / 0% | 71% / 0% |
| 29 | 52 | 58% / 48% | 0% / 0% | 0% / 0% | 69% / 0% |
| 30 | 24 | 50% / 50% | 0% / 0% | 0% / 0% | 75% / 0% |
| 31 | 26 | 62% / 62% | 0% / 0% | 0% / 0% | 85% / 8% |
| 32 | 12 | 67% / 67% | 0% / 0% | 0% / 0% | 67% / 0% |
| 33 | 6 | 0% / 0% | 0% / 0% | 17% / 0% | 67% / 0% |
| 34 | 2 | 0% / 0% | 0% / 0% | 0% / 0% | 0% / 0% |
| 35 | 2 | 100% / 100% | 0% / 0% | 0% / 0% | 0% / 0% |
