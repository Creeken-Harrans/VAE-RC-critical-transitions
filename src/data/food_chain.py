from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.integrate import solve_ivp

from src.data.base import TrajectoryBundle, compute_channel_stats, normalize_trajectories


@dataclass
class FoodChainParams:
    xc: float = 0.4
    yc: float = 2.009
    xp: float = 0.08
    yp: float = 2.876
    r0: float = 0.16129
    c0: float = 0.5


def food_chain_rhs(_: float, state: np.ndarray, kappa: float, p: FoodChainParams) -> np.ndarray:
    R, C, P = np.maximum(state, 1e-10)
    dR = R * (1.0 - R / kappa) - p.xc * p.yc * C * R / (R + p.r0)
    dC = p.xc * C * (p.yc * R / (R + p.r0) - 1.0) - p.xp * p.yp * P * C / (C + p.c0)
    dP = p.xp * P * (p.yp * C / (C + p.c0) - 1.0)
    return np.array([dR, dC, dP], dtype=np.float64)


def simulate_food_chain(kappa: float, cfg: dict, seed: int) -> np.ndarray:
    p = FoodChainParams(**cfg["system"]["fixed_params"])
    rng = np.random.default_rng(seed)
    y0 = np.array([0.8, 0.3, 0.4]) + 0.05 * rng.standard_normal(3)
    dt = cfg["data"]["dt"]
    t_eval = np.arange(0.0, cfg["data"]["transient_time"] + cfg["data"]["trajectory_time"] + dt, dt)
    sol = solve_ivp(
        food_chain_rhs,
        (float(t_eval[0]), float(t_eval[-1])),
        np.maximum(y0, 1e-6),
        method="DOP853",
        t_eval=t_eval,
        args=(kappa, p),
        rtol=1e-9,
        atol=1e-9,
    )
    traj = np.maximum(sol.y[:, int(cfg["data"]["transient_time"] / dt) :], 0.0)
    return traj


def generate_food_chain(cfg: dict) -> TrajectoryBundle:
    data_cfg = cfg["data"]
    params = np.linspace(data_cfg["train_param_min"], data_cfg["train_param_max"], data_cfg["num_param_samples"]).reshape(-1, 1)
    trajectories = np.stack([simulate_food_chain(float(kappa), cfg, cfg["seed"] + i) for i, (kappa,) in enumerate(params)], axis=0)
    train_mask = np.ones(len(params), dtype=bool)
    mean, std = compute_channel_stats(trajectories, train_mask)
    trajectories = normalize_trajectories(trajectories, mean, std)
    return TrajectoryBundle(
        trajectories=trajectories,
        params=params,
        param_names=["kappa"],
        train_mask=train_mask,
        system_type="food_chain",
        meta={"paper_truth": cfg["evaluation"]["critical_truth"]},
        norm_mean=mean,
        norm_std=std,
    )
