from datetime import UTC, datetime

import numpy as np
import pandas as pd
import pytest

from tsfmbench.data.sources import coinbase
from tsfmbench.data.sources.coinbase import parse_candles
from tsfmbench.data.sources.deribit import fetch_volatility_index_data
from tsfmbench.data.sources.ecb import parse_ecb_csv, rates_to_series
from tsfmbench.data.sources.mof import merge_history_current, parse_mof_csv
from tsfmbench.data.sources.nikkei import parse_nikkei_csv


def test_ecb_missing_marker_stays_nan_and_quotes_are_not_inverted() -> None:
    raw = "Date, USD, JPY,GBP\n2026-01-02,1.20,180.0,0.84\n2026-01-05,-,181.0,N/A\n"
    frame = parse_ecb_csv(raw)
    assert np.isnan(frame.loc[1, "USD"])
    assert np.isnan(frame.loc[1, "GBP"])
    long = rates_to_series(frame)
    assert long.query("unique_id == 'EURJPY'")["y"].tolist() == [180.0, 181.0]


def test_mof_cp932_wareki_rows_and_current_priority() -> None:
    history_text = (
        "公表資料\r\n基準日,2年,5年,10年,20年,30年,40年\r\n"
        "S49.9.24,8.0,8.1,8.2,-,8.4,8.5\r\nR8.7.31,0.2,0.5,1.0,2.0,2.5,2.8\r\n"
    )
    current_text = "基準日,2年,5年,10年,20年,30年,40年\r\nR8.7.31,0.3,0.6,1.1,2.1,2.6,2.9\r\n"
    history = parse_mof_csv(history_text.encode("cp932"))
    current = parse_mof_csv(current_text.encode("cp932"))
    assert history.loc[0, "ds"] == pd.Timestamp("1974-09-24")
    assert np.isnan(history.loc[0, "JGB_20Y"])
    merged = merge_history_current(history, current)
    assert merged.loc[merged["ds"] == pd.Timestamp("2026-07-31"), "JGB_2Y"].item() == 0.3


def test_nikkei_close_is_second_column_and_footer_is_skipped() -> None:
    raw = (
        "データ日付,終値,始値,高値,安値\r\n"
        "2026/08/31,42100.5,42000.0,42200.0,41900.0\r\n"
        "Copyright Nikkei Inc.\r\n"
    ).encode("cp932")
    frame = parse_nikkei_csv(raw)
    assert len(frame) == 1
    assert frame.loc[0, "close"] == 42100.5
    assert frame.loc[0, "open"] == 42000.0


def test_coinbase_newest_first_is_sorted_and_identical_duplicate_is_deduped() -> None:
    payload = [
        [300, 95, 110, 100, 105, 12],
        [0, 90, 105, 95, 100, 10],
        [300, 95, 110, 100, 105, 12],
    ]
    frame = parse_candles(payload)
    assert frame["epoch"].tolist() == [0, 300]
    assert frame["close"].dtype == np.dtype("float64")


def test_coinbase_conflicting_duplicate_is_rejected() -> None:
    with pytest.raises(ValueError, match="conflicting"):
        parse_candles([[0, 1, 2, 1, 2, 3], [0, 1, 2, 1, 1.5, 3]])


def test_coinbase_backwards_pages_overlap_and_validate_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    pages = [
        [[90000, 1, 2, 1, 2, 3], [300, 1, 2, 1, 2, 3]],
        [[300, 1, 2, 1, 2, 3], [0, 1, 2, 1, 2, 3]],
    ]
    monkeypatch.setattr(coinbase, "_request_candles", lambda _url, _params: pages.pop(0))
    result = coinbase.fetch_candles(
        "BTC-USD", 300, datetime.fromtimestamp(0, tz=UTC), datetime.fromtimestamp(90000, tz=UTC)
    )
    assert result["epoch"].tolist() == [0, 300, 90000]
    assert result.attrs["boundary_checks"] == 1


class _Response:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self.payload


class _Session:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        # Deribit returns the NEWEST window first; `continuation` is the next
        # (older) end_timestamp. Page 1 holds the newer row, page 2 the older one.
        self.payloads = [
            {
                "result": {
                    "data": [[1641168000000, 52, 56, 50, 54]],
                    "continuation": 1641081600000,
                }
            },
            {"result": {"data": [[1640995200000, 50, 55, 45, 52]], "continuation": None}},
        ]

    def get(self, _url: str, *, params: dict[str, object], timeout: int) -> _Response:
        self.calls.append(dict(params))
        return _Response(self.payloads.pop(0))


def test_deribit_continuation_is_followed() -> None:
    session = _Session()
    result = fetch_volatility_index_data(
        "BTC", datetime(2022, 1, 1, tzinfo=UTC), datetime(2022, 1, 3, tzinfo=UTC), session=session
    )
    assert result["close"].tolist() == [52.0, 54.0]
    assert len(session.calls) == 2
    assert session.calls[1]["end_timestamp"] == 1641081600000
    assert session.calls[1]["start_timestamp"] == 1640995200000
