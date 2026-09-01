"""Vectorized forecast metrics with explicit complete-case accounting."""

from __future__ import annotations

from collections.abc import Sequence
from typing import NamedTuple

import numpy as np
import pandas as pd


class MetricResult(NamedTuple):
    """A scalar metric and the number of rows used and dropped."""

    value: float
    n_used: int
    n_dropped: int


def absolute_errors(y: object, f: object) -> np.ndarray:
    """Return row-level absolute errors, with incomplete pairs represented by NaN.

    Report generation needs an aligned loss matrix for resampling and MCS.  Keeping
    the row-level definition here prevents the aggregate and report definitions from
    drifting apart.
    """

    actual = np.asarray(y, dtype="float64").reshape(-1)
    forecast = np.asarray(f, dtype="float64").reshape(-1)
    if actual.shape != forecast.shape:
        raise ValueError("metric inputs must have identical shapes")
    result = np.full(actual.shape, np.nan, dtype="float64")
    valid = np.isfinite(actual) & np.isfinite(forecast)
    result[valid] = np.abs(actual[valid] - forecast[valid])
    return result


def qlike_losses(y: object, f: object) -> np.ndarray:
    """Return row-level QLIKE losses, with incomplete pairs represented by NaN."""

    actual = np.asarray(y, dtype="float64").reshape(-1)
    forecast = np.asarray(f, dtype="float64").reshape(-1)
    if actual.shape != forecast.shape:
        raise ValueError("metric inputs must have identical shapes")
    valid = np.isfinite(actual) & np.isfinite(forecast)
    if np.any(actual[valid] <= 0.0):
        raise ValueError("QLIKE requires y > 0")
    if np.any(forecast[valid] <= 0.0):
        raise ValueError("QLIKE requires f > 0; forecasts are not clipped")
    result = np.full(actual.shape, np.nan, dtype="float64")
    ratio = actual[valid] / forecast[valid]
    result[valid] = ratio - np.log(ratio) - 1.0
    return result


def _complete_rows(*values: object) -> tuple[list[np.ndarray], int, int]:
    arrays = [np.asarray(value, dtype="float64") for value in values]
    if not arrays:
        raise ValueError("at least one input is required")
    if any(array.shape != arrays[0].shape for array in arrays[1:]):
        raise ValueError("metric inputs must have identical shapes")
    flattened = [array.reshape(-1) for array in arrays]
    valid = np.logical_and.reduce([np.isfinite(array) for array in flattened])
    n_used = int(valid.sum())
    return [array[valid] for array in flattened], n_used, int(valid.size - n_used)


def _mean_result(values: np.ndarray, n_used: int, n_dropped: int) -> MetricResult:
    value = float(np.mean(values)) if n_used else float("nan")
    return MetricResult(value, n_used, n_dropped)


def qlike(y: object, f: object) -> MetricResult:
    """Return mean QLIKE, ``mean(y/f - log(y/f) - 1)``, on finite rows."""

    (actual, forecast), n_used, n_dropped = _complete_rows(y, f)
    if np.any(actual <= 0.0):
        raise ValueError("QLIKE requires y > 0")
    if np.any(forecast <= 0.0):
        raise ValueError("QLIKE requires f > 0; forecasts are not clipped")
    return _mean_result(qlike_losses(actual, forecast), n_used, n_dropped)


def pinball(y: object, q: object, tau: float) -> MetricResult:
    """Return mean pinball loss ``(tau - 1[y < q]) * (y - q)``."""

    if not 0.0 < tau < 1.0:
        raise ValueError("tau must lie strictly between 0 and 1")
    (actual, quantile), n_used, n_dropped = _complete_rows(y, q)
    residual = actual - quantile
    loss = np.where(residual >= 0.0, tau * residual, (tau - 1.0) * residual)
    return _mean_result(loss, n_used, n_dropped)


def _quantile_column(frame: pd.DataFrame, tau: float) -> object:
    candidates: tuple[object, ...] = (
        tau,
        str(tau),
        f"{tau:g}",
        f"q{tau:g}",
        f"q{round(100 * tau)}",
    )
    for candidate in candidates:
        if candidate in frame.columns:
            return candidate
    for column in frame.columns:
        if isinstance(column, (float, int, np.floating, np.integer)) and np.isclose(
            float(column), tau, rtol=0.0, atol=1e-12
        ):
            return column
    raise ValueError(f"quantiles_df has no column for tau={tau:g}")


