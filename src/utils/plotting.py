from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def save_channel_stats(path: str | Path, var_mu: np.ndarray, mean_sigma2: np.ndarray, title: str) -> None:
    idx = np.arange(len(var_mu))
    fig, ax1 = plt.subplots(figsize=(7, 4))
    ax1.bar(idx - 0.2, var_mu, width=0.4, color="tab:blue", label="var(mu_z)")
    ax1.bar(idx + 0.2, mean_sigma2, width=0.4, color="tab:red", label="mean(sigma_z^2)")
    ax1.set_xlabel("latent channel")
    ax1.set_title(title)
    ax1.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def save_scatter_with_fit(path: str | Path, x: np.ndarray, y: np.ndarray, y_fit: np.ndarray, xlabel: str, ylabel: str, title: str) -> None:
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.scatter(x, y, s=16, alpha=0.8, color="tab:green")
    order = np.argsort(x)
    ax.plot(np.asarray(x)[order], np.asarray(y_fit)[order], color="goldenrod", linewidth=2)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def save_histogram(path: str | Path, values: np.ndarray, truth: float | None, xlabel: str, title: str) -> None:
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.hist(values, bins=30, color="tab:blue", alpha=0.8)
    if truth is not None:
        ax.axvline(truth, color="tab:red", linestyle="--", linewidth=2)
    ax.set_xlabel(xlabel)
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def save_two_param_planes(path: str | Path, params: np.ndarray, z: np.ndarray, title: str) -> None:
    fig = plt.figure(figsize=(8, 4))
    ax1 = fig.add_subplot(121, projection="3d")
    ax2 = fig.add_subplot(122, projection="3d")
    ax1.scatter(xs=params[:, 0], ys=params[:, 1], zs=z[:, 0], s=10, alpha=0.7, color="purple")
    ax1.set_xlabel("rho")
    ax1.set_ylabel("beta")
    ax1.set_zlabel("z1")
    ax2.scatter(xs=params[:, 0], ys=params[:, 1], zs=z[:, 1], s=10, alpha=0.7, color="violet")
    ax2.set_xlabel("rho")
    ax2.set_ylabel("beta")
    ax2.set_zlabel("z2")
    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def save_classification_scatter(path: str | Path, pts: np.ndarray, pred_is_unhealthy: np.ndarray, train_rect: tuple[float, float, float, float], title: str) -> None:
    fig, ax = plt.subplots(figsize=(6, 5))
    colors = np.where(pred_is_unhealthy, "tab:red", "tab:green")
    ax.scatter(pts[:, 0], pts[:, 1], s=14, c=colors, alpha=0.8)
    rho_min, rho_max, beta_min, beta_max = train_rect
    ax.plot([rho_min, rho_max, rho_max, rho_min, rho_min], [beta_min, beta_min, beta_max, beta_max, beta_min], linestyle="--", color="tab:blue")
    ax.set_xlabel("rho")
    ax.set_ylabel("beta")
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)
