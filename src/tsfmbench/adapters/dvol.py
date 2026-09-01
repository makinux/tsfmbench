"""BTC/ETH DVOL-to-realized-variance direct regressions."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from tsfmbench.adapters.base import (
    auxiliary_frame,
    ctx_config,
    estimation_series,
    failed_row,
    horizon_detail,
    make_row,
    target_cells,
    target_history,
    validate_forecasts,
)


@dataclass(frozen=True)
class DVOLFit:
    coefficients: np.ndarray
    residuals: np.ndarray
    sigma2: float
    current_x: float


def _dvol_id(rv_id: str) -> str:
    return "DVOL_" + rv_id.removeprefix("RV_")


def _prepare_dvol(task_ctx, uid: str, origin) -> pd.DataFrame:
    frame = auxiliary_frame(task_ctx, "dvol")
    if frame.empty:
        frame = auxiliary_frame(task_ctx, "series")
    if frame.empty:
        return pd.DataFrame(columns=["ds", "x"])
    value = "y" if "y" in frame else "value"
    result = frame.loc[frame["unique_id"].astype(str) == _dvol_id(uid), ["ds", value]].copy()
    result["ds"] = pd.to_datetime(result["ds"]).dt.tz_localize(None)
    daily_variance = np.square(pd.to_numeric(result[value], errors="coerce") / 100.0) / 365.0
    result["x"] = np.log(daily_variance)
    return result.loc[result["ds"] <= pd.Timestamp(origin), ["ds", "x"]].dropna().sort_values("ds")


def fit_dvol(rv: pd.DataFrame, dvol: pd.DataFrame, h: int = 1, target: str = "direct") -> DVOLFit:
    """Fit ``log(target) = a + b log(DVOL^2/365)`` causally."""

    if dvol.empty:
        raise ValueError("missing_dvol_history")
    ordered = rv.sort_values("ds").reset_index(drop=True)
    dvol_series = dvol.set_index("ds")["x"].sort_index()

    def x_at_or_before(date) -> float | None:
        eligible = dvol_series.loc[dvol_series.index <= pd.Timestamp(date)]
        return float(eligible.iloc[-1]) if not eligible.empty else None

    design, response = [], []
    if target == "sum" and h > 1:
        blocks = target_history(ordered, h, "sum")
        positions = {pd.Timestamp(date): index for index, date in enumerate(ordered["ds"])}
        for block in blocks.itertuples(index=False):
            start = positions.get(pd.Timestamp(block.ds))
            if start is None or start == 0 or not np.isfinite(block.y) or block.y <= 0:
                continue
            x = x_at_or_before(ordered["ds"].iloc[start - 1])
            if x is not None and np.isfinite(x):
                design.append([1.0, x])
                response.append(np.log(float(block.y)))
    else:
        for target_index in range(h, len(ordered)):
            y = float(ordered["y"].iloc[target_index])
            x = x_at_or_before(ordered["ds"].iloc[target_index - h])
            if x is not None and np.isfinite(x) and np.isfinite(y) and y > 0:
                design.append([1.0, x])
                response.append(np.log(y))
    if len(response) < 4:
        raise ValueError("insufficient_history")
    matrix = np.asarray(design, dtype="float64")
    response_array = np.asarray(response, dtype="float64")
    coefficients, *_ = np.linalg.lstsq(matrix, response_array, rcond=None)
    residuals = response_array - matrix @ coefficients
    return DVOLFit(
        coefficients, residuals, float(np.mean(np.square(residuals))), float(dvol["x"].iloc[-1])
    )


class DVOLRegression:
    name = "DVOL"
    requires_fit = True
    auxiliary_names = ("dvol", "series")

    def __init__(self) -> None:
        self._fits: dict[tuple[str, int], tuple[pd.Timestamp, DVOLFit]] = {}

    def supports(self, unique_id: str) -> bool:
        return unique_id in {"RV_BTC", "RV_ETH"}

    def predict(self, task_ctx, origin, series_batch: pd.DataFrame) -> pd.DataFrame:
        rows = []
        for cell in target_cells(task_ctx, origin, series_batch).itertuples(index=False):
            uid, h = str(cell.unique_id), int(cell.h)
            if not self.supports(uid):
                continue
            rv = estimation_series(task_ctx, series_batch, uid)
            dvol = _prepare_dvol(task_ctx, uid, origin)
            target = str(horizon_detail(task_ctx, h).get("target", "direct"))
            try:
                key = (uid, h)
                cached = self._fits.get(key)
                refit_every = int(ctx_config(task_ctx).get("refit_every", 5))
                new_count = int((rv["ds"] > cached[0]).sum()) if cached else refit_every
                if cached is None or cached[0] > pd.Timestamp(origin) or new_count >= refit_every:
                    fitted = fit_dvol(rv, dvol, h, target)
                    self._fits[key] = (pd.Timestamp(origin), fitted)
                else:
                    previous = cached[1]
                    fitted = DVOLFit(
                        previous.coefficients,
                        previous.residuals,
                        previous.sigma2,
                        float(dvol["x"].iloc[-1]),
                    )
            except (ValueError, np.linalg.LinAlgError) as exc:
                rows.append(failed_row(uid, h, cell.ds_target, str(exc)))
                continue
            mu = float(np.array([1.0, fitted.current_x]) @ fitted.coefficients)
            median = float(np.exp(mu))
            mean = float(np.exp(mu + fitted.sigma2 / 2.0))
            quantiles = np.exp(mu + np.quantile(fitted.residuals, np.arange(0.1, 1.0, 0.1)))
            rows.append(make_row(uid, h, cell.ds_target, mean, median, quantiles))
        return validate_forecasts(pd.DataFrame(rows), positive=True)


DVOL = DVOLRegression
