# 100 validation mazes: joint JEPA (v2), no retraining

100 layouts never used for training, validation or testing (seed 21; all 100 experiment layouts and the reference map excluded), 8-12 walls, goal (5,0). Navigation starts from every free cell of every map (1996 start cells), seeds [0, 1] -> 3992 episodes per rung. Average shortest path to the goal 8.5 steps, longest 18. Unknown threshold 7.05 (99.9% quantile of correct one-step snap distances, validation maps). Planner: P2 with every imagined step snapped to the codebook.

## Headline

| metric | result |
|---|---|
| navigation success (Full: learned dynamics + learned cost) | 3992/3992 (100.0%) |
| shortest-path accuracy (episodes with exactly the BFS length) | 3992/3992 (100.0%) |
| shortest path, among successful episodes | 3992/3992 (100.0%) |
| maps solved optimally from every start | 100/100 (100.0%) |
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
| normal moves | 4506/4506 (100.0%) | 0/4506 (0.0%) | 0/4506 (0.0%) |
| border bumps | 1719/1719 (100.0%) | 0/1719 (0.0%) | 0/1719 (0.0%) |
| wall bumps | 2159/2159 (100.0%) | 3/2159 (0.1%) | 0/2159 (0.0%) |
| all | 8384/8384 (100.0%) | 3/8384 (0.0%) | 0/8384 (0.0%) |
| D(c) exact | 2096/2096 (100.0%) cells; 100/100 (100.0%) maps exact everywhere; 0 fake shortcuts | | |

## Navigation and ladder

| rung | dynamics | cost | success | shortest path | collisions / action | loop failures | timeouts |
|---|---|---|---|---|---|---|---|
| Oracle | true | A* | 3992/3992 (100.0%) | 3992/3992 (100.0%) | 0.0% | 0 | 0 |
| D1 | true | true | 3992/3992 (100.0%) | 3992/3992 (100.0%) | 0.0% | 0 | 0 |
| D2 | true | learned | 3992/3992 (100.0%) | 3992/3992 (100.0%) | 0.0% | 0 | 0 |
| D3 | learned | true | 3992/3992 (100.0%) | 3992/3992 (100.0%) | 0.0% | 0 | 0 |
| Full | learned | learned | 3992/3992 (100.0%) | 3992/3992 (100.0%) | 0.0% | 0 | 0 |
| Random | - | - | 109/3992 (2.7%) | 44/3992 (1.1%) | 45.9% | 3883 | 0 |

Full, by number of walls:

| walls | maps | success | shortest path |
|---|---|---|---|
| 8 | 36 | 1512/1512 (100.0%) | 1512/1512 (100.0%) |
| 9 | 33 | 1320/1320 (100.0%) | 1320/1320 (100.0%) |
| 10 | 23 | 874/874 (100.0%) | 874/874 (100.0%) |
| 11 | 7 | 252/252 (100.0%) | 252/252 (100.0%) |
| 12 | 1 | 34/34 (100.0%) | 34/34 (100.0%) |

Full, by shortest-path length from the start:

| BFS distance | episodes | success | shortest path |
|---|---|---|---|
| 1 | 222 | 222/222 (100.0%) | 222/222 (100.0%) |
| 2 | 220 | 220/220 (100.0%) | 220/220 (100.0%) |
| 3 | 246 | 246/246 (100.0%) | 246/246 (100.0%) |
| 4 | 246 | 246/246 (100.0%) | 246/246 (100.0%) |
| 5 | 240 | 240/240 (100.0%) | 240/240 (100.0%) |
| 6 | 248 | 248/248 (100.0%) | 248/248 (100.0%) |
| 7 | 230 | 230/230 (100.0%) | 230/230 (100.0%) |
| 8 | 242 | 242/242 (100.0%) | 242/242 (100.0%) |
| 9 | 270 | 270/270 (100.0%) | 270/270 (100.0%) |
| 10 | 294 | 294/294 (100.0%) | 294/294 (100.0%) |
| 11 | 344 | 344/344 (100.0%) | 344/344 (100.0%) |
| 12 | 344 | 344/344 (100.0%) | 344/344 (100.0%) |
| 13 | 322 | 322/322 (100.0%) | 322/322 (100.0%) |
| 14 | 248 | 248/248 (100.0%) | 248/248 (100.0%) |
| 15 | 164 | 164/164 (100.0%) | 164/164 (100.0%) |
| 16 | 86 | 86/86 (100.0%) | 86/86 (100.0%) |
| 17 | 24 | 24/24 (100.0%) | 24/24 (100.0%) |
| 18 | 2 | 2/2 (100.0%) | 2/2 (100.0%) |

Reading:

- D1 = 100% optimal: the planner and control loop are correct.
- D2 matches D1: the learned cost D(c) costs nothing.
- D3 matches D1: the learned dynamics costs nothing.
- Full (100% optimal) is no worse than the weaker of D2 / D3: no compounding.
- Random reaches the goal in 3% of episodes (lower bound); Oracle in 100%.
