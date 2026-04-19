from __future__ import annotations

import json
import math

import numpy as np
from tqdm import tqdm

from src.data.lorenz import LorenzConfig, simulate_lorenz
from src.models.reservoir.esn_parameter_driven import ParameterDrivenReservoir
from src.models.reservoir.transition_search import (
    detect_food_chain_health,
    detect_ks_health,
    detect_lorenz_health,
    scan_single_transition,
)
from src.train.train_vae import load_resolved_config, npz_data_path, parse_args
from src.utils.io import get_output_dirs, save_json
from src.utils.linear_map import apply_matrix_affine, apply_single_affine
from src.utils.metrics import classification_rates, relative_error, summarize_hist
from src.utils.plotting import save_classification_scatter, save_histogram


def load_run_fitted_mapping(vae_summary: dict) -> dict[str, float]:
    mapping = vae_summary["physical_from_latent"]
    return {
        "coef": float(mapping["coef"]),
        "intercept": float(mapping["intercept"]),
        "r2": float(mapping["r2"]),
    }


def resolve_single_param_mapping(cfg: dict, vae_summary: dict) -> dict[str, float | str]:
    evaluation_cfg = cfg["evaluation"]
    if bool(evaluation_cfg.get("use_paper_reference_mapping", False)):
        paper_mapping = evaluation_cfg["paper_reference_mapping"]
        return {
            "source": "paper_reference",
            "coef": float(paper_mapping["coef"]),
            "intercept": float(paper_mapping["intercept"]),
            "r2": float("nan"),
        }
    fitted = load_run_fitted_mapping(vae_summary)
    return {
        "source": "run_fitted",
        "coef": fitted["coef"],
        "intercept": fitted["intercept"],
        "r2": fitted["r2"],
    }


def infer_latent_scan_direction(physical_slope: float, target_physical_direction: str) -> float:
    if physical_slope == 0.0:
        raise ValueError("Cannot infer latent scan direction from zero physical slope.")
    if target_physical_direction == "decrease":
        return -1.0 if physical_slope > 0 else 1.0
    if target_physical_direction == "increase":
        return 1.0 if physical_slope > 0 else -1.0
    raise ValueError(f"Unsupported target_physical_direction: {target_physical_direction}")


def choose_single_param_base_index(params: np.ndarray, evaluation_cfg: dict) -> int:
    strategy = str(evaluation_cfg.get("base_param_strategy", "target_value"))
    if strategy == "max":
        return int(np.argmax(params[:, 0]))
    if strategy == "target_value":
        # repo-informed completion:
        # use a representative healthy operating point in the normal regime rather than the extreme training edge.
        target_value = float(
            evaluation_cfg.get(
                "base_param_value",
                0.5 * (float(np.min(params[:, 0])) + float(np.max(params[:, 0]))),
            )
        )
        return int(np.argmin(np.abs(params[:, 0] - target_value)))
    raise ValueError(f"Unsupported base_param_strategy: {strategy}")


def check_base_attractor_health(
    rollout_fn,
    base_z: np.ndarray,
    detector,
) -> bool:
    # paper-hard constraint:
    # only realizations that can sustain a healthy attractor at the base operating point
    # should participate in critical-transition search.
    base_pred = rollout_fn(base_z.copy())
    return bool(detector(base_pred))


def build_found_only_summary(values: np.ndarray) -> dict | None:
    if values.size == 0:
        return None
    return summarize_hist(values)


