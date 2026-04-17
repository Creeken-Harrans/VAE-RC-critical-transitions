from __future__ import annotations

import numpy as np


def ridge_regression(states: np.ndarray, targets: np.ndarray, reg: float) -> np.ndarray:
    rr_t = states @ states.T + reg * np.eye(states.shape[0], dtype=states.dtype)
    return targets @ states.T @ np.linalg.inv(rr_t)
