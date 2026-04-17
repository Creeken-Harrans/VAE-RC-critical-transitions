#!/usr/bin/env bash
set -euo pipefail
python -m src.train.reproduce --config configs/food_chain.yaml "$@"
