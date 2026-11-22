# 200 maze maps (8-14 walls, longest paths): joint JEPA (v2), no retraining

200 layouts never used for training, validation or testing (seed 3; all 100 experiment layouts and the reference map excluded), 8-12 walls, goal (5,0). Navigation starts from every free cell of every map (4024 start cells), seeds [0, 1] -> 8048 episodes per rung. Average shortest path to the goal 8.5 steps, longest 18. Unknown threshold 7.05 (99.9% quantile of correct one-step snap distances, validation maps).

## Headline

| metric | result |
|---|---|
| navigation success (Full: learned dynamics + learned cost) | 6234/8048 (77.5%) |
| shortest-path accuracy (episodes with exactly the BFS length) | 6007/8048 (74.6%) |
| shortest path, among successful episodes | 6007/6234 (96.4%) |
| maps solved optimally from every start | 39/200 (19.5%) |
| collision accuracy, episode data (stay vs move) | 99.99% of 200000 transitions |
| collision accuracy, every (cell, action) pair: wall bumps | 4211/4211 (100.0%) |
| collision accuracy, every (cell, action) pair: border bumps | 3537/3537 (100.0%) |
| rollout accuracy at 1 / 5 / 10 steps | 100.0% / 81.0% / 55.1% |

## Collisions (episode data)

| | correct |
|---|---|
| blocked moves predicted as blocked | 91112/91132 (100.0%) |
|   interior-wall bumps | 50135/50155 (100.0%) |
|   border bumps | 40977/40977 (100.0%) |
| free moves wrongly predicted as blocked | 0/108868 (0.0%) |
| precision of "blocked" | 100.00% |

## One-step prediction and rollouts (episode data)

| move type | correct |
|---|---|
| normal moves | 108868/108868 (100.0%) |
| border bumps | 40977/40977 (100.0%) |
| wall bumps | 50135/50155 (100.0%) |
| all | 199980/200000 (100.0%) |

Rollout snap accuracy by imagined step (164000 windows):

| 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|
| 100.0% | 97.9% | 92.8% | 87.1% | 81.0% | 75.1% | 69.7% | 64.4% | 59.5% | 55.1% |

## Imagined graph (every cell x action of every map)

| edges | correct | unknown -> self-loop | wrong but trusted |
|---|---|---|---|
| normal moves | 9148/9148 (100.0%) | 0/9148 (0.0%) | 0/9148 (0.0%) |
| border bumps | 3537/3537 (100.0%) | 0/3537 (0.0%) | 0/3537 (0.0%) |
| wall bumps | 4211/4211 (100.0%) | 6/4211 (0.1%) | 0/4211 (0.0%) |
| all | 16896/16896 (100.0%) | 6/16896 (0.0%) | 0/16896 (0.0%) |
| D(c) exact | 4224/4224 (100.0%) cells; 200/200 (100.0%) maps exact everywhere; 0 fake shortcuts | | |

## Navigation and ladder

| rung | dynamics | cost | success | shortest path | collisions / action | loop failures | timeouts |
|---|---|---|---|---|---|---|---|
| Oracle | true | A* | 8048/8048 (100.0%) | 8048/8048 (100.0%) | 0.0% | 0 | 0 |
| D1 | true | true | 8048/8048 (100.0%) | 8048/8048 (100.0%) | 0.0% | 0 | 0 |
| D2 | true | learned | 8048/8048 (100.0%) | 8048/8048 (100.0%) | 0.0% | 0 | 0 |
| D3 | learned | true | 6234/8048 (77.5%) | 6007/8048 (74.6%) | 4.2% | 1814 | 0 |
| Full | learned | learned | 6234/8048 (77.5%) | 6007/8048 (74.6%) | 4.2% | 1814 | 0 |
| Random | - | - | 213/8048 (2.6%) | 89/8048 (1.1%) | 46.3% | 7835 | 0 |

Full, by number of walls:

