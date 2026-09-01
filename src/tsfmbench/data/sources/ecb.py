"""ECB euro foreign-exchange reference-rate ingestion."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pandas as pd
import requests

URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip"
CURRENCIES = ("USD", "JPY", "GBP", "CHF", "AUD", "CNY", "KRW", "MXN")


def parse_ecb_csv(data: str | bytes | Path) -> pd.DataFrame:
    """Parse ECB rates, preserving missing markers as NaN rather than zero."""

    if isinstance(data, Path):
        source: str | io.StringIO = str(data)
    elif isinstance(data, bytes):
        source = io.StringIO(data.decode("utf-8-sig"))
    else:
        source = io.StringIO(data)
    frame = pd.read_csv(source, na_values=["", "-", "N/A"], keep_default_na=True)
    frame.columns = [str(column).strip() for column in frame.columns]
    if "Date" not in frame.columns:
        raise ValueError("ECB CSV has no Date column")
    frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce").dt.normalize()
    frame = frame.dropna(subset=["Date"])
    for currency in CURRENCIES:
        if currency in frame.columns:
            frame[currency] = pd.to_numeric(frame[currency], errors="coerce").astype("float64")
    return frame.sort_values("Date").drop_duplicates("Date", keep="last").reset_index(drop=True)


def rates_to_series(frame: pd.DataFrame) -> pd.DataFrame:
    """Convert ECB wide rates to EURXXX long series without synthesizing crosses."""

    available = [currency for currency in CURRENCIES if currency in frame.columns]
    long = frame.melt(
        id_vars="Date", value_vars=available, var_name="currency", value_name="y"
    ).rename(columns={"Date": "ds"})
    long["unique_id"] = "EUR" + long.pop("currency")
    long["y"] = pd.to_numeric(long["y"], errors="coerce").astype("float64")
    return long[["unique_id", "ds", "y"]].sort_values(["unique_id", "ds"]).reset_index(
        drop=True
    )


def download_raw(path: Path, *, session: requests.Session | None = None) -> Path:
    """Download and extract the ECB historical CSV into its raw cache path."""

    client = session or requests.Session()
    response = client.get(URL, timeout=60)
    response.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        csv_names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if not csv_names:
            raise ValueError("ECB archive contains no CSV")
        content = archive.read(csv_names[0])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


parse_csv = parse_ecb_csv
