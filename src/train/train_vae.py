from __future__ import annotations

import json

import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader
from tqdm import trange

from src.data.datasets import TrajectoryWindowDataset
from src.data.food_chain import generate_food_chain
from src.data.ks import generate_ks
from src.data.lorenz import generate_lorenz_partial, generate_lorenz_single, generate_lorenz_two_param
from src.models.vae import LatentVAE
from src.utils.io import get_output_dirs, resolve_config, save_json
from src.utils.seed import seed_everything


def parse_args():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--full", action="store_true")
    return parser.parse_args()


def load_resolved_config(args):
    cfg = resolve_config(args.config, quick=args.quick, full=args.full)
    seed_everything(cfg["seed"])
    return cfg


def generate_bundle(cfg: dict):
    system_type = cfg["system"]["type"]
    if system_type == "lorenz_single":
        return generate_lorenz_single(cfg)
    if system_type == "lorenz_two_param":
        return generate_lorenz_two_param(cfg)
    if system_type == "lorenz_partial_obs":
        return generate_lorenz_partial(cfg)
    if system_type == "ks":
        return generate_ks(cfg)
    if system_type == "food_chain":
        return generate_food_chain(cfg)
    raise ValueError(f"Unsupported system type: {system_type}")


def build_vae(cfg: dict, data_channels: int) -> LatentVAE:
    partial = cfg["system"]["type"] == "lorenz_partial_obs"
    observed_channels = 1 if partial else data_channels
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = LatentVAE(
        data_channels=data_channels,
        param_size=cfg["vae"]["param_size"],
        hidden_channels=cfg["vae"]["hidden_channels"],
        prop_layers=cfg["vae"]["prop_layers"],
        eps=cfg["vae"]["eps"],
        param_dropout_prob=cfg["vae"]["param_dropout_prob"],
        correlation_length=cfg["vae"]["correlation_length"],
        partial_observation=partial,
        delay=cfg["system"].get("delay", 0),
        observed_channels=observed_channels,
        decoder_dt=cfg["vae"]["decoder_dt"],
        prop_noise=cfg["vae"]["prop_noise"],
    ).to(device)
    return model


def npz_data_path(dirs: dict) -> str:
    return str(dirs["data"] / "trajectories.npz")


def temporal_weights(length: int, rate: float, device: torch.device) -> torch.Tensor | None:
    if rate <= 0:
        return None
    w = torch.exp(-rate * torch.arange(length, device=device, dtype=torch.float32))
    return (length * w / w.sum()).view(1, 1, -1)


def main() -> None:
    args = parse_args()
    cfg = load_resolved_config(args)
    dirs = get_output_dirs(cfg)
    data_path = npz_data_path(dirs)
    if not data_path.exists():
        bundle = generate_bundle(cfg)
        bundle.save(data_path)

    dataset = TrajectoryWindowDataset(
        data_path,
        input_length=cfg["vae"]["input_length"],
        validation_length=cfg["vae"]["validation_length"],
        validation_random_length=cfg["vae"]["validation_random_length"],
        partial_observation=cfg["system"]["type"] == "lorenz_partial_obs",
        delay=cfg["system"].get("delay", 0),
        observed_indices=cfg["system"].get("observed_indices", [0]),
        seed=cfg["seed"],
    )
    loader = DataLoader(dataset, batch_size=cfg["vae"]["batch_size"], shuffle=True)
    sample = dataset[0]
    model = build_vae(cfg, sample["encoder_x"].shape[0])
    device = next(model.parameters()).device
    optimizer = torch.optim.Adam(model.parameters(), lr=cfg["vae"]["lr"], eps=cfg["vae"]["eps"])
    best = float("inf")
    history = []
    weights = temporal_weights(cfg["vae"]["validation_length"], cfg["vae"]["discount_rate"], device)
    best_path = dirs["vae"] / "best.tar"

    for epoch in trange(cfg["vae"]["max_epochs"], desc="train_vae"):
        model.train()
        losses = []
        for batch in loader:
            x = batch["encoder_x"].to(device)
            y0 = batch["y0"].to(device)
            target = batch["target"].to(device)
            pred, params, logvar = model(x, y0, predict_length=cfg["vae"]["validation_length"])
            recon = F.mse_loss(pred * weights, target * weights) if weights is not None else F.mse_loss(pred, target)
            kl = 0.5 * torch.mean(torch.sum(params.pow(2) + logvar.exp() - logvar - 1.0, dim=-1))
            loss = recon + cfg["vae"]["beta_vae"] * kl
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            losses.append((float(loss.item()), float(recon.item()), float(kl.item())))
        mean_loss = np.mean(losses, axis=0)
        history.append({"epoch": epoch + 1, "loss": mean_loss[0], "recon": mean_loss[1], "kl": mean_loss[2]})
        if mean_loss[1] < best:
            best = float(mean_loss[1])
            torch.save(model.state_dict(), best_path)

    save_json(dirs["vae"] / "train_history.json", {"history": history})
    with open(dirs["vae"] / "train_done.json", "w", encoding="utf-8") as f:
        json.dump({"best_recon": best, "checkpoint": str(best_path)}, f, indent=2)


if __name__ == "__main__":
    main()