def summarize_scan_results(
    critical_latent_found: np.ndarray,
    critical_physical_found: np.ndarray,
    mapping_used: dict[str, float | str],
    latent_scan_direction: float,
    target_physical_direction: str,
    num_realizations: int,
    base_param_value: float,
    requested_base_param_value: float | None,
    base_latent_value: float,
    base_index: int,
    base_param_strategy: str,
    status_counts: dict[str, int],
    require_healthy_base: bool,
    coarse_unhealthy_streak: int,
    realization_records: list[dict],
) -> dict:
    num_found = int(status_counts.get("found", 0))
    num_miss = int(num_realizations - num_found)
    return {
        "mapping_used": {
            "source": str(mapping_used["source"]),
            "coef": float(mapping_used["coef"]),
            "intercept": float(mapping_used["intercept"]),
            "r2": None if math.isnan(float(mapping_used["r2"])) else float(mapping_used["r2"]),
        },
        "latent_scan_direction": float(latent_scan_direction),
        "target_physical_direction": target_physical_direction,
        "num_realizations": int(num_realizations),
        "num_found": num_found,
        "num_miss": num_miss,
        "miss_rate": float(num_miss / max(num_realizations, 1)),
        "status_counts": {k: int(v) for k, v in status_counts.items()},
        "base_param_value": float(base_param_value),
        "requested_base_param_value": None
        if requested_base_param_value is None
        else float(requested_base_param_value),
        "base_latent_value": float(base_latent_value),
        "base_index": int(base_index),
        "base_param_strategy": base_param_strategy,
        "require_healthy_base": bool(require_healthy_base),
        "coarse_unhealthy_streak": int(coarse_unhealthy_streak),
        "found_only_predicted_critical_point": build_found_only_summary(critical_physical_found),
        "found_only_predicted_critical_latent": build_found_only_summary(critical_latent_found),
        "realizations": realization_records,
    }


