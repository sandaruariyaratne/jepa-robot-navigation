# Mini-JEPA evaluation report

A small action-conditioned latent world model on a 6 × 5 grid: a frozen CNN
encoder maps each RGB frame to a 32-D latent, a residual MLP predicts how an
action changes that latent, and planners search over imagined rollouts. Every
number below comes from `python main.py all` with seed 0 (config.yaml); the
full tables are in [results/results.md](results/results.md).

**Bottom line.** On the one fixed map it was trained on, the system navigates
perfectly: the primary planner (P2) reaches the goal by a shortest path in
120/120 episodes. That is a statement about **fit**. On the only real
**generalization** test, (state, action) pairs never seen in training, the
learned dynamics fail: 1 of 10 held-out pairs predicted correctly, against 9 of
10 for a plain MLP on coordinates. Navigation stays perfect only because the
model flags all 10 of those predictions as unknown and the map has enough
alternative shortest routes to avoid them.

**Step 12.** Joint JEPA training alone does not change this on one map (§7).
Trained on 70 layouts, though, it generalizes to unseen ones: 99.9% navigation
success on 500 new layouts, against 36% for the v1 recipe (§8).

## 1. Setup

| | |
|---|---|
| World | 6 × 5 grid, 5 fixed walls, fixed goal (5,0), 25 free cells, 4 actions; blocked moves stay in place |
| Observation | 3 × 40 × 48 RGB frame; only 25 distinct frames exist |
| Data | 200 episodes × 50 uniformly random actions = 10,000 transitions, random non-goal starts |
| Fit split | train / val / test = 160 / 20 / 20 **episodes** |
| Generalization split | 10 of the 100 (cell, action) pairs held out of all predictor training and model selection (7 moves, 3 bumps; at most one per cell) |
| Encoder | 3 stride-2 convs + linear → 32-D, trained as an autoencoder (pixel MSE), then frozen |
| Predictor | ẑ = z + f(z, a), f = MLP 36 → 128 → 128 → 32, rollout curriculum K = 1 → 2 → 4, checkpoint chosen by 5-step validation snap accuracy |
| Snap | nearest of the 25 codebook latents; **unknown** if farther than 3 × the median one-step error (0.0089) |
| Planners | P0: 1,024 five-step plans, final latent distance. P1: beam search 12 × 64, closest latent distance. P2: 64 three-step plans, min_k [k + D(snap(ẑ_k))], with D(c) from BFS on the imagined graph |

Why two splits: on a fixed map every (cell, action) pair recurs in every
episode, so test episodes contain the same transitions as training episodes.
The episode split therefore measures fit only. Held-out pairs are the one place
the model must predict something it has never seen.

## 2. Fit (test episodes, trained pairs)

| Measure | Result |
|---|---|
| Encoder gate: linear probe on validation latents | 100% (gate ≥ 99%) |
| Encoder gate: robot drawn in the right cell, 25 decodes | 25/25 |
| One-step latent MSE, model vs persistence (ẑ = z) | 0.00000 vs 1.206 |
| Snap accuracy, trained pairs (all 90) | 90/90 |
| Imagined rollouts on trained-pair windows, steps 1–10 | 100% at every step |
| Imagined graph, trained edges | 90/90 correct, none wrong |
| Imagined steps-to-goal D(c) vs true distance | exact for 25/25 cells |
| P2, 120 episodes | 120 success, 120 optimal, path ratio 1.00 |

The diagnostic ladder runs P2 with each part swapped for the truth. All four
model rungs are 100% optimal, so on this map neither the learned cost nor the
learned dynamics costs anything:

| Rung | Dynamics | Cost | Optimal episodes |
|---|---|---|---|
| Oracle (A*) | true | true | 120/120 |
| D1 | true | true D(c) | 120/120 |
| D2 | true | learned D(c) | 120/120 |
| D3 | learned | true D(c) | 120/120 |
| Full | learned | learned D(c) | 120/120 |
| Random policy | – | – | 7/120 (13 reach the goal) |

## 3. Generalization (held-out pairs)

| Held-out pairs (one step) | Latent predictor | Numerical baseline (x, y, a → next x, y) |
|---|---|---|
| moves | 0/7 | 7/7 |
| bumps | 1/3 | 2/3 |
| **all** | **1/10** | **9/10** |

