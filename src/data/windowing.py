from __future__ import annotations

import numpy as np


def build_delay_embedding(series: np.ndarray, delay: int) -> np.ndarray:
    # series: [T] or [1, T]
    arr = np.asarray(series)
    if arr.ndim == 1:
        arr = arr[None, :]
    obs_channels, total_t = arr.shape
    windows = []
    for t in range(delay, total_t):
        windows.append(arr[:, t - delay : t + 1].reshape(-1))
    return np.stack(windows, axis=0)


def sample_window(trajectory: np.ndarray, total_length: int, rng: np.random.Generator) -> tuple[np.ndarray, int]:
    t_len = trajectory.shape[-1]
    if t_len <= total_length:
        return trajectory, 0
    start = int(rng.integers(0, t_len - total_length))
    return trajectory[:, start : start + total_length], start
