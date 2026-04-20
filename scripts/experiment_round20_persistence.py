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
CONFIG_DIR = Path("/tmp/lorenz_eval_layer_configs_round20_persistence")
OUT_ROOT = REPO / "outputs_abfull" / "eval_layer_persistence_round20"


VARIANTS = [
    {"name": "ridge7e-5_ratio0375_streak2_n100", "coarse_unhealthy_streak": 2, "tail_windows": 3},
    {"name": "ridge7e-5_ratio0375_tailwindows4_n100", "coarse_unhealthy_streak": 1, "tail_windows": 4},
    {"name": "ridge7e-5_ratio0375_streak2_tailwindows4_n100", "coarse_unhealthy_streak": 2, "tail_windows": 4},
]


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


def score_summary(summary: dict, values: list[float]) -> float:
    hist = summary.get("found_only_predicted_critical_point") or {}
    if not hist:
        return 999.0
    counts = bins(values)
    return (
        abs(hist.get("mean", 999.0) - 24.0)
        + abs(hist.get("median", 999.0) - 24.05)
        + max(0.0, hist.get("std", 999.0) - 0.75)
        + counts["bin_22_0_23_3"] * 0.02
        + counts["above25p5"] * 0.5
        + counts["below22"] * 0.5
        + max(0, 68 - summary.get("num_found", 0)) * 0.2
        + max(0.0, summary.get("miss_rate", 1.0) - 0.32) * 4.0
    )


def main() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    OUT_ROOT.mkdir(parents=True, exist_ok=True)

    summaries: list[dict] = []
    for variant in VARIANTS:
        with BASE_CFG_PATH.open("r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)

        cfg["evaluation"]["num_realizations"] = 100
        cfg["evaluation"]["base_param_value"] = 30.0
        cfg["evaluation"]["use_paper_reference_mapping"] = True
        cfg["evaluation"]["coarse_steps"] = 50
        cfg["evaluation"]["scan_step"] = 0.02
        cfg["evaluation"]["coarse_unhealthy_streak"] = variant["coarse_unhealthy_streak"]
        cfg["reservoir"]["predict_steps"] = 400
        cfg["reservoir"]["train_length"] = 500
        cfg["reservoir"]["ridge_reg"] = 7.0e-5
        cfg["detector"]["tail_std_ratio_threshold"] = 0.375
        cfg["detector"]["tail_amplitude_ratio_threshold"] = 0.375
        cfg["detector"]["tail_windows"] = variant["tail_windows"]

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
        row = {
            "name": variant["name"],
            "coarse_unhealthy_streak": variant["coarse_unhealthy_streak"],
            "tail_windows": variant["tail_windows"],
            "score": score_summary(summary, values),
            "summary": summary,
        }
        row.update(bins(values))
        summaries.append(row)
        with (OUT_ROOT / "round20_persistence_summary.json").open("w", encoding="utf-8") as f:
            json.dump(sorted(summaries, key=lambda x: x["score"]), f, indent=2, sort_keys=True)


if __name__ == "__main__":
    main()
