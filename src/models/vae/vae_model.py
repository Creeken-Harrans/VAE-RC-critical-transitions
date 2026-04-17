from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn

from .blocks import aggregate_latent
from .decoder_hyper import HyperDecoder
from .encoder_ode import DilatedCNNEncoder


class LatentVAE(nn.Module):
    def __init__(
        self,
        data_channels: int,
        param_size: int = 5,
        hidden_channels: int = 32,
        prop_layers: int = 1,
        eps: float = 1e-8,
        param_dropout_prob: float = 0.0,
        correlation_length: int = 31,
        partial_observation: bool = False,
        delay: int = 0,
        observed_channels: int | None = None,
        decoder_dt: float = 1e-6,
        prop_noise: float = 0.0,
    ) -> None:
        super().__init__()
        self.data_channels = data_channels
        self.param_size = param_size
        self.eps = eps
        self.param_dropout_prob = param_dropout_prob
        self.correlation_length = correlation_length
        self.partial_observation = partial_observation
        self.delay = delay
        self.observed_channels = observed_channels or data_channels
        self.encoder = DilatedCNNEncoder(data_channels=data_channels, param_size=param_size, hidden_channels=hidden_channels)
        state_size = self.observed_channels * (delay + 1) if partial_observation else self.observed_channels
        self.decoder = HyperDecoder(
            param_size=param_size,
            state_size=state_size,
            output_size=self.observed_channels,
            hidden_channels=hidden_channels,
            prop_layers=prop_layers,
            dt=decoder_dt,
            prop_noise=prop_noise,
            partial_observation=partial_observation,
            delay=delay,
        )

    def encode(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        raw_params, raw_logvar = self.encoder(x)
        params = raw_params.view(raw_params.shape[0], raw_params.shape[1], -1)
        logvar = raw_logvar.view(raw_logvar.shape[0], raw_logvar.shape[1], -1)
        agg_params, agg_logvar, weights = aggregate_latent(params, logvar, self.training, self.param_dropout_prob, self.correlation_length)
        return agg_params, agg_logvar, weights

    def reparameterize(self, params: torch.Tensor, logvar: torch.Tensor) -> torch.Tensor:
        if self.training:
            std = torch.exp(0.5 * logvar)
            return params + std * torch.randn_like(std)
        return params

    def forward(self, x: torch.Tensor, y0: torch.Tensor, predict_length: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        params, logvar, _ = self.encode(x)
        z = self.reparameterize(params, logvar)
        pred = self.decoder(y0, z, predict_length)
        return pred, params, logvar


def select_active_channels(mu: np.ndarray, logvar: np.ndarray, top_k: int) -> dict[str, np.ndarray]:
    # paper-hard constraint: high var(mu_z) + low mean(sigma_z^2) identifies informative latent channels.
    var_mu = np.var(mu, axis=0)
    mean_sigma2 = np.mean(np.exp(logvar), axis=0)
    score = var_mu / (mean_sigma2 + 1e-8)
    active = np.argsort(-score)[:top_k]
    return {
        "var_mu": var_mu,
        "mean_sigma2": mean_sigma2,
        "score": score,
        "active": active,
    }
