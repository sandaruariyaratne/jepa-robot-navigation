# 500 new maps: joint JEPA (v2), no retraining

500 layouts never used for training, validation or testing (seed 1; all 100 experiment layouts and the reference map excluded), 3-7 walls, goal (5,0). Navigation starts from every free cell of every map (12073 start cells), seeds [0, 1] -> 24146 episodes per rung. Average shortest path to the goal 5.0 steps, longest 14. Unknown threshold 7.05 (99.9% quantile of correct one-step snap distances, validation maps). Planner: P2 with every imagined step snapped to the codebook.

## Headline

| metric | result |
|---|---|
| navigation success (Full: learned dynamics + learned cost) | 24146/24146 (100.0%) |
| shortest-path accuracy (episodes with exactly the BFS length) | 24146/24146 (100.0%) |
| shortest path, among successful episodes | 24146/24146 (100.0%) |
| maps solved optimally from every start | 500/500 (100.0%) |
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
| normal moves | 34236/34236 (100.0%) | 0/34236 (0.0%) | 0/34236 (0.0%) |
| border bumps | 9312/9312 (100.0%) | 0/9312 (0.0%) | 0/9312 (0.0%) |
| wall bumps | 6744/6744 (100.0%) | 3/6744 (0.0%) | 0/6744 (0.0%) |
| all | 50292/50292 (100.0%) | 3/50292 (0.0%) | 0/50292 (0.0%) |
| D(c) exact | 12573/12573 (100.0%) cells; 500/500 (100.0%) maps exact everywhere; 0 fake shortcuts | | |

## Navigation and ladder

| rung | dynamics | cost | success | shortest path | collisions / action | loop failures | timeouts |
|---|---|---|---|---|---|---|---|
| Oracle | true | A* | 24146/24146 (100.0%) | 24146/24146 (100.0%) | 0.0% | 0 | 0 |
| D1 | true | true | 24146/24146 (100.0%) | 24146/24146 (100.0%) | 0.0% | 0 | 0 |
| D2 | true | learned | 24146/24146 (100.0%) | 24146/24146 (100.0%) | 0.0% | 0 | 0 |
| D3 | learned | true | 24146/24146 (100.0%) | 24146/24146 (100.0%) | 0.0% | 0 | 0 |
| Full | learned | learned | 24146/24146 (100.0%) | 24146/24146 (100.0%) | 0.0% | 0 | 0 |
| Random | - | - | 1621/24146 (6.7%) | 777/24146 (3.2%) | 30.3% | 22525 | 0 |

Full, by number of walls:

| walls | maps | success | shortest path |
|---|---|---|---|
| 3 | 108 | 5616/5616 (100.0%) | 5616/5616 (100.0%) |
| 4 | 104 | 5200/5200 (100.0%) | 5200/5200 (100.0%) |
| 5 | 115 | 5520/5520 (100.0%) | 5520/5520 (100.0%) |
| 6 | 99 | 4554/4554 (100.0%) | 4554/4554 (100.0%) |
| 7 | 74 | 3256/3256 (100.0%) | 3256/3256 (100.0%) |

Full, by shortest-path length from the start:

| BFS distance | episodes | success | shortest path |
|---|---|---|---|
| 1 | 1678 | 1678/1678 (100.0%) | 1678/1678 (100.0%) |
| 2 | 2252 | 2252/2252 (100.0%) | 2252/2252 (100.0%) |
| 3 | 2758 | 2758/2758 (100.0%) | 2758/2758 (100.0%) |
| 4 | 3426 | 3426/3426 (100.0%) | 3426/3426 (100.0%) |
| 5 | 3724 | 3724/3724 (100.0%) | 3724/3724 (100.0%) |
| 6 | 3574 | 3574/3574 (100.0%) | 3574/3574 (100.0%) |
| 7 | 3010 | 3010/3010 (100.0%) | 3010/3010 (100.0%) |
| 8 | 2094 | 2094/2094 (100.0%) | 2094/2094 (100.0%) |
| 9 | 1168 | 1168/1168 (100.0%) | 1168/1168 (100.0%) |
| 10 | 242 | 242/242 (100.0%) | 242/242 (100.0%) |
| 11 | 118 | 118/118 (100.0%) | 118/118 (100.0%) |
| 12 | 54 | 54/54 (100.0%) | 54/54 (100.0%) |
| 13 | 34 | 34/34 (100.0%) | 34/34 (100.0%) |
| 14 | 14 | 14/14 (100.0%) | 14/14 (100.0%) |

Reading:

- D1 = 100% optimal: the planner and control loop are correct.
- D2 matches D1: the learned cost D(c) costs nothing.
- D3 matches D1: the learned dynamics costs nothing.
- Full (100% optimal) is no worse than the weaker of D2 / D3: no compounding.
- Random reaches the goal in 7% of episodes (lower bound); Oracle in 100%.
