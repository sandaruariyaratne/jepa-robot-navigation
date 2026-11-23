# 100 validation mazes: joint JEPA (v2), no retraining

100 layouts never used for training, validation or testing (seed 21; all 100 experiment layouts and the reference map excluded), 8-12 walls, goal (5,0). Navigation starts from every free cell of every map (1996 start cells), seeds [0, 1] -> 3992 episodes per rung. Average shortest path to the goal 8.5 steps, longest 18. Unknown threshold 4.25 (3 x median one-step error).

## Headline

| metric | result |
|---|---|
| navigation success (Full: learned dynamics + learned cost) | 3688/3992 (92.4%) |
| shortest-path accuracy (episodes with exactly the BFS length) | 3684/3992 (92.3%) |
| shortest path, among successful episodes | 3684/3688 (99.9%) |
| maps solved optimally from every start | 80/100 (80.0%) |
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
| Full | learned | learned | 3688/3992 (92.4%) | 3684/3992 (92.3%) | 1.5% | 304 | 0 |
| Random | - | - | 109/3992 (2.7%) | 44/3992 (1.1%) | 45.9% | 3883 | 0 |

Full, by number of walls:

| walls | maps | success | shortest path |
|---|---|---|---|
| 8 | 36 | 1452/1512 (96.0%) | 1450/1512 (95.9%) |
| 9 | 33 | 1168/1320 (88.5%) | 1166/1320 (88.3%) |
| 10 | 23 | 824/874 (94.3%) | 824/874 (94.3%) |
| 11 | 7 | 210/252 (83.3%) | 210/252 (83.3%) |
| 12 | 1 | 34/34 (100.0%) | 34/34 (100.0%) |

Full, by shortest-path length from the start:

| BFS distance | episodes | success | shortest path |
|---|---|---|---|
| 1 | 222 | 222/222 (100.0%) | 222/222 (100.0%) |
| 2 | 220 | 220/220 (100.0%) | 220/220 (100.0%) |
| 3 | 246 | 246/246 (100.0%) | 246/246 (100.0%) |
| 4 | 246 | 244/246 (99.2%) | 244/246 (99.2%) |
| 5 | 240 | 232/240 (96.7%) | 232/240 (96.7%) |
| 6 | 248 | 234/248 (94.4%) | 232/248 (93.5%) |
| 7 | 230 | 214/230 (93.0%) | 214/230 (93.0%) |
| 8 | 242 | 222/242 (91.7%) | 222/242 (91.7%) |
| 9 | 270 | 248/270 (91.9%) | 248/270 (91.9%) |
| 10 | 294 | 272/294 (92.5%) | 272/294 (92.5%) |
| 11 | 344 | 314/344 (91.3%) | 314/344 (91.3%) |
| 12 | 344 | 314/344 (91.3%) | 312/344 (90.7%) |
| 13 | 322 | 284/322 (88.2%) | 284/322 (88.2%) |
| 14 | 248 | 212/248 (85.5%) | 212/248 (85.5%) |
| 15 | 164 | 134/164 (81.7%) | 134/164 (81.7%) |
| 16 | 86 | 62/86 (72.1%) | 62/86 (72.1%) |
| 17 | 24 | 14/24 (58.3%) | 14/24 (58.3%) |
| 18 | 2 | 0/2 (0.0%) | 0/2 (0.0%) |

Maps where Full was not optimal from every start:

| map | walls | optimal | success | wrong edges | D(c) exact |
|---|---|---|---|---|---|
| 0 | 9 | 8/40 | 8/40 | 1 | 5/21 |
| 19 | 9 | 10/40 | 10/40 | 1 | 6/21 |
| 49 | 10 | 10/38 | 10/38 | 5 | 6/20 |
| 57 | 9 | 12/40 | 12/40 | 1 | 7/21 |
| 5 | 8 | 14/42 | 14/42 | 3 | 7/22 |
| 35 | 11 | 12/36 | 12/36 | 7 | 7/19 |
| 15 | 9 | 14/40 | 14/40 | 2 | 8/21 |
| 75 | 8 | 16/42 | 16/42 | 8 | 9/22 |
| 45 | 9 | 16/40 | 16/40 | 4 | 7/21 |
| 80 | 11 | 18/36 | 18/36 | 3 | 10/19 |
| 68 | 10 | 28/38 | 28/38 | 2 | 15/20 |
| 24 | 10 | 30/38 | 30/38 | 9 | 11/20 |
| 55 | 10 | 34/38 | 34/38 | 4 | 18/20 |
| 72 | 9 | 36/40 | 36/40 | 3 | 19/21 |
| 85 | 9 | 36/40 | 36/40 | 4 | 19/21 |

Reading:

- D1 = 100% optimal: the planner and control loop are correct.
- D2 vs D1: the learned cost D(c) costs 1% success and 4% optimal episodes.
- D3 vs D1: the learned dynamics costs 9% success and 9% optimal episodes.
- Full (92% optimal) is no worse than the weaker of D2 / D3: no compounding.
- Random reaches the goal in 3% of episodes (lower bound); Oracle in 100%.
