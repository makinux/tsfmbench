"""RiskMetrics EWMA variance adapter."""

from __future__ import annotations

import numpy as np
import pandas as pd

from tsfmbench.adapters.base import (
    auxiliary_frame,
    estimation_series,
    failed_row,
    horizon_detail,
    make_row,
    target_cells,
    target_history,
    validate_forecasts,
)
from tsfmbench.adapters.calibration import RollingRatioCalibration


def _asset_from_rv(unique_id: str) -> str:
    if unique_id == "RV_N225_GK":
        return "N225"
    return unique_id.removeprefix("RV_") + "-USD"


def returns_for_series(task_ctx, unique_id: str, origin) -> pd.DataFrame:
    """Resolve pre-origin open-to-close decimal returns for an RV id."""

    frame = auxiliary_frame(task_ctx, "returns")
    if frame.empty:
        return pd.DataFrame(columns=["ds", "return"])
    id_col = "unique_id" if "unique_id" in frame else None
    result = frame.copy()
    if id_col:
        accepted = {str(unique_id), _asset_from_rv(str(unique_id))}
        result = result.loc[result[id_col].astype(str).isin(accepted)]
    return_col = next((name for name in ("return", "o2c_return", "r", "y") if name in result), None)
    if return_col is None:
        raise ValueError("returns auxiliary requires return or o2c_return column")
    result = result[["ds", return_col]].rename(columns={return_col: "return"})
    if isinstance(result["ds"].dtype, pd.DatetimeTZDtype) or not pd.api.types.is_datetime64_dtype(
        result["ds"].dtype
    ):
        result["ds"] = pd.to_datetime(result["ds"]).dt.tz_localize(None)
    if not pd.api.types.is_float_dtype(result["return"].dtype):
        result["return"] = pd.to_numeric(result["return"], errors="coerce")
    result = result.loc[result["ds"] <= pd.Timestamp(origin)].dropna()
    if not result["ds"].is_monotonic_increasing:
        result = result.sort_values("ds")
    return result.reset_index(drop=True)


def ewma_variance_path(returns: np.ndarray, lam: float = 0.94) -> tuple[np.ndarray, float]:
    """Return one-step-ahead variance at each observation and after the sample."""

    values = np.asarray(returns, dtype="float64")
    values = values[np.isfinite(values)]
    if values.size < 2:
        raise ValueError("insufficient_return_history")
    initial_n = min(20, values.size)
    variance = float(np.mean(np.square(values[:initial_n])))
    if not np.isfinite(variance) or variance <= 0:
        raise ValueError("nonpositive_forecast")
    forecasts = np.empty(values.size, dtype="float64")
    for index, value in enumerate(values):
        forecasts[index] = variance
        variance = float(lam * variance + (1.0 - lam) * value * value)
    return forecasts, variance


class _EWMAPathState:
    """Causal EWMA recursion that extends an unchanged return prefix in O(new)."""

    def __init__(self, lam: float) -> None:
        self.lam = float(lam)
        self.dates = np.array([], dtype="datetime64[ns]")
        self.values = np.array([], dtype="float64")
        self.forecasts = np.array([], dtype="float64")
        self.next_variance = np.nan
        self.rebuilt = False
        self.forecast_by_date: dict[pd.Timestamp, float] = {}

    def update(self, returns: pd.DataFrame) -> tuple[np.ndarray, float]:
        dates = pd.to_datetime(returns["ds"]).to_numpy(dtype="datetime64[ns]")
        values = returns["return"].to_numpy(dtype="float64")
        can_extend = (
            len(self.values) >= 20
            and len(values) >= len(self.values)
            and np.array_equal(values[: len(self.values)], self.values)
            and np.array_equal(dates[: len(self.dates)], self.dates)
        )
        if can_extend:
            self.rebuilt = False
            appended = values[len(self.values) :]
            path = np.empty(len(appended), dtype="float64")
            variance = float(self.next_variance)
            for index, value in enumerate(appended):
                path[index] = variance
                variance = float(self.lam * variance + (1.0 - self.lam) * value * value)
            if len(path):
                self.forecasts = np.concatenate([self.forecasts, path])
                self.next_variance = variance
                for date, forecast in zip(dates[-len(path) :], path, strict=True):
                    self.forecast_by_date[pd.Timestamp(date)] = float(forecast)
        else:
            self.forecasts, self.next_variance = ewma_variance_path(values, self.lam)
            self.rebuilt = True
            self.forecast_by_date = {
                pd.Timestamp(date): float(forecast)
                for date, forecast in zip(dates, self.forecasts, strict=True)
            }
        self.dates = dates.copy()
        self.values = values.copy()
        return self.forecasts, float(self.next_variance)


