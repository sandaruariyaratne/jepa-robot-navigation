# Planning without privileged pictures: new_maps

500 maps, every free start cell, seeds as configured. Snapped P2, threshold 7.05 (same / new node and unknown rule), at most 60 nodes. Budget: 30 moves, third visit to a cell = loop failure (as every other run).

| | Picture of every cell (as before) | A: imagine from start + goal pictures | B: imagine, then correct while walking |
|---|---|---|---|
| navigation success | 24146/24146 (100.0%) | 21593/24146 (89.4%) | 24061/24146 (99.6%) |
| shortest path | 24146/24146 (100.0%) | 20739/24146 (85.9%) | 22636/24146 (93.7%) |
| loop failures | 0 | 2553 | 85 |
| extra moves per successful episode | 0.00 | 0.07 | 0.23 |
| collisions per action | 0.00% | 4.79% | 0.16% |
| map rebuilds per episode | 0.00 | 0.00 | 4.18 |
| plans heading for unexplored cells (no route seen) | 0.00% | 0.00% | 2.18% |
| plans with nothing known (latent fallback) | 0.00% | 2.30% | 0.13% |

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

| length | episodes | privileged | imagine | explore |
|---|---|---|---|---|
| 1 | 1678 | 100% / 100% | 100% / 100% | 100% / 100% |
| 2 | 2252 | 100% / 100% | 100% / 100% | 100% / 100% |
| 3 | 2758 | 100% / 100% | 100% / 99% | 100% / 100% |
| 4 | 3426 | 100% / 100% | 97% / 93% | 100% / 98% |
| 5 | 3724 | 100% / 100% | 95% / 92% | 100% / 96% |
| 6 | 3574 | 100% / 100% | 89% / 85% | 100% / 94% |
| 7 | 3010 | 100% / 100% | 83% / 77% | 99% / 90% |
| 8 | 2094 | 100% / 100% | 73% / 66% | 99% / 86% |
| 9 | 1168 | 100% / 100% | 64% / 58% | 100% / 81% |
| 10 | 242 | 100% / 100% | 27% / 21% | 95% / 50% |
| 11 | 118 | 100% / 100% | 17% / 12% | 93% / 42% |
| 12 | 54 | 100% / 100% | 7% / 7% | 91% / 39% |
| 13 | 34 | 100% / 100% | 6% / 0% | 85% / 18% |
| 14 | 14 | 100% / 100% | 0% / 0% | 79% / 36% |
