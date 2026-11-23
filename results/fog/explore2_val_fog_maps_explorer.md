# Planning without privileged pictures: validation maps (10 x 10, fog)

50 maps, 10 random free start cells per map, seeds as configured. Snapped P2, threshold stay 3.53 / merge 4.47 (fog: blocked vs same / new node), at most 250 nodes. Budget: 300 moves, no loop rule.

| | Picture of every cell (as before) | A: imagine from start + goal pictures | B: imagine, then correct while walking |
|---|---|---|---|
| navigation success | 960/1000 (96.0%) | 416/1000 (41.6%) | 1000/1000 (100.0%) |
| shortest path | 843/1000 (84.3%) | 292/1000 (29.2%) | 446/1000 (44.6%) |
| loop failures | 0 | 0 | 0 |
| extra moves per successful episode | 1.68 | 0.96 | 17.31 |
| collisions per action | 10.28% | 89.23% | 0.70% |
| map rebuilds per episode | 0.00 | 0.00 | 17.66 |
| plans heading for unexplored cells (no route seen) | 0.00% | 0.00% | 22.44% |
| plans with nothing known (latent fallback) | 58.46% | 6.18% | 0.80% |

Imagined map before the first move (one per start cell; A and B start identically):

| | value |
|---|---|
| maps exactly right (one node per cell, every edge right) | 0/500 (0.0%) |
| nodes / true cells | 181.7 / 83.3 |
| cells found | 18936/41660 (45.5%) |
| duplicate nodes (a cell imagined twice) | 2452 |
| spurious nodes (match no real cell) | 69444 |
| edges right (nodes matching a real cell) | 51130/85552 (59.8%) |
| steps-to-goal from the start exact | 220/500 (44.0%) |
| goal unreachable from the start in imagination | 29 |
| growth hit the node cap | 205 |

By shortest-path length (success / shortest path):

| length | episodes | privileged | imagine | explore |
|---|---|---|---|---|
| 1 | 32 | 100% / 100% | 100% / 100% | 100% / 100% |
| 2 | 26 | 100% / 100% | 100% / 100% | 100% / 92% |
| 3 | 38 | 100% / 100% | 100% / 100% | 100% / 95% |
| 4 | 36 | 100% / 100% | 89% / 78% | 100% / 83% |
| 5 | 46 | 96% / 91% | 72% / 54% | 100% / 67% |
| 6 | 56 | 100% / 86% | 54% / 38% | 100% / 54% |
| 7 | 68 | 96% / 81% | 53% / 34% | 100% / 49% |
| 8 | 62 | 97% / 92% | 55% / 35% | 100% / 50% |
| 9 | 98 | 97% / 85% | 46% / 27% | 100% / 43% |
| 10 | 80 | 92% / 75% | 42% / 15% | 100% / 40% |
| 11 | 76 | 95% / 84% | 28% / 17% | 100% / 34% |
| 12 | 82 | 98% / 73% | 21% / 13% | 100% / 24% |
| 13 | 90 | 91% / 69% | 9% / 3% | 100% / 27% |
| 14 | 60 | 100% / 92% | 12% / 5% | 100% / 30% |
| 15 | 54 | 89% / 81% | 13% / 9% | 100% / 33% |
| 16 | 32 | 94% / 69% | 22% / 6% | 100% / 34% |
| 17 | 38 | 95% / 95% | 13% / 3% | 100% / 13% |
| 18 | 22 | 100% / 86% | 18% / 5% | 100% / 14% |
| 20 | 4 | 100% / 100% | 0% / 0% | 100% / 0% |
