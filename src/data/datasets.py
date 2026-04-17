from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
from torch.utils.data import Dataset

from src.data.windowing import build_delay_embedding


class TrajectoryWindowDataset(Dataset):
    def __init__(
        self,
        npz_path: str | Path,
        input_length: int,
        validation_length: int,
        validation_random_length: int,
        partial_observation: bool = False,
        delay: int = 0,
        observed_indices: list[int] | None = None,
        seed: int = 0,
    ) -> None:
        data = np.load(npz_path, allow_pickle=True)
        self.trajectories = data["trajectories"]
        self.params = data["params"]
        self.train_mask = data["train_mask"]
        self.system_type = str(data["system_type"])
        self.input_length = input_length
        self.validation_length = validation_length
        self.validation_random_length = validation_random_length
        self.partial_observation = partial_observation
        self.delay = delay
        self.observed_indices = observed_indices or [0]
        self.rng = np.random.default_rng(seed)
        self.indices = np.where(self.train_mask)[0]

    def __len__(self) -> int:
        return len(self.indices)

    def __getitem__(self, idx: int) -> dict[str, torch.Tensor]:
        real_idx = int(self.indices[idx])
        traj = self.trajectories[real_idx]
        extra = self.delay if self.partial_observation else 0
        usable = self.input_length + self.validation_random_length + self.validation_length + 2 + extra
        max_start = max(traj.shape[-1] - usable, 1)
        start = int(self.rng.integers(0, max_start))
        chunk = traj[:, start : start + usable]

        encoder_x = chunk[:, : self.input_length]
        low = self.delay if self.partial_observation else 0
        target_start = int(self.rng.integers(low, max(low + 1, self.validation_random_length)))
        if self.partial_observation:
            begin = self.input_length - 1 + target_start - self.delay
            end = self.input_length - 1 + target_start + self.validation_length + 1
        else:
            begin = self.input_length - 1 + target_start
            end = self.input_length - 1 + target_start + self.validation_length + 1
        target_chunk = chunk[:, begin:end]

        if self.partial_observation:
            obs = target_chunk[self.observed_indices]
            embedded = build_delay_embedding(obs, self.delay)
            y0 = embedded[0]
            target = obs[:, self.delay + 1 : self.delay + 1 + self.validation_length]
        else:
            y0 = target_chunk[:, 0]
            target = target_chunk[:, 1 : 1 + self.validation_length]

        return {
            "encoder_x": torch.tensor(encoder_x, dtype=torch.float32),
            "y0": torch.tensor(y0, dtype=torch.float32),
            "target": torch.tensor(target, dtype=torch.float32),
            "param": torch.tensor(self.params[real_idx], dtype=torch.float32),
        }
