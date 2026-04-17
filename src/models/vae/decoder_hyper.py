from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

from .blocks import DecoderLayer


class HyperDecoder(nn.Module):
    def __init__(
        self,
        param_size: int,
        state_size: int,
        output_size: int,
        hidden_channels: int,
        prop_layers: int,
        dt: float = 1e-6,
        prop_noise: float = 0.0,
        partial_observation: bool = False,
        delay: int = 0,
    ) -> None:
        super().__init__()
        self.state_size = state_size
        self.output_size = output_size
        self.hidden_channels = hidden_channels
        self.prop_layers = prop_layers
        self.dt = dt
        self.prop_noise = prop_noise
        self.partial_observation = partial_observation
        self.delay = delay

        self.conv_in = DecoderLayer(state_size, hidden_channels)
        self.conv_out = DecoderLayer(hidden_channels, output_size)
        self.conv_prop = nn.ModuleList([DecoderLayer(hidden_channels, hidden_channels) for _ in range(prop_layers)])
        self.cutoff = nn.Parameter(torch.tensor([1.0], dtype=torch.float32))

        # repo-informed completion: decoder weights are generated from z through MLP hypernetworks as in the author VAE code.
        self.param_to_in_weight = self._mlp(param_size, state_size * hidden_channels)
        self.param_to_in_bias = self._mlp(param_size, hidden_channels)
        self.param_to_out_weight = self._mlp(param_size, hidden_channels * output_size)
        self.param_to_out_bias = self._mlp(param_size, output_size)
        self.param_to_prop_weight = self._mlp(param_size, max(prop_layers, 1) * hidden_channels * hidden_channels)
        self.param_to_prop_bias = self._mlp(param_size, max(prop_layers, 1) * hidden_channels)

    @staticmethod
    def _mlp(in_dim: int, out_dim: int) -> nn.Sequential:
        return nn.Sequential(nn.Linear(in_dim, 4 * max(in_dim, out_dim)), nn.ReLU(inplace=True), nn.Linear(4 * max(in_dim, out_dim), out_dim))

    def _f(self, y: torch.Tensor, in_weight: torch.Tensor, in_bias: torch.Tensor, out_weight: torch.Tensor, out_bias: torch.Tensor, prop_weight: torch.Tensor, prop_bias: torch.Tensor) -> torch.Tensor:
        h = F.relu(self.conv_in(y, in_weight, in_bias), inplace=True)
        for layer_idx in range(self.prop_layers):
            h = F.relu(self.conv_prop[layer_idx](h, prop_weight[:, layer_idx], prop_bias[:, layer_idx]), inplace=True)
        return self.conv_out(h, out_weight, out_bias)

    def generate_weights(self, z: torch.Tensor) -> dict[str, torch.Tensor]:
        return {
            "in_weight": self.param_to_in_weight(z),
            "in_bias": self.param_to_in_bias(z),
            "out_weight": self.param_to_out_weight(z),
            "out_bias": self.param_to_out_bias(z),
            "prop_weight": self.param_to_prop_weight(z).view(-1, max(self.prop_layers, 1), self.hidden_channels * self.hidden_channels),
            "prop_bias": self.param_to_prop_bias(z).view(-1, max(self.prop_layers, 1), self.hidden_channels),
        }

    def _advance_state(self, state: torch.Tensor, predicted_output: torch.Tensor) -> torch.Tensor:
        if not self.partial_observation:
            noise = self.prop_noise * torch.randn_like(state) if self.training and self.prop_noise > 0 else 0.0
            delta = self.cutoff * torch.tanh((self.dt * predicted_output) / self.cutoff)
            return state + delta + noise
        obs = predicted_output
        window = state.view(state.shape[0], self.output_size, self.delay + 1)
        window = torch.cat([window[:, :, 1:], obs.unsqueeze(-1)], dim=-1)
        return window.reshape(state.shape[0], -1)

    def forward(self, y0: torch.Tensor, z: torch.Tensor, predict_length: int) -> torch.Tensor:
        weights = self.generate_weights(z)
        state = y0
        outputs = []
        for _ in range(predict_length):
            pred = self._f(
                state,
                weights["in_weight"],
                weights["in_bias"],
                weights["out_weight"],
                weights["out_bias"],
                weights["prop_weight"],
                weights["prop_bias"],
            )
            if not self.partial_observation:
                pred = state + self.cutoff * torch.tanh((self.dt * pred) / self.cutoff)
            outputs.append(pred)
            state = self._advance_state(state, pred)
        return torch.stack(outputs, dim=-1)
