# Multi-map results (v1 model, held-out layouts)

100 random layouts (3-7 walls, goal fixed at (5,0)), split by map: train 70 / val 15 / test 15. Training maps measure fit; test maps were never seen in training and measure generalization. Navigation uses 15 of the training maps and all validation / test maps, every start cell, seeds [0, 1].

## One-step prediction (snap to the map's own codebook)

| | train maps (fit) | val maps | **test maps** |
|---|---|---|---|
| normal moves | 48307/48307 (100%) | 6946/10218 (68%) | 7243/10354 (70%) |
| border bumps | 12630/12630 (100%) | 2823/2823 (100%) | 2637/2637 (100%) |
| wall bumps | 9063/9063 (100%) | 1940/1959 (99%) | 2009/2009 (100%) |
| all | 70000/70000 (100%) | 11709/15000 (78%) | 11889/15000 (79%) |
| latent MSE, model / persistence | 0.0015 / 0.6374 | 0.1569 / 0.6298 | 0.1561 / 0.6345 |

Imagined rollouts, snap accuracy by step:

| | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| train maps | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| val maps | 78% | 57% | 45% | 37% | 32% | 28% | 26% | 24% | 23% | 22% |
| test maps | 79% | 60% | 45% | 37% | 31% | 28% | 25% | 23% | 22% | 21% |

## Imagined graph, per map

| edges | train maps | val maps | **test maps** |
|---|---|---|---|
| normal moves: correct | 4862/4862 (100%) | 711/1042 (68%) | 710/1010 (70%) |
| border bumps: correct | 1306/1306 (100%) | 282/282 (100%) | 272/272 (100%) |
| wall bumps: correct | 920/920 (100%) | 198/200 (99%) | 206/206 (100%) |
| all: correct | 7088/7088 (100%) | 1191/1524 (78%) | 1188/1488 (80%) |
| all: unknown -> self-loop | 0/7088 (0%) | 0/1524 (0%) | 0/1488 (0%) |
| all: wrong but trusted | 0/7088 (0%) | 333/1524 (22%) | 300/1488 (20%) |
| D(c) exact (cells) | 1772/1772 (100%) | 173/381 (45%) | 201/372 (54%) |
| D(c) under-estimates (fake shortcuts) | 0 | 73 | 45 |
| maps with D(c) exact everywhere | 70/70 (100%) | 4/15 (27%) | 5/15 (33%) |

## Navigation and ladder (P2 on D1-Full)

| | dynamics | cost | train maps: success / optimal | val maps | **test maps** |
|---|---|---|---|---|---|
| Oracle | true | A* | 100% / 100% | 100% / 100% | 100% / 100% |
| D1 | true | true | 100% / 100% | 100% / 100% | 100% / 100% |
| D2 | true | learned | 100% / 100% | 71% / 62% | 84% / 78% |
| D3 | learned | true | 100% / 100% | 27% / 17% | 43% / 27% |
| Full | learned | learned | 100% / 100% | 24% / 16% | 44% / 30% |
| Random | - | - | 7% / 4% | 7% / 3% | 8% / 3% |

Reading (test maps):

- D1 = 100% optimal: the planner and control loop are correct.
- D2 vs D1: the learned cost D(c) costs 16% success and 22% optimal episodes.
- D3 vs D1: the learned dynamics costs 57% success and 73% optimal episodes.
- Full (30% optimal) is no worse than the weaker of D2 / D3: no compounding.
- Random reaches the goal in 8% of episodes (lower bound); Oracle in 100%.
