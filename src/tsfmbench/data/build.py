"""Build normalized Stage 1 parquet artifacts from raw source caches."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from tsfmbench.data.config import load_data_config
from tsfmbench.data.sources import ecb, mof, nikkei
from tsfmbench.data.transforms import garman_klass_daily, realized_variance_daily

SERIES_COLUMNS = ["unique_id", "ds", "y"]
RV_COLUMNS = ["unique_id", "ds", "rv", "m_intervals", "reason"]
META_COLUMNS = [
    "unique_id",
    "group",
    "freq",
    "calendar_id",
    "timezone",
    "source",
    "license_note",
    "publication_rule",
    "first_ds",
    "last_ds",
    "n_obs",
    "proxy_m",
    "notes",
]


def _series(unique_id: str, ds: pd.Series, values: pd.Series) -> pd.DataFrame:
    result = pd.DataFrame(
        {
            "unique_id": unique_id,
            "ds": pd.to_datetime(ds, errors="coerce").dt.tz_localize(None).dt.normalize(),
            "y": pd.to_numeric(values, errors="coerce").astype("float64"),
        }
    ).dropna(subset=["ds"])
    return result.sort_values("ds").drop_duplicates("ds", keep="last").reset_index(drop=True)


def _read_jgb(raw_dir: Path) -> pd.DataFrame | None:
    history_path = raw_dir / "mof" / "jgbcm_all.csv"
    current_path = raw_dir / "mof" / "jgbcm.csv"
    if not history_path.exists() and not current_path.exists():
        parquet = raw_dir / "mof" / "jgb.parquet"
        return pd.read_parquet(parquet) if parquet.exists() else None
    history = mof.parse_mof_csv(history_path) if history_path.exists() else pd.DataFrame()
    current = mof.parse_mof_csv(current_path) if current_path.exists() else pd.DataFrame()
    if history.empty:
        return current
    if current.empty:
        return history
    return mof.merge_history_current(history, current)


def _read_nikkei(raw_dir: Path) -> pd.DataFrame | None:
    directory = raw_dir / "nikkei"
    if not directory.exists():
        return None
    parquet_files = sorted(directory.glob("*.parquet"))
    if parquet_files:
        return pd.read_parquet(parquet_files[0])
    csv_files = sorted(directory.glob("*.csv"))
    return nikkei.parse_nikkei_csv(csv_files[0]) if csv_files else None


def _daily_coinbase(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    if "epoch" in result.columns:
        result["ds"] = pd.to_datetime(result["epoch"], unit="s", utc=True).dt.tz_localize(None)
    elif "timestamp" in result.columns:
        result["ds"] = pd.to_datetime(result["timestamp"], utc=True).dt.tz_localize(None)
    else:
        raise ValueError("Coinbase raw cache requires epoch or timestamp")
    result["ds"] = result["ds"].dt.normalize()
    return result.sort_values("ds").drop_duplicates("ds", keep="last")


def _metadata_spec(unique_id: str, config: dict[str, Any]) -> dict[str, object]:
    if unique_id.startswith("EUR"):
        return {
            "group": "fx", "calendar_id": "target2", "timezone": "Europe/Frankfurt",
            "source": "ECB", "license_note": "ECB reference rates; source attribution required.",
            "publication_rule": "ECB ~16:15 CET same day", "proxy_m": np.nan, "notes": "X per EUR",
        }
    if unique_id.startswith("JGB_"):
        return {
            "group": "rates", "calendar_id": "jpx", "timezone": "Asia/Tokyo", "source": "MOF",
            "license_note": "Japanese Ministry of Finance public data.",
            "publication_rule": "MOF business-day publication; full file approximately one month lag",
            "proxy_m": np.nan, "notes": "percent",
        }
    if unique_id == "N225":
        return {
            "group": "equity", "calendar_id": "jpx", "timezone": "Asia/Tokyo", "source": "Nikkei",
            "license_note": config["nikkei"]["license_note"],
            "publication_rule": "JPX close 15:30 JST", "proxy_m": np.nan, "notes": "close",
        }
    if unique_id.startswith("VOL_Coinbase_"):
        return {
            "group": "volume", "calendar_id": "247", "timezone": "UTC", "source": "Coinbase",
            "license_note": "Coinbase Exchange public market data.",
            "publication_rule": "interval end UTC", "proxy_m": np.nan,
            "notes": "base volume; not USD-notional volume",
        }
    if unique_id.startswith("DVOL_"):
        return {
            "group": "ivol", "calendar_id": "247", "timezone": "UTC", "source": "Deribit",
            "license_note": "Deribit public API data.", "publication_rule": "interval end UTC",
            "proxy_m": np.nan, "notes": "annualized volatility percent",
        }
    if unique_id.startswith("RV_"):
        nikkei_rv = unique_id == "RV_N225_GK"
        return {
            "group": "rv", "calendar_id": "jpx" if nikkei_rv else "247",
            "timezone": "Asia/Tokyo" if nikkei_rv else "UTC",
            "source": "Nikkei" if nikkei_rv else "Coinbase",
            "license_note": config["nikkei"]["license_note"] if nikkei_rv else "Coinbase Exchange public market data.",
            "publication_rule": "JPX close 15:30 JST" if nikkei_rv else "interval end UTC",
            "proxy_m": 7.4 if nikkei_rv else 288.0,
            "notes": "Garman-Klass open-to-close proxy" if nikkei_rv else "complete 5-minute UTC days only",
        }
    product_note = ""
    for product in config["coinbase"]["products"]:
        if product["product"] == unique_id:
            product_note = str(product.get("notes", ""))
            break
    return {
        "group": "crypto", "calendar_id": "247", "timezone": "UTC", "source": "Coinbase",
        "license_note": "Coinbase Exchange public market data.", "publication_rule": "interval end UTC",
        "proxy_m": np.nan, "notes": product_note,
    }


def _build_meta(
    series: pd.DataFrame, rv_daily: pd.DataFrame, config: dict[str, Any]
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for unique_id, frame, value_column in [
        *((uid, group, "y") for uid, group in series.groupby("unique_id", sort=False)),
        *((uid, group, "rv") for uid, group in rv_daily.groupby("unique_id", sort=False)),
    ]:
        spec = _metadata_spec(str(unique_id), config)
        observed = frame.loc[frame[value_column].notna()]
        rows.append(
            {
                "unique_id": unique_id,
                **spec,
                "freq": "D",
                "first_ds": observed["ds"].min() if not observed.empty else pd.NaT,
                "last_ds": observed["ds"].max() if not observed.empty else pd.NaT,
                "n_obs": int(frame[value_column].notna().sum()),
            }
        )
    meta = pd.DataFrame(rows).reindex(columns=META_COLUMNS)
    if not meta.empty:
        meta["first_ds"] = pd.to_datetime(meta["first_ds"]).dt.normalize()
        meta["last_ds"] = pd.to_datetime(meta["last_ds"]).dt.normalize()
        meta["n_obs"] = meta["n_obs"].astype("int64")
        meta["proxy_m"] = pd.to_numeric(meta["proxy_m"], errors="coerce").astype("float64")
    return meta


def _assert_outputs(series: pd.DataFrame, rv_daily: pd.DataFrame) -> None:
    if not pd.api.types.is_datetime64_ns_dtype(series["ds"]):
        raise AssertionError("series ds must be tz-naive datetime64[ns]")
    if series["ds"].dt.tz is not None or series["y"].dtype != np.dtype("float64"):
        raise AssertionError("series types must be tz-naive ds and float64 y")
    for unique_id, group in series.groupby("unique_id"):
        if group["ds"].duplicated().any() or not group["ds"].is_monotonic_increasing:
            raise AssertionError(f"series {unique_id} has duplicate or non-monotonic dates")
    for unique_id, group in rv_daily.groupby("unique_id"):
        if group["ds"].duplicated().any() or not group["ds"].is_monotonic_increasing:
            raise AssertionError(f"RV series {unique_id} has duplicate or non-monotonic dates")
    if not pd.api.types.is_datetime64_ns_dtype(rv_daily["ds"]):
        raise AssertionError("RV ds must be tz-naive datetime64[ns]")
    if rv_daily["ds"].dt.tz is not None or rv_daily["rv"].dtype != np.dtype("float64"):
        raise AssertionError("RV types must be tz-naive ds and float64 rv")


def build_processed(
    raw_dir: Path | str = Path("data/raw"),
    processed_dir: Path | str = Path("data/processed"),
    *,
    config_path: Path | str | None = None,
) -> dict[str, pd.DataFrame]:
    """Build series, metadata, and realized-variance parquet artifacts."""

    raw_root, output_root = Path(raw_dir), Path(processed_dir)
    config = load_data_config(config_path)
    series_frames: list[pd.DataFrame] = []
    rv_frames: list[pd.DataFrame] = []

    ecb_path = raw_root / "ecb" / "eurofxref-hist.csv"
    if ecb_path.exists():
        series_frames.append(ecb.rates_to_series(ecb.parse_ecb_csv(ecb_path)))

    jgb = _read_jgb(raw_root)
    if jgb is not None:
        for maturity in config["mof"]["maturities"]:
            column = f"JGB_{int(maturity)}Y"
            if column in jgb.columns:
                series_frames.append(_series(column, jgb["ds"], jgb[column]))

    n225 = _read_nikkei(raw_root)
    if n225 is not None and not n225.empty:
        series_frames.append(_series("N225", n225["ds"], n225["close"]))
        n225_rv = garman_klass_daily(n225)
        n225_rv["unique_id"] = "RV_N225_GK"
        n225_rv["m_intervals"] = np.nan
        n225_rv["reason"] = None
        rv_frames.append(n225_rv[RV_COLUMNS])

    for entry in config["coinbase"]["products"]:
        product = str(entry["product"])
        daily_path = raw_root / "coinbase" / f"{product}_86400.parquet"
        if daily_path.exists():
            daily = _daily_coinbase(pd.read_parquet(daily_path))
            series_frames.append(_series(product, daily["ds"], daily["close"]))
            volume_id = f"VOL_Coinbase_{product}_base"
            series_frames.append(_series(volume_id, daily["ds"], daily["volume"]))
        intraday_path = raw_root / "coinbase" / f"{product}_300.parquet"
        if intraday_path.exists():
            rv = realized_variance_daily(pd.read_parquet(intraday_path))
            rv["unique_id"] = f"RV_{product.split('-')[0]}"
            rv_frames.append(rv[RV_COLUMNS])

    for currency in config["deribit"]["currencies"]:
        path = raw_root / "deribit" / f"{currency}.parquet"
        if path.exists():
            frame = pd.read_parquet(path)
            if "timestamp_ms" in frame.columns:
                ds = pd.to_datetime(frame["timestamp_ms"], unit="ms", utc=True).dt.tz_localize(None)
            else:
                ds = pd.to_datetime(frame["ds"], utc=True).dt.tz_localize(None)
            series_frames.append(_series(f"DVOL_{currency}", ds, frame["close"]))

    series = (
        pd.concat(series_frames, ignore_index=True)[SERIES_COLUMNS]
        if series_frames
        else pd.DataFrame({
            "unique_id": pd.Series(dtype="string"), "ds": pd.Series(dtype="datetime64[ns]"),
            "y": pd.Series(dtype="float64")
        })
    )
    series["unique_id"] = series["unique_id"].astype("string")
    series["y"] = series["y"].astype("float64")
    series = series.sort_values(["unique_id", "ds"]).reset_index(drop=True)

    rv_daily = (
        pd.concat(rv_frames, ignore_index=True)[RV_COLUMNS]
        if rv_frames
        else pd.DataFrame({
            "unique_id": pd.Series(dtype="string"), "ds": pd.Series(dtype="datetime64[ns]"),
            "rv": pd.Series(dtype="float64"), "m_intervals": pd.Series(dtype="float64"),
            "reason": pd.Series(dtype="object")
        })
    )
    rv_daily["unique_id"] = rv_daily["unique_id"].astype("string")
    rv_daily["ds"] = pd.to_datetime(rv_daily["ds"]).dt.normalize()
    rv_daily["rv"] = pd.to_numeric(rv_daily["rv"], errors="coerce").astype("float64")
    rv_daily["m_intervals"] = pd.to_numeric(rv_daily["m_intervals"], errors="coerce").astype("float64")
    rv_daily = rv_daily.sort_values(["unique_id", "ds"]).reset_index(drop=True)

    _assert_outputs(series, rv_daily)
    meta = _build_meta(series, rv_daily, config)
    output_root.mkdir(parents=True, exist_ok=True)
    series.to_parquet(output_root / "series.parquet", index=False)
    meta.to_parquet(output_root / "meta.parquet", index=False)
    rv_daily.to_parquet(output_root / "rv_daily.parquet", index=False)
    return {"series": series, "meta": meta, "rv_daily": rv_daily}


build_from_raw = build_processed