class _EWMARatioState:
    """Incrementally maintain EWMA/realized-variance calibration pairs."""

    def __init__(self, h: int, target: str) -> None:
        self.h = int(h)
        self.target = str(target)
        self.dates = np.array([], dtype="datetime64[ns]")
        self.values = np.array([], dtype="float64")
        self.blocks: list[tuple[pd.Timestamp, float]] = []
        self.ratios = RollingRatioCalibration()

    @property
    def is_sum(self) -> bool:
        return self.target == "sum" and self.h > 1

    @staticmethod
    def _overlap(
        old_dates: np.ndarray,
        old_values: np.ndarray,
        dates: np.ndarray,
        values: np.ndarray,
    ) -> tuple[int, int] | None:
        if not len(old_dates) or not len(dates):
            return None
        drop = int(np.searchsorted(old_dates, dates[0]))
        overlap = min(len(old_dates) - drop, len(dates))
        if overlap <= 0 or overlap < len(old_dates) - drop:
            return None
        if not np.array_equal(old_dates[drop : drop + overlap], dates[:overlap]):
            return None
        if not np.array_equal(old_values[drop : drop + overlap], values[:overlap]):
            return None
        return drop, len(dates) - overlap

    def _rebuild(
        self,
        dates: np.ndarray,
        values: np.ndarray,
        forecasts: dict[pd.Timestamp, float],
    ) -> None:
        self.ratios.clear()
        self.blocks = []
        if self.is_sum:
            offset = len(values) % self.h
            for start in range(offset, len(values) - self.h + 1, self.h):
                identity = pd.Timestamp(dates[start + self.h - 1])
                self.blocks.append((identity, float(values[start : start + self.h].sum())))
                if start > 0:
                    previous_date = pd.Timestamp(dates[start - 1])
                    if previous_date in forecasts:
                        self.ratios.append(identity, self.h * forecasts[previous_date], self.blocks[-1][1])
        else:
            for date, realized in zip(dates, values, strict=True):
                identity = pd.Timestamp(date)
                if identity in forecasts:
                    self.ratios.append(identity, forecasts[identity], float(realized))
        self.dates = dates.copy()
        self.values = values.copy()

    def _advance_sum(
        self,
        dates: np.ndarray,
        values: np.ndarray,
        forecasts: dict[pd.Timestamp, float],
        drop: int,
        appended: int,
    ) -> bool:
        if drop % self.h or appended % self.h or len(dates) % self.h != len(self.dates) % self.h:
            return False
        dropped_blocks = drop // self.h
        if dropped_blocks > len(self.blocks):
            return False
        if dropped_blocks:
            self.blocks = self.blocks[dropped_blocks:]
        offset = len(dates) % self.h
        first_pair = 1 if offset == 0 else 0
        if len(self.blocks) > first_pair:
            self.ratios.drop_before(self.blocks[first_pair][0])
        else:
            self.ratios.clear()
        first_new = len(dates) - appended
        for start in range(first_new, len(dates), self.h):
            if start + self.h > len(dates) or start == 0:
                return False
            previous_date = pd.Timestamp(dates[start - 1])
            identity = pd.Timestamp(dates[start + self.h - 1])
            block_sum = float(values[start : start + self.h].sum())
            self.blocks.append((identity, block_sum))
            if previous_date in forecasts:
                self.ratios.append(identity, self.h * forecasts[previous_date], block_sum)
        return True

    def update(
        self,
        rv_series: pd.DataFrame,
        forecasts: dict[pd.Timestamp, float],
        point: float,
        *,
        force_rebuild: bool = False,
    ) -> np.ndarray:
        dates = pd.to_datetime(rv_series["ds"]).to_numpy(dtype="datetime64[ns]")
        values = rv_series["y"].to_numpy(dtype="float64")
        overlap = None if force_rebuild else self._overlap(self.dates, self.values, dates, values)
        if overlap is None:
            self._rebuild(dates, values, forecasts)
        else:
            drop, appended = overlap
            advanced = True
            if drop or appended:
                if self.is_sum:
                    advanced = self._advance_sum(dates, values, forecasts, drop, appended)
                else:
                    if len(dates):
                        self.ratios.drop_before(pd.Timestamp(dates[0]))
                    else:
                        self.ratios.clear()
                    for index in range(len(dates) - appended, len(dates)):
                        identity = pd.Timestamp(dates[index])
                        if identity in forecasts and (
                            self.ratios.last_id is None or identity > self.ratios.last_id
                        ):
                            self.ratios.append(identity, forecasts[identity], float(values[index]))
            if not advanced:
                self._rebuild(dates, values, forecasts)
            else:
                self.dates = dates.copy()
                self.values = values.copy()
        return self.ratios.calibrated(point)


