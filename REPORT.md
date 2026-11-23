# Mini-JEPA: evaluation report

Can a small world model, trained only on pixels and actions, plan its way through grid mazes
it has never seen? This report follows one model family from a single fixed map to unseen
layouts, then takes away its privileged information step by step: first the pictures of every
cell, then the view of the whole map (fog of war). Every number comes from a results file in
this repository (§11). Settings were always chosen on validation maps, and each test set was
run once.

## Summary

**Key findings**

1. **On one map, perfect navigation is only fit.** The planner reaches the goal by a shortest
   path in 120/120 episodes. Yet on (cell, action) pairs held out of training, the learned
   dynamics are right 1/10 times, against 9/10 for a plain coordinate model (§2).
   Joint JEPA training alone does not change that on one map (§3).
2. **Many maps make it generalize.** Trained on 70 layouts, the joint JEPA navigates 100% of
   held-out test maps, against 44% for the same predictor on frozen autoencoder latents (§4).
3. **Planning on the learned graph removes the remaining failures.** Each imagined step is
   snapped to a known place, with one threshold chosen on validation maps. That brings all
   1,200 stress-test layouts, mazes included, to 100% success by shortest paths (§5).
4. **The JEPA objective is what makes this work.** A pixel world model with the same networks
   and data ties on the validation metric but solves 79% of mazes. Without the variance and
   covariance terms the latent collapses (§6).
5. **Without the free pictures, imagination alone drifts.** Given only the start and goal
   pictures, it reaches 41–89%. Its multi-step imagination is reliable only 3–4 moves ahead.
   An explorer that trusts experience over imagination reaches 83–99.6% (§7).
6. **Under fog of war the explorer still works.** On a 10 × 10 grid where it sees only its
   3 × 3 neighbourhood, it reaches the goal on 100% of test maps and 97.8% of test mazes, at
   the cost of long detours. Imagination alone manages 14–47% (§8).

**Headline results** (test sets; success / shortest path)

| World | Test set | What the planner gets | Result |
|---|---|---|---|
| 6 × 5, one map | 120 episodes | a picture of every cell | 100% / 100% |
| 6 × 5, unseen layouts | 1,200 maps (mazes included) | a picture of every cell | **100% / 100%** |
| 6 × 5, unseen mazes | 200 mazes | the same, pixel world model instead of JEPA | 79.4% (mean of 3 seeds) |
| 6 × 5, unseen mazes | 200 mazes | start + goal pictures, then what it sees (B) | 82.7% / 55.9% (94.1% with 60 moves) |
| 10 × 10, fog of war | 200 maps | start + goal pictures, then what it sees (B) | **100% / 48.7%** |
| 10 × 10, fog of war | 100 mazes | the same | **97.8% / 14.7%** |
| 10 × 10, fog of war | 100 mazes | oracle explorer (true walls once seen, no model) | 100% / 34.0% |

## Contents

