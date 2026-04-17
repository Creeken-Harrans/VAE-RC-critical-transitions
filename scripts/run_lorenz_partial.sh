#!/usr/bin/env bash
set -euo pipefail
conda run -n pytorch python -m src.train.reproduce --config configs/lorenz_partial_obs.yaml "$@"
