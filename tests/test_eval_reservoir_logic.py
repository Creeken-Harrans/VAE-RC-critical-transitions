import math

import numpy as np

from src.models.reservoir.transition_search import scan_single_transition
from src.train.eval_reservoir import infer_latent_scan_direction, summarize_scan_results


def test_mapping_direction_inference_for_physical_decrease() -> None:
    assert infer_latent_scan_direction(2.0, "decrease") == -1.0
    assert infer_latent_scan_direction(-2.0, "decrease") == 1.0


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
        status_counts={"found": 2, "no_transition_found": 2, "unhealthy_at_base": 1},
    )
    assert summary["num_found"] == 2
    assert summary["num_miss"] == 3
    assert abs(summary["miss_rate"] - 0.6) < 1e-12
    found_only = summary["found_only_predicted_critical_point"]
    assert found_only is not None
    assert abs(found_only["mean"] - np.mean([23.8, 24.1])) < 1e-12
