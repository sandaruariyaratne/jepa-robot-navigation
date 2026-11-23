# Planning without privileged pictures: validation dense-wall maps

100 maps, every free start cell, seeds as configured. Snapped P2, threshold 7.05 (same / new node and unknown rule), at most 60 nodes. Explorer's budget: 60 moves, no loop rule.

| | B: imagine, then correct while walking |
|---|---|
| navigation success | 3935/3936 (100.0%) |
| shortest path | 3383/3936 (86.0%) |
| loop failures | 0 |
| extra moves per successful episode | 0.81 |
| collisions per action | 0.57% |
| map rebuilds per episode | 4.89 |
| plans heading for unexplored cells (no route seen) | 9.61% |
| plans with nothing known (latent fallback) | 1.59% |

Imagined map before the first move (one per start cell; A and B start identically):

| | value |
|---|---|
| maps exactly right (one node per cell, every edge right) | 0/1968 (0.0%) |
| nodes / true cells | 21.4 / 20.8 |
| cells found | 34899/40890 (85.3%) |
| duplicate nodes (a cell imagined twice) | 705 |
| spurious nodes (match no real cell) | 6529 |
| edges right (nodes matching a real cell) | 123957/142416 (87.0%) |
| steps-to-goal from the start exact | 1640/1968 (83.3%) |
| goal unreachable from the start in imagination | 102 |
| growth hit the node cap | 0 |

By shortest-path length (success / shortest path):

| length | episodes | explore |
|---|---|---|
| 1 | 276 | 100% / 100% |
| 2 | 380 | 100% / 100% |
| 3 | 408 | 100% / 99% |
| 4 | 514 | 100% / 96% |
| 5 | 468 | 100% / 93% |
| 6 | 512 | 100% / 87% |
| 7 | 466 | 100% / 80% |
| 8 | 392 | 100% / 75% |
| 9 | 248 | 100% / 65% |
| 10 | 98 | 100% / 56% |
| 11 | 64 | 100% / 47% |
| 12 | 46 | 100% / 20% |
| 13 | 38 | 100% / 39% |
| 14 | 16 | 100% / 56% |
| 15 | 8 | 100% / 50% |
| 16 | 2 | 100% / 100% |
