# Planning without privileged pictures: dense-wall maps (8-14 walls)

500 maps, every free start cell, seeds as configured. Snapped P2, threshold 7.05 (same / new node and unknown rule), at most 60 nodes. Budget: 30 moves, third visit to a cell = loop failure (as every other run).

| | Picture of every cell (as before) | A: imagine from start + goal pictures | B: imagine, then correct while walking |
|---|---|---|---|
| navigation success | 19680/19680 (100.0%) | 14722/19680 (74.8%) | 19210/19680 (97.6%) |
| shortest path | 19680/19680 (100.0%) | 13768/19680 (70.0%) | 16831/19680 (85.5%) |
| loop failures | 0 | 4958 | 470 |
| extra moves per successful episode | 0.00 | 0.09 | 0.50 |
| collisions per action | 0.00% | 11.68% | 0.41% |
| map rebuilds per episode | 0.00 | 0.00 | 4.72 |
| plans heading for unexplored cells (no route seen) | 0.00% | 0.00% | 8.48% |
| plans with nothing known (latent fallback) | 0.00% | 6.66% | 0.50% |

Imagined map before the first move (one per start cell; A and B start identically):

| | value |
|---|---|
| maps exactly right (one node per cell, every edge right) | 4/9840 (0.0%) |
| nodes / true cells | 21.1 / 20.8 |
| cells found | 173085/204616 (84.6%) |
| duplicate nodes (a cell imagined twice) | 3269 |
| spurious nodes (match no real cell) | 31704 |
| edges right (nodes matching a real cell) | 613938/705416 (87.0%) |
| steps-to-goal from the start exact | 8161/9840 (82.9%) |
| goal unreachable from the start in imagination | 523 |
| growth hit the node cap | 0 |

By shortest-path length (success / shortest path):

| length | episodes | privileged | imagine | explore |
|---|---|---|---|---|
| 1 | 1492 | 100% / 100% | 100% / 100% | 100% / 100% |
| 2 | 1768 | 100% / 100% | 100% / 100% | 100% / 100% |
| 3 | 2040 | 100% / 100% | 98% / 97% | 100% / 99% |
| 4 | 2418 | 100% / 100% | 91% / 85% | 99% / 95% |
| 5 | 2582 | 100% / 100% | 86% / 81% | 99% / 93% |
| 6 | 2556 | 100% / 100% | 75% / 68% | 98% / 87% |
| 7 | 2316 | 100% / 100% | 63% / 56% | 97% / 80% |
| 8 | 1912 | 100% / 100% | 52% / 43% | 96% / 70% |
| 9 | 1256 | 100% / 100% | 38% / 29% | 95% / 62% |
| 10 | 578 | 100% / 100% | 22% / 18% | 92% / 52% |
| 11 | 366 | 100% / 100% | 14% / 10% | 90% / 52% |
| 12 | 212 | 100% / 100% | 7% / 3% | 87% / 42% |
| 13 | 106 | 100% / 100% | 1% / 1% | 88% / 35% |
| 14 | 46 | 100% / 100% | 2% / 2% | 87% / 54% |
| 15 | 20 | 100% / 100% | 0% / 0% | 75% / 45% |
| 16 | 6 | 100% / 100% | 0% / 0% | 67% / 33% |
| 17 | 6 | 100% / 100% | 0% / 0% | 67% / 67% |
