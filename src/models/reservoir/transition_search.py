from __future__ import annotations

import numpy as np


def detect_lorenz_health(series: np.ndarray, cfg: dict) -> bool:
    # paper-hard constraint:
    # healthy Lorenz behavior should preserve chaotic oscillations rather than collapsing to a near-fixed state.
    std_ok = np.std(series) > cfg["std_threshold"]
    amp_ok = (np.max(series) - np.min(series)) > cfg["amplitude_threshold"]
    finite_ok = np.isfinite(series).all()

    # inferred default due to missing detail in paper:
    # add a configurable tail-collapse check so late-time fixed-point collapse is not mislabeled healthy.
    tail_fraction = float(cfg.get("tail_fraction", 0.25))
    tail_start = int(max(0, (1.0 - tail_fraction) * series.shape[-1]))
    tail = series[:, tail_start:] if series.ndim == 2 else series[tail_start:]
    tail_std_ok = np.std(tail) > float(cfg.get("tail_std_threshold", 0.05))
    tail_amp_ok = (np.max(tail) - np.min(tail)) > float(cfg.get("tail_amplitude_threshold", 0.2))
    return bool(std_ok and amp_ok and finite_ok and tail_std_ok and tail_amp_ok)


def detect_ks_health(series: np.ndarray, cfg: dict) -> bool:
    energy = np.mean(series**2, axis=0)
    tail = energy[int(len(energy) * 0.7) :]
    return bool(
        np.mean(tail) > cfg["energy_threshold"]
        and np.std(tail) > cfg["tail_std_threshold"]
    )


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
) -> dict[str, float | str]:
    # paper-hard constraint:
    # coarse scan + binary refinement over latent parameter extrapolation.
    del initial_series
    last_healthy = None
    first_unhealthy = None

    for i in range(coarse_steps + 1):
        z = base_z.copy()
        z[0] = z[0] + direction * scan_step * i
        pred = rollout_fn(z)
        healthy = health_fn(pred)

        if i == 0 and not healthy:
            return {"status": "unhealthy_at_base", "z_critical": float("nan")}

        if healthy:
            last_healthy = z[0]
        elif first_unhealthy is None:
            first_unhealthy = z[0]
            break

    if first_unhealthy is None:
        return {"status": "no_transition_found", "z_critical": float("nan")}

    if last_healthy is None:
        return {"status": "unhealthy_at_base", "z_critical": float("nan")}

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

    return {"status": "found", "z_critical": float(0.5 * (lo + hi))}
