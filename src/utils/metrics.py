from __future__ import annotations

import numpy as np


def mse(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.mean((a - b) ** 2))


def rmse(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.sqrt(mse(a, b)))


def relative_error(pred: float, truth: float) -> float:
    return float(abs(pred - truth) / abs(truth))


def summarize_hist(values: np.ndarray) -> dict[str, float]:
    return {
        "mean": float(np.mean(values)),
        "std": float(np.std(values)),
        "min": float(np.min(values)),
        "max": float(np.max(values)),
        "median": float(np.median(values)),
    }


def classification_rates(pred_is_unhealthy: np.ndarray, truth_is_unhealthy: np.ndarray) -> dict[str, float]:
    pred_is_unhealthy = np.asarray(pred_is_unhealthy).astype(bool)
    truth_is_unhealthy = np.asarray(truth_is_unhealthy).astype(bool)

    false_positive = np.logical_and(pred_is_unhealthy, ~truth_is_unhealthy).sum()
    false_negative = np.logical_and(~pred_is_unhealthy, truth_is_unhealthy).sum()
    healthy_total = max((~truth_is_unhealthy).sum(), 1)
    unhealthy_total = max(truth_is_unhealthy.sum(), 1)
    return {
        "FPR": float(false_positive / healthy_total),
        "FNR": float(false_negative / unhealthy_total),
    }
