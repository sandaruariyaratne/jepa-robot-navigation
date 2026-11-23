# Planning without privileged pictures: validation mazes (10 x 10, fog)

50 maps, 10 random free start cells per map, seeds as configured. Snapped P2, threshold stay 3.53 / merge 4.47 (fog: blocked vs same / new node), at most 250 nodes. Budget: 300 moves, no loop rule.

| | Picture of every cell (as before) | A: imagine from start + goal pictures | B: imagine, then correct while walking |
|---|---|---|---|
| navigation success | 420/1000 (42.0%) | 151/1000 (15.1%) | 969/1000 (96.9%) |
| shortest path | 324/1000 (32.4%) | 122/1000 (12.2%) | 140/1000 (14.0%) |
| loop failures | 0 | 0 | 0 |
| extra moves per successful episode | 17.19 | 0.72 | 77.37 |
| collisions per action | 18.69% | 91.48% | 4.25% |
| map rebuilds per episode | 0.00 | 0.00 | 41.57 |
| plans heading for unexplored cells (no route seen) | 0.00% | 0.00% | 28.17% |
| plans with nothing known (latent fallback) | 97.70% | 12.29% | 7.29% |

Imagined map before the first move (one per start cell; A and B start identically):

| | value |
|---|---|
| maps exactly right (one node per cell, every edge right) | 0/500 (0.0%) |
| nodes / true cells | 207.9 / 71.3 |
| cells found | 9116/35670 (25.6%) |
| duplicate nodes (a cell imagined twice) | 721 |
| spurious nodes (match no real cell) | 94136 |
| edges right (nodes matching a real cell) | 21306/39348 (54.1%) |
| steps-to-goal from the start exact | 72/500 (14.4%) |
| goal unreachable from the start in imagination | 76 |
| growth hit the node cap | 290 |

By shortest-path length (success / shortest path):

| length | episodes | privileged | imagine | explore |
|---|---|---|---|---|
| 1 | 16 | 100% / 100% | 100% / 100% | 100% / 100% |
| 2 | 24 | 100% / 100% | 100% / 100% | 100% / 92% |
| 3 | 24 | 100% / 100% | 92% / 92% | 100% / 79% |
| 4 | 28 | 93% / 93% | 71% / 64% | 100% / 64% |
| 5 | 30 | 87% / 87% | 57% / 47% | 100% / 57% |
| 6 | 38 | 92% / 79% | 45% / 29% | 100% / 61% |
| 7 | 20 | 60% / 60% | 30% / 25% | 100% / 25% |
| 8 | 42 | 67% / 43% | 19% / 10% | 100% / 26% |
| 9 | 36 | 50% / 44% | 22% / 6% | 100% / 6% |
| 10 | 20 | 75% / 70% | 30% / 20% | 100% / 10% |
| 11 | 30 | 43% / 33% | 10% / 3% | 97% / 10% |
| 12 | 34 | 32% / 26% | 6% / 0% | 97% / 3% |
| 13 | 28 | 43% / 36% | 0% / 0% | 100% / 0% |
| 14 | 20 | 65% / 35% | 10% / 5% | 95% / 5% |
| 15 | 42 | 26% / 19% | 0% / 0% | 98% / 0% |
| 16 | 46 | 24% / 9% | 0% / 0% | 91% / 0% |
| 17 | 40 | 40% / 15% | 0% / 0% | 100% / 0% |
| 18 | 38 | 21% / 11% | 0% / 0% | 95% / 0% |
| 19 | 50 | 22% / 12% | 0% / 0% | 100% / 0% |
| 20 | 70 | 34% / 14% | 0% / 0% | 94% / 0% |
| 21 | 26 | 23% / 15% | 0% / 0% | 88% / 0% |
| 22 | 56 | 27% / 18% | 0% / 0% | 93% / 0% |
| 23 | 46 | 24% / 17% | 0% / 0% | 98% / 0% |
| 24 | 34 | 6% / 6% | 0% / 0% | 100% / 0% |
| 25 | 54 | 31% / 19% | 0% / 0% | 100% / 0% |
| 26 | 20 | 10% / 0% | 0% / 0% | 95% / 0% |
| 27 | 26 | 8% / 8% | 0% / 0% | 85% / 0% |
| 28 | 18 | 11% / 11% | 0% / 0% | 89% / 0% |
| 29 | 10 | 20% / 0% | 0% / 0% | 100% / 0% |
| 30 | 14 | 0% / 0% | 0% / 0% | 86% / 0% |
| 31 | 8 | 50% / 50% | 0% / 0% | 100% / 0% |
| 32 | 6 | 33% / 33% | 0% / 0% | 100% / 0% |
| 33 | 4 | 25% / 0% | 0% / 0% | 100% / 0% |
| 34 | 2 | 0% / 0% | 0% / 0% | 100% / 0% |
