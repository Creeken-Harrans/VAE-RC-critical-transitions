from pathlib import Path

import torch

from src.train.train_vae import build_vae
from src.utils.io import resolve_config


ROOT = Path(__file__).resolve().parents[1]


def test_lorenz_vae_shapes() -> None:
    cfg = resolve_config(ROOT / "configs" / "lorenz_single.yaml", quick=True)
    model = build_vae(cfg, data_channels=3)
    x = torch.randn(4, 3, cfg["vae"]["input_length"])
    y0 = torch.randn(4, 3)
    pred, params, logvar = model(x, y0, predict_length=cfg["vae"]["validation_length"])
    assert pred.shape == (4, 3, cfg["vae"]["validation_length"])
    assert params.shape == (4, cfg["vae"]["param_size"])
    assert logvar.shape == (4, cfg["vae"]["param_size"])


def test_partial_obs_shapes() -> None:
    cfg = resolve_config(ROOT / "configs" / "lorenz_partial_obs.yaml", quick=True)
    model = build_vae(cfg, data_channels=1)
    x = torch.randn(2, 1, cfg["vae"]["input_length"])
    y0 = torch.randn(2, cfg["system"]["delay"] + 1)
    pred, params, logvar = model(x, y0, predict_length=cfg["vae"]["validation_length"])
    assert pred.shape == (2, 1, cfg["vae"]["validation_length"])
    assert params.shape[-1] == cfg["vae"]["param_size"]