def _calibration_pairs(
    rv_series: pd.DataFrame, return_dates: pd.Series, forecast_path: np.ndarray, h: int, target: str
) -> tuple[np.ndarray, np.ndarray]:
    forecasts = pd.Series(forecast_path, index=pd.DatetimeIndex(return_dates)).groupby(level=0).last()
    if target == "sum" and h > 1:
        blocks = target_history(rv_series, h, "sum")
        pairs_f, pairs_y = [], []
        dates = rv_series["ds"].tolist()
        date_position = {pd.Timestamp(date): i for i, date in enumerate(dates)}
        for block in blocks.itertuples(index=False):
            start = date_position.get(pd.Timestamp(block.ds))
            if start is None or start == 0:
                continue
            previous_date = pd.Timestamp(dates[start - 1])
            if previous_date in forecasts.index:
                pairs_f.append(float(h * forecasts.loc[previous_date]))
                pairs_y.append(float(block.y))
        return np.asarray(pairs_f), np.asarray(pairs_y)
    merged = rv_series[["ds", "y"]].copy()
    merged["f"] = merged["ds"].map(forecasts)
    merged = merged.dropna()
    return merged["f"].to_numpy(), merged["y"].to_numpy()


class EWMA:
    """RiskMetrics lambda=.94 using open-to-close returns."""

    name = "EWMA"
    requires_fit = False
    auxiliary_names = ("returns",)

    def __init__(self, lam: float = 0.94) -> None:
        self.lam = float(lam)
        self._path_states: dict[str, _EWMAPathState] = {}
        self._ratio_states: dict[tuple[str, int, str], _EWMARatioState] = {}

    def predict(self, task_ctx, origin, series_batch: pd.DataFrame) -> pd.DataFrame:
        rows = []
        cells = target_cells(task_ctx, origin, series_batch)
        input_by_id = {
            str(uid): group
            for uid, group in series_batch.groupby(series_batch["unique_id"].astype(str), sort=False)
        }
        rv_by_id = {
            uid: estimation_series(task_ctx, input_by_id[uid], uid)
            for uid in cells["unique_id"].astype(str).drop_duplicates()
        }
        return_data: dict[
            str, tuple[pd.DataFrame, np.ndarray, float, bool, dict[pd.Timestamp, float]] | ValueError
        ] = {}
        for uid in rv_by_id:
            returns = returns_for_series(task_ctx, uid, origin)
            try:
                state = self._path_states.setdefault(uid, _EWMAPathState(self.lam))
                path, next_variance = state.update(returns)
                return_data[uid] = (
                    returns, path, next_variance, state.rebuilt, state.forecast_by_date
                )
            except ValueError as exc:
                return_data[uid] = exc
        for cell in cells.itertuples(index=False):
            uid, h = str(cell.unique_id), int(cell.h)
            rv = rv_by_id[uid]
            resolved = return_data[uid]
            if isinstance(resolved, ValueError):
                rows.append(failed_row(uid, h, cell.ds_target, str(resolved)))
                continue
            returns, path, next_variance, path_rebuilt, forecast_map = resolved
            target = str(horizon_detail(task_ctx, h).get("target", "direct"))
            point = float(next_variance * h) if target == "sum" else float(next_variance)
            ratio_state = self._ratio_states.setdefault((uid, h, target), _EWMARatioState(h, target))
            quantiles = ratio_state.update(
                rv,
                forecast_map,
                point,
                force_rebuild=path_rebuilt,
            )
            rows.append(make_row(uid, h, cell.ds_target, point, point, quantiles))
        return validate_forecasts(pd.DataFrame(rows), positive=True)


RiskMetricsEWMA = EWMA
EWMAAdapter = EWMA
