#!/usr/bin/env bash
set -euo pipefail
conda run -n pytorch python -m src.train.reproduce --config configs/lorenz_two_param.yaml "$@"