1. [Setup](#1-setup)
2. [One map: fit vs generalization](#2-one-map-fit-vs-generalization)
3. [Joint JEPA training on one map](#3-joint-jepa-training-on-one-map)
4. [Many maps: unseen layouts](#4-many-maps-unseen-layouts)
5. [Planning on the learned graph](#5-planning-on-the-learned-graph)
6. [Is it the JEPA objective? Baselines and ablations](#6-is-it-the-jepa-objective-baselines-and-ablations)
7. [Without privileged pictures: imagine and explore](#7-without-privileged-pictures-imagine-and-explore)
8. [Fog of war on a 10 × 10 grid](#8-fog-of-war-on-a-10--10-grid)
9. [Limitations](#9-limitations)
10. [Next steps](#10-next-steps)
11. [Reproducing and files](#11-reproducing-and-files)

## 1. Setup

**Task.** A robot on a grid must reach a fixed goal cell (top right) using 4 actions (up, down,
left, right). A move into a wall or the border leaves it in place. It observes only an RGB
frame: no coordinates, no map.

<p>
  <img src="docs/start.png" width="240" alt="Frame with the robot at the start, bottom left">
  <img src="docs/goal.png" width="240" alt="Frame with the robot at the goal, top right">
</p>

*The robot's whole input on the single map: start frame and goal frame (shown enlarged; the
real frames are 48 × 40 pixels).*

**Three worlds.**

| | One map | Many maps | Fog of war |
|---|---|---|---|
| Grid | 6 × 5, 5 fixed walls | 6 × 5, 3–7 random walls | 10 × 10, 10–25 random walls |
| Frame | 3 × 40 × 48, whole map | 3 × 40 × 48, whole map | 3 × 80 × 80, only the 3 × 3 cells around the robot, the rest drawn as fog |
| Training data | 10,000 random-action transitions | 70 training maps × 1,000 transitions | 70 training maps × 4,000 transitions |
| Latent size | 32 | 64 | 64 |
| Sections | §2–3 | §4–7 | §8 |

**Model.** An encoder (3 stride-2 convolutions + linear layer) maps a frame to a latent z. A
residual predictor maps (z, action) to the next latent, ẑ = z + f(z, a), with f an MLP. It is
trained on rollouts that lengthen over training (K = 1 → 2 → 4 steps). Two training recipes are
compared:

- **Autoencoder** (called v1 in configs and result files). The encoder is trained to
  reconstruct pixels and then frozen; the predictor learns on its latents.
- **Joint JEPA** (v2). Encoder and predictor train together. Each predicted latent must match an
  EMA copy of the encoder (τ = 0.99, no gradient) applied to the real next frame. VICReg-style
  variance and covariance penalties prevent collapse. There is no decoder and no pixel loss.

**Planning.** A map's **codebook** is the latents of known places: on a new map, the encoded
picture of the robot on each free cell, or in §7–8 only real observations plus imagined nodes.
Each prediction **snaps** to its nearest codebook entry, or is flagged **unknown** if farther
than a threshold. Snapping every (place, action) gives the **imagined graph**. A breadth-first
search on that graph gives each place's imagined steps to the goal, **D(c)**.

The primary planner **P2** scores all 64 three-move action sequences by
min_k [k + D(snap(ẑ_k))], plus a small penalty for revisiting places. It executes the first
move, observes and replans (model-predictive control). Two simpler planners score by latent
distance to the goal: P0 (1,024 five-step plans) and P1 (beam search).

**Measurements.**

- **Success:** the robot reaches the goal within the move budget.
- **Shortest path:** it does so in the minimum number of moves.
- **Loop failure:** it enters the same cell for the third time (the usual rule; some
  experiments drop it and give a larger budget, as stated).
- **Navigation runs** start from every free cell (or a seeded subset per map) and repeat with
  several planner seeds (5 on the single map, 2 elsewhere).

Settings and thresholds are chosen on validation maps; test maps are never used for training
or selection, and each test set is run once.

## 2. One map: fit vs generalization

### 2.1 Setup

| | |
|---|---|
| World | 6 × 5 grid, 5 fixed walls, goal (5,0), 25 free cells, 4 actions; blocked moves stay in place |
| Observation | 3 × 40 × 48 RGB frame; only 25 distinct frames exist |
| Data | 200 episodes × 50 uniformly random actions = 10,000 transitions, random non-goal starts |
| Fit split | train / val / test = 160 / 20 / 20 **episodes** |
| Generalization split | 10 of the 100 (cell, action) pairs held out of all predictor training and model selection (7 moves, 3 bumps; at most one per cell) |
| Encoder | autoencoder (pixel MSE) → 32-D, then frozen |
| Predictor | f = MLP 36 → 128 → 128 → 32, rollout curriculum K = 1 → 2 → 4, checkpoint chosen by 5-step validation snap accuracy |
| Snap | nearest of the 25 codebook latents; **unknown** if farther than 3 × the median one-step error (0.0089) |
| Planners | P0: 1,024 five-step plans, final latent distance. P1: beam search 12 × 64, closest latent distance. P2: 64 three-step plans, min_k [k + D(snap(ẑ_k))] |

Why two splits: on a fixed map every (cell, action) pair recurs in every episode, so test
episodes contain the same transitions as training episodes. The episode split therefore
measures fit only. Held-out pairs are the one place the model must predict something it has
never seen.

### 2.2 Fit (test episodes, trained pairs)

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

A diagnostic ladder runs P2 with each learned part swapped for the truth. All four model rungs
are 100% optimal, so on this map neither the learned cost nor the learned dynamics costs
anything:

| Rung | Dynamics | Cost | Optimal episodes |
|---|---|---|---|
| Oracle (A*) | true | true | 120/120 |
| D1 | true | true D(c) | 120/120 |
| D2 | true | learned D(c) | 120/120 |
| D3 | learned | true D(c) | 120/120 |
| Full | learned | learned D(c) | 120/120 |
| Random policy | – | – | 7/120 (13 reach the goal) |

### 2.3 Generalization (held-out pairs)

| Held-out pairs (one step) | Latent predictor | Coordinate baseline (x, y, a → next x, y) |
|---|---|---|
| moves | 0/7 | 7/7 |
| bumps | 1/3 | 2/3 |
| **all** | **1/10** | **9/10** |

- **It memorised the transitions.** The latent predictor learned the 90 training transitions
  by heart; it did not learn "up moves the robot one cell up" as a rule it can apply
  elsewhere. Several held-out moves are predicted as the *opposite* move. The coordinate
  baseline generalizes 9/10; its one miss is an interior wall it has no way to know about.
- **The latents carry no grid geometry.** The encoder was trained only to reconstruct pixels,
  so its 25 latents give the predictor no structure to exploit. Freezing it prevents collapse
  but does not provide useful structure.
- **Errors compound.** Over all test windows (which include held-out pairs), snap accuracy falls
  from 91% after one imagined step to 49% after ten. A linear position probe on the imagined
  latents tracks snapping within 1–2 points.
- **What saves planning is calibration, not generalization.** All 10 held-out predictions land
  1.8–5.5 units from any codebook entry (threshold 0.0089). So all 10 are flagged unknown and
  become self-loops; none is trusted while wrong. Every affected cell still has another
  shortest route, so D(c) stays exact. A test with one injected, confidently wrong edge shows
  the failure mode this avoids: D(reference start) drops from 9 to 2.

### 2.4 Planners

| Planner (learned model, 120 episodes) | Success | Optimal | Path ratio | Loop failures |
|---|---|---|---|---|
| P0 (latent distance, 5 steps) | 80 | 50 | 1.45 | 40 |
| P1 (latent distance, beam 12 × 64) | 115 | 65 | 1.32 | 5 |
| P2 (imagined steps-to-goal, 3 steps) | 120 | 120 | 1.00 | 0 |

Latent distance is a weak cost here. Even with the true model (one-hot latents), P0 and P1 are
only 9/24 and 15/24 optimal: distance to the goal latent says "at the goal or not", not "how
far". P0 succeeds only within its 5-step horizon (100% up to distance 5, 0% from 7 on).
Replays also show P0 trusting plans that start with a held-out move, whose decoded rollouts
lose the robot entirely. The cost built from the imagined graph (P2) is what makes planning
reliable.

### 2.5 What this does not show

- **Anything about other maps.** One layout, one goal, 25 distinct frames: perfect navigation
  here is fit to this map.
- **That the model learned the dynamics.** It reproduces the transitions it was trained on; on
  new pairs it fails (1/10).
- **That navigation would survive a less redundant map.** P2 is optimal because every cell has
  a second shortest route around each unknown move. Where a held-out move is the only shortest
  route, paths would get longer; where it is the only route at all, the goal would become
  unreachable.
- **Statistical strength.** One training seed, a single draw of 10 held-out pairs, and
  navigation varies only the planner's tie-breaking seeds (5).
- **A strong encoder gate.** Any 25 distinct points in 32 dimensions are linearly separable, so
  the ≥ 99% probe gate mostly rules out collapse; the 25 decodes are the stricter half.

## 3. Joint JEPA training on one map

The obvious fix for §2.3 is to train the encoder *for prediction* instead of reconstruction.
The online encoder and predictor train together against an EMA target encoder (τ = 0.99, no
gradient), with variance and covariance penalties (weights 1 : 1 : 0.04) and no decoder.
Data, held-out pairs, rollout curriculum, checkpoint selection, planners and evaluation are
unchanged (`configs/single_map_jepa.yaml`; full tables in
[results/single_map_jepa/results.md](results/single_map_jepa/results.md)).

| | Autoencoder (v1) | Joint JEPA (v2) |
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

**On one map, joint training does not fix generalization.** Fit is the same, held-out moves
stay at 0/7, and the latents are no more grid-shaped than the autoencoder's. Nothing in the
objective rewards a latent space where "up" is the same change everywhere. With 25 states and
90 training transitions, memorising each transition still satisfies the loss.

**Latent size is not the fix either** (one seed each, so small differences are noise):

| Latent size | Trained pairs | Held-out moves | Held-out bumps | (x, y) R² |
|---|---|---|---|---|
| 2 | 81/90 | 3/7 | 1/3 | 0.10 |
| 4 | 90/90 | 2/7 | 2/3 | 0.29 |
| 8 | 90/90 | 1/7 | 2/3 | 0.19 |
| 16 | 90/90 | 0/7 | 2/3 | 0.52 |
| 32 | 90/90 | 0/7 | 2/3 | 0.24 |

Smaller latents help a little (2–3 of 7 held-out moves), but 2 dimensions already underfits
the training pairs, and none approaches the coordinate baseline's 7/7.

**A side effect the ladder caught.** The JEPA's one-step errors are less uniform, so "unknown =
farther than 3 × the median error" now also rejects 5 *correct* trained moves. That leaves the
reference start (0,4) with no trusted move toward the goal in the imagined graph. Full P2 still
succeeds from there by falling back to latent distance for one step. D3, which has a trusted
cost and so never falls back, bumps twice and stops (all 5 of its loop failures). The fault is
the threshold's calibration, not the predicted dynamics.

**What this suggests.** Generalization here needs either an inductive bias toward
action-consistent latents, or data that punishes memorisation, such as many layouts with
held-out layouts. §4 tests the second. The unknown threshold should be set from a quantile of
trained-pair errors rather than a multiple of the median.

## 4. Many maps: unseen layouts

§3 suggested that generalization needs data that punishes memorisation. This tests that
directly. There are 100 random layouts (same 6 × 5 grid, 3–7 walls, goal fixed at (5,0)),
split **by map** 70 / 15 / 15, with 1,000 random-action transitions per map. Each map gets its
own codebook (the latents of its ~25 frames) and snaps only to it. Both models share the data,
split, predictor size (latent 64, hidden 256 × 256), planners and evaluation:

- **Autoencoder (v1).** The gate was checked on the validation maps; it needed the
  robot-pixel weight × 10 fallback. A residual predictor learns on the frozen latents
  (`configs/multimap.yaml`).
- **Joint JEPA.** The §3 objective, 6,000 steps of 8 maps / 512 windows each
  (`configs/multimap_jepa.yaml`).

Checkpoints are chosen on validation-map 5-step snap accuracy; test maps are never used for
training or selection.

### 4.1 Fifteen held-out test maps

| | Autoencoder (v1) | Joint JEPA |
|---|---|---|
| One-step, normal moves | 70% | **100%** |
| One-step, border and wall bumps | 100% | 100% |
| Imagined rollouts, step 5 / 10 | 31% / 21% | **90% / 70%** |
| Imagined graph edges correct | 80% | **~100%** (1 of 1,488 wrong, flagged unknown) |
| Maps with D(c) exact everywhere | 5/15 | **15/15** |
| P2 navigation (Full): success / shortest path | 44% / 30% | **100% / 100%** |

- **The autoencoder memorises.** It fits the training maps perfectly (100% everywhere), but on
  a new layout a third of its normal moves land on the wrong cell. Its unknown threshold (3 × a
  median error of 2.27) never fires, so the planner trusts all of them.
- **The JEPA does not.** It scores the same on validation and test maps, and slightly *lower*
  than the autoencoder on training maps (91% vs 100% at 10 rollout steps).

With one layout (§3) the JEPA did not generalize; with 70 layouts it does.

### 4.2 Stress tests: 1,200 more layouts, no retraining

Fresh layouts from new seeds, none equal to any of the 100 experiment layouts (checked; no
frame of them occurs in the training data either). Navigation starts from every free cell of
every map, with two seeds.

| Test set | Maps | Avg path to goal | JEPA success / shortest path | Autoencoder success / shortest path |
|---|---|---|---|---|
| Like training (3–7 walls) | 500 | 5.0 | **99.9% / 99.8%** | 36% / 26% |
| Dense walls (8–14) | 500 | 5.4 | **97.3% / 97.2%** | 13% / 12% |
| Mazes (8–12 walls, the 200 most winding of 20,000) | 200 | 8.5 (max 18) | **94.0% / 93.9%** | 10% / 9.5% |
| Random actions (lower bound) | | | 3–7% | |

| | Like training | Dense | Mazes |
|---|---|---|---|
| JEPA collision accuracy (blocked vs free, all episode transitions) | 100.00% | 100.00% | 99.99% |
| Autoencoder collision accuracy | 81.0% | 56.6% | 65.4% |
| JEPA rollout accuracy, step 5 | 89.5% | 80.3% | 81.0% |
| JEPA edges wrong but trusted | 0 / 50,292 | 0 / 41,360 | 0 / 16,896 |
| JEPA edges flagged unknown | 0.7% | 2.4% | 2.9% |

- **The JEPA degrades gracefully.** Success drops with wall count (86.8% at 13–14 walls) and
  with path length (mazes: ~100% at 1–3 steps, 87% at 15, 68% at 17).
- **The autoencoder's collision accuracy is near chance on dense maps**, because it predicts
  "blocked" for many free moves.

**Every JEPA failure is a doubted correct move, never a trusted wrong one.** The unknown rule
flags ~2% of real moves, and the planner treats them as walls, which blocks the only route in
a corridor. On the mazes the learned cost alone (ladder D2) reaches 99.4%; the losses sit in
the learned dynamics (D3, 93.3%).

### 4.3 Recalibrating the unknown threshold: worse on its own

The threshold was set from the validation maps only, before looking at test results: the 99.9%
quantile of correct one-step snap distances (4.25 → 7.05). On the validation maps this cuts
correct step-1 moves rejected from 0.92% to 0.06%. But it also trusts 67–74% of the wrong
predictions at imagined steps 2–3 (up from 16–18%), where drift makes distance a poor signal.

| JEPA, Full success / shortest path | 3 × median (default) | Calibrated |
|---|---|---|
| Like training | 99.9% / 99.8% | 97.8% / 97.0% |
| Dense walls | 97.3% / 97.2% | 94.3% / 92.4% |
| Mazes | 94.0% / 93.9% | 77.5% / 74.6% |

The imagined graph became essentially perfect (D(c) exact on all 1,200 maps, ladder D2 = 100%).
But P2's 3-step look-ahead now trusts drifted wrong states and loops (maze loop failures
482 → 1,814). One threshold is doing two jobs: one-step edges want it high, unsnapped
multi-step rollouts want it low. The fix is not a second threshold but to snap every imagined
step and continue from the codebook entry (planning on the learned graph), so that only the
one-step check is needed. That is §5.

Full tables: [results/multimap/](results/multimap/) and
[results/multimap_jepa/](results/multimap_jepa/) (`results.md`, `new_maps.md`, `hard_maps.md`,
`maze_maps.md`, `*_calibrated.md`).

## 5. Planning on the learned graph

P2 still scores 64 three-step action sequences, but every imagined step is snapped to the
map's codebook, and the next step starts from that codebook entry, not from the raw prediction
(`P2(snap_each_step=True)`, `--planner snap`). Drift can no longer accumulate. The look-ahead is
exactly a walk on the imagined graph, and the unknown threshold only has to judge one-step
predictions, the job it was calibrated for.

**Choosing the setting without touching the test sets.** Two fresh validation sets were
generated with new seeds and excluded from every other set: 100 mazes (the most winding of
10,000) and 100 dense-wall maps (8–13 walls). JEPA, Full rung, success / shortest path:

| Setting | 100 validation mazes | 100 validation dense maps |
|---|---|---|
| P2, threshold 4.25 (3 × median) | 92.4% / 92.3% | 98.2% / 97.7% |
| Snapped P2, threshold 4.25 | 94.1% / 93.9% | 99.3% / 98.8% |
| **Snapped P2, threshold 7.05 (calibrated)** | **100% / 100%** | **100% / 100%** |

**Test sets, run once with the chosen setting** (the same 1,200 layouts as §4.2, every free
start cell, two seeds):

| Test set | Episodes | Before (§4, P2, 4.25) | Snapped P2, 7.05 |
|---|---|---|---|
| Like training (3–7 walls) | 24,146 | 99.9% / 99.8% | **100% / 100%** |
| Dense walls (8–14) | 19,680 | 97.3% / 97.2% | **100% / 100%** |
| Mazes (path up to 18) | 8,048 | 94.0% / 93.9% | **100% / 100%** |

Every imagined graph is exact (D(c) correct on all 1,200 maps, no fake shortcuts). No correct
normal move is flagged unknown, no wrong edge is trusted, and there are no loop failures. The
single calibrated threshold is enough once rollouts are snapped; the "two jobs" problem of §4.3
came from scoring unsnapped multi-step rollouts.

Files: `results/multimap_jepa/val_*.md` (selection) and `*_calibrated_snap.md` (test).

## 6. Is it the JEPA objective? Baselines and ablations

Is the JEPA objective doing the work, or would any encoder trained end to end with the
predictor do as well? Four variants share the data, the 100-map split, the encoder and
predictor architecture, the curriculum, the training steps and checkpoint selection
(`python -m multimap.step3 train | eval | summary`):

- **JEPA**: as in §4.
- **Pixel world model** (the fair baseline): encoder, predictor and a decoder trained together.
  The loss reconstructs each frame and decodes every imagined step into the true next frame
  (robot pixels weighted × 10).
- **No EMA target**: JEPA with the online encoder (stop-gradient) as target.
- **No variance / covariance terms**: JEPA with those weights set to 0.

Each is evaluated with both planners (P2 at 3 × median, and snapped P2 with its own
validation-calibrated threshold) on the 15 test maps and the 200 mazes. Mean ± standard
deviation over training seeds:

| | JEPA | Pixel world model | No EMA | No var / cov |
|---|---|---|---|---|
| Seeds | 3 | 3 | 2 | 2 |
| Val-map snap@5 (selection metric) | 90.1% ± 0.5 | 90.2% ± 1.1 | 91.1% ± 0.1 | 17.1% |
| Robot cell from latent, linear probe | 100% | 100% | 100% | 15.6% |
| Test maps: rollout accuracy, step 5 | 89.6% ± 0.2 | 89.5% ± 1.0 | 90.3% ± 0.8 | 16.7% |
| Mazes: one-step, normal moves | **100%** | 97.6% ± 0.8 | 100% | 0.1% |
| Mazes: wrong edges trusted (P2) | **0%** | 1.3% ± 0.5 | 0% | 54.5% |
| Test maps: navigation, snapped P2 | **100% ± 0** | 96.8% ± 5.5 | 99.9% ± 0.2 | 7.8% |
| Mazes: navigation, P2 | **95.2% ± 3.6** | 56.0% ± 5.7 | 83.8% ± 0.4 | 2.7% |
| **Mazes: navigation, snapped P2** | **100% ± 0** | 79.4% ± 11.9 | 98.3% ± 1.0 | 2.6% |
| Latent: smallest per-dimension std | 1.02 | 0.43 ± 0.04 | 1.01 | 0.00 |

- **The JEPA result holds across seeds.** All three seeds reach 100% on the mazes with snapped
  P2. With unsnapped P2 they spread from 92% to 99%, further evidence for planning on the
  graph.
- **The pixel baseline ties on the selection metric and still navigates worse.** It predicts
  ~2% of maze moves wrong and trusts about 1% of wrong edges; in a corridor one trusted wrong
  edge breaks the route. Maze success is 66%, 89% and 83% across seeds. Validation snap@5 does
  not predict navigation: the two models tie on it and differ by 20 points on mazes.
- **The EMA target helps modestly.** Predictions are as good, but navigation is slightly worse,
  mainly with unsnapped P2 (84% vs 95% on mazes).
- **The variance / covariance terms are essential.** Without them the encoder collapses to
  near-constant latents and navigation is at random-walk level.

Caveat: the pixel model trains on 128 windows per step instead of 512, because decoding every
imagined step is ~4× more expensive per window. Part of its gap may come from seeing fewer
windows rather than from the objective. It also took ~3× longer to train (49–69 min vs
~17 min).

Files: [results/baselines/summary.md](results/baselines/summary.md) and one JSON per run;
checkpoints in `checkpoints/baselines/`.

## 7. Without privileged pictures: imagine and explore

Every result above hands the planner a codebook: one rendered picture of the robot on every
free cell of the new map. A real agent never sees itself where it has not been. Here it gets
only real observations (`python -m multimap.explore`, same model, no retraining):

- **A (imagine).** Start from two pictures: the current observation and the goal image (the
  task). Imagine all 4 moves from each, breadth first. A prediction within the calibrated
  threshold (7.05) of an existing node is that node; otherwise it becomes a new imagined node
  and is expanded in turn. The nodes become the codebook; graph, D(c) and planner are as in §5.
- **B (explore).** As A, but each newly reached cell's real picture becomes an anchor, and the
  map is regrown around it. Every move actually made (a bump included) overrides the imagined
  edge for that cell and action. When the imagined map has no route to the goal, the robot
  heads for the nearest node it has only imagined (frontier exploration).

Planning walks the graph (`GraphP2`); on the privileged codebook it chooses exactly what
snapped P2 chooses (tested), and reproduces its 100%. Settings and both budgets were fixed on
the 200 validation maps of §5, then the test sets were run once. Success / shortest path,
every free start, two seeds:

| Test set | Picture of every cell | A: imagine | B: explore | B, explorer's budget |
|---|---|---|---|---|
| Like training (24,146 episodes) | 100% / 100% | 89.4% / 85.9% | **99.6% / 93.7%** | 100.0% / 93.7% |
| Dense walls (19,680) | 100% / 100% | 74.8% / 70.0% | **97.6% / 85.5%** | 99.6% / 85.5% |
| Mazes (8,048) | 100% / 100% | 40.6% / 38.4% | **82.7% / 55.9%** | 94.1% / 55.9% |

The first three columns use the usual rules: 30 moves, and a third visit to a cell counts as a
loop failure. An explorer must back out of dead ends, so the last column gives B 60 moves and
no loop rule.

**Why A fails on long routes: drift.** On validation mazes the nearest other cell's latent is
6.5–9.6 away (median 9.6). A raw imagined latent drifts that far within 3–5 moves (median
error 2.0 after one step, 4.5 after five, 99th percentile 10–11 from step 3). Beyond that the
model cannot tell which cell it is imagining, whatever the threshold.

- **The imagined maze before the first move** finds 75% of the real cells, gets 86% of their
  edges right, adds ~3 nodes that match no cell, and is never exactly right.
- **Steps-to-goal from the start** is exact in 47% of mazes (92% on training-like maps).
- **A's maze success falls with distance:** 99% at 3 moves, 80% at 5, 33% at 8, 5% at 12.

**Why B recovers: real pictures replace imagined ones.** B walks into a wall on 0.9% of maze
moves (A: 24%), and its maze success stays at 71–87% for every route length from 9 to 17
moves. The price is detours (1.9 extra moves per success on mazes, so only 56% shortest paths)
and loop failures on long mazes. With the explorer's budget, 94% of maze runs reach the goal.
Without the experience override and frontier step, B reached 58% on the first 10 validation
mazes; with them, 83%.

So the 100% of §5 depends on the privileged pictures for long routes. The model's one-step
predictions are good enough to explore with, but its multi-step imagination is reliable only
3–4 moves ahead.

Files: `results/multimap_jepa/explore_*.md` (`_budget` = explorer's budget; `val_` =
selection).

## 8. Fog of war on a 10 × 10 grid

In §7 every picture still shows the whole map. Here the robot sees only the 3 × 3 cells around
itself (view radius 1), and every other cell is drawn as fog (`configs/fog.yaml`). The grid is
10 × 10 (goal top right, 10–25 walls, 80 × 80 frames), so routes are up to 3× longer than on
6 × 5. The robot's own position is still visible in every frame, since the view window sits
where the robot is. What is hidden is the walls, and the goal, beyond one step.

**Model.** Same joint-JEPA recipe, retrained on fogged frames: 70 training maps, 40 random
episodes of 100 moves each, 8,000 steps, rollout length K = 1 → 2 → 4. On unseen validation
maps a linear probe reads the robot's cell from the latent 100% of the time. One-step
predictions snap to the right cell 99.0% of the time, five-step rollouts 73.7%.

**One threshold breaks imagination under fog.** A move into fog cannot be predicted exactly:
the next picture shows walls the robot has never seen. The predicted latent lands between the
possibilities, often nearer its own cell than the 6.93 calibrated threshold, so the §7 rule
reads it as "blocked". On validation mazes, imagination stalled at 5.7 nodes for 71 real
cells, and the goal was unreachable in 474 of 500 imagined maps. The fix is two thresholds,
both measured on the validation split of the training maps:

- **stay = 3.53.** 99% of blocked moves predict within this distance of their own cell. Closer
  than that, the move is a bump.
- **merge = 4.47.** Only 1% of real moves come this close to a wrong cell. Within it, the
  prediction is that node; otherwise it is a new imagined node. 94% of real moves land within
  merge of their true cell.

On validation (300 moves, no loop rule; 1,000 runs per set):

| Validation | Rule | Every-cell pictures | A: imagine | B: explore |
|---|---|---|---|---|
| Maps | one threshold | **100%** | 12.5% | 38.8% |
| Maps | stay / merge | 96.0% | **41.6%** | **100%** |
| Mazes | one threshold | **73.8%** | 9.8% | 21.7% |
| Mazes | stay / merge | 42.0% | **15.1%** | **96.9%** |

So the frozen setting is per mode: imagined maps (A, B) use stay / merge, and the every-cell
codebook keeps the calibrated single threshold. The comparison point is an **oracle
explorer**: perfect perception, true walls known once seen, unseen cells assumed free,
shortest route re-planned after every move. It needs no model and shows the cost of not
seeing the map.

**Test**, run once with those settings: 200 maps and 100 mazes (25–35 walls) never used for
training or selection, 10 seeded start cells per map, two seeds. Each cell is success /
shortest path:

| Test set | Budget | Every-cell pictures | A: imagine | B: explore | Oracle explorer |
|---|---|---|---|---|---|
| Maps (4,000 runs) | 300 moves, no loop rule | 99.8% / 96.3% | 47.3% / 33.9% | **100% / 48.7%** | 100% / 64.9% |
| Mazes (2,000 runs) | 300 moves, no loop rule | 81.0% / 70.3% | 14.0% / 12.4% | **97.8% / 14.7%** | 100% / 34.0% |
| Maps | 100 moves, 3rd visit = loop | 99.5% / 96.3% | 41.8% / 33.9% | 80.0% / 48.7% | 99.0% / 64.9% |
| Mazes | 100 moves, 3rd visit = loop | 75.8% / 70.3% | 13.2% / 12.4% | 21.7% / 14.7% | 78.8% / 34.0% |

The 300-move budget is the primary one. Even the oracle has to walk back out of dead ends it
could not see, and the usual loop rule fails it on 19% of validation mazes. That rule mostly
measures how often a run backtracks, so the lower rows are for comparison only.

**B works under fog.** With nothing but the start and goal pictures and what it sees as it
walks, B reaches the goal on every test map and on 97.8% of test mazes. On mazes it stays at
96–100% for every route length up to 40 moves.

- **B does better than the every-cell pictures on mazes** (97.8% against 81.0%). Those
  pictures still give every cell, but the edges between them are imagined moves into fog, and
  that planner never corrects them. On mazes, 83% of its plans find no route on the graph and
  fall back to latent search, and its success drops to 72% for routes over 20 moves. B
  replaces imagined edges with the moves it really made, and walks into a wall on 3.5% of
  moves.
- **B pays in detours.** On mazes it averages 72 extra moves per success against the oracle's
  10, and 93 moves per run against 26. Only 15% of its maze runs follow a shortest path
  (oracle 34%). About a quarter of its plans head for cells it has only imagined, because its
  map has no route to the goal yet. The difference from the oracle is the price of seeing walls
  through a model instead of exactly.

**A does not work under fog.** Imagining the whole map from two pictures means imagining walls
that are hidden.

- **The imagined maze before the first move** has 3× as many nodes as there are cells, mostly
  imagined fog contents matching no real cell. It finds 24% of the real cells (maps: 47%).
- **Steps-to-goal from the start** is right in 14% of mazes.
- **In motion,** A walks into a wall on about 90% of moves. It succeeds on short routes (91% of
  mazes up to 3 moves) and almost never beyond 10.

Mazes have more walls than any training map (25–35 against 10–25). B handles them; the
every-cell planner's 81% is partly that shift.

**The browser port matches.** The web demo's JavaScript planner reproduces these results on the
same test maps and start cells: on 20 maps, A 57.8% (Python 56.2%) and B 100% (100%); on 10
mazes, A 14.0% (14.5%) and B 100% (100%). The small differences come from tie-breaking with a
different random generator.

Files: `results/fog/explore_fog_*` (test), `explore2_val_fog_*` (validation, stay / merge),
`explore_val_fog_*` (validation, one threshold), `oracle_val_fog_*`. Thresholds:
`checkpoints/fog/fog_thresholds.json`.

## 9. Limitations

- **Narrow conditions.** Two grid sizes (6 × 5, and 10 × 10 under fog), a fixed goal,
  deterministic dynamics and noise-free frames. Every test layout comes from the same kind of
  generator.
- **Not a good long-horizon model.** Raw rollouts drift (69% correct at 10 steps on new maps).
  Navigation is perfect because each imagined step is snapped to a per-map codebook, i.e. the
  planner works on a learned graph.
- **Not full partial observability.** Under fog (§8) the walls are hidden, but the robot's
  position is not: the view window shows where it is. A robot that had to work out where it is
  would need memory in the encoder; here the explorer's map is the only memory.
- **Not a fully matched baseline.** The pixel model saw a quarter as many windows per step, and
  the ablations have 2 seeds, not 3–5.
- **Validation snap@5 is a weak selection metric.** It does not predict navigation (§6).

## 10. Next steps

1. **Longer reliable imagination.** Train with longer rollouts (K = 8–12), or with a loss that
   keeps distinct cells farther apart than the multi-step drift, and re-run §7; A is the
   direct measure.
2. **A fairer baseline and a better checkpoint metric.** Train the pixel baseline at 512
   windows per step, and select checkpoints on validation navigation rather than snap@5.
3. **Fewer detours under fog.** B pays 7–10× the oracle's extra moves. Training on longer
   rollouts into fog, or predicting a distribution over what fog hides, would bring imagined
   frontier cells closer to the real ones.
4. **Harder conditions.** Random goals, a learned goal-distance head, moving obstacles, a hidden
   robot position and stochastic dynamics.

## 11. Reproducing and files

Each experiment has one config in `configs/`; its data, checkpoints and results are in matching
folders. Every run uses a fixed seed, and every stage reads only its config.

| Experiment | Config | Results | Checkpoints |
|---|---|---|---|
| One map (§2) | `configs/single_map.yaml` | [results/single_map/](results/single_map/) | `checkpoints/single_map/` |
| Joint JEPA, one map (§3) | `configs/single_map_jepa.yaml` | [results/single_map_jepa/](results/single_map_jepa/) | `checkpoints/single_map_jepa/` |
| Many maps, autoencoder (§4) | `configs/multimap.yaml` | [results/multimap/](results/multimap/) | `checkpoints/multimap/` |
| Many maps, JEPA (§4, 5, 7) | `configs/multimap_jepa.yaml` | [results/multimap_jepa/](results/multimap_jepa/) | `checkpoints/multimap_jepa/` |
| Baselines and ablations (§6) | built from `configs/multimap_jepa.yaml` | [results/baselines/](results/baselines/) | `checkpoints/baselines/` |
| Fog of war (§8) | `configs/fog.yaml` | [results/fog/](results/fog/) | `checkpoints/fog/` |

**The single-map pipeline is deterministic.**

```
python main.py all           # ~10 min on a laptop CPU; stops at the first failed gate
python main.py fingerprint   # hashes of every deterministic output
```

A clean copy (no data, checkpoints or results) re-run with `main.py all` (9.4 min) produced
fingerprints identical to the run reported here for all 13 outputs: data, splits, the four
checkpoints' tensors, every metrics file and the results table. Wall-clock planning times are
the only fields excluded.

The commands for every other experiment are in the [README](README.md#reproducing-the-experiments).
