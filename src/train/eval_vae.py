from __future__ import annotations

import numpy as np
import torch
from torch.utils.data import DataLoader

from src.data.datasets import TrajectoryWindowDataset
from src.models.vae import select_active_channels
from src.train.train_vae import build_vae, load_resolved_config, npz_data_path, parse_args
from src.utils.io import get_output_dirs, save_json
from src.utils.linear_map import fit_line_xy, fit_multi_affine, fit_single_affine
from src.utils.plotting import save_channel_stats, save_scatter_with_fit, save_two_param_planes


def main() -> None:
    args = parse_args()
    cfg = load_resolved_config(args)
    dirs = get_output_dirs(cfg)
    dataset = TrajectoryWindowDataset(
        npz_data_path(dirs),
        input_length=cfg["vae"]["input_length"],
        validation_length=cfg["vae"]["validation_length"],
        validation_random_length=cfg["vae"]["validation_random_length"],
        partial_observation=cfg["system"]["type"] == "lorenz_partial_obs",
        delay=cfg["system"].get("delay", 0),
        observed_indices=cfg["system"].get("observed_indices", [0]),
        seed=cfg["seed"] + 11,
    )
    loader = DataLoader(dataset, batch_size=cfg["eval"]["batch_size"], shuffle=False)
    sample = dataset[0]
    model = build_vae(cfg, sample["encoder_x"].shape[0])
    model.load_state_dict(torch.load(dirs["vae"] / "best.tar", map_location=next(model.parameters()).device))
    model.eval()
    device = next(model.parameters()).device

    mu_list = []
    logvar_list = []
    param_list = []
    with torch.no_grad():
        for batch in loader:
            x = batch["encoder_x"].to(device)
            params, logvar, _ = model.encode(x)
            mu_list.append(params.cpu().numpy())
            logvar_list.append(logvar.cpu().numpy())
            param_list.append(batch["param"].numpy())
    mu = np.concatenate(mu_list, axis=0)
    logvar = np.concatenate(logvar_list, axis=0)
    true_params = np.concatenate(param_list, axis=0)

    top_k = 2 if cfg["system"]["type"] == "lorenz_two_param" else 1
    stats = select_active_channels(mu, logvar, top_k=top_k)
    latent_payload = {
        "mu": mu,
        "logvar": logvar,
        "true_params": true_params,
        "var_mu": stats["var_mu"],
        "mean_sigma2": stats["mean_sigma2"],
        "score": stats["score"],
        "active": stats["active"],
    }
    np.savez_compressed(dirs["vae"] / "latent_stats.npz", **latent_payload)

    fig_prefix = cfg["figures"]["prefix"]
    save_channel_stats(
        dirs["figures"] / f"{fig_prefix}_channel_stats.png",
        stats["var_mu"],
        stats["mean_sigma2"],
        cfg["experiment_name"],
    )

    summary = {
        "active_latent_channel_ids": stats["active"].tolist(),
        "var_mu": stats["var_mu"].tolist(),
        "mean_sigma2": stats["mean_sigma2"].tolist(),
    }

    if top_k == 1:
        active_channel = int(stats["active"][0])
        active_z = mu[:, active_channel]
        fit = fit_single_affine(active_z, true_params[:, 0])
        line = np.asarray(fit_line_xy(true_params[:, 0], active_z)["prediction"])
        save_scatter_with_fit(
            dirs["figures"] / f"{fig_prefix}_latent_vs_{cfg['evaluation']['param_name']}.png",
            true_params[:, 0],
            active_z,
            line,
            cfg["evaluation"]["param_name"],
            "z_hat",
            cfg["experiment_name"],
        )
        summary["linear_mapping_coefficients"] = {
            "coef": np.asarray(fit["coef"]).tolist(),
            "intercept": fit["intercept"],
            "r2": fit["score"],
        }
        summary["active_channel"] = active_channel
        summary["physical_from_latent"] = {
            "coef": float(np.asarray(fit["coef"]).reshape(-1)[0]),
            "intercept": float(fit["intercept"]),
            "r2": float(fit["score"]),
            "active_channel": active_channel,
        }
    else:
        active_z = mu[:, stats["active"]]
        fit = fit_multi_affine(active_z, true_params)
        save_two_param_planes(
            dirs["figures"] / f"{fig_prefix}_latent_planes.png",
            true_params,
            active_z,
            cfg["experiment_name"],
        )
        summary["linear_mapping_coefficients"] = {
            "coef": np.asarray(fit["coef"]).tolist(),
            "intercept": np.asarray(fit["intercept"]).tolist(),
            "r2": fit["score"],
        }
        summary["active_channel"] = [int(v) for v in stats["active"].tolist()]

    save_json(dirs["vae"] / "latent_summary.json", summary)


if __name__ == "__main__":
    main()
