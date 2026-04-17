# Unsupervised Critical Transition Reproduction

This repository is a runnable, modular reproduction-oriented implementation of the paper **“Unsupervised learning for anticipating critical transitions”**.

It is not a literal source-code reconstruction. The implementation follows three priority levels:

1. `paper-hard constraint`: the 2025 paper is treated as the primary specification for system equations, parameter ranges, Table I hyperparameters, latent-channel selection logic, experiment types, and reporting targets.
2. `repo-informed completion`: details omitted by the paper are filled from the closest public code by the same authors:
   - `lw-kong/VAE-CNN-RNN-extracting-parameter`
   - `lw-kong/Reservoir_with_a_Parameter_Channel_PRR2021`
3. `inferred default due to missing detail in paper`: conservative numerical choices are exposed in config when neither the paper nor public code fully specifies them.

## Constraint provenance

Directly from the paper:

- Two-stage pipeline: VAE latent-parameter extraction + parameter-driven reservoir computing.
- Active latent-channel criterion: high `var(mu_z)` and low `mean(sigma_z^2)`.
- Lorenz single-parameter, Lorenz two-parameter, Lorenz partial-observation, KS, and food-chain experiments.
- Table I VAE and reservoir hyperparameters.
- Appendix D/E/F linear mappings and evaluation logic.
- Appendix G: `ReLU` activation and `Adam` optimizer.

From author public repositories:

- `hidden_channels=32`, `prop_layers=1`, `param_size=5`.
- 4-layer dilated `Conv1d` encoder.
- inverse-variance weighted latent aggregation with correlation-length correction.
- hypernetwork-style decoder generating dynamic weights from latent `z`.
- Euler-like residual one-step decoder update.
- parameter-channel reservoir update with leak, spectral-radius scaling, and ridge readout.

Conservative numerical completions:

- Lorenz and food-chain trajectories use `solve_ivp`.
- KS uses Fourier pseudo-spectral ETDRK4 with periodic boundary conditions.
- The paper says “number of hidden layers fixed at 32”; this repo interprets that as `hidden_channels=32`, not 32 stacked CNN layers, because that matches the author VAE code and is the most conservative reading.
- Reservoir ridge regularization is configurable as `ridge_reg`; the paper does not explicitly provide it.
- Lorenz partial observation uses configurable delay embedding length `delay=8` by default; the paper specifies delay embedding but not the exact window size.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Project layout

- `configs/`: experiment configs, with paper-style defaults plus quick-demo overrides.
- `src/data/`: dynamical-system solvers, dataset/window creation, normalization helpers.
- `src/models/vae/`: latent-parameter extractor and hypernetwork decoder.
- `src/models/reservoir/`: parameter-driven ESN, ridge regression, transition search.
- `src/train/`: training, evaluation, and end-to-end reproduction entrypoints.
- `scripts/`: convenience shell wrappers.
- `tests/`: shape and smoke tests.

## Quick start

Generate data and run the full pipeline for Lorenz single-parameter in quick mode:

```bash
python -m src.train.reproduce --config configs/lorenz_single.yaml --quick
```

Run the paper-scale configuration for the same system:

```bash
python -m src.train.reproduce --config configs/lorenz_single.yaml --full
```

## Step-by-step usage

Generate data only:

```bash
python scripts/generate_all_data.py --config configs/lorenz_single.yaml --quick
```

Train only the VAE:

```bash
python -m src.train.train_vae --config configs/lorenz_single.yaml --quick
```

Train only the reservoir:

```bash
python -m src.train.train_reservoir --config configs/lorenz_single.yaml --quick
```

Evaluate and draw figures:

```bash
python -m src.train.eval_vae --config configs/lorenz_single.yaml --quick
python -m src.train.eval_reservoir --config configs/lorenz_single.yaml --quick
```

Run the end-to-end reproduction pipeline:

```bash
python -m src.train.reproduce --config configs/lorenz_single.yaml --quick
python -m src.train.reproduce --config configs/lorenz_two_param.yaml --quick
python -m src.train.reproduce --config configs/lorenz_partial_obs.yaml --quick
python -m src.train.reproduce --config configs/ks.yaml --quick
python -m src.train.reproduce --config configs/food_chain.yaml --quick
```

## Expected outputs

Each run writes under `outputs/<experiment_name>/`:

- `data/trajectories.npz`
- `vae/best.tar`
- `vae/latent_stats.npz`
- `reservoir/*.pkl`
- `figures/*.png`
- `summary.json`

## Quick demo mode vs full reproduction mode

`quick`:

- fewer parameter samples
- shorter trajectories
- fewer epochs
- fewer reservoir realizations
- intended for CPU smoke tests and iterative debugging

`full`:

- closer to the paper’s parameter counts and Table I hyperparameters
- intended for long reproduction runs

## Notes on scientific fidelity

- The primary target is **scientific consistency**, not pixel-level figure matching.
- The generated figures reproduce the same experiment types: active latent identification, latent-to-parameter affine fitting, critical-point histograms, and two-parameter healthy/unhealthy classification.
- The main pipeline uses only latent space for prediction. Mapping back to physical parameters is evaluation-only.
