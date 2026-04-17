#!/usr/bin/env python
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.train.train_vae import generate_bundle, load_resolved_config, npz_data_path, parse_args
from src.utils.io import get_output_dirs


def main() -> None:
    args = parse_args()
    cfg = load_resolved_config(args)
    dirs = get_output_dirs(cfg)
    bundle = generate_bundle(cfg)
    bundle.save(npz_data_path(dirs))


if __name__ == "__main__":
    main()
