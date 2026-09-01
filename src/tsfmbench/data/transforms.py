"""Deterministic transformations used by the benchmark data layer."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd


def garman_klass(
    o: float | Sequence[float] | pd.Series,
    h: float | Sequence[float] | pd.Series,
    l: float | Sequence[float] | pd.Series,
    c: float | Sequence[float] | pd.Series,
) -> float | np.ndarray | pd.Series:
    """Return open-to-close Garman--Klass variance (no overnight component)."""

    result = 0.5 * np.log(np.asarray(h) / np.asarray(l)) ** 2 - (
        2.0 * np.log(2.0) - 1.0
    ) * np.log(np.asarray(c) / np.asarray(o)) ** 2
    if all(np.isscalar(value) for value in (o, h, l, c)):
        return float(result)
    if isinstance(o, pd.Series):
        return pd.Series(result, index=o.index, name="rv", dtype="float64")
    return np.asarray(result, dtype="float64")


def garman_klass_daily(
    ohlc: pd.DataFrame,
    *,
    open_col: str = "open",
    high_col: str = "high",
    low_col: str = "low",
    close_col: str = "close",
) -> pd.DataFrame:
    """Calculate vectorized daily Garman--Klass variance from an OHLC frame."""

    required = {"ds", open_col, high_col, low_col, close_col}
    missing = required.difference(ohlc.columns)
    if missing:
        raise ValueError(f"missing OHLC columns: {sorted(missing)}")
    result = ohlc[["ds"]].copy()
    result["rv"] = garman_klass(
        ohlc[open_col], ohlc[high_col], ohlc[low_col], ohlc[close_col]
    )
    return result


def _utc_timestamps(candles: pd.DataFrame) -> pd.Series:
    if "epoch" in candles.columns:
        return pd.to_datetime(candles["epoch"], unit="s", utc=True, errors="coerce")
    for column in ("timestamp", "datetime", "ds"):
        if column in candles.columns:
            return pd.to_datetime(candles[column], utc=True, errors="coerce")
    raise ValueError("candles require an epoch, timestamp, datetime, or ds column")


def realized_variance_daily(candles_5min: pd.DataFrame) -> pd.DataFrame:
    """Aggregate complete UTC days of 5-minute closes into realized variance."""

    if "close" not in candles_5min.columns:
        raise ValueError("candles require a close column")
    work = pd.DataFrame(
        {
            "timestamp": _utc_timestamps(candles_5min),
            "close": pd.to_numeric(candles_5min["close"], errors="coerce"),
        }
    ).dropna(subset=["timestamp"])
    if work["timestamp"].duplicated().any():
        duplicates = work.loc[work["timestamp"].duplicated(False)]
        if duplicates.groupby("timestamp")["close"].nunique(dropna=False).gt(1).any():
            raise ValueError("conflicting duplicate 5-minute candles")
        work = work.drop_duplicates("timestamp", keep="last")
    work = work.sort_values("timestamp")
    work["day"] = work["timestamp"].dt.floor("D")

    if work.empty:
        return pd.DataFrame(
            {
                "ds": pd.Series(dtype="datetime64[ns]"),
                "rv": pd.Series(dtype="float64"),
                "m_intervals": pd.Series(dtype="int64"),
                "reason": pd.Series(dtype="object"),
            }
        )

    groups = {day: group for day, group in work.groupby("day", sort=True)}
    days = pd.date_range(work["day"].min(), work["day"].max(), freq="D", tz="UTC")
    rows: list[dict[str, object]] = []
    for day in days:
        group = groups.get(day, work.head(0)).sort_values("timestamp")
        expected = pd.date_range(day, periods=288, freq="5min", tz="UTC")
        complete = (
            len(group) == 288
            and group["timestamp"].reset_index(drop=True).equals(pd.Series(expected))
            and group["close"].notna().all()
            and group["close"].gt(0).all()
        )
        m_intervals = max(len(group) - 1, 0)
        rv = float(
            np.square(np.diff(np.log(group["close"].to_numpy(dtype="float64")))).sum()
        )
        rows.append(
            {
                "ds": day.tz_localize(None),
                "rv": rv if complete else np.nan,
                "m_intervals": m_intervals,
                "reason": None if complete else "missing_intervals",
            }
        )
    return pd.DataFrame(rows, columns=["ds", "rv", "m_intervals", "reason"]).astype(
        {"rv": "float64", "m_intervals": "int64"}
    )


def h_sum_series(
    df: pd.DataFrame,
    h: int,
    *,
    alignment: str = "start",
    align: str | None = None,
    tail_aligned: bool | None = None,
) -> pd.DataFrame:
    """Create non-overlapping, complete ``h``-row sums for each daily series.

    ``alignment="start"`` preserves the Stage 1 behaviour.  ``"end"`` drops a
    partial block at the *start*, so the newest block is always complete and
    ends at the newest observation.  The latter is the only safe construction
    for pre-origin rolling estimation of non-overlapping sum targets.
    """

    if h <= 0:
        raise ValueError("h must be positive")
    if "ds" not in df.columns:
        raise ValueError("series requires a ds column")
    value_col = "y" if "y" in df.columns else "rv" if "rv" in df.columns else None
    if value_col is None:
        numeric = [column for column in df.select_dtypes(include="number") if column != "m_intervals"]
        if len(numeric) != 1:
            raise ValueError("cannot infer value column")
        value_col = numeric[0]

    if align is not None:
        alignment = align
    if tail_aligned is not None:
        alignment = "end" if tail_aligned else "start"
    if alignment not in {"start", "end"}:
        raise ValueError("alignment must be 'start' or 'end'")

    group_columns = ["unique_id"] if "unique_id" in df.columns else []
    rows: list[dict[str, object]] = []
    grouped = df.groupby("unique_id", sort=False) if group_columns else [(None, df)]
    for key, group in grouped:
        ordered = group.sort_values("ds").reset_index(drop=True)
        complete_count = len(ordered) // h
        offset = len(ordered) % h if alignment == "end" else 0
        for block_index in range(complete_count):
            block_start = offset + block_index * h
            block = ordered.iloc[block_start : block_start + h]
            row: dict[str, object] = {
                "ds": pd.Timestamp(block["ds"].iloc[0]),
                value_col: float(block[value_col].sum(min_count=h)),
                "block_end_ds": pd.Timestamp(block["ds"].iloc[-1]),
            }
            if group_columns:
                row["unique_id"] = key
            rows.append(row)
    columns = [*group_columns, "ds", value_col, "block_end_ds"]
    return pd.DataFrame(rows, columns=columns)


def h_sum_series_tail(df: pd.DataFrame, h: int) -> pd.DataFrame:
    """Return tail-aligned non-overlapping sums (Stage 3 convenience API)."""

    return h_sum_series(df, h, alignment="end")


def log1p_series(df: pd.DataFrame, value_col: str = "y") -> pd.DataFrame:
    """Return a copy with ``value_col`` transformed by ``log1p``."""

    result = df.copy()
    result[value_col] = np.log1p(pd.to_numeric(result[value_col], errors="coerce"))
    return result
