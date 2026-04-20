from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import yaml


REPO = Path("/home/Creeken/Paper/数院大创赛/Code")
PYTHON = Path("/home/Creeken/miniconda3/envs/pytorch/bin/python")
BASE_CFG_PATH = (
    REPO
    / "outputs_abfull"
    / "eval_layer_alpha05_ratio_round23"
    / "alpha0p5_ratio0350_n30"
    / "config.yaml"
)
CONFIG_DIR = Path("/tmp/lorenz_eval_layer_configs_round24_alpha05_ratio035")
OUT_ROOT = REPO / "outputs_abfull" / "eval_layer_alpha05_ratio_round24_n100"
RUN_NAME = "alpha0p5_ratio0350_n100"


def bins(values: list[float]) -> dict[str, int]:
    return {
        "bin_22_0_23_3": sum(22.0 <= v < 23.3 for v in values),
        "bin_23_3_23_8": sum(23.3 <= v < 23.8 for v in values),
        "bin_23_8_24_7": sum(23.8 <= v < 24.7 for v in values),
        "bin_24_7_25_5": sum(24.7 <= v <= 25.5 for v in values),
        "below22": sum(v < 22.0 for v in values),
        "below21": sum(v < 21.0 for v in values),
        "above25p5": sum(v > 25.5 for v in values),
        "above26": sum(v > 26.0 for v in values),
    }


def gate(summary: dict, counts: dict[str, int]) -> dict[str, bool]:
    hist = summary.get("found_only_predicted_critical_point") or {}
    return {
        "found_ge_68": summary.get("num_found", 0) >= 68,
        "miss_le_0p32": summary.get("miss_rate", 1.0) <= 0.32,
        "mean_in_range": 23.90 <= hist.get("mean", 999.0) <= 24.15,
        "median_in_range": 23.95 <= hist.get("median", 999.0) <= 24.20,
        "std_le_0p80": hist.get("std", 999.0) <= 0.80,
        "below22_eq_0": counts["below22"] == 0,
        "above25p5_eq_0": counts["above25p5"] == 0,
        "above26_eq_0": counts["above26"] == 0,
        "shoulder_le_10": counts["bin_22_0_23_3"] <= 10,
        "right_bin_le_18": counts["bin_24_7_25_5"] <= 18,
    }


def main() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    OUT_ROOT.mkdir(parents=True, exist_ok=True)

    with BASE_CFG_PATH.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    cfg["evaluation"]["num_realizations"] = 100
    cfg["evaluation"]["base_param_value"] = 30.0
    cfg["evaluation"]["use_paper_reference_mapping"] = True
    cfg["evaluation"]["coarse_steps"] = 50
    cfg["evaluation"]["scan_step"] = 0.02
    cfg["evaluation"]["coarse_unhealthy_streak"] = 1
    cfg["reservoir"]["predict_steps"] = 400
    cfg["reservoir"]["train_length"] = 500
    cfg["reservoir"]["ridge_reg"] = 7.0e-5
    cfg["reservoir"]["alpha"] = 0.5
    cfg["detector"]["tail_std_ratio_threshold"] = 0.35
    cfg["detector"]["tail_amplitude_ratio_threshold"] = 0.35
    cfg["detector"]["tail_windows"] = 3

    cfg_path = CONFIG_DIR / f"{RUN_NAME}.yaml"
    with cfg_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, sort_keys=False)

    command = [
        str(PYTHON),
        "-m",
        "src.train.eval_reservoir",
        "--config",
        str(cfg_path),
        "--full",
    ]
    print("RUN", RUN_NAME, flush=True)
    subprocess.run(
        command,
        cwd=REPO,
        env={**os.environ, "PYTHONPATH": str(REPO)},
        check=True,
    )

    dest = OUT_ROOT / RUN_NAME
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(cfg_path, dest / "config.yaml")
    shutil.copy2(
        REPO / "outputs_abfull/lorenz_single_linspace_ab/full/reservoir/eval_summary.json",
        dest / "eval_summary.json",
    )
    shutil.copy2(
        REPO / "outputs_abfull/lorenz_single_linspace_ab/full/figures/fig_lorenz_single_critical_hist.png",
        dest / "fig_lorenz_single_critical_hist.png",
    )
    (dest / "run_command.txt").write_text(" ".join(command) + "\n", encoding="utf-8")

    with (dest / "eval_summary.json").open("r", encoding="utf-8") as f:
        summary = json.load(f)
    values = [
        r["critical_physical"]
        for r in summary.get("realizations", [])
        if r.get("status") == "found"
    ]
    counts = bins(values)
    row = {
        "name": RUN_NAME,
        "alpha": 0.5,
        "ratio": 0.35,
        "ridge_reg": 7.0e-5,
        "predict_steps": 400,
        "coarse_steps": 50,
        "train_length": 500,
        "summary": summary,
        "gate": gate(summary, counts),
    }
    row.update(counts)
    (OUT_ROOT / "round24_alpha05_ratio035_n100_summary.json").write_text(
        json.dumps(row, indent=2, sort_keys=True),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
