# Planning without privileged pictures: validation maps (10 x 10, fog)

50 maps, 10 random free start cells per map, seeds as configured. Snapped P2, threshold 6.93 (same / new node and unknown rule), at most 250 nodes. Budget: 100 moves, third visit to a cell = loop failure.

| | Picture of every cell (as before) | A: imagine from start + goal pictures | B: imagine, then correct while walking | Oracle explorer (true walls once seen) |
|---|---|---|---|---|
| navigation success | 999/1000 (99.9%) | 52/1000 (5.2%) | 94/1000 (9.4%) | 980/1000 (98.0%) |
| shortest path | 958/1000 (95.8%) | 47/1000 (4.7%) | 64/1000 (6.4%) | 682/1000 (68.2%) |
| loop failures | 1 | 948 | 906 | 20 |
| extra moves per successful episode | 0.15 | 0.33 | 3.85 | 1.13 |
| collisions per action | 0.03% | 16.02% | 2.67% | 0.00% |
| map rebuilds per episode | 0.00 | 0.00 | 14.42 | 0.00 |
| plans heading for unexplored cells (no route seen) | 0.00% | 0.00% | 83.29% | 0.00% |
| plans with nothing known (latent fallback) | 0.04% | 97.25% | 15.64% | 0.00% |

Imagined map before the first move (one per start cell; A and B start identically):

| | value |
|---|---|
| maps exactly right (one node per cell, every edge right) | 0/500 (0.0%) |
| nodes / true cells | 6.4 / 83.3 |
| cells found | 3013/41660 (7.2%) |
| duplicate nodes (a cell imagined twice) | 0 |
| spurious nodes (match no real cell) | 203 |
| edges right (nodes matching a real cell) | 7523/12052 (62.4%) |
| steps-to-goal from the start exact | 23/500 (4.6%) |
| goal unreachable from the start in imagination | 473 |
| growth hit the node cap | 0 |

By shortest-path length (success / shortest path):

| length | episodes | privileged | imagine | explore | oracle |
|---|---|---|---|---|---|
| 1 | 32 | 100% / 100% | 100% / 100% | 100% / 100% | 100% / 100% |
| 2 | 26 | 100% / 100% | 46% / 38% | 65% / 58% | 100% / 100% |
| 3 | 38 | 97% / 95% | 8% / 5% | 13% / 11% | 100% / 100% |
| 4 | 36 | 100% / 94% | 8% / 8% | 31% / 11% | 100% / 100% |
| 5 | 46 | 100% / 100% | 0% / 0% | 11% / 2% | 100% / 91% |
| 6 | 56 | 100% / 96% | 0% / 0% | 5% / 4% | 100% / 96% |
| 7 | 68 | 100% / 85% | 0% / 0% | 1% / 0% | 100% / 85% |
| 8 | 62 | 100% / 100% | 0% / 0% | 16% / 3% | 100% / 84% |
| 9 | 98 | 100% / 96% | 1% / 0% | 3% / 2% | 100% / 86% |
| 10 | 80 | 100% / 98% | 0% / 0% | 8% / 2% | 100% / 52% |
| 11 | 76 | 100% / 100% | 0% / 0% | 0% / 0% | 97% / 66% |
| 12 | 82 | 100% / 93% | 1% / 0% | 0% / 0% | 98% / 49% |
| 13 | 90 | 100% / 89% | 0% / 0% | 0% / 0% | 96% / 56% |
| 14 | 60 | 100% / 97% | 0% / 0% | 0% / 0% | 100% / 57% |
| 15 | 54 | 100% / 100% | 0% / 0% | 0% / 0% | 93% / 41% |
| 16 | 32 | 100% / 100% | 0% / 0% | 3% / 0% | 100% / 38% |
| 17 | 38 | 100% / 95% | 0% / 0% | 0% / 0% | 89% / 11% |
| 18 | 22 | 100% / 100% | 0% / 0% | 0% / 0% | 82% / 18% |
| 20 | 4 | 100% / 100% | 0% / 0% | 0% / 0% | 100% / 50% |
