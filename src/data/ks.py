from __future__ import annotations

import numpy as np

from src.data.base import TrajectoryBundle, compute_channel_stats, normalize_trajectories


def ks_etdrk4(phi: float, nu: float, nx: int, length: float, dt: float, total_time: float, transient_time: float, sample_stride: int, seed: int) -> np.ndarray:
    # repo-informed completion: ETDRK4 is the most conservative completion consistent with the paper and the public KS code.
    rng = np.random.default_rng(seed)
    x = np.linspace(0.0, length, nx, endpoint=False)
    u0 = np.cos(2 * x / length) + 0.5 * rng.standard_normal(nx)
    k = 2 * np.pi * np.fft.fftfreq(nx, d=length / nx)
    L = phi * k**2 - nu * k**4
    g = -0.5j * phi * k

    m = 32
    E = np.exp(dt * L)
    E2 = np.exp(dt * L / 2.0)
    r = np.exp(1j * np.pi * ((np.arange(1, m + 1) - 0.5) / m))
    LR = dt * L[:, None] + r[None, :]
    Q = dt * np.real(np.mean((np.exp(LR / 2.0) - 1.0) / LR, axis=1))
    f1 = dt * np.real(np.mean((-4 - LR + np.exp(LR) * (4 - 3 * LR + LR**2)) / LR**3, axis=1))
    f2 = dt * np.real(np.mean((2 + LR + np.exp(LR) * (-2 + LR)) / LR**3, axis=1))
    f3 = dt * np.real(np.mean((-4 - 3 * LR - LR**2 + np.exp(LR) * (4 - LR)) / LR**3, axis=1))

    n_steps = int((transient_time + total_time) / dt)
    transient_steps = int(transient_time / dt)
    v = np.fft.fft(u0)
    out = []
    for step in range(n_steps):
        Nv = g * np.fft.fft(np.real(np.fft.ifft(v)) ** 2)
        a = E2 * v + Q * Nv
        Na = g * np.fft.fft(np.real(np.fft.ifft(a)) ** 2)
        b = E2 * v + Q * Na
        Nb = g * np.fft.fft(np.real(np.fft.ifft(b)) ** 2)
        c = E2 * a + Q * (2.0 * Nb - Nv)
        Nc = g * np.fft.fft(np.real(np.fft.ifft(c)) ** 2)
        v = E * v + f1 * Nv + 2.0 * f2 * (Na + Nb) + f3 * Nc
        if step >= transient_steps and (step - transient_steps) % sample_stride == 0:
            out.append(np.real(np.fft.ifft(v)))
    return np.stack(out, axis=1)


def generate_ks(cfg: dict) -> TrajectoryBundle:
    data_cfg = cfg["data"]
    sys_cfg = cfg["system"]
    params = np.linspace(data_cfg["train_param_min"], data_cfg["train_param_max"], data_cfg["num_param_samples"]).reshape(-1, 1)
    trajectories = np.stack(
        [
            ks_etdrk4(
                phi=float(phi),
                nu=sys_cfg["nu"],
                nx=data_cfg["nx"],
                length=sys_cfg["domain_length"],
                dt=data_cfg["solver_dt"],
                total_time=data_cfg["trajectory_time"],
                transient_time=data_cfg["transient_time"],
                sample_stride=data_cfg["sample_stride"],
                seed=cfg["seed"] + i,
            )
            for i, (phi,) in enumerate(params)
        ],
        axis=0,
    )
    train_mask = np.ones(len(params), dtype=bool)
    mean, std = compute_channel_stats(trajectories, train_mask)
    trajectories = normalize_trajectories(trajectories, mean, std)
    return TrajectoryBundle(
        trajectories=trajectories,
        params=params,
        param_names=["phi"],
        train_mask=train_mask,
        system_type="ks",
        meta={"paper_mapping": cfg["evaluation"]["single_param_mapping"]},
        norm_mean=mean,
        norm_std=std,
    )
