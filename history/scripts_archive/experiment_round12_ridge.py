from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import yaml


REPO = Path("/home/Creeken/Paper/数院大创赛/Code")
PYTHON = Path("/home/Creeken/miniconda3/envs/pytorch/bin/python")
BASE_CFG_PATH = Path("/tmp/lorenz_eval_layer_configs_round2/ratio2p0_coarse50_n8.yaml")
CONFIG_DIR = Path("/tmp/lorenz_eval_layer_configs_round12_ridge")
OUT_ROOT = REPO / "outputs_abfull" / "eval_layer_ridge_round12"


VARIANTS = [
    {"name": "ratio1p875_ridge1e-7_predict400_n30", "ridge_reg": 1.0e-7, "ratio": 0.375},
    {"name": "ratio1p875_ridge1e-5_predict400_n30", "ridge_reg": 1.0e-5, "ratio": 0.375},
    {"name": "ratio1p875_ridge1e-4_predict400_n30", "ridge_reg": 1.0e-4, "ratio": 0.375},
    {"name": "ratio1p875_ridge1e-3_predict400_n30", "ridge_reg": 1.0e-3, "ratio": 0.375},
]


def score_summary(summary: dict, above25p5: int) -> float:
    hist = summary.get("found_only_predicted_critical_point") or {}
    if not hist:
        return 999.0
    mean = hist.get("mean", 999.0)
    median = hist.get("median", 999.0)
    std = hist.get("std", 999.0)
    min_value = hist.get("min", 999.0)
    max_value = hist.get("max", 0.0)
    found = summary.get("num_found", 0)
    miss_rate = summary.get("miss_rate", 1.0)
    return (
        abs(mean - 23.99)
        + abs(median - 23.99) * 0.75
        + max(0.0, std - 1.05) * 1.5
        + max(0.0, 22.3 - min_value) * 3.0
        + max(0.0, max_value - 25.5) * 2.0
        + above25p5 * 0.08
        + max(0, 20 - found) * 0.35
        + max(0.0, miss_rate - 0.35) * 4.0
    )


def main() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    OUT_ROOT.mkdir(parents=True, exist_ok=True)

    summaries: list[dict] = []
    for variant in VARIANTS:
        with BASE_CFG_PATH.open("r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)

        cfg["evaluation"]["num_realizations"] = 30
        cfg["evaluation"]["base_param_value"] = 30.0
        cfg["evaluation"]["use_paper_reference_mapping"] = True
        cfg["evaluation"]["coarse_steps"] = 50
        cfg["evaluation"]["scan_step"] = 0.02
        cfg["evaluation"]["coarse_unhealthy_streak"] = 1
        cfg["reservoir"]["predict_steps"] = 400
        cfg["reservoir"]["train_length"] = 500
        cfg["reservoir"]["ridge_reg"] = variant["ridge_reg"]
        cfg["detector"]["tail_std_ratio_threshold"] = variant["ratio"]
        cfg["detector"]["tail_amplitude_ratio_threshold"] = variant["ratio"]

        cfg_path = CONFIG_DIR / f"{variant['name']}.yaml"
        with cfg_path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(cfg, f, sort_keys=False)

        print(f"RUN {variant['name']}", flush=True)
        subprocess.run(
            [str(PYTHON), "-m", "src.train.eval_reservoir", "--config", str(cfg_path), "--full"],
            cwd=REPO,
            env={**os.environ, "PYTHONPATH": str(REPO)},
            check=True,
        )

        dest = OUT_ROOT / variant["name"]
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

        with (dest / "eval_summary.json").open("r", encoding="utf-8") as f:
            summary = json.load(f)
        values = [
            r["critical_physical"]
            for r in summary.get("realizations", [])
            if r.get("status") == "found"
        ]
        above25p5 = sum(v > 25.5 for v in values)
        summaries.append(
            {
                "name": variant["name"],
                "ridge_reg": variant["ridge_reg"],
                "above25p5": above25p5,
                "score": score_summary(summary, above25p5),
                "summary": summary,
            }
        )
        with (OUT_ROOT / "round12_ridge_summary.json").open("w", encoding="utf-8") as f:
            json.dump(sorted(summaries, key=lambda x: x["score"]), f, indent=2, sort_keys=True)


if __name__ == "__main__":
    main()