- The latent predictor learned the 90 training transitions by heart; it did not
  learn "UP moves the robot one cell up" as a rule it can apply elsewhere.
  Several held-out moves are predicted as the *opposite* move. The numerical
  baseline, given coordinates, generalizes 9/10 (its one miss is an interior
  wall it has no way to know about).
- The encoder was trained only to reconstruct pixels, so its 25 latents carry
  no grid geometry for the predictor to exploit. Freezing it prevents collapse
  but does not provide useful structure, as the spec anticipated.
- Errors compound: over all test windows (which include held-out pairs) snap
  accuracy falls from 91% after one imagined step to 49% after ten. A linear
  position probe on the imagined latents tracks snapping within 1–2 points.
- **What saves planning is calibration, not generalization.** All 10 held-out
  predictions land 1.8–5.5 units from any codebook entry (threshold 0.0089), so
  all 10 are flagged unknown and become self-loops; none is trusted while
  wrong. Every affected cell still has another shortest route, so D(c) stays
  exact. A test with one injected confidently wrong edge shows the failure mode
  this avoids: D(reference start) drops from 9 to 2.

## 4. Planners

| Planner (learned model, 120 episodes) | Success | Optimal | Path ratio | Loop failures |
|---|---|---|---|---|
| P0 (latent distance, 5 steps) | 80 | 50 | 1.45 | 40 |
| P1 (latent distance, beam 12 × 64) | 115 | 65 | 1.32 | 5 |
| P2 (imagined steps-to-goal, 3 steps) | 120 | 120 | 1.00 | 0 |

Latent distance is a weak cost here: with the true model (one-hot latents) P0
and P1 are still only 9/24 and 15/24 optimal, because distance to the goal
latent says "at the goal or not", not "how far". P0 succeeds only within its
5-step horizon (100% up to distance 5, 0% from 7 on). Replays show P0 also
trusting plans that start with a held-out move, whose decoded rollouts lose the
robot entirely. The cost built from the imagined graph (P2) is what makes
planning reliable.

## 5. What these results do not show

- **Anything about other maps.** One layout, one goal, 25 distinct frames.
  Perfect navigation here is fit to this map. Unseen layouts were not tested.
- **That the model learned the dynamics.** It reproduces the transitions it was
  trained on; on new pairs it fails (1/10).
- **That navigation would survive a less redundant map.** P2 is optimal because
  every cell has a second shortest route around each unknown move. On a map
  where a held-out move is the only shortest route, paths would get longer,
  and where it is the only route at all, the goal would become unreachable.
- **Statistical strength.** One training seed; a single draw of 10 held-out
  pairs; navigation varies only the planner's tie-breaking seeds (5).
- **A strong encoder gate.** Any 25 distinct points in 32-D are linearly
  separable, so the ≥ 99% probe gate mostly rules out collapse; the 25 decodes
  are the stricter half.

## 6. Reproducing

```
python main.py all           # ~10 min on a laptop CPU; stops at the first failed gate
python main.py fingerprint   # hashes of every deterministic output
```

A clean copy (no data, checkpoints or results) re-run with `main.py all`
(9.4 min) produced fingerprints identical to the run reported here for all 13
outputs: data, splits, the four checkpoints' tensors, every metrics file and
the results table. Wall-clock planning times are the only fields excluded.

## 7. v2 experiment 1: joint JEPA training

The first step 12 experiment tests the obvious fix for §3: train the encoder
*for prediction* instead of reconstruction. The online encoder and predictor
train together against an EMA target encoder (τ = 0.99, no gradient), with
VICReg-style variance and covariance penalties (weights 1 : 1 : 0.04) to
prevent collapse; no decoder. Data, held-out pairs, rollout curriculum,
checkpoint selection, planners and evaluation are unchanged
(`config_v2.yaml`; full tables in [results_v2/results.md](results_v2/results.md)).

| | v1 frozen autoencoder | v2 joint JEPA |
|---|---|---|
| Trained pairs (fit) | 90/90 | 90/90 |
| Held-out moves | 0/7 | 0/7 |
| Held-out bumps | 1/3 | 2/3 |
| Held-out test transitions | 15/103 | 29/103 |
| Imagined rollouts, all test windows, step 1 → 10 | 91% → 49% | 92% → 50% |
| (x, y) from the top 3 latent principal components, R² | 0.20 | 0.24 |
| Effective rank of the 25 latents | 22.9 | 18.0 |
| Median one-step error (sets the "unknown" threshold) | 0.003 | 0.052 |
| Imagined graph edges correct | 93/100 | 88/100 |
| P2 navigation, 120 episodes | 120 optimal | 120 optimal |
| Ladder D3 (learned dynamics, true cost) | 120 optimal | 115 optimal, 5 loop failures |

