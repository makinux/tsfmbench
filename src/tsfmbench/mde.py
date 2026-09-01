"""Pre-run minimum-detectable-effect reports derived from task schedules."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from tsfmbench.stattests import design_effect_overlap, mde_analytic

DEFAULT_TASKS_DIR = Path("configs/tasks")
DEFAULT_MDE_DIR = Path("results/mde")


@dataclass(frozen=True)
class OriginSchedule:
    """The schedule inputs required for one task-by-horizon MDE cell."""

    task: str
    h_days: int
    step_days: int
    n_origins: int
    source: str


def _first(mapping: Mapping[str, Any], names: Sequence[str]) -> Any:
    for name in names:
        if name in mapping and mapping[name] is not None:
            return mapping[name]
    return None


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _task_entries(document: Any, source: Path) -> list[Mapping[str, Any]]:
    if isinstance(document, list):
        entries = document
    elif isinstance(document, Mapping) and isinstance(document.get("tasks"), list):
        entries = document["tasks"]
    elif isinstance(document, Mapping):
        entries = [document]
    else:
        raise TypeError(f"task configuration must be a mapping or list: {source}")
    if not all(isinstance(entry, Mapping) for entry in entries):
        raise TypeError(f"every task entry must be a mapping: {source}")
    return entries


def _horizon_entries(task: Mapping[str, Any]) -> list[tuple[int, Mapping[str, Any]]]:
    raw = _first(task, ("horizons", "h", "h_days"))
    if raw is None:
        raise ValueError("task configuration requires horizons, h, or h_days")
    raw_values = raw if isinstance(raw, list) else [raw]
    steps = _first(task, ("steps", "step", "step_days"))
    step_values = steps if isinstance(steps, list) else None
    entries: list[tuple[int, Mapping[str, Any]]] = []
    for index, item in enumerate(raw_values):
        if isinstance(item, Mapping):
            h_value = _first(item, ("h", "h_days", "horizon"))
            detail: dict[str, Any] = dict(item)
        else:
            h_value = item
            detail = {}
        if step_values is not None and index < len(step_values) and "step" not in detail:
            detail["step"] = step_values[index]
        try:
            h_days = int(h_value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid horizon: {h_value!r}") from exc
        if h_days <= 0:
            raise ValueError("horizons must be positive")
        entries.append((h_days, detail))
    return entries


def _period_count(start: Any, end: Any, frequency: str) -> int:
    if start is None or end is None:
        raise ValueError("task configuration requires a test-window start and end")
    start_timestamp = pd.Timestamp(start)
    end_timestamp = pd.Timestamp(end)
    if end_timestamp < start_timestamp:
        raise ValueError("test-window end precedes its start")
    normalized = frequency.lower().replace("_", " ").replace("-", " ")
    if normalized in {"b", "business", "business day", "business days", "trading"}:
        return len(pd.bdate_range(start_timestamp, end_timestamp))
    if normalized in {"d", "day", "days", "daily", "calendar", "calendar days"}:
        return len(pd.date_range(start_timestamp, end_timestamp, freq="D"))
    if normalized in {"native", "native calendar"}:
        # The config-only MDE report has no observed series calendar.  Daily is
        # a conservative schedule proxy; the backtest OriginSchedule uses the
        # exact per-series observed calendar.
        return len(pd.date_range(start_timestamp, end_timestamp, freq="D"))
    raise ValueError(f"unsupported schedule frequency: {frequency!r}")


def _date_text(value: Any) -> str:
    if isinstance(value, (date, datetime, pd.Timestamp)):
        return value.isoformat()
    return str(value)


def load_origin_schedules(tasks_dir: Path | str = DEFAULT_TASKS_DIR) -> list[OriginSchedule]:
    """Load the minimal test-window, step, and horizon schema from task YAML files."""

    directory = Path(tasks_dir)
    if not directory.exists():
        return []
    paths = sorted([*directory.glob("*.yaml"), *directory.glob("*.yml")])
    schedules: list[OriginSchedule] = []
    for path in paths:
        with path.open("r", encoding="utf-8") as handle:
            document = yaml.safe_load(handle)
        for task_index, task in enumerate(_task_entries(document, path), start=1):
            task_name = str(_first(task, ("task", "name", "id")) or path.stem)
            if task_index > 1 and task_name == path.stem:
                task_name = f"{task_name}-{task_index}"
            test = _as_mapping(_first(task, ("test_window", "test")))
            origin = _as_mapping(task.get("origin_schedule"))
            start = _first(origin, ("start", "start_date"))
            start = start if start is not None else _first(test, ("start", "start_date"))
            start = start if start is not None else _first(task, ("test_start", "start"))
            end = _first(origin, ("end", "end_date"))
            end = end if end is not None else _first(test, ("end", "end_date"))
            end = end if end is not None else _first(task, ("test_end", "end"))
            frequency = str(
                _first(origin, ("frequency", "freq", "calendar"))
                or _first(test, ("frequency", "freq", "calendar"))
                or _first(task, ("frequency", "freq", "calendar"))
                or "B"
            )
            explicit_origins = _first(origin, ("origins", "dates"))
            explicit_origins = (
                explicit_origins
                if explicit_origins is not None
                else _first(task, ("origins", "origin_dates"))
            )
            for h_days, detail in _horizon_entries(task):
                step = _first(detail, ("step", "step_days", "origin_step"))
                step = step if step is not None else _first(origin, ("step", "step_days"))
                step = step if step is not None else _first(task, ("step", "origin_step"))
                step_days = int(step if step is not None else h_days)
                if step_days <= 0:
                    raise ValueError("origin steps must be positive")
                configured_n = _first(detail, ("n_origins", "origins_count"))
                if configured_n is not None:
                    n_origins = int(configured_n)
                elif isinstance(explicit_origins, list):
                    n_origins = len(explicit_origins)
                else:
                    periods = _period_count(start, end, frequency)
                    n_origins = max(0, (periods - h_days) // step_days + 1)
                if n_origins <= 0:
                    raise ValueError(f"no complete origins for task={task_name}, h={h_days}")
                window = (
                    f"{_date_text(start)}..{_date_text(end)}"
                    if start is not None and end is not None
                    else "explicit origins"
                )
                schedules.append(
                    OriginSchedule(task_name, h_days, step_days, n_origins, f"{path.name}: {window}")
                )
    return schedules


def build_mde_rows(
    schedules: Sequence[OriginSchedule],
    *,
    alpha: float = 0.05,
    power: float = 0.8,
) -> list[dict[str, object]]:
    """Calculate analytic MDE rows and a documented benchmark-QLIKE ratio reference."""

    rows: list[dict[str, object]] = []
    for schedule in schedules:
        design_effect = design_effect_overlap(schedule.h_days, schedule.step_days)
        mde_sd = mde_analytic(schedule.n_origins, design_effect, alpha, power)
        rows.append(
            {
                "task": schedule.task,
                "h_days": schedule.h_days,
                "step_days": schedule.step_days,
                "n_origins": schedule.n_origins,
                "design_effect": design_effect,
                "mde_sd": mde_sd,
                # Schedule-only inputs cannot identify the QLIKE scale. This reference
                # assumes SD(loss difference) / mean(benchmark QLIKE) = 1.
                "reference_qlike_ratio": 1.0 + mde_sd,
                "source": schedule.source,
            }
        )
    return rows


def _markdown_report(rows: Sequence[Mapping[str, object]], alpha: float, power: float) -> str:
    lines = [
        "# Analytic minimum detectable effects",
        "",
        f"Two-sided alpha = {alpha:g}; power = {power:g}. MDE values use finite-sample t quantiles.",
        "",
        (
            "The reference QLIKE ratio is `1 + MDE_SD` and assumes "
            "`SD(loss difference) / mean(benchmark QLIKE) = 1`. It is a schedule-only "
            "reference, not an empirical scale conversion."
        ),
        "",
        "| task | h | step | origins | design effect | MDE (SD) | reference QLIKE ratio |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['task']} | {row['h_days']} | {row['step_days']} | {row['n_origins']} "
            f"| {float(row['design_effect']):.4f} | {float(row['mde_sd']):.4f} "
            f"| {float(row['reference_qlike_ratio']):.4f} |"
        )
    if not rows:
        lines.extend(("", "No task YAML files were found."))
    return "\n".join(lines) + "\n"


def write_mde_report(
    tasks_dir: Path | str = DEFAULT_TASKS_DIR,
    results_dir: Path | str = DEFAULT_MDE_DIR,
    *,
    alpha: float = 0.05,
    power: float = 0.8,
) -> dict[str, object]:
    """Write ``mde_report.md`` and ``mde_report.json`` and return their manifest."""

    schedules = load_origin_schedules(tasks_dir)
    rows = build_mde_rows(schedules, alpha=alpha, power=power)
    output = Path(results_dir)
    output.mkdir(parents=True, exist_ok=True)
    markdown_path = output / "mde_report.md"
    json_path = output / "mde_report.json"
    payload = {
        "alpha": alpha,
        "power": power,
        "units": "standard deviations of the paired loss difference",
        "qlike_reference_assumption": "SD(loss difference) / mean(benchmark QLIKE) = 1",
        "rows": rows,
    }
    markdown_path.write_text(_markdown_report(rows, alpha, power), encoding="utf-8")
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {
        "rows": rows,
        "markdown_path": markdown_path,
        "json_path": json_path,
    }
