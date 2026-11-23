# Planning without privileged pictures: dense-wall maps (8-14 walls)

500 maps, every free start cell, seeds as configured. Snapped P2, threshold 7.05 (same / new node and unknown rule), at most 60 nodes. Explorer's budget: 60 moves, no loop rule.

| | B: imagine, then correct while walking |
|---|---|
| navigation success | 19611/19680 (99.6%) |
| shortest path | 16831/19680 (85.5%) |
| loop failures | 0 |
| extra moves per successful episode | 0.82 |
| collisions per action | 1.53% |
| map rebuilds per episode | 4.85 |
| plans heading for unexplored cells (no route seen) | 9.14% |
| plans with nothing known (latent fallback) | 4.43% |

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

| length | episodes | explore |
|---|---|---|
| 1 | 1492 | 100% / 100% |
| 2 | 1768 | 100% / 100% |
| 3 | 2040 | 100% / 99% |
| 4 | 2418 | 100% / 95% |
| 5 | 2582 | 100% / 93% |
| 6 | 2556 | 100% / 87% |
| 7 | 2316 | 100% / 80% |
| 8 | 1912 | 100% / 70% |
| 9 | 1256 | 99% / 62% |
| 10 | 578 | 99% / 52% |
| 11 | 366 | 98% / 52% |
| 12 | 212 | 98% / 42% |
| 13 | 106 | 97% / 35% |
| 14 | 46 | 91% / 54% |
| 15 | 20 | 90% / 45% |
| 16 | 6 | 83% / 33% |
| 17 | 6 | 83% / 67% |