**Joint training, as specified, does not fix generalization.** Fit is the
same, held-out moves stay at 0/7, and the latents are no more grid-shaped than
v1's. Nothing in the objective rewards a latent space where "UP" is the same
change everywhere; with 25 states and 90 training transitions, memorising each
transition still satisfies the loss.

**Latent size is not the fix either** (one seed each, so small differences
are noise):

| Latent size | Trained pairs | Held-out moves | Held-out bumps | (x, y) R² |
|---|---|---|---|---|
| 2 | 81/90 | 3/7 | 1/3 | 0.10 |
| 4 | 90/90 | 2/7 | 2/3 | 0.29 |
| 8 | 90/90 | 1/7 | 2/3 | 0.19 |
| 16 | 90/90 | 0/7 | 2/3 | 0.52 |
| 32 | 90/90 | 0/7 | 2/3 | 0.24 |

Smaller latents help a little (2–3 of 7 held-out moves), but 2 dimensions
already underfits the training pairs, and none approaches the numerical
baseline's 7/7.

**A side effect the ladder caught.** v2's one-step errors are less uniform, so
"unknown = farther than 3 × the median error" now also rejects 5 *correct*
trained moves. That leaves the reference start (0,4) with no trusted move
toward the goal in the imagined graph. Full P2 still succeeds from there by
falling back to latent distance for one step; D3, which has a trusted cost and
so never falls back, bumps twice and stops (all 5 of its loop failures). The
fault is the threshold's calibration, not the predicted dynamics.

**What this suggests.** Generalization here needs either an inductive bias
toward action-consistent latents (e.g. an action effect shared across states,
with a separate term for blocked moves) or data that punishes memorisation,
which is what the plan's later items provide (many layouts with held-out
layouts). The unknown threshold should be set from a quantile of trained-pair
errors rather than a multiple of the median.

## 8. Multi-map experiments: held-out layouts

§7 suggested that generalization needs data that punishes memorisation. This
tests that directly: 100 random layouts (same 6 × 5 grid, 3–7 walls, goal fixed
at (5,0)), split **by map** 70 / 15 / 15, 1,000 random-action transitions per
map. Each map gets its own codebook (the latents of its ~25 frames) and snaps
only to it. Two models, same data, split, predictor size (latent 64, hidden
256 × 256), planners and evaluation:

- **v1**: autoencoder (gate checked on the validation maps; it needed the
  robot-pixel weight × 10 fallback), then a residual predictor on frozen latents
  (`config_multimap.yaml`).
- **Joint JEPA**: the §7 objective, 6,000 steps of 8 maps / 512 windows each
  (`config_multimap_jepa.yaml`).

Checkpoints are chosen on validation-map 5-step snap accuracy; test maps are
never used for training or selection.

### 15 held-out test maps

| | v1 | Joint JEPA |
|---|---|---|
| One-step, normal moves | 70% | **100%** |
| One-step, border and wall bumps | 100% | 100% |
| Imagined rollouts, step 5 / 10 | 31% / 21% | **90% / 70%** |
| Imagined graph edges correct | 80% | **~100%** (1 of 1,488 wrong, flagged unknown) |
| Maps with D(c) exact everywhere | 5/15 | **15/15** |
| P2 navigation (Full): success / shortest path | 44% / 30% | **100% / 100%** |

v1 fits the training maps perfectly (100% everywhere) and memorises them: on a
new layout a third of its normal moves land on the wrong cell, and its unknown
threshold (3 × a median error of 2.27) never fires, so the planner trusts all
of them. The JEPA scores the same on validation and test maps, and slightly
*lower* than v1 on training maps (91% vs 100% at 10 rollout steps): it is not
memorising. With one layout (§7) it did not generalize; with 70 layouts it does.

### Stress tests: 1,200 more layouts, no retraining

Fresh layouts from new seeds, none equal to any of the 100 experiment layouts
(checked; no frame of them occurs in the training data either). Navigation
starts from every free cell of every map, two seeds.

