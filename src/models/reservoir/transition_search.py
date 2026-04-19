from __future__ import annotations

import numpy as np


def _as_channel_time(series: np.ndarray) -> np.ndarray:
    arr = np.asarray(series, dtype=np.float64)
    if arr.ndim == 1:
        return arr[None, :]
    return arr


def _split_tail_windows(arr: np.ndarray, num_windows: int) -> list[np.ndarray]:
    return [window for window in np.array_split(arr, max(num_windows, 1), axis=-1) if window.shape[-1] > 0]


def detect_lorenz_health(series: np.ndarray, cfg: dict) -> bool:
    # paper-hard constraint:
    # healthy Lorenz behavior should preserve chaotic oscillations rather than collapsing to a near-fixed state.
    arr = _as_channel_time(series)
    finite_ok = np.isfinite(arr).all()
    if not finite_ok or arr.shape[-1] < 8:
        return False

    full_std = float(np.std(arr))
    full_amp = float(np.max(arr) - np.min(arr))
    full_energy = float(np.mean(arr**2))
    std_ok = full_std > float(cfg["std_threshold"])
    amp_ok = full_amp > float(cfg["amplitude_threshold"])

    # inferred default due to missing detail in paper:
    # use tail statistics to approximate whether a long-lived chaotic attractor still exists,
    # instead of relying only on whole-trajectory amplitude thresholds.
    tail_fraction = float(cfg.get("tail_fraction", 0.25))
    tail_start = int(max(0, (1.0 - tail_fraction) * arr.shape[-1]))
    tail = arr[:, tail_start:]
    tail_std = float(np.std(tail))
    tail_amp = float(np.max(tail) - np.min(tail))
    tail_energy = float(np.mean(tail**2))
    tail_std_ok = tail_std > float(cfg.get("tail_std_threshold", 0.05))
    tail_amp_ok = tail_amp > float(cfg.get("tail_amplitude_threshold", 0.2))
    tail_energy_ok = tail_energy > float(cfg.get("tail_energy_threshold", 0.05))

    # repo-informed completion:
    # fixed-point collapse should strongly reduce late-time variance/amplitude relative to the full rollout.
    tail_std_ratio_ok = (tail_std / max(full_std, 1e-12)) > float(cfg.get("tail_std_ratio_threshold", 0.2))
    tail_amp_ratio_ok = (tail_amp / max(full_amp, 1e-12)) > float(cfg.get("tail_amplitude_ratio_threshold", 0.2))

    # inferred default due to missing detail in paper:
    # require sustained oscillation across multiple late-time subwindows,
    # so "early transient then late collapse" is rejected without introducing a highly bespoke peak detector.
    tail_windows = _split_tail_windows(tail, int(cfg.get("tail_windows", 3)))
    min_tail_window_std = float(cfg.get("tail_window_std_threshold", cfg.get("tail_std_threshold", 0.05)))
    min_tail_window_amp = float(
        cfg.get("tail_window_amplitude_threshold", cfg.get("tail_amplitude_threshold", 0.2))
    )
    sustained_tail_ok = all(
        (float(np.std(window)) > min_tail_window_std)
        and (float(np.max(window) - np.min(window)) > min_tail_window_amp)
        for window in tail_windows
    )

    return bool(
        std_ok
        and amp_ok
        and tail_std_ok
        and tail_amp_ok
        and tail_energy_ok
        and tail_std_ratio_ok
        and tail_amp_ratio_ok
        and sustained_tail_ok
    )


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
    base_is_healthy: bool | None = None,
    coarse_unhealthy_streak: int = 1,
) -> dict[str, float | str]:
    # paper-hard constraint:
    # coarse scan + binary refinement over latent parameter extrapolation.
    del initial_series
    last_healthy = None
    first_unhealthy = None
    candidate_last_healthy = None
    candidate_first_unhealthy = None
    unhealthy_run = 0
    required_unhealthy_run = max(1, int(coarse_unhealthy_streak))

    for i in range(coarse_steps + 1):
        z = base_z.copy()
        z[0] = z[0] + direction * scan_step * i
        if i == 0 and base_is_healthy is not None:
            healthy = bool(base_is_healthy)
        else:
            pred = rollout_fn(z)
            healthy = health_fn(pred)

        if i == 0 and not healthy:
            return {"status": "unhealthy_at_base", "z_critical": float("nan")}

        if healthy:
            last_healthy = z[0]
            candidate_last_healthy = None
            candidate_first_unhealthy = None
            unhealthy_run = 0
        else:
            if unhealthy_run == 0:
                candidate_last_healthy = last_healthy
                candidate_first_unhealthy = z[0]
            unhealthy_run += 1
            if unhealthy_run >= required_unhealthy_run and first_unhealthy is None:
                last_healthy = candidate_last_healthy
                first_unhealthy = candidate_first_unhealthy
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
