# Planning without privileged pictures: maze maps (8-14 walls, longest paths)

200 maps, every free start cell, seeds as configured. Snapped P2, threshold 7.05 (same / new node and unknown rule), at most 60 nodes. Budget: 30 moves, third visit to a cell = loop failure (as every other run).

| | Picture of every cell (as before) | A: imagine from start + goal pictures | B: imagine, then correct while walking |
|---|---|---|---|
| navigation success | 8048/8048 (100.0%) | 3266/8048 (40.6%) | 6659/8048 (82.7%) |
| shortest path | 8048/8048 (100.0%) | 3087/8048 (38.4%) | 4495/8048 (55.9%) |
| loop failures | 0 | 4782 | 1386 |
| extra moves per successful episode | 0.00 | 0.06 | 1.87 |
| collisions per action | 0.00% | 24.03% | 0.94% |
| map rebuilds per episode | 0.00 | 0.00 | 8.33 |
| plans heading for unexplored cells (no route seen) | 0.00% | 0.00% | 32.95% |
| plans with nothing known (latent fallback) | 0.00% | 25.28% | 2.04% |

Imagined map before the first move (one per start cell; A and B start identically):

| | value |
|---|---|
| maps exactly right (one node per cell, every edge right) | 0/4024 (0.0%) |
| nodes / true cells | 19.2 / 21.2 |
| cells found | 64185/85182 (75.4%) |
| duplicate nodes (a cell imagined twice) | 1325 |
| spurious nodes (match no real cell) | 11638 |
| edges right (nodes matching a real cell) | 224442/262040 (85.7%) |
| steps-to-goal from the start exact | 1899/4024 (47.2%) |
| goal unreachable from the start in imagination | 805 |
| growth hit the node cap | 0 |

By shortest-path length (success / shortest path):

| length | episodes | privileged | imagine | explore |
|---|---|---|---|---|
| 1 | 442 | 100% / 100% | 100% / 100% | 100% / 100% |
| 2 | 466 | 100% / 100% | 100% / 100% | 100% / 100% |
| 3 | 480 | 100% / 100% | 99% / 97% | 100% / 99% |
| 4 | 508 | 100% / 100% | 92% / 89% | 98% / 97% |
| 5 | 474 | 100% / 100% | 80% / 76% | 96% / 91% |
| 6 | 462 | 100% / 100% | 61% / 56% | 89% / 84% |
| 7 | 466 | 100% / 100% | 53% / 49% | 81% / 70% |
| 8 | 496 | 100% / 100% | 33% / 28% | 78% / 53% |
| 9 | 576 | 100% / 100% | 24% / 22% | 75% / 44% |
| 10 | 578 | 100% / 100% | 13% / 11% | 71% / 34% |
| 11 | 666 | 100% / 100% | 9% / 6% | 71% / 28% |
| 12 | 694 | 100% / 100% | 5% / 3% | 74% / 25% |
| 13 | 678 | 100% / 100% | 3% / 2% | 72% / 19% |
| 14 | 514 | 100% / 100% | 2% / 1% | 76% / 23% |
| 15 | 330 | 100% / 100% | 1% / 1% | 75% / 19% |
| 16 | 164 | 100% / 100% | 2% / 2% | 87% / 39% |
| 17 | 44 | 100% / 100% | 5% / 2% | 77% / 39% |
| 18 | 10 | 100% / 100% | 0% / 0% | 60% / 60% |
