"""Nikkei 225 daily OHLC ingestion."""

from __future__ import annotations

import csv
import io
from pathlib import Path

import numpy as np
import pandas as pd
import requests

URL = "https://indexes.nikkei.co.jp/nkave/historical/nikkei_stock_average_daily_jp.csv"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


def _decode(data: str | bytes | Path) -> str:
    if isinstance(data, Path):
        return data.read_bytes().decode("cp932")
    if isinstance(data, bytes):
        return data.decode("cp932")
    return data


def parse_nikkei_csv(data: str | bytes | Path) -> pd.DataFrame:
    """Parse date, close, open, high, low order and skip non-date footer rows."""

    parsed: list[dict[str, object]] = []
    for row in csv.reader(io.StringIO(_decode(data))):
        if len(row) < 5:
            continue
        ds = pd.to_datetime(row[0].strip(), errors="coerce")
        if pd.isna(ds):
            continue
        values: list[float] = []
        for cell in row[1:5]:
            clean = cell.strip().replace(",", "")
            values.append(np.nan if clean in {"", "-", "N/A"} else float(clean))
        close, open_, high, low = values
        parsed.append(
            {"ds": pd.Timestamp(ds).normalize(), "close": close, "open": open_, "high": high, "low": low}
        )
    frame = pd.DataFrame(parsed, columns=["ds", "close", "open", "high", "low"])
    numeric = ["close", "open", "high", "low"]
    frame[numeric] = frame[numeric].astype("float64")
    return frame.sort_values("ds").drop_duplicates("ds", keep="last").reset_index(drop=True)


def download_raw(path: Path, *, session: requests.Session | None = None) -> Path:
    """Download the no-redistribution Nikkei source into the ignored raw cache."""

    # Nikkei index history is licensed as no-redistribution data. Never commit this raw file.
    client = session or requests.Session()
    response = client.get(URL, headers={"User-Agent": USER_AGENT}, timeout=60)
    response.raise_for_status()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(response.content)
    return path


parse_csv = parse_nikkei_csv
