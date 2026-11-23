# 500 dense-wall maps (8-14 walls): v1 model, no retraining

500 layouts never used for training, validation or testing (seed 2; all 100 experiment layouts and the reference map excluded), 8-14 walls, goal (5,0). Navigation starts from every free cell of every map (9840 start cells), seeds [0, 1] -> 19680 episodes per rung. Average shortest path to the goal 5.4 steps, longest 17.

## Headline

| metric | result |
|---|---|
| navigation success (Full: learned dynamics + learned cost) | 2582/19680 (13.1%) |
| shortest-path accuracy (episodes with exactly the BFS length) | 2304/19680 (11.7%) |
| shortest path, among successful episodes | 2304/2582 (89.2%) |
| maps solved optimally from every start | 0/500 (0.0%) |
| collision accuracy, episode data (stay vs move) | 56.60% of 500000 transitions |
| collision accuracy, every (cell, action) pair: wall bumps | 9847/9868 (99.8%) |
| collision accuracy, every (cell, action) pair: border bumps | 7405/7412 (99.9%) |
| rollout accuracy at 1 / 5 / 10 steps | 55.3% / 23.2% / 15.3% |

## Collisions (episode data)

| | correct |
|---|---|
| blocked moves predicted as blocked | 208927/209305 (99.8%) |
|   interior-wall bumps | 120228/120543 (99.7%) |
|   border bumps | 88699/88762 (99.9%) |
| free moves wrongly predicted as blocked | 216631/290695 (74.5%) |
| precision of "blocked" | 49.09% |

## One-step prediction and rollouts (episode data)

| move type | correct |
|---|---|
| normal moves | 67781/290695 (23.3%) |
| border bumps | 88699/88762 (99.9%) |
| wall bumps | 120228/120543 (99.7%) |
| all | 276708/500000 (55.3%) |

Rollout snap accuracy by imagined step (410000 windows):

| 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|
| 55.3% | 42.5% | 32.3% | 27.2% | 23.2% | 20.7% | 18.8% | 17.4% | 16.2% | 15.3% |

## Imagined graph (every cell x action of every map)

| edges | correct | unknown -> self-loop | wrong but trusted |
|---|---|---|---|
| normal moves | 5674/24080 (23.6%) | 0/24080 (0.0%) | 18406/24080 (76.4%) |
| border bumps | 7405/7412 (99.9%) | 0/7412 (0.0%) | 7/7412 (0.1%) |
| wall bumps | 9847/9868 (99.8%) | 0/9868 (0.0%) | 21/9868 (0.2%) |
| all | 22926/41360 (55.4%) | 0/41360 (0.0%) | 18434/41360 (44.6%) |
| D(c) exact | 1169/10340 (11.3%) cells; 2/500 (0.4%) maps exact everywhere; 884 fake shortcuts | | |

## Navigation and ladder

| rung | dynamics | cost | success | shortest path | collisions / action | loop failures | timeouts |
|---|---|---|---|---|---|---|---|
| Oracle | true | A* | 19680/19680 (100.0%) | 19680/19680 (100.0%) | 0.0% | 0 | 0 |
| D1 | true | true | 19680/19680 (100.0%) | 19680/19680 (100.0%) | 0.0% | 0 | 0 |
| D2 | true | learned | 13013/19680 (66.1%) | 9446/19680 (48.0%) | 9.6% | 6659 | 8 |
| D3 | learned | true | 2749/19680 (14.0%) | 1843/19680 (9.4%) | 27.3% | 16931 | 0 |
| Full | learned | learned | 2582/19680 (13.1%) | 2304/19680 (11.7%) | 22.4% | 17098 | 0 |
| Random | - | - | 1187/19680 (6.0%) | 494/19680 (2.5%) | 40.5% | 18493 | 0 |

Full, by number of walls:

