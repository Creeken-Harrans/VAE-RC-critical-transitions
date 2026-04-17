#!/usr/bin/env bash
set -euo pipefail
python -m src.train.reproduce --config configs/lorenz_partial_obs.yaml "$@"
