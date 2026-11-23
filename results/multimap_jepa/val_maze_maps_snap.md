# 100 validation mazes: joint JEPA (v2), no retraining

100 layouts never used for training, validation or testing (seed 21; all 100 experiment layouts and the reference map excluded), 8-12 walls, goal (5,0). Navigation starts from every free cell of every map (1996 start cells), seeds [0, 1] -> 3992 episodes per rung. Average shortest path to the goal 8.5 steps, longest 18. Unknown threshold 4.25 (3 x median one-step error). Planner: P2 with every imagined step snapped to the codebook.

## Headline

| metric | result |
|---|---|
| navigation success (Full: learned dynamics + learned cost) | 3757/3992 (94.1%) |
| shortest-path accuracy (episodes with exactly the BFS length) | 3749/3992 (93.9%) |
| shortest path, among successful episodes | 3749/3757 (99.8%) |
| maps solved optimally from every start | 84/100 (84.0%) |
| collision accuracy, episode data (stay vs move) | 99.99% of 100000 transitions |
| collision accuracy, every (cell, action) pair: wall bumps | 2159/2159 (100.0%) |
| collision accuracy, every (cell, action) pair: border bumps | 1719/1719 (100.0%) |
| rollout accuracy at 1 / 5 / 10 steps | 100.0% / 80.1% / 54.7% |

## Collisions (episode data)

| | correct |
|---|---|
| blocked moves predicted as blocked | 46395/46407 (100.0%) |
|   interior-wall bumps | 25780/25792 (100.0%) |
|   border bumps | 20615/20615 (100.0%) |
| free moves wrongly predicted as blocked | 0/53593 (0.0%) |
| precision of "blocked" | 100.00% |

## One-step prediction and rollouts (episode data)

| move type | correct |
|---|---|
| normal moves | 53593/53593 (100.0%) |
| border bumps | 20615/20615 (100.0%) |
| wall bumps | 25780/25792 (100.0%) |
| all | 99988/100000 (100.0%) |

Rollout snap accuracy by imagined step (82000 windows):

| 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|
| 100.0% | 97.9% | 92.2% | 86.2% | 80.1% | 74.3% | 68.8% | 63.7% | 59.0% | 54.7% |

## Imagined graph (every cell x action of every map)

| edges | correct | unknown -> self-loop | wrong but trusted |
|---|---|---|---|
| normal moves | 4419/4506 (98.1%) | 87/4506 (1.9%) | 0/4506 (0.0%) |
| border bumps | 1719/1719 (100.0%) | 0/1719 (0.0%) | 0/1719 (0.0%) |
| wall bumps | 2159/2159 (100.0%) | 165/2159 (7.6%) | 0/2159 (0.0%) |
| all | 8297/8384 (99.0%) | 252/8384 (3.0%) | 0/8384 (0.0%) |
| D(c) exact | 1931/2096 (92.1%) cells; 78/100 (78.0%) maps exact everywhere; 0 fake shortcuts | | |

## Navigation and ladder

| rung | dynamics | cost | success | shortest path | collisions / action | loop failures | timeouts |
|---|---|---|---|---|---|---|---|
| Oracle | true | A* | 3992/3992 (100.0%) | 3992/3992 (100.0%) | 0.0% | 0 | 0 |
| D1 | true | true | 3992/3992 (100.0%) | 3992/3992 (100.0%) | 0.0% | 0 | 0 |
| D2 | true | learned | 3943/3992 (98.8%) | 3849/3992 (96.4%) | 0.5% | 49 | 0 |
| D3 | learned | true | 3647/3992 (91.4%) | 3646/3992 (91.3%) | 2.1% | 345 | 0 |
| Full | learned | learned | 3757/3992 (94.1%) | 3749/3992 (93.9%) | 1.2% | 235 | 0 |
| Random | - | - | 109/3992 (2.7%) | 44/3992 (1.1%) | 45.9% | 3883 | 0 |

Full, by number of walls:

