import numpy as np
import pandas as pd
import pytest

from tsfmbench.data.transforms import garman_klass, h_sum_series, realized_variance_daily


def _complete_day(day: str = "2026-01-01") -> pd.DataFrame:
    timestamps = pd.date_range(day, periods=288, freq="5min", tz="UTC")
    return pd.DataFrame({"timestamp": timestamps, "close": np.exp(np.arange(288) * 0.001)})


def test_garman_klass_known_value() -> None:
    # 0.5*ln(110/95)^2 - (2*ln(2)-1)*ln(105/100)^2
    assert garman_klass(100, 110, 95, 105) == pytest.approx(0.00982672327557351)


def test_realized_variance_known_value_and_no_overnight_return() -> None:
    first = _complete_day("2026-01-01")
    second = _complete_day("2026-01-02")
    second["close"] *= 100  # the day-boundary jump must not enter either day's RV
    result = realized_variance_daily(pd.concat([first, second], ignore_index=True))
    assert result["rv"].tolist() == pytest.approx([0.000287, 0.000287])
    assert result["m_intervals"].tolist() == [287, 287]
    assert result["reason"].isna().all()


def test_realized_variance_missing_one_candle_is_nan() -> None:
    candles = _complete_day().drop(index=100)
    result = realized_variance_daily(candles)
    assert np.isnan(result.loc[0, "rv"])
    assert result.loc[0, "m_intervals"] == 286
    assert result.loc[0, "reason"] == "missing_intervals"


def test_realized_variance_emits_an_entirely_missing_day() -> None:
    candles = pd.concat([_complete_day("2026-01-01"), _complete_day("2026-01-03")])
    result = realized_variance_daily(candles)
    assert result["ds"].tolist() == list(pd.date_range("2026-01-01", periods=3))
    assert np.isnan(result.loc[1, "rv"])
    assert result.loc[1, "m_intervals"] == 0
    assert result.loc[1, "reason"] == "missing_intervals"


def test_h_sum_is_non_overlapping_and_drops_partial_tail() -> None:
    frame = pd.DataFrame(
        {"ds": pd.date_range("2026-01-01", periods=7), "y": np.arange(1, 8, dtype=float)}
    )
    result = h_sum_series(frame, 3)
    assert result["y"].tolist() == [6.0, 15.0]
    assert result["ds"].tolist() == [pd.Timestamp("2026-01-01"), pd.Timestamp("2026-01-04")]
    assert result["block_end_ds"].tolist() == [
        pd.Timestamp("2026-01-03"),
        pd.Timestamp("2026-01-06"),
    ]


def test_h_sum_handles_a_series_shorter_than_h() -> None:
    frame = pd.DataFrame(
        {"unique_id": ["x", "x"], "ds": pd.date_range("2026-01-01", periods=2), "y": [1.0, 2.0]}
    )
    assert h_sum_series(frame, 3).empty


def test_h_sum_tail_alignment_drops_partial_head_and_ends_at_origin() -> None:
    frame = pd.DataFrame(
        {"ds": pd.date_range("2026-01-01", periods=8), "y": np.arange(1, 9, dtype=float)}
    )
    result = h_sum_series(frame, 3, alignment="end")
    assert result["y"].tolist() == [12.0, 21.0]
    assert result["ds"].tolist() == [pd.Timestamp("2026-01-03"), pd.Timestamp("2026-01-06")]
    assert result["block_end_ds"].iloc[-1] == frame["ds"].iloc[-1]
