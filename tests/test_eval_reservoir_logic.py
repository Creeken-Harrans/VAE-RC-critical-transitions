import math

import numpy as np

from src.models.reservoir.transition_search import detect_lorenz_health, scan_single_transition
from src.train.eval_reservoir import (
    check_base_attractor_health,
    choose_single_param_base_index,
    infer_latent_scan_direction,
    summarize_scan_results,
)


def test_mapping_direction_inference_for_physical_decrease() -> None:
    assert infer_latent_scan_direction(2.0, "decrease") == -1.0
    assert infer_latent_scan_direction(-2.0, "decrease") == 1.0


def test_choose_single_param_base_index_prefers_target_value() -> None:
    params = np.array([[25.0], [27.5], [30.0], [32.5], [35.0]], dtype=np.float64)
    idx = choose_single_param_base_index(
        params,
        {"base_param_strategy": "target_value", "base_param_value": 30.0},
    )
    assert idx == 2


def test_scan_single_transition_returns_no_transition_found_for_always_healthy_rollout() -> None:
    result = scan_single_transition(
        rollout_fn=lambda z: np.ones((3, 50), dtype=np.float64),
        initial_series=np.zeros((3, 10), dtype=np.float64),
        base_z=np.array([0.0], dtype=np.float64),
        direction=1.0,
        scan_step=0.1,
        coarse_steps=10,
        binary_steps=4,
        health_fn=lambda pred: True,
    )
    assert result["status"] == "no_transition_found"
    assert math.isnan(float(result["z_critical"]))


def test_scan_single_transition_returns_unhealthy_at_base_when_base_is_not_healthy() -> None:
    result = scan_single_transition(
        rollout_fn=lambda z: np.ones((3, 50), dtype=np.float64),
        initial_series=np.zeros((3, 10), dtype=np.float64),
        base_z=np.array([0.0], dtype=np.float64),
        direction=1.0,
        scan_step=0.1,
        coarse_steps=10,
        binary_steps=4,
        health_fn=lambda pred: False,
    )
    assert result["status"] == "unhealthy_at_base"
    assert math.isnan(float(result["z_critical"]))


def test_base_attractor_health_screening_uses_base_rollout_only() -> None:
    calls: list[np.ndarray] = []

    def rollout_fn(z: np.ndarray) -> np.ndarray:
        calls.append(z.copy())
        return np.ones((3, 50), dtype=np.float64)

    healthy = check_base_attractor_health(
        rollout_fn,
        base_z=np.array([0.3], dtype=np.float64),
        detector=lambda pred: bool(np.all(pred == 1.0)),
    )
    assert healthy is True
    assert len(calls) == 1
    assert abs(float(calls[0][0]) - 0.3) < 1e-12


def test_lorenz_detector_accepts_sustained_tail_oscillation() -> None:
    t = np.linspace(0.0, 80.0, 400, dtype=np.float64)
    series = np.vstack(
        [
            1.5 * np.sin(1.2 * t),
            1.1 * np.sin(1.5 * t + 0.3),
            0.9 * np.cos(1.1 * t - 0.2),
        ]
    )
    cfg = {
        "std_threshold": 0.2,
        "amplitude_threshold": 0.8,
        "tail_fraction": 0.25,
        "tail_std_threshold": 0.05,
        "tail_amplitude_threshold": 0.2,
        "tail_energy_threshold": 0.05,
        "tail_std_ratio_threshold": 0.2,
        "tail_amplitude_ratio_threshold": 0.2,
        "tail_windows": 3,
        "tail_window_std_threshold": 0.05,
        "tail_window_amplitude_threshold": 0.2,
    }
    assert detect_lorenz_health(series, cfg) is True


def test_lorenz_detector_rejects_transient_then_collapse() -> None:
    t = np.linspace(0.0, 20.0, 400, dtype=np.float64)
    active = np.sin(t[:300])
    collapsed = np.full(100, 0.01, dtype=np.float64)
    base = np.concatenate([active, collapsed])
    series = np.vstack([base, 0.8 * base, 0.6 * base])
    cfg = {
        "std_threshold": 0.2,
        "amplitude_threshold": 0.8,
        "tail_fraction": 0.25,
        "tail_std_threshold": 0.05,
        "tail_amplitude_threshold": 0.2,
        "tail_energy_threshold": 0.05,
        "tail_std_ratio_threshold": 0.2,
        "tail_amplitude_ratio_threshold": 0.2,
        "tail_windows": 3,
        "tail_window_std_threshold": 0.05,
        "tail_window_amplitude_threshold": 0.2,
    }
    assert detect_lorenz_health(series, cfg) is False


def test_eval_summary_uses_found_only_values_and_reports_miss_rate() -> None:
    summary = summarize_scan_results(
        critical_latent_found=np.array([0.1, 0.2], dtype=np.float64),
        critical_physical_found=np.array([23.8, 24.1], dtype=np.float64),
        mapping_used={"source": "run_fitted", "coef": -6.0, "intercept": 27.3, "r2": 0.99},
        latent_scan_direction=1.0,
        target_physical_direction="decrease",
        num_realizations=5,
        base_param_value=35.0,
        base_latent_value=-1.2,
        base_index=7,
        base_param_strategy="target_value",
        status_counts={"found": 2, "no_transition_found": 2, "unhealthy_at_base": 1},
        require_healthy_base=True,
    )
    assert summary["num_found"] == 2
    assert summary["num_miss"] == 3
    assert abs(summary["miss_rate"] - 0.6) < 1e-12
    assert summary["require_healthy_base"] is True
    assert summary["base_param_strategy"] == "target_value"
    found_only = summary["found_only_predicted_critical_point"]
    assert found_only is not None
    assert abs(found_only["mean"] - np.mean([23.8, 24.1])) < 1e-12
