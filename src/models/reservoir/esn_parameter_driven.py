from __future__ import annotations

import pickle
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .ridge import ridge_regression


@dataclass
class ReservoirState:
    win: np.ndarray
    wb: np.ndarray
    a: np.ndarray
    wout: np.ndarray | None = None


class ParameterDrivenReservoir:
    # repo-informed completion: explicit parameter-channel ESN based on the author's 2021 PRR implementation.
    def __init__(
        self,
        input_dim: int,
        param_dim: int,
        nr: int,
        degree: int,
        spectral_radius: float,
        kin: float,
        kb: float,
        b0: float,
        alpha: float,
        ridge_reg: float = 1e-6,
        square_even_states: bool = True,
        seed: int = 0,
    ) -> None:
        self.input_dim = input_dim
        self.param_dim = param_dim
        self.nr = nr
        self.degree = degree
        self.spectral_radius = spectral_radius
        self.kin = kin
        self.kb = kb
        self.b0 = b0
        self.alpha = alpha
        self.ridge_reg = ridge_reg
        self.square_even_states = square_even_states
        self.rng = np.random.default_rng(seed)
        self.state = self._init_state()

    def _init_state(self) -> ReservoirState:
        density = min(self.degree / max(self.nr, 1), 1.0)
        mask = self.rng.random((self.nr, self.nr)) < density
        a = self.rng.standard_normal((self.nr, self.nr)) * mask
        eig = np.max(np.abs(np.linalg.eigvals(a))) + 1e-9
        a = np.asarray(a / eig * self.spectral_radius, dtype=np.float64)
        win = self.kin * self.rng.uniform(-1.0, 1.0, size=(self.nr, self.input_dim))
        wb = self.rng.uniform(-1.0, 1.0, size=(self.nr, self.param_dim))
        return ReservoirState(win=win, wb=wb, a=a, wout=None)

    def _step(self, r: np.ndarray, u: np.ndarray, b: np.ndarray) -> np.ndarray:
        drive = self.state.a @ r + self.state.win @ u + self.kb * (self.state.wb @ (b + self.b0))
        return (1.0 - self.alpha) * r + self.alpha * np.tanh(drive)

    def _readout_state(self, r: np.ndarray) -> np.ndarray:
        r_out = r.copy()
        if self.square_even_states:
            r_out[1::2] = r_out[1::2] ** 2
        return r_out

    def fit(self, series_list: list[np.ndarray], param_list: list[np.ndarray], washout: int, train_length: int) -> dict[str, float]:
        states = []
        targets = []
        rmses = []
        for series, b in zip(series_list, param_list):
            r = np.zeros(self.nr, dtype=np.float64)
            local_states = []
            local_targets = []
            for t in range(train_length):
                u = series[:, t]
                y = series[:, t + 1]
                r = self._step(r, u, b)
                if t >= washout:
                    local_states.append(self._readout_state(r))
                    local_targets.append(y)
            states.append(np.stack(local_states, axis=1))
            targets.append(np.stack(local_targets, axis=1))
        state_mat = np.concatenate(states, axis=1)
        target_mat = np.concatenate(targets, axis=1)
        self.state.wout = ridge_regression(state_mat, target_mat, self.ridge_reg)

        for series, b in zip(series_list, param_list):
            pred = self.rollout(series[:, : washout + 1], b, steps=min(100, series.shape[1] - washout - 1), warmup=washout)
            truth = series[:, washout + 1 : washout + 1 + pred.shape[1]]
            rmses.append(float(np.sqrt(np.mean((pred - truth) ** 2))))
        return {"validation_rmse": float(np.mean(rmses))}

    def rollout(self, init_series: np.ndarray, b: np.ndarray, steps: int, warmup: int) -> np.ndarray:
        if self.state.wout is None:
            raise RuntimeError("Reservoir readout is not trained.")
        r = np.zeros(self.nr, dtype=np.float64)
        last = init_series[:, -1].copy()
        for t in range(max(warmup - 1, 0)):
            r = self._step(r, init_series[:, t], b)
            last = init_series[:, t]
        preds = []
        u = last
        for _ in range(steps):
            r = self._step(r, u, b)
            y = self.state.wout @ self._readout_state(r)
            preds.append(y)
            u = y
        return np.stack(preds, axis=1)

    def save(self, path: str | Path) -> None:
        with open(path, "wb") as f:
            pickle.dump(self.__dict__, f)

    @classmethod
    def load(cls, path: str | Path) -> "ParameterDrivenReservoir":
        with open(path, "rb") as f:
            payload = pickle.load(f)
        obj = cls.__new__(cls)
        obj.__dict__.update(payload)
        return obj