| walls | maps | success | shortest path |
|---|---|---|---|
| 8 | 90 | 2937/3780 (77.7%) | 2799/3780 (74.0%) |
| 9 | 61 | 1852/2440 (75.9%) | 1799/2440 (73.7%) |
| 10 | 36 | 1069/1368 (78.1%) | 1044/1368 (76.3%) |
| 11 | 9 | 262/324 (80.9%) | 251/324 (77.5%) |
| 12 | 4 | 114/136 (83.8%) | 114/136 (83.8%) |

Full, by shortest-path length from the start:

| BFS distance | episodes | success | shortest path |
|---|---|---|---|
| 1 | 442 | 442/442 (100.0%) | 442/442 (100.0%) |
| 2 | 466 | 466/466 (100.0%) | 466/466 (100.0%) |
| 3 | 480 | 480/480 (100.0%) | 480/480 (100.0%) |
| 4 | 508 | 508/508 (100.0%) | 508/508 (100.0%) |
| 5 | 474 | 472/474 (99.6%) | 472/474 (99.6%) |
| 6 | 462 | 458/462 (99.1%) | 458/462 (99.1%) |
| 7 | 466 | 434/466 (93.1%) | 422/466 (90.6%) |
| 8 | 496 | 420/496 (84.7%) | 398/496 (80.2%) |
| 9 | 576 | 477/576 (82.8%) | 449/576 (78.0%) |
| 10 | 578 | 425/578 (73.5%) | 392/578 (67.8%) |
| 11 | 666 | 439/666 (65.9%) | 408/666 (61.3%) |
| 12 | 694 | 411/694 (59.2%) | 380/694 (54.8%) |
| 13 | 678 | 372/678 (54.9%) | 343/678 (50.6%) |
| 14 | 514 | 244/514 (47.5%) | 221/514 (43.0%) |
| 15 | 330 | 128/330 (38.8%) | 114/330 (34.5%) |
| 16 | 164 | 50/164 (30.5%) | 46/164 (28.0%) |
| 17 | 44 | 6/44 (13.6%) | 6/44 (13.6%) |
| 18 | 10 | 2/10 (20.0%) | 2/10 (20.0%) |

Maps where Full was not optimal from every start:

| map | walls | optimal | success | wrong edges | D(c) exact |
|---|---|---|---|---|---|
| 3 | 9 | 8/40 | 8/40 | 0 | 21/21 |
| 2 | 10 | 10/38 | 10/38 | 0 | 20/20 |
| 108 | 8 | 12/42 | 12/42 | 0 | 22/22 |
| 32 | 9 | 12/40 | 12/40 | 0 | 21/21 |
| 145 | 9 | 12/40 | 28/40 | 0 | 21/21 |
| 85 | 11 | 12/36 | 12/36 | 0 | 19/19 |
| 118 | 8 | 14/42 | 14/42 | 0 | 22/22 |
| 154 | 8 | 14/42 | 14/42 | 0 | 22/22 |
| 196 | 9 | 14/40 | 14/40 | 0 | 21/21 |
| 67 | 8 | 15/42 | 15/42 | 0 | 22/22 |
| 5 | 10 | 14/38 | 14/38 | 0 | 20/20 |
| 168 | 10 | 14/38 | 28/38 | 0 | 20/20 |
| 192 | 10 | 14/38 | 14/38 | 0 | 20/20 |
| 14 | 8 | 16/42 | 16/42 | 0 | 22/22 |
| 57 | 8 | 16/42 | 16/42 | 0 | 22/22 |

Reading:

- D1 = 100% optimal: the planner and control loop are correct.
- D2 matches D1: the learned cost D(c) costs nothing.
- D3 vs D1: the learned dynamics costs 23% success and 25% optimal episodes.
- Full (75% optimal) is no worse than the weaker of D2 / D3: no compounding.
- Random reaches the goal in 3% of episodes (lower bound); Oracle in 100%.
