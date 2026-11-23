# 500 dense-wall maps (8-14 walls): joint JEPA (v2), no retraining

500 layouts never used for training, validation or testing (seed 2; all 100 experiment layouts and the reference map excluded), 8-14 walls, goal (5,0). Navigation starts from every free cell of every map (9840 start cells), seeds [0, 1] -> 19680 episodes per rung. Average shortest path to the goal 5.4 steps, longest 17. Unknown threshold 7.05 (99.9% quantile of correct one-step snap distances, validation maps). Planner: P2 with every imagined step snapped to the codebook.

## Headline

| metric | result |
|---|---|
| navigation success (Full: learned dynamics + learned cost) | 19680/19680 (100.0%) |
| shortest-path accuracy (episodes with exactly the BFS length) | 19680/19680 (100.0%) |
| shortest path, among successful episodes | 19680/19680 (100.0%) |
| maps solved optimally from every start | 500/500 (100.0%) |
| collision accuracy, episode data (stay vs move) | 100.00% of 500000 transitions |
| collision accuracy, every (cell, action) pair: wall bumps | 9868/9868 (100.0%) |
| collision accuracy, every (cell, action) pair: border bumps | 7412/7412 (100.0%) |
| rollout accuracy at 1 / 5 / 10 steps | 100.0% / 80.3% / 54.2% |

## Collisions (episode data)

| | correct |
|---|---|
| blocked moves predicted as blocked | 209305/209305 (100.0%) |
|   interior-wall bumps | 120543/120543 (100.0%) |
|   border bumps | 88762/88762 (100.0%) |
| free moves wrongly predicted as blocked | 0/290695 (0.0%) |
| precision of "blocked" | 100.00% |

## One-step prediction and rollouts (episode data)

| move type | correct |
|---|---|
| normal moves | 290695/290695 (100.0%) |
| border bumps | 88762/88762 (100.0%) |
| wall bumps | 120543/120543 (100.0%) |
| all | 500000/500000 (100.0%) |

Rollout snap accuracy by imagined step (410000 windows):

| 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|
| 100.0% | 98.1% | 92.8% | 86.7% | 80.3% | 74.2% | 68.6% | 63.3% | 58.5% | 54.2% |

## Imagined graph (every cell x action of every map)

| edges | correct | unknown -> self-loop | wrong but trusted |
|---|---|---|---|
| normal moves | 24080/24080 (100.0%) | 0/24080 (0.0%) | 0/24080 (0.0%) |
| border bumps | 7412/7412 (100.0%) | 0/7412 (0.0%) | 0/7412 (0.0%) |
| wall bumps | 9868/9868 (100.0%) | 6/9868 (0.1%) | 0/9868 (0.0%) |
| all | 41360/41360 (100.0%) | 6/41360 (0.0%) | 0/41360 (0.0%) |
| D(c) exact | 10340/10340 (100.0%) cells; 500/500 (100.0%) maps exact everywhere; 0 fake shortcuts | | |

## Navigation and ladder

| rung | dynamics | cost | success | shortest path | collisions / action | loop failures | timeouts |
|---|---|---|---|---|---|---|---|
| Oracle | true | A* | 19680/19680 (100.0%) | 19680/19680 (100.0%) | 0.0% | 0 | 0 |
| D1 | true | true | 19680/19680 (100.0%) | 19680/19680 (100.0%) | 0.0% | 0 | 0 |
| D2 | true | learned | 19680/19680 (100.0%) | 19680/19680 (100.0%) | 0.0% | 0 | 0 |
| D3 | learned | true | 19680/19680 (100.0%) | 19680/19680 (100.0%) | 0.0% | 0 | 0 |
| Full | learned | learned | 19680/19680 (100.0%) | 19680/19680 (100.0%) | 0.0% | 0 | 0 |
| Random | - | - | 1187/19680 (6.0%) | 494/19680 (2.5%) | 40.5% | 18493 | 0 |

Full, by number of walls:

| walls | maps | success | shortest path |
|---|---|---|---|
| 8 | 196 | 8232/8232 (100.0%) | 8232/8232 (100.0%) |
| 9 | 131 | 5240/5240 (100.0%) | 5240/5240 (100.0%) |
| 10 | 77 | 2926/2926 (100.0%) | 2926/2926 (100.0%) |
| 11 | 43 | 1548/1548 (100.0%) | 1548/1548 (100.0%) |
| 12 | 27 | 918/918 (100.0%) | 918/918 (100.0%) |
| 13 | 18 | 576/576 (100.0%) | 576/576 (100.0%) |
| 14 | 8 | 240/240 (100.0%) | 240/240 (100.0%) |

Full, by shortest-path length from the start:

| BFS distance | episodes | success | shortest path |
|---|---|---|---|
| 1 | 1492 | 1492/1492 (100.0%) | 1492/1492 (100.0%) |
| 2 | 1768 | 1768/1768 (100.0%) | 1768/1768 (100.0%) |
| 3 | 2040 | 2040/2040 (100.0%) | 2040/2040 (100.0%) |
| 4 | 2418 | 2418/2418 (100.0%) | 2418/2418 (100.0%) |
| 5 | 2582 | 2582/2582 (100.0%) | 2582/2582 (100.0%) |
| 6 | 2556 | 2556/2556 (100.0%) | 2556/2556 (100.0%) |
| 7 | 2316 | 2316/2316 (100.0%) | 2316/2316 (100.0%) |
| 8 | 1912 | 1912/1912 (100.0%) | 1912/1912 (100.0%) |
| 9 | 1256 | 1256/1256 (100.0%) | 1256/1256 (100.0%) |
| 10 | 578 | 578/578 (100.0%) | 578/578 (100.0%) |
| 11 | 366 | 366/366 (100.0%) | 366/366 (100.0%) |
| 12 | 212 | 212/212 (100.0%) | 212/212 (100.0%) |
| 13 | 106 | 106/106 (100.0%) | 106/106 (100.0%) |
| 14 | 46 | 46/46 (100.0%) | 46/46 (100.0%) |
| 15 | 20 | 20/20 (100.0%) | 20/20 (100.0%) |
| 16 | 6 | 6/6 (100.0%) | 6/6 (100.0%) |
| 17 | 6 | 6/6 (100.0%) | 6/6 (100.0%) |

Reading:

- D1 = 100% optimal: the planner and control loop are correct.
- D2 matches D1: the learned cost D(c) costs nothing.
- D3 matches D1: the learned dynamics costs nothing.
- Full (100% optimal) is no worse than the weaker of D2 / D3: no compounding.
- Random reaches the goal in 6% of episodes (lower bound); Oracle in 100%.
