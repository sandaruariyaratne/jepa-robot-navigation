# 500 dense-wall maps (8-14 walls): joint JEPA (v2), no retraining

500 layouts never used for training, validation or testing (seed 2; all 100 experiment layouts and the reference map excluded), 8-14 walls, goal (5,0). Navigation starts from every free cell of every map (9840 start cells), seeds [0, 1] -> 19680 episodes per rung. Average shortest path to the goal 5.4 steps, longest 17. Unknown threshold 7.05 (99.9% quantile of correct one-step snap distances, validation maps).

## Headline

| metric | result |
|---|---|
| navigation success (Full: learned dynamics + learned cost) | 18552/19680 (94.3%) |
| shortest-path accuracy (episodes with exactly the BFS length) | 18179/19680 (92.4%) |
| shortest path, among successful episodes | 18179/18552 (98.0%) |
| maps solved optimally from every start | 267/500 (53.4%) |
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
| D3 | learned | true | 18552/19680 (94.3%) | 18179/19680 (92.4%) | 2.1% | 1128 | 0 |
| Full | learned | learned | 18552/19680 (94.3%) | 18179/19680 (92.4%) | 2.1% | 1128 | 0 |
| Random | - | - | 1187/19680 (6.0%) | 494/19680 (2.5%) | 40.5% | 18493 | 0 |

Full, by number of walls:

| walls | maps | success | shortest path |
|---|---|---|---|
| 8 | 196 | 7754/8232 (94.2%) | 7661/8232 (93.1%) |
| 9 | 131 | 4944/5240 (94.4%) | 4794/5240 (91.5%) |
| 10 | 77 | 2714/2926 (92.8%) | 2669/2926 (91.2%) |
| 11 | 43 | 1478/1548 (95.5%) | 1449/1548 (93.6%) |
| 12 | 27 | 875/918 (95.3%) | 859/918 (93.6%) |
| 13 | 18 | 554/576 (96.2%) | 543/576 (94.3%) |
| 14 | 8 | 233/240 (97.1%) | 204/240 (85.0%) |

Full, by shortest-path length from the start:

| BFS distance | episodes | success | shortest path |
|---|---|---|---|
| 1 | 1492 | 1492/1492 (100.0%) | 1492/1492 (100.0%) |
| 2 | 1768 | 1768/1768 (100.0%) | 1768/1768 (100.0%) |
| 3 | 2040 | 2040/2040 (100.0%) | 2036/2040 (99.8%) |
| 4 | 2418 | 2415/2418 (99.9%) | 2390/2418 (98.8%) |
| 5 | 2582 | 2574/2582 (99.7%) | 2546/2582 (98.6%) |
| 6 | 2556 | 2489/2556 (97.4%) | 2464/2556 (96.4%) |
| 7 | 2316 | 2235/2316 (96.5%) | 2170/2316 (93.7%) |
| 8 | 1912 | 1755/1912 (91.8%) | 1682/1912 (88.0%) |
| 9 | 1256 | 1053/1256 (83.8%) | 984/1256 (78.3%) |
| 10 | 578 | 354/578 (61.2%) | 311/578 (53.8%) |
| 11 | 366 | 195/366 (53.3%) | 171/366 (46.7%) |
| 12 | 212 | 102/212 (48.1%) | 93/212 (43.9%) |
| 13 | 106 | 55/106 (51.9%) | 51/106 (48.1%) |
| 14 | 46 | 12/46 (26.1%) | 9/46 (19.6%) |
| 15 | 20 | 7/20 (35.0%) | 6/20 (30.0%) |
| 16 | 6 | 4/6 (66.7%) | 4/6 (66.7%) |
| 17 | 6 | 2/6 (33.3%) | 2/6 (33.3%) |

Maps where Full was not optimal from every start:

| map | walls | optimal | success | wrong edges | D(c) exact |
|---|---|---|---|---|---|
| 473 | 14 | 4/30 | 24/30 | 0 | 16/16 |
| 383 | 10 | 12/38 | 15/38 | 0 | 20/20 |
| 47 | 9 | 20/40 | 32/40 | 0 | 21/21 |
| 246 | 9 | 20/40 | 20/40 | 0 | 21/21 |
| 175 | 8 | 22/42 | 22/42 | 0 | 22/22 |
| 365 | 8 | 22/42 | 22/42 | 0 | 22/22 |
| 454 | 8 | 22/42 | 22/42 | 0 | 22/22 |
| 80 | 9 | 21/40 | 39/40 | 0 | 21/21 |
| 76 | 9 | 22/40 | 22/40 | 0 | 21/21 |
| 210 | 9 | 22/40 | 39/40 | 0 | 21/21 |
| 391 | 9 | 22/40 | 22/40 | 0 | 21/21 |
| 456 | 9 | 22/40 | 33/40 | 0 | 21/21 |
| 122 | 11 | 20/36 | 23/36 | 0 | 19/19 |
| 140 | 9 | 23/40 | 39/40 | 0 | 21/21 |
| 371 | 12 | 20/34 | 20/34 | 0 | 18/18 |

Reading:

- D1 = 100% optimal: the planner and control loop are correct.
- D2 matches D1: the learned cost D(c) costs nothing.
- D3 vs D1: the learned dynamics costs 6% success and 8% optimal episodes.
- Full (92% optimal) is no worse than the weaker of D2 / D3: no compounding.
- Random reaches the goal in 6% of episodes (lower bound); Oracle in 100%.
