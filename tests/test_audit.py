import pandas as pd

from tsfmbench.data.audit import (
    audit_coinbase_utc_grid,
    audit_ecb,
    audit_ohlc_invariants,
    audit_pagination_consistency,
    audit_rv,
    audit_wareki_dates,
)


def test_grid_audit_detects_missing_epoch() -> None:
    frame = pd.DataFrame({"epoch": [0, 300, 900]})
    result = audit_coinbase_utc_grid(frame, 300, "1970-01-01", "1970-01-01 00:15:00")
    assert not result["passed"]
    assert result["metrics"]["missing_count"] == 1


def test_pagination_audit_detects_conflict() -> None:
    result = audit_pagination_consistency(
        {"BTC-USD_300": {"boundary_checks": 2, "boundary_conflicts": 1}}
    )
    assert not result["passed"]


def test_ohlc_audit_detects_order_and_nonpositive_values() -> None:
    frame = pd.DataFrame(
        {"ds": pd.to_datetime(["2026-01-01", "2026-01-02"]), "open": [10, 10], "high": [9, 12], "low": [8, 0], "close": [11, 11]}
    )
    result = audit_ohlc_invariants(frame, source="fixture")
    assert result["violation_count"] == 2


def test_wareki_audit_detects_nat_weekend_and_wrong_start() -> None:
    frame = pd.DataFrame({"ds": [pd.Timestamp("1974-09-25"), pd.Timestamp("2026-08-30"), pd.NaT]})
    result = audit_wareki_dates(frame)
    kinds = {item["kind"] for item in result["violations"]}
    assert {"nat_dates", "wrong_first_date", "weekend_dates"}.issubset(kinds)


def test_ecb_audit_detects_zero() -> None:
    result = audit_ecb(pd.DataFrame({"Date": pd.to_datetime(["2026-01-01"]), "USD": [0.0]}))
    assert not result["passed"]


def test_rv_audit_detects_missing_and_nonpositive() -> None:
    frame = pd.DataFrame({"rv": [0.1, 0.0, float("nan")], "m_intervals": [287, 287, 286]})
    result = audit_rv(frame, max_missing_rate=0.1)
    kinds = {item["kind"] for item in result["violations"]}
    assert kinds == {"rv_missing_rate", "nonpositive_rv"}

