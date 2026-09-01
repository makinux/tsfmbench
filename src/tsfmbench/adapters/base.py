"""Shared adapter contract and leakage-safe context helpers."""

from __future__ import annotations

import copy
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

import numpy as np
import pandas as pd

from tsfmbench.data.transforms import h_sum_series
from tsfmbench.tasks import horizon_config

QUANTILES = tuple(range(10, 100, 10))
QUANTILE_COLUMNS = tuple(f"q{q}" for q in QUANTILES)
ADAPTER_COLUMNS = (
    "unique_id", "h", "ds_target", "yhat_mean", "yhat_median",
    *QUANTILE_COLUMNS, "fail", "fail_reason",
)


@runtime_checkable
class Adapter(Protocol):
    """Protocol implemented by every batch forecasting adapter."""

    name: str
    requires_fit: bool

    def predict(
        self, task_ctx: TaskContext | Mapping[str, Any], origin: pd.Timestamp,
        series_batch: pd.DataFrame,
    ) -> pd.DataFrame: ...


@dataclass
class TaskContext:
    """All pre-resolved information needed by an adapter at one run.

    ``target_frame`` is deliberately separate from model input.  It contains
    only target labels (id, origin, horizon and target date), never future y.
    """

    config: dict[str, Any]
    target_frame: pd.DataFrame = field(default_factory=pd.DataFrame)
    auxiliary: dict[str, pd.DataFrame] = field(default_factory=dict)
    estimation: str = "rolling"
    window: str = "main"
    run_id: str = ""
    config_hash: str = ""
    data_hash: str = ""
    _cell_indices: dict[pd.Timestamp, np.ndarray] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.target_frame.empty or "origin" not in self.target_frame:
            return
        origins = pd.to_datetime(self.target_frame["origin"]).map(
            lambda value: pd.Timestamp(value).tz_localize(None).normalize()
        )
        self._cell_indices = {
            pd.Timestamp(origin): np.asarray(indices, dtype="int64")
            for origin, indices in origins.groupby(origins, sort=False).indices.items()
        }

    @property
    def task(self) -> str:
        return str(self.config["task"])

    @property
    def horizons(self) -> list[int]:
        return [int(item["h"]) for item in self.config["horizons"]]

    def horizon(self, h: int) -> dict[str, Any]:
        return horizon_config(self.config, h)

    def cells(self, origin: Any, unique_ids: list[str] | None = None) -> pd.DataFrame:
        if self.target_frame.empty:
            return pd.DataFrame(columns=["unique_id", "origin", "h", "ds_target"])
        timestamp = pd.Timestamp(origin).tz_localize(None).normalize()
        indices = self._cell_indices.get(timestamp)
        if indices is None:
            return self.target_frame.head(0).copy()
        result = self.target_frame.iloc[indices]
        if unique_ids is not None:
            result = result.loc[result["unique_id"].astype(str).isin(unique_ids)]
        return result.copy()

    def with_auxiliary(self, auxiliary: dict[str, pd.DataFrame]) -> TaskContext:
        """Shallow-copy a context while retaining its immutable origin index."""

        result = copy.copy(self)
        result.auxiliary = auxiliary
        return result


