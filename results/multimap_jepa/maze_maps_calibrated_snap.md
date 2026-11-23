# 200 maze maps (8-14 walls, longest paths): joint JEPA (v2), no retraining

200 layouts never used for training, validation or testing (seed 3; all 100 experiment layouts and the reference map excluded), 8-12 walls, goal (5,0). Navigation starts from every free cell of every map (4024 start cells), seeds [0, 1] -> 8048 episodes per rung. Average shortest path to the goal 8.5 steps, longest 18. Unknown threshold 7.05 (99.9% quantile of correct one-step snap distances, validation maps). Planner: P2 with every imagined step snapped to the codebook.

## Headline

| metric | result |
|---|---|
| navigation success (Full: learned dynamics + learned cost) | 8048/8048 (100.0%) |
| shortest-path accuracy (episodes with exactly the BFS length) | 8048/8048 (100.0%) |
| shortest path, among successful episodes | 8048/8048 (100.0%) |
| maps solved optimally from every start | 200/200 (100.0%) |
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
| D3 | learned | true | 8048/8048 (100.0%) | 8048/8048 (100.0%) | 0.0% | 0 | 0 |
| Full | learned | learned | 8048/8048 (100.0%) | 8048/8048 (100.0%) | 0.0% | 0 | 0 |
| Random | - | - | 213/8048 (2.6%) | 89/8048 (1.1%) | 46.3% | 7835 | 0 |

Full, by number of walls:

| walls | maps | success | shortest path |
|---|---|---|---|
| 8 | 90 | 3780/3780 (100.0%) | 3780/3780 (100.0%) |
| 9 | 61 | 2440/2440 (100.0%) | 2440/2440 (100.0%) |
| 10 | 36 | 1368/1368 (100.0%) | 1368/1368 (100.0%) |
| 11 | 9 | 324/324 (100.0%) | 324/324 (100.0%) |
| 12 | 4 | 136/136 (100.0%) | 136/136 (100.0%) |

Full, by shortest-path length from the start:

| BFS distance | episodes | success | shortest path |
|---|---|---|---|
| 1 | 442 | 442/442 (100.0%) | 442/442 (100.0%) |
| 2 | 466 | 466/466 (100.0%) | 466/466 (100.0%) |
| 3 | 480 | 480/480 (100.0%) | 480/480 (100.0%) |
| 4 | 508 | 508/508 (100.0%) | 508/508 (100.0%) |
| 5 | 474 | 474/474 (100.0%) | 474/474 (100.0%) |
| 6 | 462 | 462/462 (100.0%) | 462/462 (100.0%) |
| 7 | 466 | 466/466 (100.0%) | 466/466 (100.0%) |
| 8 | 496 | 496/496 (100.0%) | 496/496 (100.0%) |
| 9 | 576 | 576/576 (100.0%) | 576/576 (100.0%) |
| 10 | 578 | 578/578 (100.0%) | 578/578 (100.0%) |
| 11 | 666 | 666/666 (100.0%) | 666/666 (100.0%) |
| 12 | 694 | 694/694 (100.0%) | 694/694 (100.0%) |
| 13 | 678 | 678/678 (100.0%) | 678/678 (100.0%) |
| 14 | 514 | 514/514 (100.0%) | 514/514 (100.0%) |
| 15 | 330 | 330/330 (100.0%) | 330/330 (100.0%) |
| 16 | 164 | 164/164 (100.0%) | 164/164 (100.0%) |
| 17 | 44 | 44/44 (100.0%) | 44/44 (100.0%) |
| 18 | 10 | 10/10 (100.0%) | 10/10 (100.0%) |

Reading:

- D1 = 100% optimal: the planner and control loop are correct.
- D2 matches D1: the learned cost D(c) costs nothing.
- D3 matches D1: the learned dynamics costs nothing.
- Full (100% optimal) is no worse than the weaker of D2 / D3: no compounding.
- Random reaches the goal in 3% of episodes (lower bound); Oracle in 100%.
