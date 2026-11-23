# Planning without privileged pictures: validation mazes

100 maps, every free start cell, seeds as configured. Snapped P2, threshold 7.05 (same / new node and unknown rule), at most 60 nodes. Budget: 30 moves, third visit to a cell = loop failure (as every other run).

| | Picture of every cell (as before) | A: imagine from start + goal pictures | B: imagine, then correct while walking |
|---|---|---|---|
| navigation success | 3992/3992 (100.0%) | 1615/3992 (40.5%) | 3273/3992 (82.0%) |
| shortest path | 3992/3992 (100.0%) | 1506/3992 (37.7%) | 2147/3992 (53.8%) |
| loop failures | 0 | 2377 | 717 |
| extra moves per successful episode | 0.00 | 0.08 | 1.98 |
| collisions per action | 0.00% | 24.13% | 1.12% |
| map rebuilds per episode | 0.00 | 0.00 | 8.48 |
| plans heading for unexplored cells (no route seen) | 0.00% | 0.00% | 33.70% |
| plans with nothing known (latent fallback) | 0.00% | 25.55% | 2.11% |

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

| length | episodes | privileged | imagine | explore |
|---|---|---|---|---|
| 1 | 222 | 100% / 100% | 100% / 100% | 100% / 100% |
| 2 | 220 | 100% / 100% | 100% / 100% | 100% / 100% |
| 3 | 246 | 100% / 100% | 98% / 96% | 100% / 99% |
| 4 | 246 | 100% / 100% | 89% / 81% | 98% / 97% |
| 5 | 240 | 100% / 100% | 85% / 80% | 98% / 95% |
| 6 | 248 | 100% / 100% | 60% / 54% | 89% / 87% |
| 7 | 230 | 100% / 100% | 47% / 41% | 79% / 66% |
| 8 | 242 | 100% / 100% | 31% / 27% | 72% / 49% |
| 9 | 270 | 100% / 100% | 19% / 17% | 69% / 35% |
| 10 | 294 | 100% / 100% | 13% / 10% | 66% / 31% |
| 11 | 344 | 100% / 100% | 10% / 8% | 73% / 24% |
| 12 | 344 | 100% / 100% | 8% / 7% | 72% / 20% |
| 13 | 322 | 100% / 100% | 5% / 4% | 75% / 19% |
| 14 | 248 | 100% / 100% | 2% / 1% | 80% / 15% |
| 15 | 164 | 100% / 100% | 1% / 0% | 78% / 24% |
| 16 | 86 | 100% / 100% | 2% / 1% | 77% / 34% |
| 17 | 24 | 100% / 100% | 0% / 0% | 71% / 33% |
| 18 | 2 | 100% / 100% | 0% / 0% | 100% / 100% |