| Test set | Maps | Avg path to goal | JEPA success / shortest path | v1 success / shortest path |
|---|---|---|---|---|
| Like training (3–7 walls) | 500 | 5.0 | **99.9% / 99.8%** | 36% / 26% |
| Dense walls (8–14) | 500 | 5.4 | **97.3% / 97.2%** | 13% / 12% |
| Mazes (8–12 walls, the 200 most winding of 20,000) | 200 | 8.5 (max 18) | **94.0% / 93.9%** | 10% / 9.5% |
| Random actions (lower bound) | | | 3–7% | |

| | Like training | Dense | Mazes |
|---|---|---|---|
| JEPA collision accuracy (blocked vs free, all episode transitions) | 100.00% | 100.00% | 99.99% |
| v1 collision accuracy | 81.0% | 56.6% | 65.4% |
| JEPA rollout accuracy, step 5 | 89.5% | 80.3% | 81.0% |
| JEPA edges wrong but trusted | 0 / 50,292 | 0 / 41,360 | 0 / 16,896 |
| JEPA edges flagged unknown | 0.7% | 2.4% | 2.9% |

The JEPA degrades gracefully: success drops with wall count (86.8% at 13–14
walls) and with path length (mazes: ~100% at 1–3 steps, 87% at 15, 68% at 17).
v1's collision accuracy is near chance on dense maps because it predicts
"blocked" for many free moves.

**Every JEPA failure is a doubted correct move, never a trusted wrong one.**
The unknown rule flags ~2% of real moves; the planner treats them as walls,
which blocks the only route in a corridor. On the mazes the learned cost alone
(ladder D2) reaches 99.4%; the losses sit in the learned dynamics (D3, 93.3%).

### Recalibrating the unknown threshold: worse

Threshold set from the validation maps only, before looking at test results:
the 99.9% quantile of correct one-step snap distances (4.25 → 7.05). On the
validation maps this cuts correct step-1 moves rejected from 0.92% to 0.06%,
but also trusts 67–74% of the wrong predictions at imagined steps 2–3 (up
from 16–18%), where drift makes distance a poor signal.

| JEPA, Full success / shortest path | 3 × median (default) | Calibrated |
|---|---|---|
| Like training | 99.9% / 99.8% | 97.8% / 97.0% |
| Dense walls | 97.3% / 97.2% | 94.3% / 92.4% |
| Mazes | 94.0% / 93.9% | 77.5% / 74.6% |

The imagined graph became essentially perfect (D(c) exact on all 1,200 maps,
ladder D2 = 100%), but P2's 3-step look-ahead now trusts drifted wrong
states and loops (maze loop failures 482 → 1,814). One threshold is doing two
jobs: one-step edges want it high, unsnapped multi-step rollouts want it low.
The default stays 3 × median; the calibrated value is only used with
`--threshold calibrated`. The standard fix is not a second threshold but to
snap every imagined step and continue from the codebook entry (planning on the
learned graph), so only the one-step check is needed.

### What these results do not show

- **That JEPA specifically is needed.** The baseline is a frozen reconstruction
  encoder. An encoder trained end to end with the predictor under a
  reconstruction loss has not been tried; neither have ablations of the EMA
  target or the variance / covariance terms.
- **Robustness across seeds.** One training seed per model.
- **Other conditions.** Same grid size, fixed goal, deterministic dynamics,
  noise-free frames; every test layout comes from the same kind of generator.
- **A good long-horizon model.** Rollouts drift (69% correct at 10 steps on new
  maps); navigation works because the planner looks 3 steps ahead and snaps
  to a per-map codebook.
- **Planning without privileged frames.** Each new map's codebook is built
  from one frame of the robot on every free cell (v1 gets the same). A real
  agent would have to explore to collect them.

Full tables: [results_multimap/](results_multimap/) and
[results_multimap_jepa/](results_multimap_jepa/) (`results.md`, `new_maps.md`,
`hard_maps.md`, `maze_maps.md`, `*_calibrated.md`).

## 9. Next steps

1. **Plan on the learned graph**: snap each imagined step to the codebook and
   continue from that entry, with the one-step threshold calibrated on the
   validation maps; confirm on fresh validation mazes before re-running the
   test sets once.
2. **A fair baseline**: encoder and predictor trained end to end with a
   reconstruction loss instead of the JEPA loss.
3. **3–5 seeds** for both, and ablations of the EMA target and the variance /
   covariance terms.
4. Remaining step 12 items: random goals, a learned goal-distance head, moving
   obstacles, partial observability, stochastic dynamics; and building each new
   map's codebook by exploration.
