# 500 new maps: joint JEPA (v2), no retraining

500 layouts never used for training, validation or testing (seed 1; all 100 experiment layouts and the reference map excluded), 3-7 walls, goal (5,0). Navigation starts from every free cell of every map (12073 start cells), seeds [0, 1] -> 24146 episodes per rung. Average shortest path to the goal 5.0 steps, longest 14. Unknown threshold 7.05 (99.9% quantile of correct one-step snap distances, validation maps).

## Headline

| metric | result |
|---|---|
| navigation success (Full: learned dynamics + learned cost) | 23603/24146 (97.8%) |
| shortest-path accuracy (episodes with exactly the BFS length) | 23433/24146 (97.0%) |
| shortest path, among successful episodes | 23433/23603 (99.3%) |
| maps solved optimally from every start | 370/500 (74.0%) |
| collision accuracy, episode data (stay vs move) | 100.00% of 500000 transitions |
| collision accuracy, every (cell, action) pair: wall bumps | 6744/6744 (100.0%) |
| collision accuracy, every (cell, action) pair: border bumps | 9312/9312 (100.0%) |
| rollout accuracy at 1 / 5 / 10 steps | 100.0% / 89.5% / 68.8% |

## Collisions (episode data)

| | correct |
|---|---|
| blocked moves predicted as blocked | 161030/161030 (100.0%) |
|   interior-wall bumps | 68496/68496 (100.0%) |
|   border bumps | 92534/92534 (100.0%) |
| free moves wrongly predicted as blocked | 0/338970 (0.0%) |
| precision of "blocked" | 100.00% |

## One-step prediction and rollouts (episode data)

| move type | correct |
|---|---|
| normal moves | 338970/338970 (100.0%) |
| border bumps | 92534/92534 (100.0%) |
| wall bumps | 68496/68496 (100.0%) |
| all | 500000/500000 (100.0%) |

Rollout snap accuracy by imagined step (410000 windows):

| 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|
| 100.0% | 99.2% | 96.7% | 93.3% | 89.5% | 85.3% | 81.1% | 76.9% | 72.8% | 68.8% |

## Imagined graph (every cell x action of every map)

| edges | correct | unknown -> self-loop | wrong but trusted |
|---|---|---|---|
| normal moves | 34236/34236 (100.0%) | 0/34236 (0.0%) | 0/34236 (0.0%) |
| border bumps | 9312/9312 (100.0%) | 0/9312 (0.0%) | 0/9312 (0.0%) |
| wall bumps | 6744/6744 (100.0%) | 3/6744 (0.0%) | 0/6744 (0.0%) |
| all | 50292/50292 (100.0%) | 3/50292 (0.0%) | 0/50292 (0.0%) |
| D(c) exact | 12573/12573 (100.0%) cells; 500/500 (100.0%) maps exact everywhere; 0 fake shortcuts | | |

## Navigation and ladder

| rung | dynamics | cost | success | shortest path | collisions / action | loop failures | timeouts |
|---|---|---|---|---|---|---|---|
| Oracle | true | A* | 24146/24146 (100.0%) | 24146/24146 (100.0%) | 0.0% | 0 | 0 |
| D1 | true | true | 24146/24146 (100.0%) | 24146/24146 (100.0%) | 0.0% | 0 | 0 |
| D2 | true | learned | 24146/24146 (100.0%) | 24146/24146 (100.0%) | 0.0% | 0 | 0 |
| D3 | learned | true | 23603/24146 (97.8%) | 23433/24146 (97.0%) | 0.8% | 543 | 0 |
| Full | learned | learned | 23603/24146 (97.8%) | 23433/24146 (97.0%) | 0.8% | 543 | 0 |
| Random | - | - | 1621/24146 (6.7%) | 777/24146 (3.2%) | 30.3% | 22525 | 0 |

Full, by number of walls:

| walls | maps | success | shortest path |
|---|---|---|---|
| 3 | 108 | 5579/5616 (99.3%) | 5575/5616 (99.3%) |
| 4 | 104 | 5135/5200 (98.8%) | 5106/5200 (98.2%) |
| 5 | 115 | 5406/5520 (97.9%) | 5388/5520 (97.6%) |
| 6 | 99 | 4387/4554 (96.3%) | 4320/4554 (94.9%) |
| 7 | 74 | 3096/3256 (95.1%) | 3044/3256 (93.5%) |

Full, by shortest-path length from the start:

| BFS distance | episodes | success | shortest path |
|---|---|---|---|
| 1 | 1678 | 1678/1678 (100.0%) | 1678/1678 (100.0%) |
| 2 | 2252 | 2252/2252 (100.0%) | 2252/2252 (100.0%) |
| 3 | 2758 | 2758/2758 (100.0%) | 2758/2758 (100.0%) |
| 4 | 3426 | 3426/3426 (100.0%) | 3420/3426 (99.8%) |
| 5 | 3724 | 3718/3724 (99.8%) | 3711/3724 (99.7%) |
| 6 | 3574 | 3532/3574 (98.8%) | 3518/3574 (98.4%) |
| 7 | 3010 | 2950/3010 (98.0%) | 2922/3010 (97.1%) |
| 8 | 2094 | 1986/2094 (94.8%) | 1934/2094 (92.4%) |
| 9 | 1168 | 1071/1168 (91.7%) | 1036/1168 (88.7%) |
| 10 | 242 | 138/242 (57.0%) | 122/242 (50.4%) |
| 11 | 118 | 65/118 (55.1%) | 57/118 (48.3%) |
| 12 | 54 | 19/54 (35.2%) | 15/54 (27.8%) |
| 13 | 34 | 10/34 (29.4%) | 10/34 (29.4%) |
| 14 | 14 | 0/14 (0.0%) | 0/14 (0.0%) |

Maps where Full was not optimal from every start:

| map | walls | optimal | success | wrong edges | D(c) exact |
|---|---|---|---|---|---|
| 471 | 7 | 12/44 | 12/44 | 0 | 23/23 |
| 53 | 6 | 20/46 | 32/46 | 0 | 24/24 |
| 414 | 7 | 28/44 | 28/44 | 0 | 23/23 |
| 393 | 6 | 30/46 | 34/46 | 0 | 24/24 |
| 238 | 6 | 31/46 | 40/46 | 0 | 24/24 |
| 106 | 6 | 32/46 | 40/46 | 0 | 24/24 |
| 1 | 7 | 31/44 | 31/44 | 0 | 23/23 |
| 137 | 7 | 32/44 | 32/44 | 0 | 23/23 |
| 261 | 7 | 32/44 | 32/44 | 0 | 23/23 |
| 117 | 5 | 35/48 | 36/48 | 0 | 25/25 |
| 430 | 6 | 34/46 | 43/46 | 0 | 24/24 |
| 36 | 6 | 35/46 | 37/46 | 0 | 24/24 |
| 162 | 6 | 35/46 | 35/46 | 0 | 24/24 |
| 419 | 6 | 35/46 | 35/46 | 0 | 24/24 |
| 378 | 5 | 37/48 | 37/48 | 0 | 25/25 |

Reading:

- D1 = 100% optimal: the planner and control loop are correct.
- D2 matches D1: the learned cost D(c) costs nothing.
- D3 vs D1: the learned dynamics costs 2% success and 3% optimal episodes.
- Full (97% optimal) is no worse than the weaker of D2 / D3: no compounding.
- Random reaches the goal in 7% of episodes (lower bound); Oracle in 100%.
