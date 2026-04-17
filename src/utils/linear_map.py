from __future__ import annotations

import numpy as np
import torch


def _r2_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true, axis=0, keepdims=True)) ** 2)
    return float(1.0 - ss_res / (ss_tot + 1e-12))


def fit_single_affine(z: np.ndarray, p: np.ndarray) -> dict[str, np.ndarray | float]:
    z_np = np.asarray(z).reshape(-1, 1)
    p_np = np.asarray(p).reshape(-1, 1)
    X = torch.tensor(np.concatenate([z_np, np.ones((z_np.shape[0], 1))], axis=1), dtype=torch.float32)
    y = torch.tensor(p_np, dtype=torch.float32)
    coef = torch.linalg.lstsq(X, y).solution
    pred = X @ coef
    coef_np = coef.detach().cpu().numpy()
    pred_np = pred.detach().cpu().numpy()
    return {
        "coef": coef_np[:1, 0].copy(),
        "intercept": float(coef_np[1, 0]),
        "score": _r2_score(p_np, pred_np),
        "prediction": pred_np[:, 0],
    }


def fit_multi_affine(z: np.ndarray, p: np.ndarray) -> dict[str, np.ndarray | float]:
    z_np = np.asarray(z)
    p_np = np.asarray(p)
    X = torch.tensor(np.concatenate([z_np, np.ones((z_np.shape[0], 1))], axis=1), dtype=torch.float32)
    y = torch.tensor(p_np, dtype=torch.float32)
    coef = torch.linalg.lstsq(X, y).solution
    pred = X @ coef
    coef_np = coef.detach().cpu().numpy()
    pred_np = pred.detach().cpu().numpy()
    return {
        "coef": coef_np[:-1].T.copy(),
        "intercept": coef_np[-1].copy(),
        "score": _r2_score(p_np, pred_np),
        "prediction": pred_np,
    }


def apply_single_affine(z: np.ndarray, coef: float, intercept: float) -> np.ndarray:
    return coef * np.asarray(z) + intercept


def apply_matrix_affine(z: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    z = np.asarray(z)
    ones = np.ones((z.shape[0], 1), dtype=z.dtype)
    aug = np.concatenate([z, ones], axis=1)
    return aug @ np.asarray(matrix).T
