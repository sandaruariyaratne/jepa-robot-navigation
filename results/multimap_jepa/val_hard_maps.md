# 100 validation dense-wall maps: joint JEPA (v2), no retraining

100 layouts never used for training, validation or testing (seed 22; all 100 experiment layouts and the reference map excluded), 8-13 walls, goal (5,0). Navigation starts from every free cell of every map (1968 start cells), seeds [0, 1] -> 3936 episodes per rung. Average shortest path to the goal 5.5 steps, longest 16. Unknown threshold 4.25 (3 x median one-step error).

## Headline

| metric | result |
|---|---|
| navigation success (Full: learned dynamics + learned cost) | 3866/3936 (98.2%) |
| shortest-path accuracy (episodes with exactly the BFS length) | 3846/3936 (97.7%) |
| shortest path, among successful episodes | 3846/3866 (99.5%) |
| maps solved optimally from every start | 87/100 (87.0%) |
| collision accuracy, episode data (stay vs move) | 99.99% of 100000 transitions |
| collision accuracy, every (cell, action) pair: wall bumps | 1980/1980 (100.0%) |
| collision accuracy, every (cell, action) pair: border bumps | 1480/1480 (100.0%) |
| rollout accuracy at 1 / 5 / 10 steps | 100.0% / 80.9% / 54.8% |

## Collisions (episode data)

| | correct |
|---|---|
| blocked moves predicted as blocked | 41728/41739 (100.0%) |
|   interior-wall bumps | 24084/24095 (100.0%) |
|   border bumps | 17644/17644 (100.0%) |
| free moves wrongly predicted as blocked | 0/58261 (0.0%) |
| precision of "blocked" | 100.00% |

## One-step prediction and rollouts (episode data)

| move type | correct |
|---|---|
| normal moves | 58261/58261 (100.0%) |
| border bumps | 17644/17644 (100.0%) |
| wall bumps | 24084/24095 (100.0%) |
| all | 99989/100000 (100.0%) |

Rollout snap accuracy by imagined step (82000 windows):

| 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|
| 100.0% | 98.1% | 93.1% | 87.0% | 80.9% | 75.0% | 69.4% | 64.1% | 59.2% | 54.8% |

## Imagined graph (every cell x action of every map)

| edges | correct | unknown -> self-loop | wrong but trusted |
|---|---|---|---|
| normal moves | 4721/4812 (98.1%) | 91/4812 (1.9%) | 0/4812 (0.0%) |
| border bumps | 1480/1480 (100.0%) | 0/1480 (0.0%) | 0/1480 (0.0%) |
| wall bumps | 1980/1980 (100.0%) | 108/1980 (5.5%) | 0/1980 (0.0%) |
| all | 8181/8272 (98.9%) | 199/8272 (2.4%) | 0/8272 (0.0%) |
| D(c) exact | 2022/2068 (97.8%) cells; 86/100 (86.0%) maps exact everywhere; 0 fake shortcuts | | |

## Navigation and ladder

| rung | dynamics | cost | success | shortest path | collisions / action | loop failures | timeouts |
|---|---|---|---|---|---|---|---|
| Oracle | true | A* | 3936/3936 (100.0%) | 3936/3936 (100.0%) | 0.0% | 0 | 0 |
| D1 | true | true | 3936/3936 (100.0%) | 3936/3936 (100.0%) | 0.0% | 0 | 0 |
| D2 | true | learned | 3934/3936 (99.9%) | 3927/3936 (99.8%) | 0.1% | 2 | 0 |
| D3 | learned | true | 3849/3936 (97.8%) | 3843/3936 (97.6%) | 0.8% | 87 | 0 |
| Full | learned | learned | 3866/3936 (98.2%) | 3846/3936 (97.7%) | 0.6% | 70 | 0 |
| Random | - | - | 225/3936 (5.7%) | 97/3936 (2.5%) | 40.3% | 3711 | 0 |

Full, by number of walls:

| walls | maps | success | shortest path |
|---|---|---|---|
| 8 | 38 | 1560/1596 (97.7%) | 1556/1596 (97.5%) |
| 9 | 24 | 954/960 (99.4%) | 938/960 (97.7%) |
| 10 | 18 | 682/684 (99.7%) | 682/684 (99.7%) |
| 11 | 11 | 380/396 (96.0%) | 380/396 (96.0%) |
| 12 | 6 | 202/204 (99.0%) | 202/204 (99.0%) |
| 13 | 3 | 88/96 (91.7%) | 88/96 (91.7%) |

Full, by shortest-path length from the start:

| BFS distance | episodes | success | shortest path |
|---|---|---|---|
| 1 | 276 | 276/276 (100.0%) | 276/276 (100.0%) |
| 2 | 380 | 380/380 (100.0%) | 380/380 (100.0%) |
| 3 | 408 | 408/408 (100.0%) | 408/408 (100.0%) |
| 4 | 514 | 512/514 (99.6%) | 512/514 (99.6%) |
| 5 | 468 | 466/468 (99.6%) | 466/468 (99.6%) |
| 6 | 512 | 504/512 (98.4%) | 504/512 (98.4%) |
| 7 | 466 | 458/466 (98.3%) | 458/466 (98.3%) |
| 8 | 392 | 382/392 (97.4%) | 380/392 (96.9%) |
| 9 | 248 | 240/248 (96.8%) | 236/248 (95.2%) |
| 10 | 98 | 94/98 (95.9%) | 90/98 (91.8%) |
| 11 | 64 | 54/64 (84.4%) | 52/64 (81.2%) |
| 12 | 46 | 36/46 (78.3%) | 34/46 (73.9%) |
| 13 | 38 | 30/38 (78.9%) | 28/38 (73.7%) |
| 14 | 16 | 16/16 (100.0%) | 14/16 (87.5%) |
| 15 | 8 | 8/8 (100.0%) | 6/8 (75.0%) |
| 16 | 2 | 2/2 (100.0%) | 2/2 (100.0%) |

Maps where Full was not optimal from every start:

| map | walls | optimal | success | wrong edges | D(c) exact |
|---|---|---|---|---|---|
| 85 | 8 | 18/42 | 18/42 | 2 | 10/22 |
| 67 | 9 | 24/40 | 40/40 | 6 | 13/21 |
| 29 | 11 | 26/36 | 26/36 | 11 | 14/19 |
| 77 | 13 | 24/32 | 24/32 | 6 | 13/17 |
| 51 | 8 | 34/42 | 34/42 | 1 | 18/22 |
| 84 | 9 | 34/40 | 34/40 | 5 | 18/21 |
| 15 | 8 | 36/42 | 40/42 | 1 | 19/22 |
| 54 | 12 | 32/34 | 32/34 | 5 | 17/18 |
| 28 | 11 | 34/36 | 34/36 | 6 | 18/19 |
| 61 | 11 | 34/36 | 34/36 | 9 | 18/19 |
| 91 | 11 | 34/36 | 34/36 | 3 | 18/19 |
| 4 | 10 | 36/38 | 36/38 | 5 | 19/20 |
| 5 | 8 | 40/42 | 40/42 | 1 | 21/22 |

Reading:

- D1 = 100% optimal: the planner and control loop are correct.
- D2 vs D1: the learned cost D(c) costs 0% success and 0% optimal episodes.
- D3 vs D1: the learned dynamics costs 2% success and 2% optimal episodes.
- Full (98% optimal) is no worse than the weaker of D2 / D3: no compounding.
- Random reaches the goal in 6% of episodes (lower bound); Oracle in 100%.
