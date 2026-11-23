# 200 maze maps (8-14 walls, longest paths): joint JEPA (v2), no retraining

200 layouts never used for training, validation or testing (seed 3; all 100 experiment layouts and the reference map excluded), 8-12 walls, goal (5,0). Navigation starts from every free cell of every map (4024 start cells), seeds [0, 1] -> 8048 episodes per rung. Average shortest path to the goal 8.5 steps, longest 18.

## Headline

| metric | result |
|---|---|
| navigation success (Full: learned dynamics + learned cost) | 7566/8048 (94.0%) |
| shortest-path accuracy (episodes with exactly the BFS length) | 7560/8048 (93.9%) |
| shortest path, among successful episodes | 7560/7566 (99.9%) |
| maps solved optimally from every start | 170/200 (85.0%) |
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
| normal moves | 8978/9148 (98.1%) | 170/9148 (1.9%) | 0/9148 (0.0%) |
| border bumps | 3537/3537 (100.0%) | 0/3537 (0.0%) | 0/3537 (0.0%) |
| wall bumps | 4211/4211 (100.0%) | 313/4211 (7.4%) | 0/4211 (0.0%) |
| all | 16726/16896 (99.0%) | 483/16896 (2.9%) | 0/16896 (0.0%) |
| D(c) exact | 3955/4224 (93.6%) cells; 158/200 (79.0%) maps exact everywhere; 0 fake shortcuts | | |

## Navigation and ladder

| rung | dynamics | cost | success | shortest path | collisions / action | loop failures | timeouts |
|---|---|---|---|---|---|---|---|
| Oracle | true | A* | 8048/8048 (100.0%) | 8048/8048 (100.0%) | 0.0% | 0 | 0 |
| D1 | true | true | 8048/8048 (100.0%) | 8048/8048 (100.0%) | 0.0% | 0 | 0 |
| D2 | true | learned | 7997/8048 (99.4%) | 7814/8048 (97.1%) | 0.3% | 49 | 2 |
| D3 | learned | true | 7507/8048 (93.3%) | 7504/8048 (93.2%) | 1.6% | 541 | 0 |
| Full | learned | learned | 7566/8048 (94.0%) | 7560/8048 (93.9%) | 1.2% | 482 | 0 |
| Random | - | - | 213/8048 (2.6%) | 89/8048 (1.1%) | 46.3% | 7835 | 0 |

Full, by number of walls:

| walls | maps | success | shortest path |
|---|---|---|---|
| 8 | 90 | 3628/3780 (96.0%) | 3624/3780 (95.9%) |
| 9 | 61 | 2306/2440 (94.5%) | 2306/2440 (94.5%) |
| 10 | 36 | 1208/1368 (88.3%) | 1206/1368 (88.2%) |
| 11 | 9 | 304/324 (93.8%) | 304/324 (93.8%) |
| 12 | 4 | 120/136 (88.2%) | 120/136 (88.2%) |

Full, by shortest-path length from the start:

| BFS distance | episodes | success | shortest path |
|---|---|---|---|
| 1 | 442 | 442/442 (100.0%) | 442/442 (100.0%) |
| 2 | 466 | 466/466 (100.0%) | 466/466 (100.0%) |
| 3 | 480 | 478/480 (99.6%) | 478/480 (99.6%) |
| 4 | 508 | 496/508 (97.6%) | 496/508 (97.6%) |
| 5 | 474 | 466/474 (98.3%) | 466/474 (98.3%) |
| 6 | 462 | 448/462 (97.0%) | 446/462 (96.5%) |
| 7 | 466 | 444/466 (95.3%) | 444/466 (95.3%) |
| 8 | 496 | 470/496 (94.8%) | 470/496 (94.8%) |
| 9 | 576 | 548/576 (95.1%) | 548/576 (95.1%) |
| 10 | 578 | 538/578 (93.1%) | 538/578 (93.1%) |
| 11 | 666 | 614/666 (92.2%) | 613/666 (92.0%) |
| 12 | 694 | 636/694 (91.6%) | 635/694 (91.5%) |
| 13 | 678 | 604/678 (89.1%) | 604/678 (89.1%) |
| 14 | 514 | 456/514 (88.7%) | 454/514 (88.3%) |
| 15 | 330 | 288/330 (87.3%) | 288/330 (87.3%) |
| 16 | 164 | 138/164 (84.1%) | 138/164 (84.1%) |
| 17 | 44 | 30/44 (68.2%) | 30/44 (68.2%) |
| 18 | 10 | 4/10 (40.0%) | 4/10 (40.0%) |

Maps where Full was not optimal from every start:

| map | walls | optimal | success | wrong edges | D(c) exact |
|---|---|---|---|---|---|
| 9 | 8 | 4/42 | 4/42 | 6 | 3/22 |
| 17 | 10 | 6/38 | 6/38 | 4 | 4/20 |
| 191 | 10 | 6/38 | 6/38 | 4 | 4/20 |
| 7 | 8 | 8/42 | 8/42 | 1 | 5/22 |
| 1 | 9 | 10/40 | 10/40 | 4 | 6/21 |
| 157 | 8 | 12/42 | 12/42 | 3 | 7/22 |
| 4 | 9 | 12/40 | 12/40 | 4 | 6/21 |
| 42 | 9 | 12/40 | 12/40 | 3 | 7/21 |
| 0 | 9 | 14/40 | 14/40 | 2 | 8/21 |
| 103 | 10 | 14/38 | 14/38 | 4 | 7/20 |
| 159 | 8 | 20/42 | 20/42 | 2 | 11/22 |
| 55 | 8 | 22/42 | 22/42 | 4 | 10/22 |
| 165 | 10 | 20/38 | 20/38 | 5 | 10/20 |
| 20 | 12 | 18/34 | 18/34 | 3 | 10/18 |
| 81 | 10 | 22/38 | 22/38 | 7 | 12/20 |

Reading:

- D1 = 100% optimal: the planner and control loop are correct.
- D2 vs D1: the learned cost D(c) costs 1% success and 3% optimal episodes.
- D3 vs D1: the learned dynamics costs 7% success and 7% optimal episodes.
- Full (94% optimal) is no worse than the weaker of D2 / D3: no compounding.
- Random reaches the goal in 3% of episodes (lower bound); Oracle in 100%.
