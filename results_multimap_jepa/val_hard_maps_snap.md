# 100 validation dense-wall maps: joint JEPA (v2), no retraining

100 layouts never used for training, validation or testing (seed 22; all 100 experiment layouts and the reference map excluded), 8-13 walls, goal (5,0). Navigation starts from every free cell of every map (1968 start cells), seeds [0, 1] -> 3936 episodes per rung. Average shortest path to the goal 5.5 steps, longest 16. Unknown threshold 4.25 (3 x median one-step error). Planner: P2 with every imagined step snapped to the codebook.

## Headline

| metric | result |
|---|---|
| navigation success (Full: learned dynamics + learned cost) | 3909/3936 (99.3%) |
| shortest-path accuracy (episodes with exactly the BFS length) | 3887/3936 (98.8%) |
| shortest path, among successful episodes | 3887/3909 (99.4%) |
| maps solved optimally from every start | 95/100 (95.0%) |
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
| Full | learned | learned | 3909/3936 (99.3%) | 3887/3936 (98.8%) | 0.1% | 27 | 0 |
| Random | - | - | 225/3936 (5.7%) | 97/3936 (2.5%) | 40.3% | 3711 | 0 |

Full, by number of walls:

| walls | maps | success | shortest path |
|---|---|---|---|
| 8 | 38 | 1572/1596 (98.5%) | 1566/1596 (98.1%) |
| 9 | 24 | 960/960 (100.0%) | 944/960 (98.3%) |
| 10 | 18 | 684/684 (100.0%) | 684/684 (100.0%) |
| 11 | 11 | 395/396 (99.7%) | 395/396 (99.7%) |
| 12 | 6 | 202/204 (99.0%) | 202/204 (99.0%) |
| 13 | 3 | 96/96 (100.0%) | 96/96 (100.0%) |

Full, by shortest-path length from the start:

| BFS distance | episodes | success | shortest path |
|---|---|---|---|
| 1 | 276 | 276/276 (100.0%) | 276/276 (100.0%) |
| 2 | 380 | 380/380 (100.0%) | 380/380 (100.0%) |
| 3 | 408 | 408/408 (100.0%) | 408/408 (100.0%) |
| 4 | 514 | 512/514 (99.6%) | 512/514 (99.6%) |
| 5 | 468 | 468/468 (100.0%) | 468/468 (100.0%) |
| 6 | 512 | 509/512 (99.4%) | 509/512 (99.4%) |
| 7 | 466 | 464/466 (99.6%) | 464/466 (99.6%) |
| 8 | 392 | 388/392 (99.0%) | 384/392 (98.0%) |
| 9 | 248 | 246/248 (99.2%) | 242/248 (97.6%) |
| 10 | 98 | 94/98 (95.9%) | 90/98 (91.8%) |
| 11 | 64 | 60/64 (93.8%) | 58/64 (90.6%) |
| 12 | 46 | 42/46 (91.3%) | 40/46 (87.0%) |
| 13 | 38 | 36/38 (94.7%) | 34/38 (89.5%) |
| 14 | 16 | 16/16 (100.0%) | 14/16 (87.5%) |
| 15 | 8 | 8/8 (100.0%) | 6/8 (75.0%) |
| 16 | 2 | 2/2 (100.0%) | 2/2 (100.0%) |

Maps where Full was not optimal from every start:

| map | walls | optimal | success | wrong edges | D(c) exact |
|---|---|---|---|---|---|
| 85 | 8 | 18/42 | 18/42 | 2 | 10/22 |
| 67 | 9 | 24/40 | 40/40 | 6 | 13/21 |
| 15 | 8 | 36/42 | 42/42 | 1 | 19/22 |
| 54 | 12 | 32/34 | 32/34 | 5 | 17/18 |
| 91 | 11 | 35/36 | 35/36 | 3 | 18/19 |

Reading:

- D1 = 100% optimal: the planner and control loop are correct.
- D2 vs D1: the learned cost D(c) costs 0% success and 0% optimal episodes.
- D3 vs D1: the learned dynamics costs 2% success and 2% optimal episodes.
- Full (99% optimal) is no worse than the weaker of D2 / D3: no compounding.
- Random reaches the goal in 6% of episodes (lower bound); Oracle in 100%.
