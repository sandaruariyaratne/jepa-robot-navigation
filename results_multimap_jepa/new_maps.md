# 500 new maps: joint JEPA (v2), no retraining

500 layouts never used for training, validation or testing (seed 1; all 100 experiment layouts and the reference map excluded), 3-7 walls, goal (5,0). Navigation starts from every free cell of every map (12073 start cells), seeds [0, 1] -> 24146 episodes per rung.

## Headline

| metric | result |
|---|---|
| navigation success (Full: learned dynamics + learned cost) | 24112/24146 (99.9%) |
| shortest-path accuracy (episodes with exactly the BFS length) | 24106/24146 (99.8%) |
| shortest path, among successful episodes | 24106/24112 (100.0%) |
| maps solved optimally from every start | 485/500 (97.0%) |
| collision accuracy, episode data (stay vs move) | 100.00% of 500000 transitions |
| collision accuracy, every (cell, action) pair: wall bumps | 6744/6744 (100.0%) |
| collision accuracy, every (cell, action) pair: border bumps | 9312/9312 (100.0%) |
| rollout accuracy at 1 / 5 / 10 steps | 100.0% / 89.5% / 68.8% |

## Collisions (episode data)

| | correct |
|---|---|
| blocked moves predicted as blocked | 161030/161030 (100.0%) |
|   interior-wall bumps | 68496/68496 (100.0%) |
|   border bumps | 92534/92534 (100.0%) |
| free moves wrongly predicted as blocked | 0/338970 (0.0%) |
| precision of "blocked" | 100.00% |

## One-step prediction and rollouts (episode data)

| move type | correct |
|---|---|
| normal moves | 338970/338970 (100.0%) |
| border bumps | 92534/92534 (100.0%) |
| wall bumps | 68496/68496 (100.0%) |
| all | 500000/500000 (100.0%) |

Rollout snap accuracy by imagined step (410000 windows):

| 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|
| 100.0% | 99.2% | 96.7% | 93.3% | 89.5% | 85.3% | 81.1% | 76.9% | 72.8% | 68.8% |

## Imagined graph (every cell x action of every map)

| edges | correct | unknown -> self-loop | wrong but trusted |
|---|---|---|---|
| normal moves | 34095/34236 (99.6%) | 141/34236 (0.4%) | 0/34236 (0.0%) |
| border bumps | 9312/9312 (100.0%) | 0/9312 (0.0%) | 0/9312 (0.0%) |
| wall bumps | 6744/6744 (100.0%) | 209/6744 (3.1%) | 0/6744 (0.0%) |
| all | 50151/50292 (99.7%) | 350/50292 (0.7%) | 0/50292 (0.0%) |
| D(c) exact | 12553/12573 (99.8%) cells; 485/500 (97.0%) maps exact everywhere; 0 fake shortcuts | | |

## Navigation and ladder

| rung | dynamics | cost | success | shortest path | collisions / action | loop failures | timeouts |
|---|---|---|---|---|---|---|---|
| Oracle | true | A* | 24146/24146 (100.0%) | 24146/24146 (100.0%) | 0.0% | 0 | 0 |
| D1 | true | true | 24146/24146 (100.0%) | 24146/24146 (100.0%) | 0.0% | 0 | 0 |
| D2 | true | learned | 24146/24146 (100.0%) | 24146/24146 (100.0%) | 0.0% | 0 | 0 |
| D3 | learned | true | 24099/24146 (99.8%) | 24098/24146 (99.8%) | 0.1% | 47 | 0 |
| Full | learned | learned | 24112/24146 (99.9%) | 24106/24146 (99.8%) | 0.0% | 34 | 0 |
| Random | - | - | 1621/24146 (6.7%) | 777/24146 (3.2%) | 30.3% | 22525 | 0 |

Full, by number of walls:

| walls | maps | success | shortest path |
|---|---|---|---|
| 3 | 108 | 5608/5616 (99.9%) | 5606/5616 (99.8%) |
| 4 | 104 | 5198/5200 (100.0%) | 5194/5200 (99.9%) |
| 5 | 115 | 5510/5520 (99.8%) | 5510/5520 (99.8%) |
| 6 | 99 | 4548/4554 (99.9%) | 4548/4554 (99.9%) |
| 7 | 74 | 3248/3256 (99.8%) | 3248/3256 (99.8%) |

Full, by shortest-path length from the start:

| BFS distance | episodes | success | shortest path |
|---|---|---|---|
| 1 | 1678 | 1678/1678 (100.0%) | 1678/1678 (100.0%) |
| 2 | 2252 | 2252/2252 (100.0%) | 2252/2252 (100.0%) |
| 3 | 2758 | 2758/2758 (100.0%) | 2758/2758 (100.0%) |
| 4 | 3426 | 3422/3426 (99.9%) | 3422/3426 (99.9%) |
| 5 | 3724 | 3720/3724 (99.9%) | 3720/3724 (99.9%) |
| 6 | 3574 | 3570/3574 (99.9%) | 3566/3574 (99.8%) |
| 7 | 3010 | 2998/3010 (99.6%) | 2996/3010 (99.5%) |
| 8 | 2094 | 2094/2094 (100.0%) | 2094/2094 (100.0%) |
| 9 | 1168 | 1166/1168 (99.8%) | 1166/1168 (99.8%) |
| 10 | 242 | 238/242 (98.3%) | 238/242 (98.3%) |
| 11 | 118 | 116/118 (98.3%) | 116/118 (98.3%) |
| 12 | 54 | 54/54 (100.0%) | 54/54 (100.0%) |
| 13 | 34 | 32/34 (94.1%) | 32/34 (94.1%) |
| 14 | 14 | 14/14 (100.0%) | 14/14 (100.0%) |

Maps where Full was not optimal from every start:

| map | walls | optimal | success | wrong edges | D(c) exact |
|---|---|---|---|---|---|
| 467 | 6 | 40/46 | 40/46 | 1 | 21/24 |
| 17 | 3 | 46/52 | 46/52 | 1 | 24/27 |
| 112 | 4 | 46/50 | 50/50 | 1 | 24/26 |
| 39 | 7 | 42/44 | 42/44 | 5 | 22/23 |
| 132 | 7 | 42/44 | 42/44 | 3 | 22/23 |
| 243 | 7 | 42/44 | 42/44 | 5 | 22/23 |
| 359 | 7 | 42/44 | 42/44 | 2 | 22/23 |
| 195 | 5 | 46/48 | 46/48 | 2 | 24/25 |
| 200 | 5 | 46/48 | 46/48 | 2 | 24/25 |
| 220 | 5 | 46/48 | 46/48 | 7 | 24/25 |
| 318 | 5 | 46/48 | 46/48 | 3 | 24/25 |
| 429 | 5 | 46/48 | 46/48 | 0 | 25/25 |
| 257 | 4 | 48/50 | 48/50 | 2 | 25/26 |
| 468 | 3 | 50/52 | 52/52 | 2 | 26/27 |
| 498 | 3 | 50/52 | 50/52 | 2 | 26/27 |

Reading:

- D1 = 100% optimal: the planner and control loop are correct.
- D2 matches D1: the learned cost D(c) costs nothing.
- D3 vs D1: the learned dynamics costs 0% success and 0% optimal episodes.
- Full (100% optimal) is no worse than the weaker of D2 / D3: no compounding.
- Random reaches the goal in 7% of episodes (lower bound); Oracle in 100%.