| walls | maps | success | shortest path |
|---|---|---|---|
| 8 | 196 | 1309/8232 (15.9%) | 1146/8232 (13.9%) |
| 9 | 131 | 635/5240 (12.1%) | 560/5240 (10.7%) |
| 10 | 77 | 320/2926 (10.9%) | 302/2926 (10.3%) |
| 11 | 43 | 149/1548 (9.6%) | 141/1548 (9.1%) |
| 12 | 27 | 97/918 (10.6%) | 89/918 (9.7%) |
| 13 | 18 | 54/576 (9.4%) | 49/576 (8.5%) |
| 14 | 8 | 18/240 (7.5%) | 17/240 (7.1%) |

Full, by shortest-path length from the start:

| BFS distance | episodes | success | shortest path |
|---|---|---|---|
| 1 | 1492 | 1065/1492 (71.4%) | 1025/1492 (68.7%) |
| 2 | 1768 | 702/1768 (39.7%) | 644/1768 (36.4%) |
| 3 | 2040 | 450/2040 (22.1%) | 382/2040 (18.7%) |
| 4 | 2418 | 203/2418 (8.4%) | 158/2418 (6.5%) |
| 5 | 2582 | 84/2582 (3.3%) | 55/2582 (2.1%) |
| 6 | 2556 | 45/2556 (1.8%) | 25/2556 (1.0%) |
| 7 | 2316 | 24/2316 (1.0%) | 10/2316 (0.4%) |
| 8 | 1912 | 9/1912 (0.5%) | 5/1912 (0.3%) |
| 9 | 1256 | 0/1256 (0.0%) | 0/1256 (0.0%) |
| 10 | 578 | 0/578 (0.0%) | 0/578 (0.0%) |
| 11 | 366 | 0/366 (0.0%) | 0/366 (0.0%) |
| 12 | 212 | 0/212 (0.0%) | 0/212 (0.0%) |
| 13 | 106 | 0/106 (0.0%) | 0/106 (0.0%) |
| 14 | 46 | 0/46 (0.0%) | 0/46 (0.0%) |
| 15 | 20 | 0/20 (0.0%) | 0/20 (0.0%) |
| 16 | 6 | 0/6 (0.0%) | 0/6 (0.0%) |
| 17 | 6 | 0/6 (0.0%) | 0/6 (0.0%) |

Maps where Full was not optimal from every start:

| map | walls | optimal | success | wrong edges | D(c) exact |
|---|---|---|---|---|---|
| 6 | 9 | 0/40 | 0/40 | 39 | 1/21 |
| 7 | 13 | 0/32 | 0/32 | 36 | 1/17 |
| 8 | 8 | 0/42 | 0/42 | 39 | 1/22 |
| 18 | 13 | 0/32 | 0/32 | 27 | 1/17 |
| 20 | 9 | 0/40 | 0/40 | 43 | 1/21 |
| 23 | 9 | 0/40 | 0/40 | 37 | 1/21 |
| 29 | 12 | 0/34 | 0/34 | 36 | 1/18 |
| 32 | 9 | 0/40 | 0/40 | 46 | 1/21 |
| 33 | 12 | 0/34 | 0/34 | 40 | 1/18 |
| 46 | 9 | 0/40 | 0/40 | 50 | 1/21 |
| 53 | 8 | 0/42 | 0/42 | 54 | 1/22 |
| 54 | 10 | 0/38 | 0/38 | 39 | 1/20 |
| 57 | 9 | 0/40 | 0/40 | 42 | 1/21 |
| 66 | 8 | 0/42 | 0/42 | 45 | 1/22 |
| 71 | 9 | 0/40 | 0/40 | 44 | 1/21 |

Reading:

- D1 = 100% optimal: the planner and control loop are correct.
- D2 vs D1: the learned cost D(c) costs 34% success and 52% optimal episodes.
- D3 vs D1: the learned dynamics costs 86% success and 91% optimal episodes.
- Full (12% optimal) is no worse than the weaker of D2 / D3: no compounding.
- Random reaches the goal in 6% of episodes (lower bound); Oracle in 100%.
