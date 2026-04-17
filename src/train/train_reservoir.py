from __future__ import annotations

import numpy as np

from src.models.reservoir import ParameterDrivenReservoir
from src.train.train_vae import load_resolved_config, npz_data_path, parse_args
from src.utils.io import get_output_dirs, save_json


def main() -> None:
    args = parse_args()
    cfg = load_resolved_config(args)
    dirs = get_output_dirs(cfg)
    data = np.load(npz_data_path(dirs), allow_pickle=True)
    latent = np.load(dirs["vae"] / "latent_stats.npz", allow_pickle=True)
    active = latent["active"]
    mu = latent["mu"][:, active]
    trajectories = data["trajectories"]
    series_list = [trajectories[i] for i in range(trajectories.shape[0])]
    param_list = [mu[i] for i in range(mu.shape[0])]

    rc_cfg = cfg["reservoir"]
    reservoir = ParameterDrivenReservoir(
        input_dim=trajectories.shape[1],
        param_dim=mu.shape[1],
        nr=rc_cfg["nr"],
        degree=rc_cfg["d"],
        spectral_radius=rc_cfg["lambda"],
        kin=rc_cfg["kin"],
        kb=rc_cfg["kb"],
        b0=rc_cfg["b0"],
        alpha=rc_cfg["alpha"],
        ridge_reg=rc_cfg["ridge_reg"],
        seed=cfg["seed"],
    )
    metrics = reservoir.fit(series_list, param_list, washout=rc_cfg["washout"], train_length=rc_cfg["train_length"])
    reservoir.save(dirs["reservoir"] / "reservoir.pkl")
    save_json(dirs["reservoir"] / "train_metrics.json", metrics)


if __name__ == "__main__":
    main()
