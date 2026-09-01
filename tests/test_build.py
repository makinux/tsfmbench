from pathlib import Path

import numpy as np
import pandas as pd

from tsfmbench.data.build import META_COLUMNS, RV_COLUMNS, SERIES_COLUMNS, build_processed


def _write_raw_fixture(raw: Path) -> None:
    (raw / "ecb").mkdir(parents=True, exist_ok=True)
    (raw / "ecb" / "eurofxref-hist.csv").write_text(
        "Date,USD,JPY\n2026-01-01,1.2,180\n2026-01-02,1.3,181\n", encoding="utf-8"
    )

    (raw / "mof").mkdir(exist_ok=True)
    (raw / "mof" / "jgbcm_all.csv").write_bytes(
        (
            "基準日,2年,5年,10年,20年,30年,40年\r\n"
            "S49.9.24,8.0,8.1,8.2,8.3,8.4,8.5\r\n"
            "R8.7.31,0.2,0.5,1.0,2.0,2.5,2.8\r\n"
        ).encode("cp932")
    )

    (raw / "nikkei").mkdir(exist_ok=True)
    (raw / "nikkei" / "n225.csv").write_bytes(
        (
            "データ日付,終値,始値,高値,安値\r\n"
            "2026/01/01,105,100,110,95\r\n"
            "2026/01/02,106,105,112,101\r\n"
        ).encode("cp932")
    )

    (raw / "coinbase").mkdir(exist_ok=True)
    daily_epochs = [int(pd.Timestamp(day, tz="UTC").timestamp()) for day in ["2026-01-01", "2026-01-02"]]
    pd.DataFrame(
        {
            "epoch": daily_epochs, "low": [90.0, 100.0], "high": [110.0, 120.0],
            "open": [95.0, 105.0], "close": [100.0, 110.0], "volume": [12.0, 13.0],
        }
    ).to_parquet(raw / "coinbase" / "BTC-USD_86400.parquet", index=False)
    times = pd.date_range("2026-01-01", periods=288, freq="5min", tz="UTC")
    pd.DataFrame(
        {
            "epoch": times.astype("int64") // 10**9,
            "low": 99.0, "high": 101.0, "open": 100.0,
            "close": np.exp(np.arange(288) * 0.001), "volume": 1.0,
        }
    ).to_parquet(raw / "coinbase" / "BTC-USD_300.parquet", index=False)

    (raw / "deribit").mkdir(exist_ok=True)
    pd.DataFrame(
        {"timestamp_ms": [int(pd.Timestamp("2026-01-01", tz="UTC").timestamp() * 1000)], "open": [50.0], "high": [55.0], "low": [45.0], "close": [52.0]}
    ).to_parquet(raw / "deribit" / "BTC.parquet", index=False)


def test_build_mini_raw_fixture() -> None:
    # Avoid pytest's chmod-based tmp_path on locked-down Windows runners.
    root = Path(".test-work/build_fixture")
    raw, processed = root / "raw", root / "processed"
    _write_raw_fixture(raw)
    outputs = build_processed(raw, processed)
    series, meta, rv = outputs["series"], outputs["meta"], outputs["rv_daily"]

    assert list(series.columns) == SERIES_COLUMNS
    assert list(meta.columns) == META_COLUMNS
    assert list(rv.columns) == RV_COLUMNS
    assert series["y"].dtype == np.dtype("float64")
    assert str(series["ds"].dtype) == "datetime64[ns]"
    assert len(series) == 23
    assert len(rv) == 3
    assert meta["unique_id"].nunique() == 14
    assert series.query("unique_id == 'VOL_Coinbase_BTC-USD_base'")["y"].tolist() == [12.0, 13.0]
    assert meta.set_index("unique_id").loc["RV_N225_GK", "proxy_m"] == 7.4
    assert (processed / "series.parquet").exists()
    assert (processed / "meta.parquet").exists()
    assert (processed / "rv_daily.parquet").exists()
