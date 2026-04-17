from __future__ import annotations

import subprocess
import sys

from src.train.train_vae import parse_args


def run_module(module: str, args: list[str]) -> None:
    cmd = [sys.executable, "-m", module, *args]
    subprocess.run(cmd, check=True)


def main() -> None:
    args = parse_args()
    shared = ["--config", args.config]
    if args.quick:
        shared.append("--quick")
    if args.full:
        shared.append("--full")
    run_module("src.train.train_vae", shared)
    run_module("src.train.eval_vae", shared)
    run_module("src.train.train_reservoir", shared)
    run_module("src.train.eval_reservoir", shared)


if __name__ == "__main__":
    main()
