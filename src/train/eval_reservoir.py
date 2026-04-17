from __future__ import annotations

import numpy as np

from src.models.reservoir.esn_parameter_driven import ParameterDrivenReservoir
from src.models.reservoir.transition_search import detect_food_chain_health, detect_ks_health, detect_lorenz_health, scan_single_transition
from src.train.train_vae import load_resolved_config, npz_data_path, parse_args
from src.utils.io import get_output_dirs, save_json
from src.utils.linear_map import apply_matrix_affine, apply_single_affine
from src.utils.metrics import classification_rates, relative_error, summarize_hist
from src.utils.plotting import save_classification_scatter, save_histogram


def main() -> None:
    args = parse_args()
    cfg = load_resolved_config(args)
    dirs = get_output_dirs(cfg)
    data = np.load(npz_data_path(dirs), allow_pickle=True)
    latent = np.load(dirs["vae"] / "latent_stats.npz", allow_pickle=True)
    reservoir = ParameterDrivenReservoir.load(dirs["reservoir"] / "reservoir.pkl")
    active = latent["active"]
    mu = latent["mu"][:, active]
    trajectories = data["trajectories"]
    rc_cfg = cfg["reservoir"]

    fig_prefix = cfg["figures"]["prefix"]
    summary = {}

    if cfg["system"]["type"] in {"lorenz_single", "lorenz_partial_obs", "ks", "food_chain"}:
        idx = int(np.argmax(data["params"][:, 0]))
        init_series = trajectories[idx, :, : rc_cfg["warmup"]]
        base_z = mu[idx].astype(np.float64).copy()

        if cfg["system"]["type"] in {"lorenz_single", "lorenz_partial_obs"}:
            detector = lambda pred: detect_lorenz_health(pred, cfg["detector"])
        elif cfg["system"]["type"] == "ks":
            detector = lambda pred: detect_ks_health(pred, cfg["detector"])
        else:
            detector = lambda pred: detect_food_chain_health(pred, cfg["detector"])

        rollout = lambda z: reservoir.rollout(init_series, z, steps=rc_cfg["predict_steps"], warmup=init_series.shape[1])
        critical_latent = []
        for r_id in range(cfg["evaluation"]["num_realizations"]):
            reservoir_i = ParameterDrivenReservoir(
                input_dim=reservoir.input_dim,
                param_dim=reservoir.param_dim,
                nr=rc_cfg["nr"],
                degree=rc_cfg["d"],
                spectral_radius=rc_cfg["lambda"],
                kin=rc_cfg["kin"],
                kb=rc_cfg["kb"],
                b0=rc_cfg["b0"],
                alpha=rc_cfg["alpha"],
                ridge_reg=rc_cfg["ridge_reg"],
                seed=cfg["seed"] + r_id,
            )
            reservoir_i.fit([traj for traj in trajectories], [p for p in mu], washout=rc_cfg["washout"], train_length=rc_cfg["train_length"])
            rollout_i = lambda z, res=reservoir_i: res.rollout(init_series, z, steps=rc_cfg["predict_steps"], warmup=init_series.shape[1])
            z_star = scan_single_transition(
                rollout_i,
                init_series,
                base_z=base_z.copy(),
                direction=cfg["evaluation"]["scan_direction"],
                scan_step=cfg["evaluation"]["scan_step"],
                coarse_steps=cfg["evaluation"]["coarse_steps"],
                binary_steps=cfg["evaluation"]["binary_steps"],
                health_fn=detector,
            )
            critical_latent.append(z_star)
        critical_latent = np.array(critical_latent)

        mapping = cfg["evaluation"]["single_param_mapping"]
        critical_physical = apply_single_affine(critical_latent, mapping["coef"], mapping["intercept"])
        save_histogram(
            dirs["figures"] / f"{fig_prefix}_critical_hist.png",
            critical_physical,
            cfg["evaluation"]["critical_truth"],
            cfg["evaluation"]["param_name"],
            cfg["experiment_name"],
        )
        summary["predicted_critical_point"] = summarize_hist(critical_physical)
        if cfg["system"]["type"] == "ks":
            errs = np.array([relative_error(v, cfg["evaluation"]["critical_truth"]) for v in critical_physical])
            summary["ks_error_within_2pct"] = float(np.mean(errs < 0.02))
            summary["ks_error_within_10pct"] = float(np.mean(errs < 0.10))

    else:
        affine = np.asarray(cfg["evaluation"]["two_param_affine_matrix"], dtype=np.float64)
        mapped = apply_matrix_affine(mu, affine)
        rho, beta = mapped[:, 0], mapped[:, 1]
        healthy_truth = np.logical_and.reduce(
            [
                rho >= cfg["evaluation"]["healthy_region"]["rho_min"],
                rho <= cfg["evaluation"]["healthy_region"]["rho_max"],
                beta >= cfg["evaluation"]["healthy_region"]["beta_min"],
                beta <= cfg["evaluation"]["healthy_region"]["beta_max"],
            ]
        )
        pred_is_unhealthy = np.logical_or(rho < cfg["evaluation"]["critical_curve_proxy"]["rho_min"], beta < cfg["evaluation"]["critical_curve_proxy"]["beta_min"])
        rates = classification_rates(pred_is_unhealthy, ~healthy_truth)
        save_classification_scatter(
            dirs["figures"] / f"{fig_prefix}_classification.png",
            mapped,
            pred_is_unhealthy,
            (
                cfg["data"]["train_rho_min"],
                cfg["data"]["train_rho_max"],
                cfg["data"]["train_beta_min"],
                cfg["data"]["train_beta_max"],
            ),
            cfg["experiment_name"],
        )
        summary.update(rates)

    save_json(dirs["reservoir"] / "eval_summary.json", summary)


if __name__ == "__main__":
    main()