def main() -> None:
    args = parse_args()
    cfg = load_resolved_config(args)
    dirs = get_output_dirs(cfg)
    data = np.load(npz_data_path(dirs), allow_pickle=True)
    latent = np.load(dirs["vae"] / "latent_stats.npz", allow_pickle=True)
    with open(dirs["vae"] / "latent_summary.json", "r", encoding="utf-8") as f:
        vae_summary = json.load(f)
    reservoir = ParameterDrivenReservoir.load(dirs["reservoir"] / "reservoir.pkl")
    active = latent["active"]
    mu = latent["mu"][:, active]
    trajectories = data["trajectories"]
    rc_cfg = cfg["reservoir"]

    fig_prefix = cfg["figures"]["prefix"]
    summary = {}

    if cfg["system"]["type"] in {"lorenz_single", "lorenz_partial_obs", "ks", "food_chain"}:
        params = np.asarray(data["params"], dtype=np.float64)
        base_index = choose_single_param_base_index(params, cfg["evaluation"])
        base_param_strategy = str(cfg["evaluation"].get("base_param_strategy", "target_value"))
        requested_base_param_value = (
            float(cfg["evaluation"]["base_param_value"])
            if base_param_strategy == "target_value" and "base_param_value" in cfg["evaluation"]
            else None
        )
        init_series = trajectories[base_index, :, : rc_cfg["warmup"]]
        base_z = mu[base_index].astype(np.float64).copy()

        if cfg["system"]["type"] in {"lorenz_single", "lorenz_partial_obs"}:
            detector = lambda pred: detect_lorenz_health(pred, cfg["detector"])
        elif cfg["system"]["type"] == "ks":
            detector = lambda pred: detect_ks_health(pred, cfg["detector"])
        else:
            detector = lambda pred: detect_food_chain_health(pred, cfg["detector"])

        mapping_used = resolve_single_param_mapping(cfg, vae_summary)
        target_physical_direction = str(cfg["evaluation"].get("physical_critical_direction", "decrease"))
        if bool(cfg["evaluation"].get("auto_infer_scan_direction", False)):
            latent_scan_direction = infer_latent_scan_direction(float(mapping_used["coef"]), target_physical_direction)
        else:
            latent_scan_direction = float(cfg["evaluation"]["scan_direction"])
        require_healthy_base = bool(cfg["evaluation"].get("require_healthy_base", True))

        critical_latent_found: list[float] = []
        realization_records: list[dict] = []
        status_counts = {"found": 0, "no_transition_found": 0, "unhealthy_at_base": 0}
        for r_id in tqdm(
            range(cfg["evaluation"]["num_realizations"]),
            desc=f"eval_reservoir:{cfg['experiment_name']}",
            leave=True,
        ):
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
            reservoir_i.fit(
                [traj for traj in trajectories],
                [p for p in mu],
                washout=rc_cfg["washout"],
                train_length=rc_cfg["train_length"],
            )
            rollout_i = lambda z, res=reservoir_i: res.rollout(
                init_series,
                z,
                steps=rc_cfg["predict_steps"],
                warmup=init_series.shape[1],
            )
            base_is_healthy = check_base_attractor_health(
                rollout_i,
                base_z=base_z,
                detector=detector,
            )
            if require_healthy_base and not base_is_healthy:
                status_counts["unhealthy_at_base"] = status_counts.get("unhealthy_at_base", 0) + 1
                realization_records.append(
                    {
                        "realization": int(r_id),
                        "seed": int(cfg["seed"] + r_id),
                        "status": "unhealthy_at_base",
                        "base_is_healthy": bool(base_is_healthy),
                        "critical_latent": None,
                        "critical_physical": None,
                    }
                )
                continue
            result = scan_single_transition(
                rollout_i,
                init_series,
                base_z=base_z.copy(),
                direction=latent_scan_direction,
                scan_step=cfg["evaluation"]["scan_step"],
                coarse_steps=cfg["evaluation"]["coarse_steps"],
                binary_steps=cfg["evaluation"]["binary_steps"],
                health_fn=detector,
                base_is_healthy=base_is_healthy,
                coarse_unhealthy_streak=cfg["evaluation"].get("coarse_unhealthy_streak", 1),
            )
            status = str(result["status"])
            status_counts[status] = status_counts.get(status, 0) + 1
            if status == "found":
                critical_latent = float(result["z_critical"])
                critical_physical = float(
                    apply_single_affine(
                        np.asarray([critical_latent], dtype=np.float64),
                        float(mapping_used["coef"]),
                        float(mapping_used["intercept"]),
                    )[0]
                )
                critical_latent_found.append(critical_latent)
            else:
                critical_latent = None
                critical_physical = None
            realization_records.append(
                {
                    "realization": int(r_id),
                    "seed": int(cfg["seed"] + r_id),
                    "status": status,
                    "base_is_healthy": bool(base_is_healthy),
                    "critical_latent": critical_latent,
                    "critical_physical": critical_physical,
                }
            )

        critical_latent_found_arr = np.asarray(critical_latent_found, dtype=np.float64)
        critical_physical_found = apply_single_affine(
            critical_latent_found_arr,
            float(mapping_used["coef"]),
            float(mapping_used["intercept"]),
        )
        title = (
            cfg["experiment_name"]
            if critical_physical_found.size > 0
            else f"{cfg['experiment_name']} (no valid transitions found)"
        )
        save_histogram(
            dirs["figures"] / f"{fig_prefix}_critical_hist.png",
            critical_physical_found,
            cfg["evaluation"]["critical_truth"],
            cfg["evaluation"]["param_name"],
            title,
        )
        summary = summarize_scan_results(
            critical_latent_found=critical_latent_found_arr,
            critical_physical_found=critical_physical_found,
            mapping_used=mapping_used,
            latent_scan_direction=latent_scan_direction,
            target_physical_direction=target_physical_direction,
            num_realizations=cfg["evaluation"]["num_realizations"],
            base_param_value=float(params[base_index, 0]),
            requested_base_param_value=requested_base_param_value,
            base_latent_value=float(base_z[0]),
            base_index=base_index,
            base_param_strategy=base_param_strategy,
            status_counts=status_counts,
            require_healthy_base=require_healthy_base,
            coarse_unhealthy_streak=cfg["evaluation"].get("coarse_unhealthy_streak", 1),
            realization_records=realization_records,
        )
        if cfg["system"]["type"] == "ks":
            errs = np.array(
                [relative_error(v, cfg["evaluation"]["critical_truth"]) for v in critical_physical_found]
            )
            summary["ks_error_within_2pct"] = float(np.mean(errs < 0.02)) if errs.size > 0 else 0.0
            summary["ks_error_within_10pct"] = float(np.mean(errs < 0.10)) if errs.size > 0 else 0.0

    else:
        affine = np.asarray(cfg["evaluation"]["two_param_affine_matrix"], dtype=np.float64)
        z_active = mu[:, :2]
        z_min = z_active.min(axis=0)
        z_max = z_active.max(axis=0)
        margin = cfg["evaluation"]["latent_margin"]
        grid_size = cfg["evaluation"]["grid_size"]
        z1 = np.linspace(z_min[0] - margin, z_max[0] + margin, grid_size)
        z2 = np.linspace(z_min[1] - margin, z_max[1] + margin, grid_size)
        zz = np.array(np.meshgrid(z1, z2)).reshape(2, -1).T
        mapped = apply_matrix_affine(zz, affine)

        lorenz_cfg = LorenzConfig(
            sigma=cfg["system"]["sigma"],
            beta=cfg["system"]["beta"],
            dt=cfg["data"]["dt"],
            transient=cfg["data"]["transient_time"],
            trajectory_time=cfg["data"]["trajectory_time"],
        )
        norm_mean = np.asarray(data["norm_mean"])
        norm_std = np.asarray(data["norm_std"])
        init_series = trajectories[int(np.argmax(data["params"][:, 0])), :, : rc_cfg["warmup"]]

        def rollout_and_detect(z_pair: np.ndarray) -> bool:
            pred = reservoir.rollout(init_series, z_pair, steps=rc_cfg["predict_steps"], warmup=init_series.shape[1])
            return detect_lorenz_health(pred, cfg["detector"])

        truth_healthy = []
        pred_is_unhealthy = []
        outside_training = []
        for idx, (rho, beta) in enumerate(
            tqdm(mapped, desc=f"two_param_truth_scan:{cfg['experiment_name']}", leave=True)
        ):
            is_outside = not (
                cfg["data"]["train_rho_min"] <= rho <= cfg["data"]["train_rho_max"]
                and cfg["data"]["train_beta_min"] <= beta <= cfg["data"]["train_beta_max"]
            )
            outside_training.append(is_outside)
            raw = simulate_lorenz(float(rho), float(beta), lorenz_cfg, cfg["seed"] + idx)
            normalized = (raw - norm_mean.squeeze(0)) / norm_std.squeeze(0)
            truth_healthy.append(detect_lorenz_health(normalized, cfg["detector"]))
            pred_is_unhealthy.append(not rollout_and_detect(zz[idx]))
        truth_healthy = np.asarray(truth_healthy, dtype=bool)
        pred_is_unhealthy = np.asarray(pred_is_unhealthy, dtype=bool)
        outside_training = np.asarray(outside_training, dtype=bool)
        test_mask = outside_training
        rates = classification_rates(pred_is_unhealthy[test_mask], ~truth_healthy[test_mask])
        save_classification_scatter(
            dirs["figures"] / f"{fig_prefix}_classification.png",
            mapped[test_mask],
            pred_is_unhealthy[test_mask],
            (
                cfg["data"]["train_rho_min"],
                cfg["data"]["train_rho_max"],
                cfg["data"]["train_beta_min"],
                cfg["data"]["train_beta_max"],
            ),
            cfg["experiment_name"],
        )
        summary.update(rates)
        summary["num_two_param_test_points"] = int(test_mask.sum())

    save_json(dirs["reservoir"] / "eval_summary.json", summary)


if __name__ == "__main__":
    main()
