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
training/       train_numerical, train_encoder (with gate), train_world_model
evaluation/     linear probe, metrics, prediction accuracy, navigation, ladder, plots, `python -m evaluation`
planning/       imagination (no simulator calls), latent graph + D(c), true-model wrapper, P0/P1/P2, MPC loop
visualization/  replay dashboard
tests/          pytest suite (one file per step)
main.py         pipeline entry point
config.yaml     every setting and the seed
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
