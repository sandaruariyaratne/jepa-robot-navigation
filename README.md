# Mini-JEPA

A small action-conditioned latent world model for grid navigation: learn to
predict in a learned latent space, imagine action sequences there, and plan
with model-predictive control, all on a CPU in about ten minutes.

```
RGB frame ──CNN encoder (frozen)──▶ z (32-D) ──predictor z + f(z, a)──▶ imagined z ──snap──▶ codebook cell
                                                                     │
                                       planner scores imagined rollouts, executes the first action, re-observes
```

Results and what they do and don't show: **[REPORT.md](REPORT.md)**. Full
tables: [results/results.md](results/results.md).

## Setup

Python 3.10+. From the project folder:

```
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

`requirements.txt` pins minimum versions of numpy, PyYAML, torch (CPU is enough),
pytest, pygame and matplotlib. pygame and matplotlib are only needed for the
viewer, dashboard and plots.

## Run everything

```
.venv/bin/python main.py all
```

| Command | What it does | Writes |
|---|---|---|
| `main.py collect` | 200 random episodes × 50 steps, episode split, held-out pairs | `data/transitions.npz`, `data/splits.json` |
| `main.py train-numerical` | (x, y, action) → next (x, y) baseline | `checkpoints/numerical.pt` |
| `main.py train-encoder` | autoencoder; gate: probe ≥ 99% and 25/25 decodes, else retrain with robot pixels × 10 | `checkpoints/encoder.pt`, `decoder.pt`, `encoder_decodes.png` |
| `main.py train-world` | residual latent predictor, rollout curriculum | `checkpoints/predictor.pt` |
| `main.py eval` | probe sanity check, imagined graph, planners, full evaluation and ladder | `checkpoints/latent_graph.png`, `results/` |
| `main.py fingerprint` | hashes of all deterministic outputs, to compare two runs | – |

Every stage reads [config.yaml](config.yaml) (`--config other.yaml` to use
another) and its fixed seed; re-running gives the same data, checkpoints and
results. Each stage can also be run on its own, e.g.
`python -m training.train_encoder`.

### v2: joint JEPA (step 12, experiment 1)

```
.venv/bin/python main.py train-jepa --config config_v2.yaml    # ~1 min -> checkpoints_v2/
.venv/bin/python main.py eval --config config_v2.yaml          # -> results_v2/
.venv/bin/python -m training.train_jepa --config config_v2.yaml --ablate-latent-dim 2,4,8,16,32
```

[config_v2.yaml](config_v2.yaml) extends config.yaml and only swaps the encoder
and predictor for jointly trained ones (EMA target encoder, variance /
covariance penalties). Its checkpoints use the v1 formats, so the graph,
planners, evaluation and dashboard (`--config config_v2.yaml`) work unchanged.
Findings: [REPORT.md §7](REPORT.md#7-v2-experiment-1-joint-jepa-training).

### Multi-map: held-out layouts (step 12)

```
.venv/bin/python main.py multimap --config config_multimap.yaml              # 100 maps, v1 -> results_multimap/
.venv/bin/python main.py multimap-jepa --config config_multimap_jepa.yaml    # same maps, joint JEPA (~11 min)
.venv/bin/python -m multimap.new_maps --config config_multimap_jepa.yaml                  # 500 new layouts
.venv/bin/python -m multimap.new_maps --set hard_maps --config config_multimap_jepa.yaml  # 500, 8-14 walls
.venv/bin/python -m multimap.new_maps --set maze_maps --config config_multimap_jepa.yaml  # 200 mazes
.venv/bin/python -m multimap.calibrate --config config_multimap_jepa.yaml    # unknown threshold from validation maps
.venv/bin/python -m multimap.new_maps --set maze_maps --threshold calibrated --planner snap --config config_multimap_jepa.yaml
.venv/bin/python -m multimap.step3 train && .venv/bin/python -m multimap.step3 eval && .venv/bin/python -m multimap.step3 summary
.venv/bin/python -m multimap.explore --set maze_maps     # no picture of every cell: imagine (A) / explore (B)
```

100 random layouts split 70 / 15 / 15 by map; each map snaps to its own
codebook. The stress tests load the trained models and never retrain; add
`--threshold calibrated` to use the validation-calibrated unknown threshold and
`--planner snap` to snap every imagined step to the codebook (100% on all
1,200 stress-test layouts). `multimap.step3` trains and compares JEPA, an
end-to-end pixel world model and two ablations over several seeds
(`results_step3/summary.md`; the pixel baseline takes ~1 h per seed).
`multimap.explore` drops the privileged picture of every cell: the robot
imagines the map from the start and goal pictures (A), or also corrects it
with what it sees while walking (B; `--budget explorer` for 60 moves, no loop rule).
Findings: [REPORT.md §8–11](REPORT.md#8-multi-map-experiments-held-out-layouts).

### Level C: fog of war, 10 × 10

```
.venv/bin/python -m multimap.collect --config config_fog.yaml        # 100 fogged 10 x 10 maps -> data_fog/
.venv/bin/python -m multimap.train_jepa --config config_fog.yaml     # ~1.5 h on a laptop CPU
.venv/bin/python -m multimap.calibrate --config config_fog.yaml      # single threshold (every-cell pictures)
# validation sets first (the test sets exclude them); each builds its maps on first use
.venv/bin/python -m multimap.explore --config config_fog.yaml --set val_fog_maps  --modes privileged,imagine,explore,oracle --budget explorer --workers 7
.venv/bin/python -m multimap.explore --config config_fog.yaml --set val_fog_mazes --modes privileged,imagine,explore,oracle --budget explorer --workers 7
.venv/bin/python -m multimap.explore --config config_fog.yaml --set fog_maps  --modes privileged,imagine,explore,oracle --budget explorer --workers 7 --name explore_fog_maps_explorer
.venv/bin/python -m multimap.explore --config config_fog.yaml --set fog_mazes --modes privileged,imagine,explore,oracle --budget explorer --workers 7 --name explore_fog_mazes_explorer
```

The robot sees only the 3 × 3 cells around itself; the rest of the frame is fog.
Imagined maps use separate stay / merge thresholds, computed on first use into
`checkpoints_fog/fog_thresholds.json`. `oracle` is a model-free explorer that knows
the true walls once it has seen them. `--workers` splits the maps over processes;
the counts are identical to one process. Findings: [REPORT.md §12](REPORT.md#12-level-c-fog-of-war-on-a-10--10-grid).

### Interactive web demo

[web/](web/) runs the trained multi-map models in the browser: drag walls to build a map,
and the robot plans with the joint JEPA from the rendered pixels. A switch chooses what it gets:
a picture of every cell, only the start and goal pictures (imagination only), or those
plus what it sees while walking (imagine + explore), as in REPORT.md §11. A second switch picks the
world: the 6 × 5 grid, or the 10 × 10 fog-of-war grid with its own model (REPORT.md §12). Plain
JavaScript, no build step and no server (about 3 MB of weights for both models).

```
.venv/bin/python web/export_models.py          # weights + test vectors from the checkpoints
node web/test/check.mjs                        # JS port vs PyTorch: frames, graph, D(c) exact
node web/test/check.mjs --bench                # JS planner on the benchmark maps vs the Python numbers
node web/test/explore_bench.mjs maze_maps 50    # JS imagination-only / explore modes vs multimap.explore
node web/test/explore_bench.mjs fog_maps 20     # the same on the fog-of-war test maps (their start cells)
cd web && python -m http.server 8765           # open http://127.0.0.1:8765
```

## Look at it

```
.venv/bin/python -m environment.viewer                                   # play the grid yourself (pygame)
.venv/bin/python -m visualization.dashboard --run P2 --start 0,4         # replay any evaluation episode
.venv/bin/python -m visualization.dashboard --run P0 --episodes          # list a run's 120 episodes
.venv/bin/python -m visualization.dashboard --run P0 --start 0,1 --export out/   # PNG per step + GIF
```

Dashboard runs: `Oracle`, `P0`, `P1`, `P2`, `Random` and the ladder rungs `D1`,
`D2`, `D3`, `Full`. Keys: ←/→ step, Home/End, Space play, q quit.

Also produced: `checkpoints/latent_graph.png` (the imagined graph, laid out by
steps-to-goal), `checkpoints/encoder_decodes.png`, and three plots in
`results/`.

## Layout

```
environment/    grid world, renderer, BFS oracle, pygame viewer
data/           collection, episode split + held-out pairs, datasets (single steps or K-step windows)
models/         numerical baseline, encoder, decoder, residual predictor
training/       train_numerical, train_encoder (with gate), train_world_model, train_jepa (v2)
evaluation/     linear probe, metrics, prediction accuracy, navigation, ladder, plots, `python -m evaluation`
web/            browser demo: JS port of renderer, networks, imagined graph and P2 (checked against PyTorch)
multimap/       many-layout experiment: maps, collection, v1 and JEPA training, evaluation, stress tests, calibration
planning/       imagination (no simulator calls), latent graph + D(c), true-model wrapper, P0/P1/P2, MPC loop
visualization/  replay dashboard
tests/          pytest suite (one file per step)
main.py         pipeline entry point
config.yaml     every setting and the seed (config_v2.yaml, config_multimap*.yaml, config_fog.yaml extend it)
```

## Tests

```
.venv/bin/python -m pytest -q
```

About a minute. Tests that need trained checkpoints skip themselves if those
are missing.

## Rules the code keeps

- Models never read the simulator's rules; true positions are used only for
  probes, splitting and evaluation. Imagination code does not import the
  simulator, and a test runs it with every simulator entry point disabled.
- Encoder, standardisation statistics and probes are fit on the training split
  only. Held-out pairs are excluded from predictor training and from checkpoint
  selection.
- Fit (episode split) and generalization (held-out pairs) are reported
  separately.
