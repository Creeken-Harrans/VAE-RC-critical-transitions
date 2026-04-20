from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sweep Lorenz single base_param_value and collect eval_reservoir outputs."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/lorenz_single.yaml"),
        help="Base config path.",
    )
    parser.add_argument(
        "--base-values",
        type=float,
        nargs="+",
        default=[29.0, 30.0, 31.0],
        help="Candidate rho base values to evaluate.",
    )
    parser.add_argument("--quick", action="store_true", help="Use quick mode.")
    parser.add_argument("--full", action="store_true", help="Use full mode.")
    return parser.parse_args()


def mode_from_args(args: argparse.Namespace) -> str:
    if args.quick and args.full:
        raise ValueError("Use only one of --quick / --full.")
    if args.full:
        return "full"
    return "quick" if args.quick else "full"


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def dump_yaml(path: Path, payload: dict) -> None:
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(payload, f, sort_keys=False, allow_unicode=True)


def run_eval_reservoir(repo_root: Path, config_path: Path, mode: str) -> None:
    cmd = [sys.executable, "-m", "src.train.eval_reservoir", "--config", str(config_path)]
    cmd.append("--quick" if mode == "quick" else "--full")
    subprocess.run(cmd, cwd=repo_root, check=True)


def copy_artifacts(run_root: Path, sweep_dir: Path, base_value: float) -> dict:
    label = f"rho_{base_value:.1f}".replace(".", "_")
    target_dir = sweep_dir / label
    target_dir.mkdir(parents=True, exist_ok=True)

    eval_summary_src = run_root / "reservoir" / "eval_summary.json"
    hist_src = run_root / "figures" / "fig_lorenz_single_critical_hist.png"
    eval_summary_dst = target_dir / "eval_summary.json"
    hist_dst = target_dir / "fig_lorenz_single_critical_hist.png"

    shutil.copy2(eval_summary_src, eval_summary_dst)
    shutil.copy2(hist_src, hist_dst)

    with eval_summary_dst.open("r", encoding="utf-8") as f:
        summary = json.load(f)

    found_summary = summary.get("found_only_predicted_critical_point")
    return {
        "base_param_value": float(base_value),
        "base_param_strategy": summary.get("base_param_strategy"),
        "num_found": int(summary.get("num_found", 0)),
        "num_miss": int(summary.get("num_miss", 0)),
        "miss_rate": float(summary.get("miss_rate", 1.0)),
        "status_counts": summary.get("status_counts", {}),
        "found_mean": None if found_summary is None else found_summary.get("mean"),
        "found_median": None if found_summary is None else found_summary.get("median"),
        "found_std": None if found_summary is None else found_summary.get("std"),
        "artifact_dir": str(target_dir),
    }


def main() -> None:
    args = parse_args()
    mode = mode_from_args(args)

    repo_root = Path(__file__).resolve().parents[1]
    config_path = (repo_root / args.config).resolve() if not args.config.is_absolute() else args.config.resolve()
    cfg = load_yaml(config_path)
    if cfg.get("experiment_name") != "lorenz_single":
        raise ValueError("This helper is only intended for configs/lorenz_single.yaml-style runs.")

    run_root = repo_root / cfg["paths"]["output_root"] / cfg["experiment_name"] / mode
    required = [
        run_root / "data" / "trajectories.npz",
        run_root / "vae" / "latent_summary.json",
        run_root / "reservoir" / "reservoir.pkl",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Missing prerequisites for eval_reservoir sweep. Expected existing data/VAE/reservoir artifacts:\n"
            + "\n".join(missing)
        )

    sweep_dir = run_root / "base_sweeps"
    sweep_dir.mkdir(parents=True, exist_ok=True)

    aggregate: list[dict] = []
    for base_value in args.base_values:
        cfg_i = load_yaml(config_path)
        cfg_i.setdefault("evaluation", {})
        cfg_i["evaluation"]["base_param_strategy"] = "target_value"
        cfg_i["evaluation"]["base_param_value"] = float(base_value)

        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as tmp:
            tmp_path = Path(tmp.name)
        try:
            dump_yaml(tmp_path, cfg_i)
            print(f"[base sweep] running eval_reservoir with rho={base_value:.1f}")
            run_eval_reservoir(repo_root, tmp_path, mode)
            summary = copy_artifacts(run_root, sweep_dir, float(base_value))
            aggregate.append(summary)
            print(
                "[base sweep] "
                f"rho={base_value:.1f}, found={summary['num_found']}, miss_rate={summary['miss_rate']:.3f}, "
                f"mean={summary['found_mean']}, median={summary['found_median']}"
            )
        finally:
            tmp_path.unlink(missing_ok=True)

    aggregate_path = sweep_dir / "base_sweep_summary.json"
    with aggregate_path.open("w", encoding="utf-8") as f:
        json.dump(aggregate, f, indent=2, ensure_ascii=False)

    print(f"[base sweep] wrote summary to {aggregate_path}")


if __name__ == "__main__":
    main()
