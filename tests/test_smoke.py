from pathlib import Path

from src.data.food_chain import generate_food_chain
from src.data.ks import generate_ks
from src.data.lorenz import generate_lorenz_single
from src.utils.io import resolve_config


ROOT = Path(__file__).resolve().parents[1]


def test_quick_lorenz_generation() -> None:
    cfg = resolve_config(ROOT / "configs" / "lorenz_single.yaml", quick=True)
    bundle = generate_lorenz_single(cfg)
    assert bundle.trajectories.ndim == 3
    assert bundle.params.shape[1] == 1


def test_quick_ks_generation() -> None:
    cfg = resolve_config(ROOT / "configs" / "ks.yaml", quick=True)
    bundle = generate_ks(cfg)
    assert bundle.trajectories.shape[1] == cfg["data"]["nx"]


def test_quick_food_chain_generation() -> None:
    cfg = resolve_config(ROOT / "configs" / "food_chain.yaml", quick=True)
    bundle = generate_food_chain(cfg)
    assert bundle.trajectories.shape[1] == 3
