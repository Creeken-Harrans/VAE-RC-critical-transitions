from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


@dataclass
class TrajectoryBundle:
    trajectories: np.ndarray
    params: np.ndarray
    param_names: list[str]
    train_mask: np.ndarray
    system_type: str
    meta: dict[str, Any]
    norm_mean: np.ndarray | None = None
    norm_std: np.ndarray | None = None

    def save(self, path: str | Path) -> None:
        norm_mean = (
            np.asarray(self.norm_mean, dtype=np.float32)
            if self.norm_mean is not None
            else np.array([], dtype=np.float32)
        )
        norm_std = (
            np.asarray(self.norm_std, dtype=np.float32)
            if self.norm_std is not None
            else np.array([], dtype=np.float32)
        )
        np.savez_compressed(
            path,
            trajectories=self.trajectories.astype(np.float32),
            params=self.params.astype(np.float32),
            train_mask=self.train_mask.astype(bool),
            param_names=np.array(self.param_names, dtype=object),
            system_type=self.system_type,
            meta=np.array([self.meta], dtype=object),
            norm_mean=norm_mean,
            norm_std=norm_std,
        )


def compute_channel_stats(trajectories: np.ndarray, mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    train_traj = trajectories[mask]
    mean = train_traj.mean(axis=(0, 2), keepdims=True)
    std = train_traj.std(axis=(0, 2), keepdims=True) + 1e-6
    return mean, std


def normalize_trajectories(trajectories: np.ndarray, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    return (trajectories - mean) / std
