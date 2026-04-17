#!/usr/bin/env bash
set -euo pipefail
python -m src.train.reproduce --config configs/ks.yaml "$@"
