from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.integrate import solve_ivp

from src.data.base import TrajectoryBundle, compute_channel_stats, normalize_trajectories


@dataclass
class LorenzConfig:
    sigma: float = 10.0
    beta: float = 8.0 / 3.0
    dt: float = 0.01
    transient: float = 25.0
    trajectory_time: float = 120.0
    observed_indices: tuple[int, ...] = (0, 1, 2)


def lorenz_rhs(_: float, state: np.ndarray, sigma: float, rho: float, beta: float) -> np.ndarray:
    x1, x2, x3 = state
    return np.array(
        [
            sigma * (x2 - x1),
            x1 * (rho - x3) - x2,
            x1 * x2 - beta * x3,
        ],
        dtype=np.float64,
    )


def simulate_lorenz(rho: float, beta: float, cfg: LorenzConfig, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    y0 = np.array([1.0, 1.0, 1.0], dtype=np.float64) + 0.25 * rng.standard_normal(3)
    t_eval = np.arange(0.0, cfg.transient + cfg.trajectory_time + cfg.dt, cfg.dt)
    sol = solve_ivp(
        lorenz_rhs,
        (float(t_eval[0]), float(t_eval[-1])),
        y0,
        method="DOP853",
        t_eval=t_eval,
        args=(cfg.sigma, rho, beta),
        rtol=1e-9,
        atol=1e-9,
    )
    traj = sol.y[:, int(cfg.transient / cfg.dt) :]
    return traj[list(cfg.observed_indices)]


def sample_single_params(data_cfg: dict, seed: int) -> np.ndarray:
    strategy = str(data_cfg.get("param_sampling_strategy", "linspace"))
    low = float(data_cfg["train_param_min"])
    high = float(data_cfg["train_param_max"])
    size = int(data_cfg["num_param_samples"])
    if strategy == "linspace":
        values = np.linspace(low, high, size, dtype=np.float64)
    elif strategy == "uniform_random":
        rng = np.random.default_rng(seed)
        values = np.sort(rng.uniform(low, high, size=size))
    else:
        raise ValueError(f"Unsupported Lorenz single param_sampling_strategy: {strategy}")
    return values.reshape(-1, 1)


def generate_lorenz_single(cfg: dict) -> TrajectoryBundle:
    data_cfg = cfg["data"]
    sys_cfg = LorenzConfig(
        sigma=cfg["system"]["sigma"],
        beta=cfg["system"]["beta"],
        dt=data_cfg["dt"],
        transient=data_cfg["transient_time"],
        trajectory_time=data_cfg["trajectory_time"],
        observed_indices=tuple(cfg["system"].get("observed_indices", [0, 1, 2])),
    )
    params = sample_single_params(data_cfg, cfg["seed"])
    trajectories = np.stack([simulate_lorenz(float(rho), sys_cfg.beta, sys_cfg, cfg["seed"] + i) for i, (rho,) in enumerate(params)], axis=0)
    train_mask = np.ones(len(params), dtype=bool)
    mean, std = compute_channel_stats(trajectories, train_mask)
    trajectories = normalize_trajectories(trajectories, mean, std)
    paper_mapping = cfg["evaluation"].get(
        "paper_reference_mapping",
        cfg["evaluation"].get("single_param_mapping", {}),
    )
    return TrajectoryBundle(
        trajectories=trajectories,
        params=params,
        param_names=["rho"],
        train_mask=train_mask,
        system_type="lorenz_single",
        meta={"paper_mapping": paper_mapping},
        norm_mean=mean,
        norm_std=std,
    )


def generate_lorenz_two_param(cfg: dict) -> TrajectoryBundle:
    data_cfg = cfg["data"]
    sys_cfg = LorenzConfig(
        sigma=cfg["system"]["sigma"],
        beta=cfg["system"]["beta"],
        dt=data_cfg["dt"],
        transient=data_cfg["transient_time"],
        trajectory_time=data_cfg["trajectory_time"],
    )
    rng = np.random.default_rng(cfg["seed"])
    rho = rng.uniform(data_cfg["train_rho_min"], data_cfg["train_rho_max"], size=data_cfg["num_param_samples"])
    beta = rng.uniform(data_cfg["train_beta_min"], data_cfg["train_beta_max"], size=data_cfg["num_param_samples"])
    params = np.stack([rho, beta], axis=1)
    trajectories = np.stack([simulate_lorenz(float(r), float(b), sys_cfg, cfg["seed"] + i) for i, (r, b) in enumerate(params)], axis=0)
    train_mask = np.ones(len(params), dtype=bool)
    mean, std = compute_channel_stats(trajectories, train_mask)
    trajectories = normalize_trajectories(trajectories, mean, std)
    return TrajectoryBundle(
        trajectories=trajectories,
        params=params,
        param_names=["rho", "beta"],
        train_mask=train_mask,
        system_type="lorenz_two_param",
        meta={"paper_affine_matrix": cfg["evaluation"]["two_param_affine_matrix"]},
        norm_mean=mean,
        norm_std=std,
    )


def generate_lorenz_partial(cfg: dict) -> TrajectoryBundle:
    cfg = {**cfg}
    cfg["system"] = {**cfg["system"], "observed_indices": [0]}
    bundle = generate_lorenz_single(cfg)
    bundle.system_type = "lorenz_partial_obs"
    bundle.param_names = ["rho"]
    return bundle
