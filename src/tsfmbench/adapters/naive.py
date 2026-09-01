"""Leakage-safe naive benchmark adapters."""

from __future__ import annotations

import numpy as np
import pandas as pd

from tsfmbench.adapters.base import (
    estimation_series,
    failed_row,
    horizon_detail,
    make_row,
    target_cells,
    task_name,
    validate_forecasts,
)
from tsfmbench.adapters.calibration import RollingRatioCalibration


class _NaiveRatioState:
    """Advance NaivePrev calibration pairs without rebuilding the window."""

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
    def _arrays(series: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        dates = pd.to_datetime(series["ds"]).to_numpy(dtype="datetime64[ns]")
        values = series["y"].to_numpy(dtype="float64")
        return dates, values

    def _rebuild(self, dates: np.ndarray, values: np.ndarray) -> None:
        self.ratios.clear()
        self.blocks = []
        if self.is_sum:
            offset = len(values) % self.h
            for start in range(offset, len(values) - self.h + 1, self.h):
                self.blocks.append(
                    (pd.Timestamp(dates[start + self.h - 1]), float(values[start : start + self.h].sum()))
                )
            for previous, realized in zip(self.blocks[:-1], self.blocks[1:], strict=True):
                self.ratios.append(realized[0], previous[1], realized[1])
        else:
            for index in range(1, len(values)):
                self.ratios.append(pd.Timestamp(dates[index]), float(values[index - 1]), float(values[index]))
        self.dates = dates.copy()
        self.values = values.copy()

    def _overlap(self, dates: np.ndarray, values: np.ndarray) -> tuple[int, int] | None:
        if not len(self.dates) or not len(dates):
            return None
        drop = int(np.searchsorted(self.dates, dates[0]))
        overlap = min(len(self.dates) - drop, len(dates))
        if overlap <= 0:
            return None
        if not np.array_equal(self.dates[drop : drop + overlap], dates[:overlap]):
            return None
        if not np.array_equal(self.values[drop : drop + overlap], values[:overlap]):
            return None
        if overlap < len(self.dates) - drop:
            return None
        return drop, len(dates) - overlap

    def _advance_direct(
        self, dates: np.ndarray, values: np.ndarray, drop: int, appended: int
    ) -> None:
        del drop  # The first retained pair identity determines all removals.
        if len(dates) < 2:
            self.ratios.clear()
        else:
            self.ratios.drop_before(pd.Timestamp(dates[1]))
            first_new = len(dates) - appended
            for index in range(max(1, first_new), len(dates)):
                identity = pd.Timestamp(dates[index])
                if self.ratios.last_id is None or identity > self.ratios.last_id:
                    self.ratios.append(identity, float(values[index - 1]), float(values[index]))

    def _advance_sum(
        self, dates: np.ndarray, values: np.ndarray, drop: int, appended: int
    ) -> bool:
        if drop % self.h or appended % self.h or len(dates) % self.h != len(self.dates) % self.h:
            return False
        dropped_blocks = drop // self.h
        if dropped_blocks > len(self.blocks):
            return False
        if dropped_blocks:
            self.blocks = self.blocks[dropped_blocks:]
        if len(self.blocks) >= 2:
            self.ratios.drop_before(self.blocks[1][0])
        else:
            self.ratios.clear()
        first_new = len(dates) - appended
        for start in range(first_new, len(dates), self.h):
            if start + self.h > len(dates):
                return False
            block = (
                pd.Timestamp(dates[start + self.h - 1]),
                float(values[start : start + self.h].sum()),
            )
            if self.blocks:
                self.ratios.append(block[0], self.blocks[-1][1], block[1])
            self.blocks.append(block)
        return True

    def update(self, series: pd.DataFrame) -> tuple[float, np.ndarray]:
        dates, values = self._arrays(series)
        overlap = self._overlap(dates, values)
        if overlap is None:
            self._rebuild(dates, values)
        else:
            drop, appended = overlap
            advanced = True
            if drop or appended:
                if self.is_sum:
                    advanced = self._advance_sum(dates, values, drop, appended)
                else:
                    self._advance_direct(dates, values, drop, appended)
            if not advanced:
                self._rebuild(dates, values)
            else:
                self.dates = dates.copy()
                self.values = values.copy()
        if self.is_sum:
            if not self.blocks:
                raise ValueError("insufficient_history")
            forecast = self.blocks[-1][1]
        else:
            if not len(values):
                raise ValueError("insufficient_history")
            forecast = float(values[-1])
        return forecast, self.ratios.calibrated(forecast)


class RandomWalk:
    """Last-level forecast with empirical h-period-change quantiles."""

    name = "RW"
    requires_fit = False

    def predict(self, task_ctx, origin, series_batch: pd.DataFrame) -> pd.DataFrame:
        rows = []
        for cell in target_cells(task_ctx, origin, series_batch).itertuples(index=False):
            series = estimation_series(task_ctx, series_batch, str(cell.unique_id))
            h = int(cell.h)
            if series.empty:
                rows.append(failed_row(cell.unique_id, h, cell.ds_target, "insufficient_history"))
                continue
            values = series["y"].to_numpy(dtype="float64")
            last = float(values[-1])
            changes = values[h:] - values[:-h]
            quantiles = last + np.quantile(changes, np.arange(0.1, 1.0, 0.1)) if len(changes) else None
            rows.append(make_row(cell.unique_id, h, cell.ds_target, last, last, quantiles))
        return validate_forecasts(pd.DataFrame(rows))


class NaivePrev:
    """Previous realized variance (or previous complete h-block sum)."""

    name = "NaivePrev"
    requires_fit = False

    def __init__(self) -> None:
        self._ratio_states: dict[tuple[str, int, str], _NaiveRatioState] = {}

    def predict(self, task_ctx, origin, series_batch: pd.DataFrame) -> pd.DataFrame:
        rows = []
        cells = target_cells(task_ctx, origin, series_batch)
        input_by_id = {
            str(uid): group
            for uid, group in series_batch.groupby(series_batch["unique_id"].astype(str), sort=False)
        }
        series_by_id = {
            uid: estimation_series(task_ctx, input_by_id[uid], uid)
            for uid in cells["unique_id"].astype(str).drop_duplicates()
        }
        for cell in cells.itertuples(index=False):
            uid = str(cell.unique_id)
            series = series_by_id[uid]
            h = int(cell.h)
            detail = horizon_detail(task_ctx, h)
            target = str(detail.get("target", "direct"))
            state_key = (uid, h, target)
            state = self._ratio_states.setdefault(state_key, _NaiveRatioState(h, target))
            try:
                forecast, quantiles = state.update(series)
            except ValueError:
                rows.append(failed_row(cell.unique_id, h, cell.ds_target, "insufficient_history"))
                continue
            rows.append(make_row(cell.unique_id, h, cell.ds_target, forecast, forecast, quantiles))
        return validate_forecasts(pd.DataFrame(rows), positive=True)


class _SeasonalBase:
    requires_fit = False
    n_same_weekdays = 1

    def _point(self, candidates: np.ndarray) -> float:
        return float(candidates[-1])

    def predict(self, task_ctx, origin, series_batch: pd.DataFrame) -> pd.DataFrame:
        rows = []
        for cell in target_cells(task_ctx, origin, series_batch).itertuples(index=False):
            series = estimation_series(task_ctx, series_batch, str(cell.unique_id))
            target_weekday = pd.Timestamp(cell.ds_target).weekday()
            same = series.loc[series["ds"].dt.weekday == target_weekday, "y"].to_numpy(dtype="float64")
            if same.size < self.n_same_weekdays:
                rows.append(failed_row(cell.unique_id, int(cell.h), cell.ds_target, "insufficient_history"))
                continue
            point = self._point(same[-self.n_same_weekdays :])
            quantiles = np.quantile(same, np.arange(0.1, 1.0, 0.1))
            rows.append(make_row(cell.unique_id, int(cell.h), cell.ds_target, point, point, quantiles))
        return validate_forecasts(pd.DataFrame(rows), positive=task_name(task_ctx) == "rv")


class SeasonalNaive7(_SeasonalBase):
    """Most recent observation from the target weekday (season seven)."""

    name = "SeasonalNaive7"


class SeasonalMedian4(_SeasonalBase):
    """Median of the most recent four observations from the target weekday."""

    name = "SeasonalMedian4"
    n_same_weekdays = 4

    def _point(self, candidates: np.ndarray) -> float:
        return float(np.median(candidates))


RandomWalkAdapter = RandomWalk
NaivePrevious = NaivePrev
SeasonalNaive = SeasonalNaive7
SeasonalMedian = SeasonalMedian4
