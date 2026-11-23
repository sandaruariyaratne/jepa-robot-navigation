# Planning without privileged pictures: validation mazes (10 x 10, fog)

50 maps, 10 random free start cells per map, seeds as configured. Snapped P2, threshold no model, at most 0 nodes. Budget: 300 moves, no loop rule.

| | Oracle explorer (true walls once seen) |
|---|---|
| navigation success | 1000/1000 (100.0%) |
| shortest path | 332/1000 (33.2%) |
| loop failures | 0 |
| extra moves per successful episode | 9.51 |
| collisions per action | 0.00% |
| map rebuilds per episode | 0.00 |
| plans heading for unexplored cells (no route seen) | 0.00% |
| plans with nothing known (latent fallback) | 0.00% |

By shortest-path length (success / shortest path):

| length | episodes | oracle |
|---|---|---|
| 1 | 16 | 100% / 100% |
| 2 | 24 | 100% / 100% |
| 3 | 24 | 100% / 100% |
| 4 | 28 | 100% / 86% |
| 5 | 30 | 100% / 93% |
| 6 | 38 | 100% / 95% |
| 7 | 20 | 100% / 90% |
| 8 | 42 | 100% / 90% |
| 9 | 36 | 100% / 50% |
| 10 | 20 | 100% / 80% |
| 11 | 30 | 100% / 47% |
| 12 | 34 | 100% / 35% |
| 13 | 28 | 100% / 50% |
| 14 | 20 | 100% / 50% |
| 15 | 42 | 100% / 29% |
| 16 | 46 | 100% / 13% |
| 17 | 40 | 100% / 10% |
| 18 | 38 | 100% / 5% |
| 19 | 50 | 100% / 8% |
| 20 | 70 | 100% / 6% |
| 21 | 26 | 100% / 8% |
| 22 | 56 | 100% / 0% |
| 23 | 46 | 100% / 0% |
| 24 | 34 | 100% / 0% |
| 25 | 54 | 100% / 0% |
| 26 | 20 | 100% / 10% |
| 27 | 26 | 100% / 0% |
| 28 | 18 | 100% / 0% |
| 29 | 10 | 100% / 20% |
| 30 | 14 | 100% / 0% |
| 31 | 8 | 100% / 0% |
| 32 | 6 | 100% / 33% |
| 33 | 4 | 100% / 0% |
| 34 | 2 | 100% / 0% |
