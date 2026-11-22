# 500 new maps: v1 model, no retraining

500 layouts never used for training, validation or testing (seed 1; all 100 experiment layouts and the reference map excluded), 3-7 walls, goal (5,0). Navigation starts from every free cell of every map (12073 start cells), seeds [0, 1] -> 24146 episodes per rung.

## Headline

| metric | result |
|---|---|
| navigation success (Full: learned dynamics + learned cost) | 8756/24146 (36.3%) |
| shortest-path accuracy (episodes with exactly the BFS length) | 6184/24146 (25.6%) |
| shortest path, among successful episodes | 6184/8756 (70.6%) |
| maps solved optimally from every start | 2/500 (0.4%) |
| collision accuracy, episode data (stay vs move) | 80.98% of 500000 transitions |
| collision accuracy, every (cell, action) pair: wall bumps | 6734/6744 (99.9%) |
| collision accuracy, every (cell, action) pair: border bumps | 9312/9312 (100.0%) |
| rollout accuracy at 1 / 5 / 10 steps | 80.0% / 32.9% / 22.7% |

## Collisions (episode data)

| | correct |
|---|---|
| blocked moves predicted as blocked | 160921/161030 (99.9%) |
|   interior-wall bumps | 68387/68496 (99.8%) |
|   border bumps | 92534/92534 (100.0%) |
| free moves wrongly predicted as blocked | 94997/338970 (28.0%) |
| precision of "blocked" | 62.88% |

## One-step prediction and rollouts (episode data)

| move type | correct |
|---|---|
| normal moves | 238841/338970 (70.5%) |
| border bumps | 92534/92534 (100.0%) |
| wall bumps | 68387/68496 (99.8%) |
| all | 399762/500000 (80.0%) |

Rollout snap accuracy by imagined step (410000 windows):

| 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|
| 80.0% | 60.5% | 47.1% | 38.6% | 32.9% | 29.1% | 26.6% | 24.8% | 23.6% | 22.7% |

## Imagined graph (every cell x action of every map)

| edges | correct | unknown -> self-loop | wrong but trusted |
|---|---|---|---|
| normal moves | 24384/34236 (71.2%) | 0/34236 (0.0%) | 9852/34236 (28.8%) |
| border bumps | 9312/9312 (100.0%) | 0/9312 (0.0%) | 0/9312 (0.0%) |
| wall bumps | 6734/6744 (99.9%) | 0/6744 (0.0%) | 10/6744 (0.1%) |
| all | 40430/50292 (80.4%) | 0/50292 (0.0%) | 9862/50292 (19.6%) |
| D(c) exact | 6213/12573 (49.4%) cells; 109/500 (21.8%) maps exact everywhere; 2165 fake shortcuts | | |

## Navigation and ladder

| rung | dynamics | cost | success | shortest path | collisions / action | loop failures | timeouts |
|---|---|---|---|---|---|---|---|
| Oracle | true | A* | 24146/24146 (100.0%) | 24146/24146 (100.0%) | 0.0% | 0 | 0 |
| D1 | true | true | 24146/24146 (100.0%) | 24146/24146 (100.0%) | 0.0% | 0 | 0 |
| D2 | true | learned | 17574/24146 (72.8%) | 16253/24146 (67.3%) | 7.0% | 6564 | 8 |
| D3 | learned | true | 9205/24146 (38.1%) | 6224/24146 (25.8%) | 6.5% | 14940 | 1 |
| Full | learned | learned | 8756/24146 (36.3%) | 6184/24146 (25.6%) | 5.8% | 15389 | 1 |
| Random | - | - | 1621/24146 (6.7%) | 777/24146 (3.2%) | 30.3% | 22525 | 0 |

Full, by number of walls:

| walls | maps | success | shortest path |
|---|---|---|---|
| 3 | 108 | 3084/5616 (54.9%) | 2131/5616 (37.9%) |
| 4 | 104 | 2025/5200 (38.9%) | 1435/5200 (27.6%) |
| 5 | 115 | 1760/5520 (31.9%) | 1202/5520 (21.8%) |
| 6 | 99 | 1205/4554 (26.5%) | 894/4554 (19.6%) |
| 7 | 74 | 682/3256 (20.9%) | 522/3256 (16.0%) |

Full, by shortest-path length from the start:

| BFS distance | episodes | success | shortest path |
|---|---|---|---|
| 1 | 1678 | 1556/1678 (92.7%) | 1516/1678 (90.3%) |
| 2 | 2252 | 1710/2252 (75.9%) | 1574/2252 (69.9%) |
| 3 | 2758 | 1537/2758 (55.7%) | 1204/2758 (43.7%) |
| 4 | 3426 | 1313/3426 (38.3%) | 766/3426 (22.4%) |
| 5 | 3724 | 1056/3724 (28.4%) | 502/3724 (13.5%) |
| 6 | 3574 | 747/3574 (20.9%) | 327/3574 (9.1%) |
| 7 | 3010 | 450/3010 (15.0%) | 162/3010 (5.4%) |
| 8 | 2094 | 266/2094 (12.7%) | 89/2094 (4.3%) |
| 9 | 1168 | 116/1168 (9.9%) | 43/1168 (3.7%) |
| 10 | 242 | 4/242 (1.7%) | 1/242 (0.4%) |
| 11 | 118 | 1/118 (0.8%) | 0/118 (0.0%) |
| 12 | 54 | 0/54 (0.0%) | 0/54 (0.0%) |
| 13 | 34 | 0/34 (0.0%) | 0/34 (0.0%) |
| 14 | 14 | 0/14 (0.0%) | 0/14 (0.0%) |

Maps where Full was not optimal from every start:

| map | walls | optimal | success | wrong edges | D(c) exact |
|---|---|---|---|---|---|
| 39 | 7 | 0/44 | 0/44 | 46 | 1/23 |
| 49 | 4 | 0/50 | 0/50 | 22 | 1/26 |
| 59 | 5 | 0/48 | 0/48 | 58 | 1/25 |
| 60 | 6 | 0/46 | 0/46 | 42 | 1/24 |
| 64 | 6 | 0/46 | 0/46 | 57 | 1/24 |
| 71 | 6 | 0/46 | 0/46 | 56 | 1/24 |
| 219 | 6 | 0/46 | 0/46 | 50 | 1/24 |
| 237 | 6 | 0/46 | 3/46 | 33 | 3/24 |
| 261 | 7 | 0/44 | 0/44 | 50 | 1/23 |
| 272 | 7 | 0/44 | 1/44 | 49 | 1/23 |
| 279 | 7 | 0/44 | 0/44 | 48 | 3/23 |
| 317 | 7 | 0/44 | 0/44 | 45 | 1/23 |
| 327 | 7 | 0/44 | 0/44 | 24 | 5/23 |
| 344 | 7 | 0/44 | 0/44 | 56 | 1/23 |
| 369 | 7 | 0/44 | 0/44 | 58 | 1/23 |

Reading:

- D1 = 100% optimal: the planner and control loop are correct.
- D2 vs D1: the learned cost D(c) costs 27% success and 33% optimal episodes.
- D3 vs D1: the learned dynamics costs 62% success and 74% optimal episodes.
- Full (26% optimal) is below both D2 and D3: the two errors compound.
- Random reaches the goal in 7% of episodes (lower bound); Oracle in 100%.
