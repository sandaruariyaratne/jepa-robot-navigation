# Planning without privileged pictures: test maps (10 x 10, fog)

200 maps, 10 random free start cells per map, seeds as configured. Snapped P2, threshold every-cell pictures: 6.93 (same / new node and unknown rule); A and B: stay 3.53 / merge 4.47 (fog: blocked vs same / new node), at most 250 nodes. Budget: 300 moves, no loop rule.

| | Picture of every cell (as before) | A: imagine from start + goal pictures | B: imagine, then correct while walking | Oracle explorer (true walls once seen) |
|---|---|---|---|---|
| navigation success | 3994/4000 (99.8%) | 1891/4000 (47.3%) | 4000/4000 (100.0%) | 4000/4000 (100.0%) |
| shortest path | 3854/4000 (96.3%) | 1355/4000 (33.9%) | 1948/4000 (48.7%) | 2596/4000 (64.9%) |
| loop failures | 0 | 0 | 0 | 0 |
| extra moves per successful episode | 0.17 | 1.08 | 13.21 | 1.31 |
| collisions per action | 1.58% | 88.49% | 0.77% | 0.00% |
| map rebuilds per episode | 0.00 | 0.00 | 16.16 | 0.00 |
| plans heading for unexplored cells (no route seen) | 0.00% | 0.00% | 28.34% | 0.00% |
| plans with nothing known (latent fallback) | 4.99% | 6.75% | 0.32% | 0.00% |

Imagined map before the first move (one per start cell; A and B start identically):

| | value |
|---|---|
| maps exactly right (one node per cell, every edge right) | 0/2000 (0.0%) |
| nodes / true cells | 184.0 / 84.1 |
| cells found | 79679/168180 (47.4%) |
| duplicate nodes (a cell imagined twice) | 10387 |
| spurious nodes (match no real cell) | 277935 |
| edges right (nodes matching a real cell) | 220855/360264 (61.3%) |
| steps-to-goal from the start exact | 869/2000 (43.5%) |
| goal unreachable from the start in imagination | 126 |
| growth hit the node cap | 840 |

By shortest-path length (success / shortest path):

| length | episodes | privileged | imagine | explore | oracle |
|---|---|---|---|---|---|
| 1 | 88 | 100% / 100% | 100% / 100% | 100% / 100% | 100% / 100% |
| 2 | 122 | 100% / 100% | 98% / 98% | 100% / 92% | 100% / 100% |
| 3 | 130 | 100% / 100% | 95% / 89% | 100% / 88% | 100% / 100% |
| 4 | 170 | 100% / 100% | 87% / 78% | 100% / 77% | 100% / 96% |
| 5 | 228 | 100% / 97% | 77% / 61% | 100% / 72% | 100% / 93% |
| 6 | 222 | 100% / 98% | 65% / 49% | 100% / 62% | 100% / 90% |
| 7 | 294 | 100% / 97% | 69% / 54% | 100% / 57% | 100% / 82% |
| 8 | 300 | 100% / 97% | 59% / 38% | 100% / 54% | 100% / 73% |
| 9 | 390 | 99% / 94% | 50% / 31% | 100% / 44% | 100% / 65% |
| 10 | 362 | 100% / 97% | 36% / 23% | 100% / 36% | 100% / 59% |
| 11 | 390 | 100% / 95% | 28% / 17% | 100% / 39% | 100% / 58% |
| 12 | 332 | 99% / 94% | 24% / 9% | 100% / 33% | 100% / 46% |
| 13 | 278 | 100% / 94% | 24% / 9% | 100% / 34% | 100% / 53% |
| 14 | 212 | 100% / 99% | 22% / 10% | 100% / 33% | 100% / 42% |
| 15 | 174 | 100% / 95% | 18% / 5% | 100% / 30% | 100% / 32% |
| 16 | 140 | 100% / 99% | 16% / 7% | 100% / 32% | 100% / 31% |
| 17 | 96 | 100% / 92% | 18% / 5% | 100% / 39% | 100% / 33% |
| 18 | 36 | 100% / 89% | 28% / 11% | 100% / 14% | 100% / 11% |
| 19 | 12 | 100% / 83% | 0% / 0% | 100% / 8% | 100% / 17% |
| 20 | 2 | 100% / 100% | 0% / 0% | 100% / 0% | 100% / 0% |
| 21 | 6 | 100% / 83% | 0% / 0% | 100% / 0% | 100% / 0% |
| 22 | 6 | 100% / 100% | 0% / 0% | 100% / 0% | 100% / 0% |
| 24 | 2 | 100% / 100% | 0% / 0% | 100% / 0% | 100% / 0% |
| 26 | 2 | 100% / 100% | 0% / 0% | 100% / 0% | 100% / 0% |
| 28 | 6 | 100% / 100% | 0% / 0% | 100% / 0% | 100% / 0% |
