# Planning without privileged pictures: validation mazes

100 maps, every free start cell, seeds as configured. Snapped P2, threshold 7.05 (same / new node and unknown rule), at most 60 nodes. Explorer's budget: 60 moves, no loop rule.

| | B: imagine, then correct while walking |
|---|---|
| navigation success | 3808/3992 (95.4%) |
| shortest path | 2147/3992 (53.8%) |
| loop failures | 0 |
| extra moves per successful episode | 4.37 |
| collisions per action | 4.93% |
| map rebuilds per episode | 9.70 |
| plans heading for unexplored cells (no route seen) | 29.67% |
| plans with nothing known (latent fallback) | 16.88% |

Imagined map before the first move (one per start cell; A and B start identically):

| | value |
|---|---|
| maps exactly right (one node per cell, every edge right) | 0/1996 (0.0%) |
| nodes / true cells | 19.2 / 21.0 |
| cells found | 31916/41932 (76.1%) |
| duplicate nodes (a cell imagined twice) | 601 |
| spurious nodes (match no real cell) | 5756 |
| edges right (nodes matching a real cell) | 110960/130068 (85.3%) |
| steps-to-goal from the start exact | 951/1996 (47.6%) |
| goal unreachable from the start in imagination | 408 |
| growth hit the node cap | 0 |

By shortest-path length (success / shortest path):

| length | episodes | explore |
|---|---|---|
| 1 | 222 | 100% / 100% |
| 2 | 220 | 100% / 100% |
| 3 | 246 | 100% / 99% |
| 4 | 246 | 100% / 97% |
| 5 | 240 | 99% / 95% |
| 6 | 248 | 95% / 87% |
| 7 | 230 | 93% / 66% |
| 8 | 242 | 92% / 49% |
| 9 | 270 | 94% / 35% |
| 10 | 294 | 95% / 31% |
| 11 | 344 | 95% / 24% |
| 12 | 344 | 94% / 20% |
| 13 | 322 | 94% / 19% |
| 14 | 248 | 93% / 15% |
| 15 | 164 | 90% / 24% |
| 16 | 86 | 90% / 34% |
| 17 | 24 | 92% / 33% |
| 18 | 2 | 100% / 100% |
