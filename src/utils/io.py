import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


def load_yaml(path: str | Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def deep_update(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(base)
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_update(out[key], value)
        else:
            out[key] = deepcopy(value)
    return out


def resolve_config(path: str | Path, quick: bool = False, full: bool = False) -> dict[str, Any]:
    cfg = load_yaml(path)
    mode = "quick" if quick else "full" if full else cfg.get("run", {}).get("mode", "quick")
    cfg["run"]["mode"] = mode
    overrides = cfg.get("quick_demo", {}) if mode == "quick" else cfg.get("full_reproduction", {})
    return deep_update(cfg, overrides)


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def save_json(path: str | Path, payload: dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)


def save_yaml(path: str | Path, payload: dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(payload, f, sort_keys=False)


def get_output_dirs(cfg: dict[str, Any]) -> dict[str, Path]:
    root = ensure_dir(Path(cfg["paths"]["output_root"]) / cfg["experiment_name"] / cfg["run"]["mode"])
    return {
        "root": root,
        "data": ensure_dir(root / "data"),
        "vae": ensure_dir(root / "vae"),
        "reservoir": ensure_dir(root / "reservoir"),
        "figures": ensure_dir(root / "figures"),
    }
