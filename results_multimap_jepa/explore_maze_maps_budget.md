# Planning without privileged pictures: maze maps (8-14 walls, longest paths)

200 maps, every free start cell, seeds as configured. Snapped P2, threshold 7.05 (same / new node and unknown rule), at most 60 nodes. Explorer's budget: 60 moves, no loop rule.

| | B: imagine, then correct while walking |
|---|---|
| navigation success | 7570/8048 (94.1%) |
| shortest path | 4495/8048 (55.9%) |
| loop failures | 0 |
| extra moves per successful episode | 3.98 |
| collisions per action | 5.60% |
| map rebuilds per episode | 9.46 |
| plans heading for unexplored cells (no route seen) | 27.95% |
| plans with nothing known (latent fallback) | 20.84% |

Imagined map before the first move (one per start cell; A and B start identically):

| | value |
|---|---|
| maps exactly right (one node per cell, every edge right) | 0/4024 (0.0%) |
| nodes / true cells | 19.2 / 21.2 |
| cells found | 64185/85182 (75.4%) |
| duplicate nodes (a cell imagined twice) | 1325 |
| spurious nodes (match no real cell) | 11638 |
| edges right (nodes matching a real cell) | 224442/262040 (85.7%) |
| steps-to-goal from the start exact | 1899/4024 (47.2%) |
| goal unreachable from the start in imagination | 805 |
| growth hit the node cap | 0 |

By shortest-path length (success / shortest path):

| length | episodes | explore |
|---|---|---|
| 1 | 442 | 100% / 100% |
| 2 | 466 | 100% / 100% |
| 3 | 480 | 100% / 99% |
| 4 | 508 | 100% / 97% |
| 5 | 474 | 100% / 91% |
| 6 | 462 | 95% / 84% |
| 7 | 466 | 94% / 70% |
| 8 | 496 | 93% / 53% |
| 9 | 576 | 91% / 44% |
| 10 | 578 | 90% / 34% |
| 11 | 666 | 89% / 28% |
| 12 | 694 | 91% / 25% |
| 13 | 678 | 91% / 19% |
| 14 | 514 | 92% / 23% |
| 15 | 330 | 89% / 19% |
| 16 | 164 | 95% / 39% |
| 17 | 44 | 91% / 39% |
| 18 | 10 | 100% / 60% |
