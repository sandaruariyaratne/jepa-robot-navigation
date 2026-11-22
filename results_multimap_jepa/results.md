# Multi-map results (joint JEPA (v2), held-out layouts)

100 random layouts (3-7 walls, goal fixed at (5,0)), split by map: train 70 / val 15 / test 15. Training maps measure fit; test maps were never seen in training and measure generalization. Navigation uses 15 of the training maps and all validation / test maps, every start cell, seeds [0, 1].

## One-step prediction (snap to the map's own codebook)

| | train maps (fit) | val maps | **test maps** |
|---|---|---|---|
| normal moves | 48307/48307 (100%) | 10218/10218 (100%) | 10354/10354 (100%) |
| border bumps | 12630/12630 (100%) | 2823/2823 (100%) | 2637/2637 (100%) |
| wall bumps | 9063/9063 (100%) | 1959/1959 (100%) | 2009/2009 (100%) |
| all | 70000/70000 (100%) | 15000/15000 (100%) | 15000/15000 (100%) |
| latent MSE, model / persistence | 0.0242 / 1.2234 | 0.0483 / 1.2105 | 0.0481 / 1.2029 |

Imagined rollouts, snap accuracy by step:

| | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| train maps | 100% | 100% | 100% | 100% | 99% | 99% | 98% | 96% | 94% | 91% |
| val maps | 100% | 99% | 97% | 93% | 90% | 86% | 82% | 78% | 74% | 70% |
| test maps | 100% | 99% | 97% | 94% | 90% | 86% | 82% | 78% | 74% | 70% |

## Imagined graph, per map

| edges | train maps | val maps | **test maps** |
|---|---|---|---|
| normal moves: correct | 4861/4862 (100%) | 1038/1042 (100%) | 1009/1010 (100%) |
| border bumps: correct | 1306/1306 (100%) | 282/282 (100%) | 272/272 (100%) |
| wall bumps: correct | 920/920 (100%) | 200/200 (100%) | 206/206 (100%) |
| all: correct | 7087/7088 (100%) | 1520/1524 (100%) | 1487/1488 (100%) |
| all: unknown -> self-loop | 5/7088 (0%) | 15/1524 (1%) | 10/1488 (1%) |
| all: wrong but trusted | 0/7088 (0%) | 0/1524 (0%) | 0/1488 (0%) |
| D(c) exact (cells) | 1772/1772 (100%) | 381/381 (100%) | 372/372 (100%) |
| D(c) under-estimates (fake shortcuts) | 0 | 0 | 0 |
| maps with D(c) exact everywhere | 70/70 (100%) | 15/15 (100%) | 15/15 (100%) |

## Navigation and ladder (P2 on D1-Full)

| | dynamics | cost | train maps: success / optimal | val maps | **test maps** |
|---|---|---|---|---|---|
| Oracle | true | A* | 100% / 100% | 100% / 100% | 100% / 100% |
| D1 | true | true | 100% / 100% | 100% / 100% | 100% / 100% |
| D2 | true | learned | 100% / 100% | 100% / 100% | 100% / 100% |
| D3 | learned | true | 100% / 100% | 100% / 100% | 100% / 100% |
| Full | learned | learned | 100% / 100% | 100% / 100% | 100% / 100% |
| Random | - | - | 7% / 4% | 7% / 3% | 8% / 3% |

Reading (test maps):

- D1 = 100% optimal: the planner and control loop are correct.
- D2 matches D1: the learned cost D(c) costs nothing.
- D3 matches D1: the learned dynamics costs nothing.
- Full (100% optimal) is no worse than the weaker of D2 / D3: no compounding.
- Random reaches the goal in 8% of episodes (lower bound); Oracle in 100%.
