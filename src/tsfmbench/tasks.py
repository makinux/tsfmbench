"""Declarative Stage 3 task configuration loading and normalization."""

from __future__ import annotations

import copy
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

DEFAULT_TASKS_DIR = Path(__file__).resolve().parents[2] / "configs" / "tasks"
TASK_NAMES = ("price", "rv", "volume")


def load_task_config(
    task: str | Path | Mapping[str, Any], *, tasks_dir: Path | str | None = None
) -> dict[str, Any]:
    """Load and validate a task YAML, returning a mutable resolved mapping."""

    if isinstance(task, Mapping):
        config = copy.deepcopy(dict(task))
        source = "<mapping>"
    else:
        candidate = Path(task)
        if candidate.suffix.lower() not in {".yaml", ".yml"}:
            root = Path(tasks_dir) if tasks_dir is not None else DEFAULT_TASKS_DIR
            candidate = root / f"{candidate}.yaml"
        source = str(candidate)
        with candidate.open("r", encoding="utf-8") as handle:
            config = yaml.safe_load(handle)
    if not isinstance(config, dict):
        raise TypeError(f"task configuration must be a mapping: {source}")
    required = {"task", "series", "horizons", "windows", "primary_benchmark"}
    missing = required.difference(config)
    if missing:
        raise ValueError(f"task configuration missing {sorted(missing)}: {source}")
    if not isinstance(config["series"], list) or not config["series"]:
        raise ValueError("task series must be a non-empty list")
    normalized_horizons: list[dict[str, Any]] = []
    for raw in config["horizons"]:
        detail = dict(raw) if isinstance(raw, Mapping) else {"h": raw}
        detail["h"] = int(detail["h"])
        if detail["h"] <= 0:
            raise ValueError("horizons must be positive")
        detail.setdefault("name", f"h{detail['h']}")
        detail.setdefault("target", "direct")
        detail.setdefault("step", int(config.get("origin_schedule", {}).get("step", detail["h"])))
        detail.setdefault("probabilistic", True)
        normalized_horizons.append(detail)
    config["horizons"] = normalized_horizons
    config["series"] = [str(value) for value in config["series"]]
    config["task"] = str(config["task"])
    config.setdefault("refit_every", 5)
    config.setdefault("estimation_windows", {})
    config.setdefault("context_length", {"default": 2048})
    config["_source"] = source
    return config


def horizon_config(config: Mapping[str, Any], h: int) -> dict[str, Any]:
    """Return one normalized horizon entry."""

    for detail in config["horizons"]:
        if int(detail["h"]) == int(h):
            return dict(detail)
    raise KeyError(f"horizon {h} is not configured for task {config.get('task')}")
