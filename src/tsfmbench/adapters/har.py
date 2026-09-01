"""Direct HAR-RV regressions with lognormal smearing."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from tsfmbench.adapters.base import (
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
class HARFit:
    coefficients: np.ndarray
    residuals: np.ndarray
    sigma2: float
    last_features: np.ndarray

    @property
    def beta(self) -> np.ndarray:
        return self.coefficients


def _features(values: np.ndarray, index: int) -> np.ndarray | None:
    if index < 21:
        return None
    window = values[: index + 1]
    if not np.isfinite(window[-22:]).all() or np.any(window[-22:] <= 0):
        return None
    return np.array(
        [1.0, np.log(window[-1]), np.log(window[-5:].mean()), np.log(window[-22:].mean())],
        dtype="float64",
    )


def har_design_matrix(
    series: pd.DataFrame, h: int = 1, target: str = "direct"
) -> tuple[np.ndarray, np.ndarray]:
    """Build causal direct-HAR design and log targets.

    For sum horizons, targets are tail-aligned non-overlapping complete blocks;
    each block is paired with features available immediately before it starts.
    """

    ordered = series.sort_values("ds").reset_index(drop=True)
    values = pd.to_numeric(ordered["y"], errors="coerce").to_numpy(dtype="float64")
    dates = pd.to_datetime(ordered["ds"]).to_numpy()
    rows: list[np.ndarray] = []
    targets: list[float] = []
    if target == "sum" and h > 1:
        blocks = target_history(ordered[["ds", "y"]], h, "sum")
        date_to_index = {pd.Timestamp(value): index for index, value in enumerate(dates)}
        for block in blocks.itertuples(index=False):
            start_index = date_to_index.get(pd.Timestamp(block.ds))
            feature = _features(values, int(start_index) - 1) if start_index is not None else None
            if feature is not None and np.isfinite(block.y) and block.y > 0:
                rows.append(feature)
                targets.append(float(np.log(block.y)))
    else:
        for target_index in range(h, len(values)):
            feature = _features(values, target_index - h)
            target_value = values[target_index]
            if feature is not None and np.isfinite(target_value) and target_value > 0:
                rows.append(feature)
                targets.append(float(np.log(target_value)))
    return (
        np.vstack(rows) if rows else np.empty((0, 4), dtype="float64"),
        np.asarray(targets, dtype="float64"),
    )


def fit_har(series: pd.DataFrame, h: int = 1, target: str = "direct") -> HARFit:
    """Fit one horizon-specific HAR regression with ``numpy.linalg.lstsq``."""

    design, response = har_design_matrix(series, h, target)
    if len(response) < design.shape[1] + 1:
        raise ValueError("insufficient_history")
    coefficients, *_ = np.linalg.lstsq(design, response, rcond=None)
    residuals = response - design @ coefficients
    sigma2 = float(np.mean(np.square(residuals)))
    last = _features(pd.to_numeric(series["y"], errors="coerce").to_numpy(dtype="float64"), len(series) - 1)
    if last is None:
        raise ValueError("insufficient_history")
    return HARFit(coefficients, residuals, sigma2, last)


class HARRV:
    """Heterogeneous autoregressive realized-variance adapter."""

    name = "HAR-RV"
    requires_fit = True

    def __init__(self) -> None:
        self._fits: dict[tuple[str, int], tuple[pd.Timestamp, HARFit]] = {}

    def predict(self, task_ctx, origin, series_batch: pd.DataFrame) -> pd.DataFrame:
        rows = []
        for cell in target_cells(task_ctx, origin, series_batch).itertuples(index=False):
            h = int(cell.h)
            series = estimation_series(task_ctx, series_batch, str(cell.unique_id))
            target = str(horizon_detail(task_ctx, h).get("target", "direct"))
            try:
                key = (str(cell.unique_id), h)
                cached = self._fits.get(key)
                refit_every = int(ctx_config(task_ctx).get("refit_every", 5))
                new_count = int((series["ds"] > cached[0]).sum()) if cached else refit_every
                if cached is None or cached[0] > pd.Timestamp(origin) or new_count >= refit_every:
                    fitted = fit_har(series, h, target)
                    self._fits[key] = (pd.Timestamp(origin), fitted)
                else:
                    previous = cached[1]
                    current = _features(series["y"].to_numpy(dtype="float64"), len(series) - 1)
                    if current is None:
                        raise ValueError("insufficient_history")
                    fitted = HARFit(
                        previous.coefficients, previous.residuals, previous.sigma2, current
                    )
            except (ValueError, np.linalg.LinAlgError) as exc:
                rows.append(failed_row(cell.unique_id, h, cell.ds_target, str(exc)))
                continue
            mu = float(fitted.last_features @ fitted.coefficients)
            median = float(np.exp(mu))
            mean = float(np.exp(mu + fitted.sigma2 / 2.0))
            quantiles = np.exp(mu + np.quantile(fitted.residuals, np.arange(0.1, 1.0, 0.1)))
            rows.append(make_row(cell.unique_id, h, cell.ds_target, mean, median, quantiles))
        return validate_forecasts(pd.DataFrame(rows), positive=True)


HAR = HARRV
HARAdapter = HARRV
HARRVAdapter = HARRV
