"""Configuration loading for the data layer."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG = Path(__file__).resolve().parents[3] / "configs" / "data.yaml"


def load_data_config(path: Path | str | None = None) -> dict[str, Any]:
    """Load the declarative Stage 1 data configuration."""

    config_path = Path(path) if path is not None else DEFAULT_CONFIG
    with config_path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict):
        raise TypeError(f"invalid data configuration: {config_path}")
    return config
