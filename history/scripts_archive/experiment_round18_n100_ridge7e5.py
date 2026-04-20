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
CONFIG_DIR = Path("/tmp/lorenz_eval_layer_configs_round18_n100_ridge7e5")
OUT_ROOT = REPO / "outputs_abfull" / "eval_layer_n100_ridge7e5_round18"


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
    cfg["detector"]["tail_std_ratio_threshold"] = 0.375
    cfg["detector"]["tail_amplitude_ratio_threshold"] = 0.375

    name = "ridge7e-5_ratio0375_predict400_n100"
    cfg_path = CONFIG_DIR / f"{name}.yaml"
    with cfg_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, sort_keys=False)

    print(f"RUN {name}", flush=True)
    subprocess.run(
        [str(PYTHON), "-m", "src.train.eval_reservoir", "--config", str(cfg_path), "--full"],
        cwd=REPO,
        env={**os.environ, "PYTHONPATH": str(REPO)},
        check=True,
    )

    dest = OUT_ROOT / name
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
        "name": name,
        "summary": summary,
        "below22": sum(v < 22.0 for v in values),
        "below21": sum(v < 21.0 for v in values),
        "above25p5": sum(v > 25.5 for v in values),
        "above26": sum(v > 26.0 for v in values),
    }
    with (OUT_ROOT / "round18_n100_ridge7e5_summary.json").open("w", encoding="utf-8") as f:
        json.dump(row, f, indent=2, sort_keys=True)


if __name__ == "__main__":
    main()
