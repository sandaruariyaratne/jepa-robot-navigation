# 100 validation dense-wall maps: joint JEPA (v2), no retraining

100 layouts never used for training, validation or testing (seed 22; all 100 experiment layouts and the reference map excluded), 8-13 walls, goal (5,0). Navigation starts from every free cell of every map (1968 start cells), seeds [0, 1] -> 3936 episodes per rung. Average shortest path to the goal 5.5 steps, longest 16. Unknown threshold 7.05 (99.9% quantile of correct one-step snap distances, validation maps). Planner: P2 with every imagined step snapped to the codebook.

## Headline

| metric | result |
|---|---|
| navigation success (Full: learned dynamics + learned cost) | 3936/3936 (100.0%) |
| shortest-path accuracy (episodes with exactly the BFS length) | 3936/3936 (100.0%) |
| shortest path, among successful episodes | 3936/3936 (100.0%) |
| maps solved optimally from every start | 100/100 (100.0%) |
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
| normal moves | 4812/4812 (100.0%) | 0/4812 (0.0%) | 0/4812 (0.0%) |
| border bumps | 1480/1480 (100.0%) | 0/1480 (0.0%) | 0/1480 (0.0%) |
| wall bumps | 1980/1980 (100.0%) | 5/1980 (0.3%) | 0/1980 (0.0%) |
| all | 8272/8272 (100.0%) | 5/8272 (0.1%) | 0/8272 (0.0%) |
| D(c) exact | 2068/2068 (100.0%) cells; 100/100 (100.0%) maps exact everywhere; 0 fake shortcuts | | |

## Navigation and ladder

| rung | dynamics | cost | success | shortest path | collisions / action | loop failures | timeouts |
|---|---|---|---|---|---|---|---|
| Oracle | true | A* | 3936/3936 (100.0%) | 3936/3936 (100.0%) | 0.0% | 0 | 0 |
| D1 | true | true | 3936/3936 (100.0%) | 3936/3936 (100.0%) | 0.0% | 0 | 0 |
| D2 | true | learned | 3936/3936 (100.0%) | 3936/3936 (100.0%) | 0.0% | 0 | 0 |
| D3 | learned | true | 3936/3936 (100.0%) | 3936/3936 (100.0%) | 0.0% | 0 | 0 |
| Full | learned | learned | 3936/3936 (100.0%) | 3936/3936 (100.0%) | 0.0% | 0 | 0 |
| Random | - | - | 225/3936 (5.7%) | 97/3936 (2.5%) | 40.3% | 3711 | 0 |

Full, by number of walls:

| walls | maps | success | shortest path |
|---|---|---|---|
| 8 | 38 | 1596/1596 (100.0%) | 1596/1596 (100.0%) |
| 9 | 24 | 960/960 (100.0%) | 960/960 (100.0%) |
| 10 | 18 | 684/684 (100.0%) | 684/684 (100.0%) |
| 11 | 11 | 396/396 (100.0%) | 396/396 (100.0%) |
| 12 | 6 | 204/204 (100.0%) | 204/204 (100.0%) |
| 13 | 3 | 96/96 (100.0%) | 96/96 (100.0%) |

Full, by shortest-path length from the start:

| BFS distance | episodes | success | shortest path |
|---|---|---|---|
| 1 | 276 | 276/276 (100.0%) | 276/276 (100.0%) |
| 2 | 380 | 380/380 (100.0%) | 380/380 (100.0%) |
| 3 | 408 | 408/408 (100.0%) | 408/408 (100.0%) |
| 4 | 514 | 514/514 (100.0%) | 514/514 (100.0%) |
| 5 | 468 | 468/468 (100.0%) | 468/468 (100.0%) |
| 6 | 512 | 512/512 (100.0%) | 512/512 (100.0%) |
| 7 | 466 | 466/466 (100.0%) | 466/466 (100.0%) |
| 8 | 392 | 392/392 (100.0%) | 392/392 (100.0%) |
| 9 | 248 | 248/248 (100.0%) | 248/248 (100.0%) |
| 10 | 98 | 98/98 (100.0%) | 98/98 (100.0%) |
| 11 | 64 | 64/64 (100.0%) | 64/64 (100.0%) |
| 12 | 46 | 46/46 (100.0%) | 46/46 (100.0%) |
| 13 | 38 | 38/38 (100.0%) | 38/38 (100.0%) |
| 14 | 16 | 16/16 (100.0%) | 16/16 (100.0%) |
| 15 | 8 | 8/8 (100.0%) | 8/8 (100.0%) |
| 16 | 2 | 2/2 (100.0%) | 2/2 (100.0%) |

Reading:

- D1 = 100% optimal: the planner and control loop are correct.
- D2 matches D1: the learned cost D(c) costs nothing.
- D3 matches D1: the learned dynamics costs nothing.
- Full (100% optimal) is no worse than the weaker of D2 / D3: no compounding.
- Random reaches the goal in 6% of episodes (lower bound); Oracle in 100%.