| walls | maps | success | shortest path |
|---|---|---|---|
| 8 | 36 | 1464/1512 (96.8%) | 1462/1512 (96.7%) |
| 9 | 33 | 1195/1320 (90.5%) | 1193/1320 (90.4%) |
| 10 | 23 | 850/874 (97.3%) | 846/874 (96.8%) |
| 11 | 7 | 214/252 (84.9%) | 214/252 (84.9%) |
| 12 | 1 | 34/34 (100.0%) | 34/34 (100.0%) |

Full, by shortest-path length from the start:

| BFS distance | episodes | success | shortest path |
|---|---|---|---|
| 1 | 222 | 222/222 (100.0%) | 222/222 (100.0%) |
| 2 | 220 | 220/220 (100.0%) | 220/220 (100.0%) |
| 3 | 246 | 246/246 (100.0%) | 246/246 (100.0%) |
| 4 | 246 | 245/246 (99.6%) | 245/246 (99.6%) |
| 5 | 240 | 240/240 (100.0%) | 240/240 (100.0%) |
| 6 | 248 | 248/248 (100.0%) | 246/248 (99.2%) |
| 7 | 230 | 222/230 (96.5%) | 222/230 (96.5%) |
| 8 | 242 | 228/242 (94.2%) | 228/242 (94.2%) |
| 9 | 270 | 252/270 (93.3%) | 252/270 (93.3%) |
| 10 | 294 | 274/294 (93.2%) | 274/294 (93.2%) |
| 11 | 344 | 316/344 (91.9%) | 316/344 (91.9%) |
| 12 | 344 | 314/344 (91.3%) | 312/344 (90.7%) |
| 13 | 322 | 288/322 (89.4%) | 286/322 (88.8%) |
| 14 | 248 | 217/248 (87.5%) | 216/248 (87.1%) |
| 15 | 164 | 139/164 (84.8%) | 138/164 (84.1%) |
| 16 | 86 | 70/86 (81.4%) | 70/86 (81.4%) |
| 17 | 24 | 16/24 (66.7%) | 16/24 (66.7%) |
| 18 | 2 | 0/2 (0.0%) | 0/2 (0.0%) |

Maps where Full was not optimal from every start:

| map | walls | optimal | success | wrong edges | D(c) exact |
|---|---|---|---|---|---|
| 0 | 9 | 12/40 | 12/40 | 1 | 5/21 |
| 19 | 9 | 14/40 | 14/40 | 1 | 6/21 |
| 35 | 11 | 14/36 | 14/36 | 7 | 7/19 |
| 45 | 9 | 16/40 | 16/40 | 4 | 7/21 |
| 5 | 8 | 18/42 | 18/42 | 3 | 7/22 |
| 75 | 8 | 18/42 | 18/42 | 8 | 9/22 |
| 15 | 9 | 18/40 | 18/40 | 2 | 8/21 |
| 57 | 9 | 18/40 | 18/40 | 1 | 7/21 |
| 80 | 11 | 20/36 | 20/36 | 3 | 10/19 |
| 49 | 10 | 24/38 | 24/38 | 5 | 6/20 |
| 68 | 10 | 28/38 | 32/38 | 2 | 15/20 |
| 24 | 10 | 34/38 | 34/38 | 9 | 11/20 |
| 46 | 9 | 38/40 | 38/40 | 3 | 20/21 |
| 94 | 9 | 38/40 | 40/40 | 4 | 20/21 |
| 86 | 8 | 40/42 | 42/42 | 6 | 21/22 |

Reading:

- D1 = 100% optimal: the planner and control loop are correct.
- D2 vs D1: the learned cost D(c) costs 1% success and 4% optimal episodes.
- D3 vs D1: the learned dynamics costs 9% success and 9% optimal episodes.
- Full (94% optimal) is no worse than the weaker of D2 / D3: no compounding.
- Random reaches the goal in 3% of episodes (lower bound); Oracle in 100%.
