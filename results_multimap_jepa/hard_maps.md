# 500 dense-wall maps (8-14 walls): joint JEPA (v2), no retraining

500 layouts never used for training, validation or testing (seed 2; all 100 experiment layouts and the reference map excluded), 8-14 walls, goal (5,0). Navigation starts from every free cell of every map (9840 start cells), seeds [0, 1] -> 19680 episodes per rung. Average shortest path to the goal 5.4 steps, longest 17.

## Headline

| metric | result |
|---|---|
| navigation success (Full: learned dynamics + learned cost) | 19154/19680 (97.3%) |
| shortest-path accuracy (episodes with exactly the BFS length) | 19129/19680 (97.2%) |
| shortest path, among successful episodes | 19129/19154 (99.9%) |
| maps solved optimally from every start | 407/500 (81.4%) |
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
| normal moves | 23648/24080 (98.2%) | 432/24080 (1.8%) | 0/24080 (0.0%) |
| border bumps | 7412/7412 (100.0%) | 0/7412 (0.0%) | 0/7412 (0.0%) |
| wall bumps | 9868/9868 (100.0%) | 549/9868 (5.6%) | 0/9868 (0.0%) |
| all | 40928/41360 (99.0%) | 981/41360 (2.4%) | 0/41360 (0.0%) |
| D(c) exact | 10036/10340 (97.1%) cells; 396/500 (79.2%) maps exact everywhere; 0 fake shortcuts | | |

## Navigation and ladder

| rung | dynamics | cost | success | shortest path | collisions / action | loop failures | timeouts |
|---|---|---|---|---|---|---|---|
| Oracle | true | A* | 19680/19680 (100.0%) | 19680/19680 (100.0%) | 0.0% | 0 | 0 |
| D1 | true | true | 19680/19680 (100.0%) | 19680/19680 (100.0%) | 0.0% | 0 | 0 |
| D2 | true | learned | 19658/19680 (99.9%) | 19566/19680 (99.4%) | 0.1% | 22 | 0 |
| D3 | learned | true | 19066/19680 (96.9%) | 19063/19680 (96.9%) | 1.1% | 614 | 0 |
| Full | learned | learned | 19154/19680 (97.3%) | 19129/19680 (97.2%) | 0.8% | 526 | 0 |
| Random | - | - | 1187/19680 (6.0%) | 494/19680 (2.5%) | 40.5% | 18493 | 0 |

Full, by number of walls:

| walls | maps | success | shortest path |
|---|---|---|---|
| 8 | 196 | 8118/8232 (98.6%) | 8108/8232 (98.5%) |
| 9 | 131 | 5172/5240 (98.7%) | 5164/5240 (98.5%) |
| 10 | 77 | 2820/2926 (96.4%) | 2820/2926 (96.4%) |
| 11 | 43 | 1456/1548 (94.1%) | 1456/1548 (94.1%) |
| 12 | 27 | 880/918 (95.9%) | 873/918 (95.1%) |
| 13 | 18 | 500/576 (86.8%) | 500/576 (86.8%) |
| 14 | 8 | 208/240 (86.7%) | 208/240 (86.7%) |

Full, by shortest-path length from the start:

| BFS distance | episodes | success | shortest path |
|---|---|---|---|
| 1 | 1492 | 1492/1492 (100.0%) | 1492/1492 (100.0%) |
| 2 | 1768 | 1766/1768 (99.9%) | 1766/1768 (99.9%) |
| 3 | 2040 | 2038/2040 (99.9%) | 2038/2040 (99.9%) |
| 4 | 2418 | 2402/2418 (99.3%) | 2402/2418 (99.3%) |
| 5 | 2582 | 2562/2582 (99.2%) | 2562/2582 (99.2%) |
| 6 | 2556 | 2510/2556 (98.2%) | 2502/2556 (97.9%) |
| 7 | 2316 | 2224/2316 (96.0%) | 2218/2316 (95.8%) |
| 8 | 1912 | 1796/1912 (93.9%) | 1794/1912 (93.8%) |
| 9 | 1256 | 1182/1256 (94.1%) | 1179/1256 (93.9%) |
| 10 | 578 | 518/578 (89.6%) | 516/578 (89.3%) |
| 11 | 366 | 316/366 (86.3%) | 316/366 (86.3%) |
| 12 | 212 | 182/212 (85.8%) | 180/212 (84.9%) |
| 13 | 106 | 98/106 (92.5%) | 96/106 (90.6%) |
| 14 | 46 | 42/46 (91.3%) | 42/46 (91.3%) |
| 15 | 20 | 18/20 (90.0%) | 18/20 (90.0%) |
| 16 | 6 | 4/6 (66.7%) | 4/6 (66.7%) |
| 17 | 6 | 4/6 (66.7%) | 4/6 (66.7%) |

Maps where Full was not optimal from every start:

| map | walls | optimal | success | wrong edges | D(c) exact |
|---|---|---|---|---|---|
| 380 | 10 | 4/38 | 4/38 | 4 | 3/20 |
| 312 | 8 | 8/42 | 8/42 | 5 | 5/22 |
| 74 | 11 | 8/36 | 8/36 | 2 | 5/19 |
| 7 | 13 | 10/32 | 10/32 | 3 | 3/17 |
| 239 | 13 | 12/32 | 12/32 | 6 | 7/17 |
| 122 | 11 | 16/36 | 16/36 | 6 | 9/19 |
| 394 | 14 | 14/30 | 14/30 | 3 | 8/16 |
| 303 | 10 | 18/38 | 18/38 | 5 | 8/20 |
| 120 | 8 | 20/42 | 20/42 | 5 | 11/22 |
| 474 | 13 | 16/32 | 16/32 | 9 | 7/17 |
| 83 | 10 | 20/38 | 20/38 | 4 | 11/20 |
| 374 | 12 | 20/34 | 20/34 | 6 | 11/18 |
| 129 | 14 | 18/30 | 18/30 | 2 | 8/16 |
| 456 | 9 | 26/40 | 26/40 | 1 | 14/21 |
| 67 | 8 | 28/42 | 28/42 | 7 | 15/22 |

Reading:

- D1 = 100% optimal: the planner and control loop are correct.
- D2 vs D1: the learned cost D(c) costs 0% success and 1% optimal episodes.
- D3 vs D1: the learned dynamics costs 3% success and 3% optimal episodes.
- Full (97% optimal) is no worse than the weaker of D2 / D3: no compounding.
- Random reaches the goal in 6% of episodes (lower bound); Oracle in 100%.
