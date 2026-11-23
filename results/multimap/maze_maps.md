# 200 maze maps (8-14 walls, longest paths): v1 model, no retraining

200 layouts never used for training, validation or testing (seed 3; all 100 experiment layouts and the reference map excluded), 8-12 walls, goal (5,0). Navigation starts from every free cell of every map (4024 start cells), seeds [0, 1] -> 8048 episodes per rung. Average shortest path to the goal 8.5 steps, longest 18.

## Headline

| metric | result |
|---|---|
| navigation success (Full: learned dynamics + learned cost) | 831/8048 (10.3%) |
| shortest-path accuracy (episodes with exactly the BFS length) | 762/8048 (9.5%) |
| shortest path, among successful episodes | 762/831 (91.7%) |
| maps solved optimally from every start | 0/200 (0.0%) |
| collision accuracy, episode data (stay vs move) | 65.41% of 200000 transitions |
| collision accuracy, every (cell, action) pair: wall bumps | 4198/4211 (99.7%) |
| collision accuracy, every (cell, action) pair: border bumps | 3535/3537 (99.9%) |
| rollout accuracy at 1 / 5 / 10 steps | 64.1% / 26.1% / 17.0% |

## Collisions (episode data)

| | correct |
|---|---|
| blocked moves predicted as blocked | 90947/91132 (99.8%) |
|   interior-wall bumps | 49997/50155 (99.7%) |
|   border bumps | 40950/40977 (99.9%) |
| free moves wrongly predicted as blocked | 69004/108868 (63.4%) |
| precision of "blocked" | 56.86% |

## One-step prediction and rollouts (episode data)

| move type | correct |
|---|---|
| normal moves | 37356/108868 (34.3%) |
| border bumps | 40950/40977 (99.9%) |
| wall bumps | 49997/50155 (99.7%) |
| all | 128303/200000 (64.2%) |

Rollout snap accuracy by imagined step (164000 windows):

| 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|
| 64.1% | 47.9% | 37.3% | 30.6% | 26.1% | 22.9% | 20.7% | 19.0% | 17.8% | 17.0% |

## Imagined graph (every cell x action of every map)

| edges | correct | unknown -> self-loop | wrong but trusted |
|---|---|---|---|
| normal moves | 3152/9148 (34.5%) | 0/9148 (0.0%) | 5996/9148 (65.5%) |
| border bumps | 3535/3537 (99.9%) | 0/3537 (0.0%) | 2/3537 (0.1%) |
| wall bumps | 4198/4211 (99.7%) | 0/4211 (0.0%) | 13/4211 (0.3%) |
| all | 10885/16896 (64.4%) | 0/16896 (0.0%) | 6011/16896 (35.6%) |
| D(c) exact | 456/4224 (10.8%) cells; 0/200 (0.0%) maps exact everywhere; 444 fake shortcuts | | |

## Navigation and ladder

| rung | dynamics | cost | success | shortest path | collisions / action | loop failures | timeouts |
|---|---|---|---|---|---|---|---|
| Oracle | true | A* | 8048/8048 (100.0%) | 8048/8048 (100.0%) | 0.0% | 0 | 0 |
| D1 | true | true | 8048/8048 (100.0%) | 8048/8048 (100.0%) | 0.0% | 0 | 0 |
| D2 | true | learned | 3999/8048 (49.7%) | 2753/8048 (34.2%) | 11.2% | 4017 | 32 |
| D3 | learned | true | 838/8048 (10.4%) | 620/8048 (7.7%) | 26.3% | 7210 | 0 |
| Full | learned | learned | 831/8048 (10.3%) | 762/8048 (9.5%) | 24.4% | 7217 | 0 |
| Random | - | - | 213/8048 (2.6%) | 89/8048 (1.1%) | 46.3% | 7835 | 0 |

Full, by number of walls:

