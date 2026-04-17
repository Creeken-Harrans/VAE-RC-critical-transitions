from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


class PeriodicPad1d(nn.Module):
    def __init__(self, pad: int, dim: int = -1) -> None:
        super().__init__()
        self.pad = pad
        self.dim = dim

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if self.pad <= 0:
            return x
        front = x.narrow(self.dim, x.shape[self.dim] - self.pad, self.pad)
        back = x.narrow(self.dim, 0, self.pad)
        return torch.cat([front, x, back], dim=self.dim)


class DecoderLayer(nn.Module):
    # repo-informed completion: dynamic sample-wise linear layer, directly aligned with the author VAE code style.
    def __init__(self, in_channels: int, out_channels: int) -> None:
        super().__init__()
        self.in_channels = in_channels
        self.out_channels = out_channels

    def forward(self, x: torch.Tensor, weight: torch.Tensor, bias: torch.Tensor | None) -> torch.Tensor:
        y = torch.matmul(x.view(-1, 1, self.in_channels), weight.view(-1, self.in_channels, self.out_channels))
        if bias is not None:
            y = y + bias.view(-1, 1, self.out_channels)
        return y.squeeze(1)


def aggregate_latent(
    params: torch.Tensor,
    logvar: torch.Tensor,
    training: bool,
    param_dropout_prob: float,
    correlation_length: int,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    if training and param_dropout_prob > 0:
        mask = torch.bernoulli(torch.full_like(logvar, param_dropout_prob))
        mask[mask > 0] = float("inf")
        logvar = logvar + mask
    weights = F.softmax(-logvar, dim=-1)
    agg_params = (params * weights).sum(dim=-1)
    correction = max(1.0, (1.0 - param_dropout_prob) * min(correlation_length, params.shape[-1]))
    agg_logvar = -torch.logsumexp(-logvar, dim=-1) + torch.log(torch.tensor(correction, dtype=logvar.dtype, device=logvar.device))
    return agg_params, agg_logvar, weights
