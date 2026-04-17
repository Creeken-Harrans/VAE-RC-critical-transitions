from __future__ import annotations

import numpy as np


def detect_lorenz_health(series: np.ndarray, cfg: dict) -> bool:
    # paper-hard constraint: healthy Lorenz behavior should preserve chaotic oscillations rather than collapsing to a near-fixed state.
    std_ok = np.std(series) > cfg["std_threshold"]
    amp_ok = (np.max(series) - np.min(series)) > cfg["amplitude_threshold"]
    finite_ok = np.isfinite(series).all()
    return bool(std_ok and amp_ok and finite_ok)


def detect_ks_health(series: np.ndarray, cfg: dict) -> bool:
    energy = np.mean(series**2, axis=0)
    tail = energy[int(len(energy) * 0.7) :]
    return bool(np.mean(tail) > cfg["energy_threshold"] and np.std(tail) > cfg["tail_std_threshold"])


def detect_food_chain_health(series: np.ndarray, cfg: dict) -> bool:
    positive = np.min(series) > cfg["min_population_threshold"]
    oscillatory = np.std(series, axis=1).mean() > cfg["std_threshold"]
    return bool(positive and oscillatory)


def scan_single_transition(
    rollout_fn,
    initial_series: np.ndarray,
    base_z: np.ndarray,
    direction: float,
    scan_step: float,
    coarse_steps: int,
    binary_steps: int,
    health_fn,
) -> float:
    # paper-hard constraint: coarse scan + binary refinement over latent parameter extrapolation.
    last_healthy = None
    first_unhealthy = None
    for i in range(coarse_steps + 1):
        z = base_z.copy()
        z[0] = z[0] + direction * scan_step * i
        pred = rollout_fn(z)
        healthy = health_fn(pred)
        if healthy:
            last_healthy = z[0]
        elif first_unhealthy is None:
            first_unhealthy = z[0]
            break
    if last_healthy is None:
        return float(base_z[0])
    if first_unhealthy is None:
        return float(base_z[0] + direction * scan_step * coarse_steps)
    lo, hi = sorted([last_healthy, first_unhealthy])
    for _ in range(binary_steps):
        mid = 0.5 * (lo + hi)
        z = base_z.copy()
        z[0] = mid
        pred = rollout_fn(z)
        if health_fn(pred):
            lo = mid
        else:
            hi = mid
    return float(0.5 * (lo + hi))
