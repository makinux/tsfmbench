"""Global LightGBM adapter with pre-origin conformal residual calibration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from tsfmbench.adapters.base import (
    clean_series,
    ctx_config,
    estimation_series,
    failed_row,
    horizon_detail,
    make_row,
    target_cells,
    target_history,
    task_name,
    validate_forecasts,
)

LAGS = [*range(1, 15), 21, 28]
DEFAULT_PARAMS = {
    "num_leaves": 31,
    "learning_rate": 0.05,
    "n_estimators": 300,
    "min_child_samples": 20,
}


@dataclass
class _MLFit:
    origin: pd.Timestamp
    mean_model: Any
    median_model: Any
    residual_quantiles: np.ndarray
    sigma2: float
    calibration_dates: pd.DatetimeIndex
    id_codes: dict[str, int]
    mode: str


def _feature(values: np.ndarray, date: pd.Timestamp, id_code: int) -> np.ndarray | None:
    if len(values) < max(LAGS) or not np.isfinite(values[-max(LAGS) :]).all():
        return None
    lag_values = [values[-lag] for lag in LAGS]
    return np.asarray(
        [
            *lag_values,
            np.mean(values[-7:]),
            np.mean(values[-28:]),
            date.weekday(),
            date.month,
            int(date.is_month_end),
            id_code,
        ],
        dtype="float64",
    )


def _space(task_ctx, values: np.ndarray) -> tuple[np.ndarray, str]:
    task = task_name(task_ctx)
    config = ctx_config(task_ctx)
    if task == "rv":
        if np.any(values <= 0):
            return np.full_like(values, np.nan), "log"
        return np.log(values), "log"
    if task == "volume" and not config.get("_panel_transformed", False):
        return np.log1p(values), "log1p"
    return values.copy(), "identity"


def _inverse(mu: float | np.ndarray, mode: str, *, smear: float = 0.0) -> np.ndarray:
    values = np.asarray(mu, dtype="float64")
    if mode == "log":
        return np.exp(values + smear)
    if mode == "log1p":
        return np.exp(values + smear) - 1.0
    return values


def _supervised(
    task_ctx, panel: pd.DataFrame, h: int, id_codes: dict[str, int]
) -> tuple[np.ndarray, np.ndarray, pd.DatetimeIndex, str]:
    features: list[np.ndarray] = []
    targets: list[float] = []
    dates: list[pd.Timestamp] = []
    mode = "identity"
    detail = horizon_detail(task_ctx, h)
    target_kind = str(detail.get("target", "direct"))
    for uid in panel["unique_id"].astype(str).drop_duplicates():
        series = clean_series(panel, uid)
        raw = series["y"].to_numpy(dtype="float64")
        transformed, mode = _space(task_ctx, raw)
        if target_kind == "sum" and h > 1:
            # Build sums on the original RV scale, then log the complete block.
            blocks = target_history(series, h, "sum")
            positions = {pd.Timestamp(date): index for index, date in enumerate(series["ds"])}
            for block in blocks.itertuples(index=False):
                start = positions.get(pd.Timestamp(block.ds))
                if start is None or start == 0 or block.y <= 0:
                    continue
                x = _feature(transformed[:start], pd.Timestamp(block.block_end_ds), id_codes[uid])
                if x is not None:
                    features.append(x)
                    targets.append(float(np.log(block.y)))
                    dates.append(pd.Timestamp(block.block_end_ds))
            mode = "log"
        else:
            for target_index in range(h, len(series)):
                x = _feature(
                    transformed[: target_index - h + 1],
                    pd.Timestamp(series["ds"].iloc[target_index]),
                    id_codes[uid],
                )
                y = transformed[target_index]
                if x is not None and np.isfinite(y):
                    features.append(x)
                    targets.append(float(y))
                    dates.append(pd.Timestamp(series["ds"].iloc[target_index]))
    return (
        np.vstack(features) if features else np.empty((0, len(LAGS) + 6)),
        np.asarray(targets, dtype="float64"),
        pd.DatetimeIndex(dates),
        mode,
    )


class LightGBMGlobal:
    """One global task model per horizon, retrained every five native periods."""

    name = "LightGBM"
    requires_fit = True

    def __init__(self, **params: Any) -> None:
        self.params = {**DEFAULT_PARAMS, **params}
        self.n_windows = 10
        self.levels = [20, 40, 60, 80]
        self._fits: dict[int, _MLFit] = {}
        self.prediction_intervals_: dict[int, Any] = {}
        self.last_conformal_dates_: pd.DatetimeIndex = pd.DatetimeIndex([])
        try:
            from mlforecast.conformal_prediction import PredictionIntervals

            self.prediction_intervals = PredictionIntervals(n_windows=self.n_windows, h=1)
        except Exception:  # noqa: BLE001 - optional package API differs by supported version
            self.prediction_intervals = None

    def _fit(self, task_ctx, panel: pd.DataFrame, h: int, origin) -> tuple[_MLFit, str]:
        from lightgbm import LGBMRegressor

        origin = pd.Timestamp(origin)
        cached = self._fits.get(h)
        refit_every = int(ctx_config(task_ctx).get("refit_every", 5))
        if cached is not None and cached.origin <= origin:
            new_counts = panel.loc[pd.to_datetime(panel["ds"]) > cached.origin].groupby("unique_id").size()
            if (new_counts.max() if len(new_counts) else 0) < refit_every:
                self.last_conformal_dates_ = cached.calibration_dates
                return cached, cached.mode
        panel = pd.concat(
            [
                estimation_series(task_ctx, panel, uid).assign(unique_id=uid)
                for uid in panel["unique_id"].astype(str).drop_duplicates()
            ],
            ignore_index=True,
        )
        ids = sorted(panel["unique_id"].astype(str).unique())
        if self.prediction_intervals is not None:
            from mlforecast.conformal_prediction import PredictionIntervals

            self.prediction_intervals_[h] = PredictionIntervals(n_windows=self.n_windows, h=h)
            self.prediction_intervals = self.prediction_intervals_[h]
        codes = {uid: index for index, uid in enumerate(ids)}
        X, y, dates, mode = _supervised(task_ctx, panel, h, codes)
        if len(y) < 30:
            raise ValueError("insufficient_history")
        common = {**self.params, "verbosity": -1, "random_state": 0, "n_jobs": 1}
        mean_model = LGBMRegressor(objective="regression_l2", **common)
        median_model = LGBMRegressor(objective="quantile", alpha=0.5, **common)
        mean_model.fit(X, y)
        median_model.fit(X, y)
        median_fitted = median_model.predict(X)
        residuals = y - median_fitted
        calibration_size = min(len(dates), self.n_windows * max(1, h))
        calibration_residuals = residuals[-calibration_size:]
        residual_quantiles = np.quantile(
            calibration_residuals, np.arange(0.1, 1.0, 0.1)
        )
        # Central conformal bands are anchored on the median model.
        residual_quantiles -= residual_quantiles[4]
        calibration_dates = dates[-calibration_size:]
        if len(calibration_dates) and calibration_dates.max() > pd.Timestamp(origin):
            raise AssertionError("conformal calibration contains post-origin observations")
        fit = _MLFit(
            origin, mean_model, median_model, residual_quantiles,
            float(np.mean(np.square(y - mean_model.predict(X)))), calibration_dates, codes, mode,
        )
        self._fits[h] = fit
        self.last_conformal_dates_ = calibration_dates
        return fit, mode

    def predict(self, task_ctx, origin, series_batch: pd.DataFrame) -> pd.DataFrame:
        # Defence in depth for direct adapter use; run_task already supplies the
        # exact same frame through backtest.slice_asof.
        panel = series_batch.loc[pd.to_datetime(series_batch["ds"]) <= pd.Timestamp(origin)].copy()
        cells = target_cells(task_ctx, origin, panel)
        rows = []
        for h, h_cells in cells.groupby("h", sort=False):
            h = int(h)
            try:
                fit, mode = self._fit(task_ctx, panel, h, origin)
            except (ValueError, RuntimeError) as exc:
                rows.extend(
                    failed_row(cell.unique_id, h, cell.ds_target, str(exc))
                    for cell in h_cells.itertuples(index=False)
                )
                continue
            target_kind = str(horizon_detail(task_ctx, h).get("target", "direct"))
            if target_kind == "sum" and h > 1:
                mode = "log"
            for cell in h_cells.itertuples(index=False):
                uid = str(cell.unique_id)
                if uid not in fit.id_codes:
                    # Series too short at this refit to enter the global fit
                    # (e.g. RV_N225_GK h=22 sums: ~22 blocks since 2023-01).
                    rows.append(failed_row(uid, h, cell.ds_target, "insufficient_history"))
                    continue
                series = estimation_series(task_ctx, panel, uid)
                transformed, base_mode = _space(task_ctx, series["y"].to_numpy(dtype="float64"))
                if target_kind != "sum":
                    mode = base_mode
                feature = _feature(transformed, pd.Timestamp(cell.ds_target), fit.id_codes[uid])
                if feature is None:
                    rows.append(failed_row(uid, h, cell.ds_target, "insufficient_history"))
                    continue
                x = feature.reshape(1, -1)
                mean_mu = float(fit.mean_model.predict(x)[0])
                median_mu = float(fit.median_model.predict(x)[0])
                mean = float(_inverse(mean_mu, mode, smear=fit.sigma2 / 2.0))
                median = float(_inverse(median_mu, mode))
                quantiles = _inverse(median_mu + fit.residual_quantiles, mode)
                rows.append(make_row(uid, h, cell.ds_target, mean, median, quantiles))
        return validate_forecasts(pd.DataFrame(rows), positive=task_name(task_ctx) == "rv")


MLForecastAdapter = LightGBMGlobal
LightGBM = LightGBMGlobal
MLAdapter = LightGBMGlobal
