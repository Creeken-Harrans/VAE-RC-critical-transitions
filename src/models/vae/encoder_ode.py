from __future__ import annotations

import torch
import torch.nn as nn

from .blocks import PeriodicPad1d


class DilatedCNNEncoder(nn.Module):
    # paper-hard constraint + repo-informed completion: 4-layer 1D dilated CNN with the author public-code channel progression.
    def __init__(self, data_channels: int, param_size: int, hidden_channels: int = 32, periodic: bool = False) -> None:
        super().__init__()
        pad_cls = PeriodicPad1d if periodic else lambda pad: nn.ConstantPad1d((pad, pad), 0.0)
        pads = [1, 2, 4, 8]
        dilations = [4, 8, 16, 32]
        kernels = [8, 8, 4, 4]

        layers: list[nn.Module] = []
        channels = [data_channels, 4, 16, 64, 64]
        for i in range(4):
            layers.extend(
                [
                    pad_cls(pads[i]),
                    nn.Conv1d(channels[i], channels[i + 1], kernel_size=kernels[i], dilation=dilations[i]),
                    nn.ReLU(inplace=True),
                ]
            )
        self.encoder = nn.Sequential(*layers)
        self.encoder_to_param = nn.Conv1d(64, param_size, kernel_size=1)
        self.encoder_to_logvar = nn.Conv1d(64, param_size, kernel_size=1)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        enc = self.encoder(x)
        params = self.encoder_to_param(enc)
        logvar = self.encoder_to_logvar(enc)
        return params, logvar
