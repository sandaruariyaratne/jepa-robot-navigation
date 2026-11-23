# Planning without privileged pictures: test maps (10 x 10, fog)

200 maps, 10 random free start cells per map, seeds as configured. Snapped P2, threshold every-cell pictures: 6.93 (same / new node and unknown rule); A and B: stay 3.53 / merge 4.47 (fog: blocked vs same / new node), at most 250 nodes. Budget: 100 moves, third visit to a cell = loop failure.

| | Picture of every cell (as before) | A: imagine from start + goal pictures | B: imagine, then correct while walking | Oracle explorer (true walls once seen) |
|---|---|---|---|---|
| navigation success | 3981/4000 (99.5%) | 1672/4000 (41.8%) | 3199/4000 (80.0%) | 3960/4000 (99.0%) |
| shortest path | 3854/4000 (96.3%) | 1355/4000 (33.9%) | 1948/4000 (48.7%) | 2596/4000 (64.9%) |
| loop failures | 19 | 2328 | 801 | 40 |
| extra moves per successful episode | 0.12 | 0.40 | 2.87 | 1.22 |
| collisions per action | 0.08% | 16.79% | 0.23% | 0.00% |
| map rebuilds per episode | 0.00 | 0.00 | 11.19 | 0.00 |
| plans heading for unexplored cells (no route seen) | 0.00% | 0.00% | 19.62% | 0.00% |
| plans with nothing known (latent fallback) | 0.38% | 5.05% | 0.08% | 0.00% |

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
| 2 | 122 | 100% / 100% | 98% / 98% | 98% / 92% | 100% / 100% |
| 3 | 130 | 100% / 100% | 95% / 89% | 96% / 88% | 100% / 100% |
| 4 | 170 | 100% / 100% | 85% / 78% | 92% / 77% | 100% / 96% |
| 5 | 228 | 100% / 97% | 73% / 61% | 92% / 72% | 100% / 93% |
| 6 | 222 | 100% / 98% | 60% / 49% | 82% / 62% | 100% / 90% |
| 7 | 294 | 100% / 97% | 65% / 54% | 87% / 57% | 100% / 82% |
| 8 | 300 | 100% / 97% | 52% / 38% | 83% / 54% | 100% / 73% |
| 9 | 390 | 98% / 94% | 41% / 31% | 81% / 44% | 99% / 65% |
| 10 | 362 | 100% / 97% | 31% / 23% | 79% / 36% | 99% / 59% |
| 11 | 390 | 100% / 95% | 23% / 17% | 77% / 39% | 99% / 58% |
| 12 | 332 | 99% / 94% | 18% / 9% | 71% / 33% | 99% / 46% |
| 13 | 278 | 100% / 94% | 16% / 9% | 74% / 34% | 100% / 53% |
| 14 | 212 | 100% / 99% | 17% / 10% | 72% / 33% | 98% / 42% |
| 15 | 174 | 99% / 95% | 11% / 5% | 67% / 30% | 97% / 32% |
| 16 | 140 | 100% / 99% | 12% / 7% | 69% / 32% | 97% / 31% |
| 17 | 96 | 98% / 92% | 8% / 5% | 76% / 39% | 96% / 33% |
| 18 | 36 | 97% / 89% | 17% / 11% | 61% / 14% | 100% / 11% |
| 19 | 12 | 83% / 83% | 0% / 0% | 50% / 8% | 83% / 17% |
| 20 | 2 | 100% / 100% | 0% / 0% | 0% / 0% | 100% / 0% |
| 21 | 6 | 83% / 83% | 0% / 0% | 17% / 0% | 67% / 0% |
| 22 | 6 | 100% / 100% | 0% / 0% | 0% / 0% | 67% / 0% |
| 24 | 2 | 100% / 100% | 0% / 0% | 0% / 0% | 100% / 0% |
| 26 | 2 | 100% / 100% | 0% / 0% | 0% / 0% | 0% / 0% |
| 28 | 6 | 100% / 100% | 0% / 0% | 0% / 0% | 0% / 0% |
