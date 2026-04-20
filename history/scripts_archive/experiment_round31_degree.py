from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import yaml

from experiment_round25_lambda import bins, gate, score


REPO = Path("/home/Creeken/Paper/数院大创赛/Code")
PYTHON = Path("/home/Creeken/miniconda3/envs/pytorch/bin/python")
BASE_CFG_PATH = (
    REPO
    / "outputs_abfull"
    / "eval_layer_n1000_ridge7e5_round19"
    / "ridge7e-5_ratio0375_predict400_n1000"
    / "config.yaml"
)
CONFIG_DIR = Path("/tmp/lorenz_eval_layer_configs_round31_degree")
OUT_ROOT = REPO / "outputs_abfull" / "eval_layer_degree_round31"


VARIANTS = [
    {"name": "d2_n30", "d": 2},
    {"name": "d4_n30", "d": 4},
    {"name": "d6_n30", "d": 6},
    {"name": "d8_n30", "d": 8},
]


def main() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    OUT_ROOT.mkdir(parents=True, exist_ok=True)

    with BASE_CFG_PATH.open("r", encoding="utf-8") as f:
        base_cfg = yaml.safe_load(f)
    control_d = base_cfg["reservoir"]["d"]

    rows: list[dict] = []
    for variant in VARIANTS:
        cfg = json.loads(json.dumps(base_cfg))

        cfg["evaluation"]["num_realizations"] = 30
        cfg["evaluation"]["base_param_value"] = 30.0
        cfg["evaluation"]["use_paper_reference_mapping"] = True
        cfg["evaluation"]["coarse_steps"] = 50
        cfg["evaluation"]["scan_step"] = 0.02
        cfg["evaluation"]["coarse_unhealthy_streak"] = 1
        cfg["reservoir"]["d"] = variant["d"]
        cfg["reservoir"]["train_length"] = 500
        cfg["reservoir"]["lambda"] = 1.34
        cfg["reservoir"]["kin"] = 0.04
        cfg["reservoir"]["kb"] = 3.0
        cfg["reservoir"]["b0"] = 3.5
        cfg["reservoir"]["predict_steps"] = 400
        cfg["reservoir"]["ridge_reg"] = 7.0e-5
        cfg["reservoir"]["alpha"] = 0.7
        cfg["detector"]["tail_std_ratio_threshold"] = 0.375
        cfg["detector"]["tail_amplitude_ratio_threshold"] = 0.375
        cfg["detector"]["tail_windows"] = 3

        cfg_path = CONFIG_DIR / f"{variant['name']}.yaml"
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
        print(f"RUN {variant['name']}", flush=True)
        subprocess.run(
            command,
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
            "name": variant["name"],
            "d": variant["d"],
            "control_d": control_d,
            "train_length": 500,
            "lambda": 1.34,
            "kin": 0.04,
            "kb": 3.0,
            "b0": 3.5,
            "alpha": 0.7,
            "ratio": 0.375,
            "ridge_reg": 7.0e-5,
            "predict_steps": 400,
            "coarse_steps": 50,
            "score": score(summary, counts),
            "gate": gate(summary, counts),
            "summary": summary,
        }
        row.update(counts)
        rows.append(row)
        (OUT_ROOT / "round31_degree_summary.json").write_text(
            json.dumps(sorted(rows, key=lambda x: x["score"]), indent=2, sort_keys=True),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
