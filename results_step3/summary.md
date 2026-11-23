# Step 3: fair baseline, seeds and ablations

Mean ± standard deviation (percentage points) over training seeds. Same data, 100-map split, encoder, predictor, curriculum and checkpoint selection; only the training objective differs. Navigation: every free start cell, 2 planning seeds. p2 = raw rollouts with unknown = 3 x median one-step error; snap = every imagined step snapped, unknown = 99.9% quantile of correct one-step snap distances on the validation maps.

| | JEPA | Pixel world model (baseline) | JEPA, no EMA target | JEPA, no variance / covariance terms |
|---|---|---|---|---|
| Seeds | 0, 1, 2 | 0, 1, 2 | 0, 1 | 0, 1 |
| Val-map snap@5 (selection) | 90.1% ± 0.5 | 90.2% ± 1.1 | 91.1% ± 0.1 | 17.1% ± 0.0 |
| Robot cell from latent, linear probe (val maps) | 100.0% ± 0.0 | 100.0% ± 0.0 | 100.0% ± 0.0 | 15.6% ± 0.6 |
| Test maps: one-step, normal moves | 100.0% ± 0.0 | 99.3% ± 0.1 | 99.9% ± 0.1 | 0.2% ± 0.3 |
| Test maps: rollout accuracy, step 5 | 89.6% ± 0.2 | 89.5% ± 1.0 | 90.3% ± 0.8 | 16.7% ± 0.1 |
| Test maps: navigation success (p2) | 99.8% ± 0.2 | 93.9% ± 4.7 | 99.4% ± 0.8 | 7.8% ± 0.0 |
| Test maps: navigation success (snap) | 100.0% ± 0.0 | 96.8% ± 5.5 | 99.9% ± 0.2 | 7.8% ± 0.0 |
| Mazes: one-step, normal moves | 100.0% ± 0.0 | 97.6% ± 0.8 | 100.0% ± 0.0 | 0.1% ± 0.2 |
| Mazes: collision accuracy | 100.0% ± 0.0 | 98.7% ± 0.4 | 99.9% ± 0.0 | 45.6% ± 0.0 |
| Mazes: imagined edges wrong but trusted (p2) | 0.0% ± 0.0 | 1.3% ± 0.5 | 0.0% ± 0.0 | 54.5% ± 0.4 |
| Mazes: navigation success (p2) | 95.2% ± 3.6 | 56.0% ± 5.7 | 83.8% ± 0.4 | 2.7% ± 0.0 |
| Mazes: shortest path (p2) | 95.1% ± 3.8 | 53.4% ± 5.9 | 83.4% ± 0.6 | 1.1% ± 0.0 |
| Mazes: navigation success (snap) | 100.0% ± 0.0 | 79.4% ± 11.9 | 98.3% ± 1.0 | 2.6% ± 0.0 |
| Mazes: shortest path (snap) | 100.0% ± 0.0 | 78.4% ± 12.3 | 98.2% ± 1.0 | 1.1% ± 0.0 |
| Latent: smallest per-dimension std | 1.02 ± 0.00 | 0.43 ± 0.04 | 1.01 ± 0.01 | 0.00 ± 0.00 |

Per run:

| run | val snap@5 | test nav (p2) | maze nav (p2) | maze nav (snap) | training min |
|---|---|---|---|---|---|
| jepa s0 | 89.6% | 100.0% | 94.0% | 100.0% | 0 |
| jepa s1 | 90.1% | 99.7% | 92.4% | 100.0% | 18 |
| jepa s2 | 90.6% | 99.7% | 99.3% | 100.0% | 17 |
| pixel s0 | 90.1% | 88.5% | 49.5% | 66.2% | 69 |
| pixel s1 | 91.4% | 97.1% | 60.3% | 89.3% | 53 |
| pixel s2 | 89.1% | 96.1% | 58.0% | 82.9% | 49 |
| no_ema s0 | 91.2% | 100.0% | 84.1% | 98.9% | 8 |
| no_ema s1 | 91.1% | 98.9% | 83.5% | 97.6% | 8 |
| no_vicreg s0 | 17.1% | 7.8% | 2.6% | 2.6% | 13 |
| no_vicreg s1 | 17.1% | 7.8% | 2.7% | 2.6% | 13 |
