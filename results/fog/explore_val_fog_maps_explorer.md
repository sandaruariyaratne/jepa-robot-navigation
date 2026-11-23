# Planning without privileged pictures: validation maps (10 x 10, fog)

50 maps, 10 random free start cells per map, seeds as configured. Snapped P2, threshold 6.93 (same / new node and unknown rule), at most 250 nodes. Budget: 300 moves, no loop rule.

| | Picture of every cell (as before) | A: imagine from start + goal pictures | B: imagine, then correct while walking | Oracle explorer (true walls once seen) |
|---|---|---|---|---|
| navigation success | 1000/1000 (100.0%) | 125/1000 (12.5%) | 388/1000 (38.8%) | 1000/1000 (100.0%) |
| shortest path | 958/1000 (95.8%) | 47/1000 (4.7%) | 64/1000 (6.4%) | 682/1000 (68.2%) |
| loop failures | 0 | 0 | 0 | 0 |
| extra moves per successful episode | 0.15 | 62.38 | 93.69 | 1.43 |
| collisions per action | 0.07% | 64.00% | 15.12% | 0.00% |
| map rebuilds per episode | 0.00 | 0.00 | 41.14 | 0.00 |
| plans heading for unexplored cells (no route seen) | 0.00% | 0.00% | 19.59% | 0.00% |
| plans with nothing known (latent fallback) | 0.09% | 93.28% | 80.04% | 0.00% |

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
| 2 | 26 | 100% / 100% | 54% / 38% | 88% / 58% | 100% / 100% |
| 3 | 38 | 100% / 95% | 26% / 5% | 53% / 11% | 100% / 100% |
| 4 | 36 | 100% / 94% | 31% / 8% | 67% / 11% | 100% / 100% |
| 5 | 46 | 100% / 100% | 13% / 0% | 43% / 2% | 100% / 91% |
| 6 | 56 | 100% / 96% | 5% / 0% | 50% / 4% | 100% / 96% |
| 7 | 68 | 100% / 85% | 9% / 0% | 54% / 0% | 100% / 85% |
| 8 | 62 | 100% / 100% | 3% / 0% | 48% / 3% | 100% / 84% |
| 9 | 98 | 100% / 96% | 8% / 0% | 28% / 2% | 100% / 86% |
| 10 | 80 | 100% / 98% | 8% / 0% | 34% / 2% | 100% / 52% |
| 11 | 76 | 100% / 100% | 4% / 0% | 30% / 0% | 100% / 66% |
| 12 | 82 | 100% / 93% | 5% / 0% | 24% / 0% | 100% / 49% |
| 13 | 90 | 100% / 89% | 9% / 0% | 30% / 0% | 100% / 56% |
| 14 | 60 | 100% / 97% | 8% / 0% | 18% / 0% | 100% / 57% |
| 15 | 54 | 100% / 100% | 2% / 0% | 28% / 0% | 100% / 41% |
| 16 | 32 | 100% / 100% | 16% / 0% | 38% / 0% | 100% / 38% |
| 17 | 38 | 100% / 95% | 0% / 0% | 13% / 0% | 100% / 11% |
| 18 | 22 | 100% / 100% | 5% / 0% | 23% / 0% | 100% / 18% |
| 20 | 4 | 100% / 100% | 0% / 0% | 50% / 0% | 100% / 50% |
