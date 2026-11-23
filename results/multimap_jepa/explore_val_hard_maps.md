# Planning without privileged pictures: validation dense-wall maps

100 maps, every free start cell, seeds as configured. Snapped P2, threshold 7.05 (same / new node and unknown rule), at most 60 nodes. Budget: 30 moves, third visit to a cell = loop failure (as every other run).

| | Picture of every cell (as before) | A: imagine from start + goal pictures | B: imagine, then correct while walking |
|---|---|---|---|
| navigation success | 3936/3936 (100.0%) | 2984/3936 (75.8%) | 3848/3936 (97.8%) |
| shortest path | 3936/3936 (100.0%) | 2809/3936 (71.4%) | 3383/3936 (86.0%) |
| loop failures | 0 | 952 | 88 |
| extra moves per successful episode | 0.00 | 0.08 | 0.51 |
| collisions per action | 0.00% | 11.03% | 0.22% |
| map rebuilds per episode | 0.00 | 0.00 | 4.74 |
| plans heading for unexplored cells (no route seen) | 0.00% | 0.00% | 8.81% |
| plans with nothing known (latent fallback) | 0.00% | 6.29% | 0.33% |

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

| length | episodes | privileged | imagine | explore |
|---|---|---|---|---|
| 1 | 276 | 100% / 100% | 100% / 100% | 100% / 100% |
| 2 | 380 | 100% / 100% | 100% / 100% | 100% / 100% |
| 3 | 408 | 100% / 100% | 98% / 98% | 100% / 99% |
| 4 | 514 | 100% / 100% | 93% / 89% | 99% / 96% |
| 5 | 468 | 100% / 100% | 88% / 83% | 99% / 93% |
| 6 | 512 | 100% / 100% | 78% / 72% | 97% / 87% |
| 7 | 466 | 100% / 100% | 64% / 56% | 98% / 80% |
| 8 | 392 | 100% / 100% | 56% / 46% | 96% / 75% |
| 9 | 248 | 100% / 100% | 39% / 30% | 92% / 65% |
| 10 | 98 | 100% / 100% | 26% / 23% | 88% / 56% |
| 11 | 64 | 100% / 100% | 6% / 6% | 97% / 47% |
| 12 | 46 | 100% / 100% | 0% / 0% | 91% / 20% |
| 13 | 38 | 100% / 100% | 0% / 0% | 97% / 39% |
| 14 | 16 | 100% / 100% | 0% / 0% | 94% / 56% |
| 15 | 8 | 100% / 100% | 0% / 0% | 75% / 50% |
| 16 | 2 | 100% / 100% | 0% / 0% | 100% / 100% |