def ctx_config(task_ctx: TaskContext | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(task_ctx, TaskContext):
        return task_ctx.config
    config = task_ctx.get("config", task_ctx)
    return dict(config) if isinstance(config, Mapping) else {}


def ctx_value(task_ctx: TaskContext | Mapping[str, Any], key: str, default: Any = None) -> Any:
    if isinstance(task_ctx, TaskContext):
        return getattr(task_ctx, key, default)
    return task_ctx.get(key, default)


def task_name(task_ctx: TaskContext | Mapping[str, Any]) -> str:
    config = ctx_config(task_ctx)
    return str(config.get("task", ctx_value(task_ctx, "task", "")))


def configured_horizons(task_ctx: TaskContext | Mapping[str, Any]) -> list[int]:
    config = ctx_config(task_ctx)
    raw = config.get("horizons", ctx_value(task_ctx, "horizons", [1]))
    return [int(item["h"] if isinstance(item, Mapping) else item) for item in raw]


def horizon_detail(task_ctx: TaskContext | Mapping[str, Any], h: int) -> dict[str, Any]:
    config = ctx_config(task_ctx)
    for item in config.get("horizons", []):
        detail = dict(item) if isinstance(item, Mapping) else {"h": item}
        if int(detail["h"]) == int(h):
            detail.setdefault("target", "direct")
            return detail
    return {"h": int(h), "target": "sum" if int(h) > 1 and task_name(task_ctx) == "rv" else "direct"}


def target_cells(
    task_ctx: TaskContext | Mapping[str, Any], origin: Any, series_batch: pd.DataFrame
) -> pd.DataFrame:
    """Resolve expected cells without exposing future observations to a model."""

    ids = series_batch["unique_id"].astype(str).drop_duplicates().tolist()
    if isinstance(task_ctx, TaskContext):
        result = task_ctx.cells(origin, ids)
    else:
        raw = task_ctx.get("target_frame", task_ctx.get("targets"))
        result = raw.copy() if isinstance(raw, pd.DataFrame) else pd.DataFrame()
        if not result.empty and "origin" in result:
            result = result.loc[pd.to_datetime(result["origin"]) == pd.Timestamp(origin)]
        if not result.empty:
            result = result.loc[result["unique_id"].astype(str).isin(ids)]
    if not result.empty:
        result["ds_target"] = pd.to_datetime(result["ds_target"]).dt.tz_localize(None)
        return result[["unique_id", "h", "ds_target"]].sort_values(["unique_id", "h"])

    # A lightweight standalone-test fallback.  Production always supplies a
    # target frame created from the complete calendar by OriginSchedule.
    origin_ts = pd.Timestamp(origin).tz_localize(None).normalize()
    rows = []
    for unique_id in ids:
        for h in configured_horizons(task_ctx):
            rows.append({"unique_id": unique_id, "h": h, "ds_target": origin_ts + pd.Timedelta(days=h)})
    return pd.DataFrame(rows)


def value_column(frame: pd.DataFrame) -> str:
    for column in ("y", "rv", "value"):
        if column in frame:
            return column
    raise ValueError("adapter input requires a y or rv column")


def clean_series(frame: pd.DataFrame, unique_id: str) -> pd.DataFrame:
    column = value_column(frame)
    result = frame.loc[frame["unique_id"].astype(str) == str(unique_id), ["ds", column]].copy()
    result = result.rename(columns={column: "y"})
    if not isinstance(result["ds"].dtype, pd.DatetimeTZDtype) and pd.api.types.is_datetime64_dtype(
        result["ds"].dtype
    ):
        pass
    else:
        result["ds"] = pd.to_datetime(result["ds"]).dt.tz_localize(None)
    if not pd.api.types.is_float_dtype(result["y"].dtype):
        result["y"] = pd.to_numeric(result["y"], errors="coerce")
    result = result.dropna()
    if not result["ds"].is_monotonic_increasing:
        result = result.sort_values("ds")
    if result["ds"].duplicated().any():
        result = result.drop_duplicates("ds", keep="last")
    return result.reset_index(drop=True)


def series_group(unique_id: str) -> str:
    if unique_id.startswith("RV_N225") or unique_id == "N225":
        return "rv_equity" if unique_id.startswith("RV_") else "equity"
    if unique_id.startswith("RV_"):
        return "rv_crypto"
    if unique_id.startswith("EUR"):
        return "fx"
    if unique_id.startswith("JGB_"):
        return "rates"
    if unique_id.startswith("VOL_"):
        return "volume"
    if "-USD" in unique_id:
        return "crypto"
    return "default"


def estimation_series(
    task_ctx: TaskContext | Mapping[str, Any], frame: pd.DataFrame, unique_id: str
) -> pd.DataFrame:
    series = clean_series(frame, unique_id)
    if str(ctx_value(task_ctx, "estimation", "rolling")) == "expanding":
        return series
    config = ctx_config(task_ctx)
    windows = config.get("estimation_windows", {})
    group = series_group(unique_id)
    size = windows.get(group, windows.get("crypto" if "crypto" in group else group))
    return series.tail(int(size)).reset_index(drop=True) if size else series


def target_history(series: pd.DataFrame, h: int, target: str) -> pd.DataFrame:
    """Construct leakage-safe historical targets ending no later than origin."""

    if target != "sum" or h == 1:
        result = series[["ds", "y"]].copy()
        result["block_end_ds"] = result["ds"]
        return result
    result = h_sum_series(series[["ds", "y"]], h, alignment="end")
    # h_sum_series uses the first date as ds; block_end_ds is the purge key.
    return result.loc[result["block_end_ds"] <= series["ds"].max()].reset_index(drop=True)


def quantile_mapping(values: Any) -> dict[str, float]:
    array = np.asarray(values, dtype="float64")
    if array.size != len(QUANTILES):
        raise ValueError("exactly nine decile forecasts are required")
    return {column: float(value) for column, value in zip(QUANTILE_COLUMNS, array, strict=True)}


def empty_quantiles() -> dict[str, float]:
    return {column: np.nan for column in QUANTILE_COLUMNS}


def make_row(
    unique_id: str,
    h: int,
    ds_target: Any,
    mean: float,
    median: float,
    quantiles: Any | None = None,
    *,
    fail: bool = False,
    fail_reason: str | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "unique_id": str(unique_id), "h": int(h), "ds_target": pd.Timestamp(ds_target),
        "yhat_mean": float(mean), "yhat_median": float(median),
        **(empty_quantiles() if quantiles is None else quantile_mapping(quantiles)),
        "fail": bool(fail), "fail_reason": fail_reason,
    }
    return row


def failed_row(unique_id: str, h: int, ds_target: Any, reason: str) -> dict[str, Any]:
    return make_row(unique_id, h, ds_target, np.nan, np.nan, None, fail=True, fail_reason=reason)


def validate_forecasts(frame: pd.DataFrame, *, positive: bool = False) -> pd.DataFrame:
    """Validate the common adapter contract and quantile monotonicity."""

    if frame.empty and not set(ADAPTER_COLUMNS).issubset(frame.columns):
        return pd.DataFrame(columns=ADAPTER_COLUMNS)
    missing = set(ADAPTER_COLUMNS).difference(frame.columns)
    if missing:
        raise AssertionError(f"adapter output missing columns: {sorted(missing)}")
    result = frame.loc[:, ADAPTER_COLUMNS].copy()
    successful = ~result["fail"].to_numpy(dtype=bool)
    points = result[["yhat_mean", "yhat_median"]].to_numpy(dtype="float64")
    if not np.isfinite(points[successful]).all():
        raise AssertionError("successful forecasts require mean and median")
    quantiles = result.loc[successful, QUANTILE_COLUMNS].to_numpy(dtype="float64", copy=False)
    for row in quantiles:
        if np.isnan(row).all():
            continue
        if not np.isfinite(row).all() or np.any(np.diff(row) < -1e-12):
            raise AssertionError("quantile forecasts must be all-null or monotone")
    if positive:
        q_values = result.loc[:, QUANTILE_COLUMNS].to_numpy(dtype="float64", copy=False)
        invalid = successful & (
            (points[:, 0] <= 0)
            | (points[:, 1] <= 0)
            | np.any((q_values <= 0) & ~np.isnan(q_values), axis=1)
        )
        if np.any(invalid):
            result.loc[invalid, ["yhat_mean", "yhat_median", *QUANTILE_COLUMNS]] = np.nan
            result.loc[invalid, "fail"] = True
            result.loc[invalid, "fail_reason"] = "nonpositive_forecast"
    return result


def auxiliary_frame(task_ctx: TaskContext | Mapping[str, Any], name: str) -> pd.DataFrame:
    auxiliary = ctx_value(task_ctx, "auxiliary", {})
    if isinstance(auxiliary, Mapping) and isinstance(auxiliary.get(name), pd.DataFrame):
        return auxiliary[name]
    direct = ctx_value(task_ctx, name)
    return direct if isinstance(direct, pd.DataFrame) else pd.DataFrame()