def wql(
    y: object,
    quantiles_df: pd.DataFrame,
    taus: Sequence[float] = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9),
) -> MetricResult:
    """Return weighted quantile loss ``2/K * sum(mean(pinball_tau))/mean(abs(y))``."""

    tau_values = tuple(float(tau) for tau in taus)
    if not tau_values or any(not 0.0 < tau < 1.0 for tau in tau_values):
        raise ValueError("taus must be a non-empty sequence in (0, 1)")
    actual = np.asarray(y, dtype="float64").reshape(-1)
    if len(quantiles_df) != actual.size:
        raise ValueError("y and quantiles_df must have the same number of rows")
    columns = [_quantile_column(quantiles_df, tau) for tau in tau_values]
    quantiles = quantiles_df.loc[:, columns].to_numpy(dtype="float64")
    valid = np.isfinite(actual) & np.isfinite(quantiles).all(axis=1)
    n_used = int(valid.sum())
    n_dropped = int(valid.size - n_used)
    if not n_used:
        return MetricResult(float("nan"), n_used, n_dropped)

    used_y = actual[valid]
    residual = used_y[:, None] - quantiles[valid]
    tau_array = np.asarray(tau_values, dtype="float64")[None, :]
    losses = np.where(residual >= 0.0, tau_array * residual, (tau_array - 1.0) * residual)
    denominator = float(np.mean(np.abs(used_y)))
    if denominator == 0.0:
        return MetricResult(float("nan"), n_used, n_dropped)
    value = (2.0 / len(tau_values)) * float(losses.mean(axis=0).sum()) / denominator
    return MetricResult(value, n_used, n_dropped)


def coverage(y: object, lo: object, hi: object) -> MetricResult:
    """Return inclusive interval coverage and complete-case row counts."""

    (actual, lower, upper), n_used, n_dropped = _complete_rows(y, lo, hi)
    covered = (lower <= actual) & (actual <= upper)
    return _mean_result(covered.astype("float64"), n_used, n_dropped)


def coverage_by_tercile(
    y: object,
    lo: object,
    hi: object,
    vol_proxy: object,
) -> pd.DataFrame:
    """Return interval coverage by low/middle/high empirical volatility tercile."""

    arrays = [np.asarray(value, dtype="float64").reshape(-1) for value in (y, lo, hi, vol_proxy)]
    if any(array.shape != arrays[0].shape for array in arrays[1:]):
        raise ValueError("coverage inputs must have identical shapes")
    matrix = np.column_stack(arrays)
    valid = np.isfinite(matrix).all(axis=1)
    n_dropped = int((~valid).sum())
    actual, lower, upper, volatility = (matrix[valid, index] for index in range(4))
    labels = ("low", "middle", "high")
    if volatility.size:
        first, second = np.quantile(volatility, (1.0 / 3.0, 2.0 / 3.0))
        group = np.where(volatility <= first, 0, np.where(volatility <= second, 1, 2))
    else:
        group = np.empty(0, dtype="int64")
    covered = (lower <= actual) & (actual <= upper)
    rows: list[dict[str, object]] = []
    for index, label in enumerate(labels):
        selected = group == index
        count = int(selected.sum())
        rows.append(
            {
                "tercile": label,
                "value": float(covered[selected].mean()) if count else float("nan"),
                "n_used": count,
                "n_dropped": n_dropped,
            }
        )
    return pd.DataFrame(rows).set_index("tercile")


def mae(y: object, f: object) -> MetricResult:
    """Return mean absolute error on paired finite rows."""

    (actual, forecast), n_used, n_dropped = _complete_rows(y, f)
    return _mean_result(absolute_errors(actual, forecast), n_used, n_dropped)


def mse(y: object, f: object) -> MetricResult:
    """Return mean squared error on paired finite rows."""

    (actual, forecast), n_used, n_dropped = _complete_rows(y, f)
    return _mean_result(np.square(actual - forecast), n_used, n_dropped)


def rmse(y: object, f: object) -> MetricResult:
    """Return root mean squared error on paired finite rows."""

    result = mse(y, f)
    return MetricResult(float(np.sqrt(result.value)), result.n_used, result.n_dropped)


def relative_mae(err_model: object, err_bench: object) -> MetricResult:
    """Return paired ``mean(abs(model error)) / mean(abs(benchmark error))``."""

    (model, benchmark), n_used, n_dropped = _complete_rows(err_model, err_bench)
    if not n_used:
        return MetricResult(float("nan"), n_used, n_dropped)
    denominator = float(np.mean(np.abs(benchmark)))
    value = float(np.mean(np.abs(model)) / denominator) if denominator > 0.0 else float("nan")
    return MetricResult(value, n_used, n_dropped)


# Never average raw QLIKE across series: each proxy has a different measurement floor
# (approximately 1/m). Cross-series aggregation must use benchmark-relative ratios or win rates.
