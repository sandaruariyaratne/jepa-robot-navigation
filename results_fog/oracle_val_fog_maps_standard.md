# Planning without privileged pictures: validation maps (10 x 10, fog)

50 maps, 10 random free start cells per map, seeds as configured. Snapped P2, threshold no model, at most 0 nodes. Budget: 100 moves, third visit to a cell = loop failure.

| | Oracle explorer (true walls once seen) |
|---|---|
| navigation success | 980/1000 (98.0%) |
| shortest path | 682/1000 (68.2%) |
| loop failures | 20 |
| extra moves per successful episode | 1.13 |
| collisions per action | 0.00% |
| map rebuilds per episode | 0.00 |
| plans heading for unexplored cells (no route seen) | 0.00% |
| plans with nothing known (latent fallback) | 0.00% |

By shortest-path length (success / shortest path):

| length | episodes | oracle |
|---|---|---|
| 1 | 32 | 100% / 100% |
| 2 | 26 | 100% / 100% |
| 3 | 38 | 100% / 100% |
| 4 | 36 | 100% / 100% |
| 5 | 46 | 100% / 91% |
| 6 | 56 | 100% / 96% |
| 7 | 68 | 100% / 85% |
| 8 | 62 | 100% / 84% |
| 9 | 98 | 100% / 86% |
| 10 | 80 | 100% / 52% |
| 11 | 76 | 97% / 66% |
| 12 | 82 | 98% / 49% |
| 13 | 90 | 96% / 56% |
| 14 | 60 | 100% / 57% |
| 15 | 54 | 93% / 41% |
| 16 | 32 | 100% / 38% |
| 17 | 38 | 89% / 11% |
| 18 | 22 | 82% / 18% |
| 20 | 4 | 100% / 50% |
