# Planning without privileged pictures: validation mazes (10 x 10, fog)

50 maps, 10 random free start cells per map, seeds as configured. Snapped P2, threshold no model, at most 0 nodes. Budget: 100 moves, third visit to a cell = loop failure.

| | Oracle explorer (true walls once seen) |
|---|---|
| navigation success | 806/1000 (80.6%) |
| shortest path | 332/1000 (33.2%) |
| loop failures | 194 |
| extra moves per successful episode | 6.52 |
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
| 9 | 36 | 94% / 50% |
| 10 | 20 | 100% / 80% |
| 11 | 30 | 93% / 47% |
| 12 | 34 | 94% / 35% |
| 13 | 28 | 86% / 50% |
| 14 | 20 | 100% / 50% |
| 15 | 42 | 71% / 29% |
| 16 | 46 | 87% / 13% |
| 17 | 40 | 80% / 10% |
| 18 | 38 | 53% / 5% |
| 19 | 50 | 72% / 8% |
| 20 | 70 | 80% / 6% |
| 21 | 26 | 62% / 8% |
| 22 | 56 | 68% / 0% |
| 23 | 46 | 65% / 0% |
| 24 | 34 | 59% / 0% |
| 25 | 54 | 59% / 0% |
| 26 | 20 | 60% / 10% |
| 27 | 26 | 69% / 0% |
| 28 | 18 | 56% / 0% |
| 29 | 10 | 80% / 20% |
| 30 | 14 | 71% / 0% |
| 31 | 8 | 100% / 0% |
| 32 | 6 | 100% / 33% |
| 33 | 4 | 50% / 0% |
| 34 | 2 | 100% / 0% |