| walls | maps | success | shortest path |
|---|---|---|---|
| 8 | 90 | 430/3780 (11.4%) | 386/3780 (10.2%) |
| 9 | 61 | 271/2440 (11.1%) | 247/2440 (10.1%) |
| 10 | 36 | 98/1368 (7.2%) | 97/1368 (7.1%) |
| 11 | 9 | 26/324 (8.0%) | 26/324 (8.0%) |
| 12 | 4 | 6/136 (4.4%) | 6/136 (4.4%) |

Full, by shortest-path length from the start:

| BFS distance | episodes | success | shortest path |
|---|---|---|---|
| 1 | 442 | 355/442 (80.3%) | 353/442 (79.9%) |
| 2 | 466 | 204/466 (43.8%) | 189/466 (40.6%) |
| 3 | 480 | 134/480 (27.9%) | 123/480 (25.6%) |
| 4 | 508 | 60/508 (11.8%) | 39/508 (7.7%) |
| 5 | 474 | 30/474 (6.3%) | 24/474 (5.1%) |
| 6 | 462 | 18/462 (3.9%) | 11/462 (2.4%) |
| 7 | 466 | 10/466 (2.1%) | 9/466 (1.9%) |
| 8 | 496 | 7/496 (1.4%) | 5/496 (1.0%) |
| 9 | 576 | 7/576 (1.2%) | 6/576 (1.0%) |
| 10 | 578 | 4/578 (0.7%) | 3/578 (0.5%) |
| 11 | 666 | 2/666 (0.3%) | 0/666 (0.0%) |
| 12 | 694 | 0/694 (0.0%) | 0/694 (0.0%) |
| 13 | 678 | 0/678 (0.0%) | 0/678 (0.0%) |
| 14 | 514 | 0/514 (0.0%) | 0/514 (0.0%) |
| 15 | 330 | 0/330 (0.0%) | 0/330 (0.0%) |
| 16 | 164 | 0/164 (0.0%) | 0/164 (0.0%) |
| 17 | 44 | 0/44 (0.0%) | 0/44 (0.0%) |
| 18 | 10 | 0/10 (0.0%) | 0/10 (0.0%) |

Maps where Full was not optimal from every start:

| map | walls | optimal | success | wrong edges | D(c) exact |
|---|---|---|---|---|---|
| 1 | 9 | 0/40 | 0/40 | 41 | 1/21 |
| 3 | 9 | 0/40 | 0/40 | 30 | 1/21 |
| 6 | 8 | 0/42 | 0/42 | 29 | 1/22 |
| 27 | 10 | 0/38 | 0/38 | 32 | 1/20 |
| 33 | 9 | 0/40 | 0/40 | 32 | 1/21 |
| 34 | 9 | 0/40 | 0/40 | 25 | 1/21 |
| 39 | 12 | 0/34 | 0/34 | 27 | 1/18 |
| 50 | 9 | 0/40 | 0/40 | 45 | 1/21 |
| 51 | 10 | 0/38 | 0/38 | 38 | 1/20 |
| 59 | 10 | 0/38 | 0/38 | 41 | 1/20 |
| 67 | 8 | 0/42 | 0/42 | 39 | 1/22 |
| 68 | 9 | 0/40 | 0/40 | 37 | 1/21 |
| 75 | 8 | 0/42 | 0/42 | 40 | 1/22 |
| 76 | 8 | 0/42 | 0/42 | 32 | 2/22 |
| 80 | 10 | 0/38 | 0/38 | 41 | 1/20 |

Reading:

- D1 = 100% optimal: the planner and control loop are correct.
- D2 vs D1: the learned cost D(c) costs 50% success and 66% optimal episodes.
- D3 vs D1: the learned dynamics costs 90% success and 92% optimal episodes.
- Full (9% optimal) is no worse than the weaker of D2 / D3: no compounding.
- Random reaches the goal in 3% of episodes (lower bound); Oracle in 100%.
