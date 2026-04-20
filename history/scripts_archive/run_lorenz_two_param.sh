#!/usr/bin/env bash
set -euo pipefail
python -m src.train.reproduce --config configs/lorenz_two_param.yaml "$@"
