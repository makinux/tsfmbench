"""Deribit daily volatility-index ingestion."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import requests

URL = "https://www.deribit.com/api/v2/public/get_volatility_index_data"


def parse_volatility_rows(rows: list[list[object]]) -> pd.DataFrame:
    """Parse Deribit ``[timestamp, open, high, low, close]`` rows."""

    columns = ["timestamp_ms", "open", "high", "low", "close"]
    if not rows:
        return pd.DataFrame(
            {
                "timestamp_ms": pd.Series(dtype="int64"),
                **{column: pd.Series(dtype="float64") for column in columns[1:]},
            }
        )
    if any(not isinstance(row, list) or len(row) != 5 for row in rows):
        raise ValueError("Deribit volatility rows must contain five values")
    frame = pd.DataFrame(rows, columns=columns)
    frame["timestamp_ms"] = pd.to_numeric(frame["timestamp_ms"], errors="raise").astype("int64")
    frame[columns[1:]] = frame[columns[1:]].apply(pd.to_numeric, errors="raise").astype(
        "float64"
    )
    duplicates = frame.loc[frame["timestamp_ms"].duplicated(False)]
    for timestamp, group in duplicates.groupby("timestamp_ms"):
        if len(group.drop(columns="timestamp_ms").drop_duplicates()) != 1:
            raise ValueError(f"conflicting Deribit row at {timestamp}")
    return frame.drop_duplicates("timestamp_ms", keep="last").sort_values("timestamp_ms").reset_index(
        drop=True
    )


def fetch_volatility_index_data(
    currency: str,
    start: datetime,
    end: datetime,
    *,
    session: requests.Session | None = None,
) -> pd.DataFrame:
    """Fetch BTC/ETH DVOL, following every continuation value."""

    currency = currency.upper()
    if currency not in {"BTC", "ETH"}:
        raise ValueError("Deribit currency must be BTC or ETH")
    client = session or requests.Session()
    start_utc = start.replace(tzinfo=UTC) if start.tzinfo is None else start.astimezone(UTC)
    end_utc = end.replace(tzinfo=UTC) if end.tzinfo is None else end.astimezone(UTC)
    params: dict[str, object] = {
        "currency": currency,
        "resolution": "1D",
        "start_timestamp": int(start_utc.timestamp() * 1000),
        "end_timestamp": int(end_utc.timestamp() * 1000),
    }
    pages: list[pd.DataFrame] = []
    seen: set[str] = set()
    while True:
        response = client.get(URL, params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()
        result = payload.get("result", {})
        page = parse_volatility_rows(result.get("data", []))
        pages.append(page)
        continuation = result.get("continuation")
        # For a wide range Deribit returns the NEWEST rows up to end_timestamp and
        # `continuation` is the end_timestamp to request the next OLDER window.
        if continuation in (None, "") or page.empty:
            break
        marker = str(continuation)
        if marker in seen:
            raise ValueError("Deribit continuation did not advance")
        seen.add(marker)
        if isinstance(continuation, (int, float)) or marker.isdigit():
            new_end = int(continuation)
            if new_end < int(params["start_timestamp"]):
                break
            params["end_timestamp"] = new_end
        else:
            params["continuation"] = continuation
    return parse_volatility_rows(
        pd.concat(pages, ignore_index=True).values.tolist() if pages else []
    )


def update_cache(
    currency: str,
    start: datetime,
    end: datetime,
    path: Path,
    *,
    update: bool = False,
) -> pd.DataFrame:
    """Idempotently save a Deribit parquet cache."""

    existing = pd.read_parquet(path) if path.exists() else parse_volatility_rows([])
    fetch_start = start
    if update and not existing.empty:
        fetch_start = datetime.fromtimestamp(int(existing["timestamp_ms"].max()) / 1000, tz=UTC)
        end_utc = end.replace(tzinfo=UTC) if end.tzinfo is None else end.astimezone(UTC)
        if fetch_start > end_utc:
            return existing
    incoming = fetch_volatility_index_data(currency, fetch_start, end)
    merged = parse_volatility_rows(
        pd.concat([existing, incoming], ignore_index=True).values.tolist()
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_parquet(path, index=False)
    return merged


fetch_dvol = fetch_volatility_index_data
