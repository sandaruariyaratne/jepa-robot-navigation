# Planning without privileged pictures: new_maps

500 maps, every free start cell, seeds as configured. Snapped P2, threshold 7.05 (same / new node and unknown rule), at most 60 nodes. Explorer's budget: 60 moves, no loop rule.

| | B: imagine, then correct while walking |
|---|---|
| navigation success | 24145/24146 (100.0%) |
| shortest path | 22636/24146 (93.7%) |
| loop failures | 0 |
| extra moves per successful episode | 0.26 |
| collisions per action | 0.27% |
| map rebuilds per episode | 4.21 |
| plans heading for unexplored cells (no route seen) | 2.25% |
| plans with nothing known (latent fallback) | 0.41% |

Imagined map before the first move (one per start cell; A and B start identically):

| | value |
|---|---|
| maps exactly right (one node per cell, every edge right) | 86/12073 (0.7%) |
| nodes / true cells | 23.7 / 25.2 |
| cells found | 267349/304508 (87.8%) |
| duplicate nodes (a cell imagined twice) | 2127 |
| spurious nodes (match no real cell) | 16341 |
| edges right (nodes matching a real cell) | 990833/1077904 (91.9%) |
| steps-to-goal from the start exact | 11144/12073 (92.3%) |
| goal unreachable from the start in imagination | 205 |
| growth hit the node cap | 0 |

By shortest-path length (success / shortest path):

| length | episodes | explore |
|---|---|---|
| 1 | 1678 | 100% / 100% |
| 2 | 2252 | 100% / 100% |
| 3 | 2758 | 100% / 100% |
| 4 | 3426 | 100% / 98% |
| 5 | 3724 | 100% / 96% |
| 6 | 3574 | 100% / 94% |
| 7 | 3010 | 100% / 90% |
| 8 | 2094 | 100% / 86% |
| 9 | 1168 | 100% / 81% |
| 10 | 242 | 100% / 50% |
| 11 | 118 | 100% / 42% |
| 12 | 54 | 100% / 39% |
| 13 | 34 | 100% / 18% |
| 14 | 14 | 100% / 36% |
