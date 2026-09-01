"""Coinbase Exchange candle ingestion with audited backwards pagination."""

from __future__ import annotations

import json
import logging
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

LOGGER = logging.getLogger(__name__)
BASE_URL = "https://api.exchange.coinbase.com"
_SESSION = requests.Session()
_THROTTLE_LOCK = threading.Lock()
_LAST_REQUEST_AT = 0.0


class _RetryableHttpError(requests.HTTPError):
    """An HTTP failure that Coinbase documents as safe to retry."""


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _iso(value: datetime) -> str:
    return _as_utc(value).isoformat().replace("+00:00", "Z")


def _throttle() -> None:
    global _LAST_REQUEST_AT
    with _THROTTLE_LOCK:
        delay = 0.15 - (time.monotonic() - _LAST_REQUEST_AT)
        if delay > 0:
            time.sleep(delay)
        _LAST_REQUEST_AT = time.monotonic()


@retry(
    retry=retry_if_exception_type(_RetryableHttpError),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=8),
    stop=stop_after_attempt(5),
    reraise=True,
)
def _request_candles(url: str, params: dict[str, object]) -> list[list[object]]:
    _throttle()
    response = _SESSION.get(url, params=params, timeout=30)
    if response.status_code == 429 or 500 <= response.status_code < 600:
        raise _RetryableHttpError(
            f"Coinbase returned HTTP {response.status_code}", response=response
        )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        raise TypeError(f"unexpected Coinbase response: {payload!r}")
    return payload


def parse_candles(payload: list[list[object]]) -> pd.DataFrame:
    """Parse newest-first Coinbase JSON into ascending numeric candle rows."""

    columns = ["epoch", "low", "high", "open", "close", "volume"]
    if not payload:
        return pd.DataFrame({
            "epoch": pd.Series(dtype="int64"),
            **{column: pd.Series(dtype="float64") for column in columns[1:]},
        })
    if any(not isinstance(row, list) or len(row) != 6 for row in payload):
        raise ValueError("Coinbase candle rows must contain exactly six values")
    frame = pd.DataFrame(payload, columns=columns)
    frame["epoch"] = pd.to_numeric(frame["epoch"], errors="raise").astype("int64")
    frame[columns[1:]] = frame[columns[1:]].apply(pd.to_numeric, errors="raise").astype(
        "float64"
    )
    duplicate_rows = frame.loc[frame["epoch"].duplicated(False)]
    for epoch, group in duplicate_rows.groupby("epoch"):
        if len(group.drop(columns="epoch").drop_duplicates()) != 1:
            raise ValueError(f"conflicting duplicate Coinbase candle at epoch {epoch}")
    return frame.drop_duplicates("epoch", keep="last").sort_values("epoch").reset_index(drop=True)


def _merge_pages(pages: list[pd.DataFrame]) -> tuple[pd.DataFrame, int]:
    if not pages:
        return parse_candles([]), 0
    combined = pd.concat(pages, ignore_index=True)
    boundary_checks = 0
    duplicate_rows = combined.loc[combined["epoch"].duplicated(False)]
    for epoch, group in duplicate_rows.groupby("epoch"):
        boundary_checks += 1
        if len(group.drop(columns="epoch").drop_duplicates()) != 1:
            raise ValueError(f"pagination boundary mismatch at epoch {epoch}")
    combined = combined.drop_duplicates("epoch", keep="last").sort_values("epoch").reset_index(
        drop=True
    )
    return combined, boundary_checks


def fetch_candles(
    product: str,
    granularity: int,
    start: datetime,
    end: datetime,
) -> pd.DataFrame:
    """Fetch Coinbase candles backwards in overlapping windows of at most 300 rows."""

    if granularity <= 0:
        raise ValueError("granularity must be positive")
    start_utc, end_utc = _as_utc(start), _as_utc(end)
    if start_utc > end_utc:
        raise ValueError("start must not be after end")

    url = f"{BASE_URL}/products/{product}/candles"
    pages: list[pd.DataFrame] = []
    window_end = end_utc
    max_span = timedelta(seconds=granularity * 299)
    while True:
        window_start = max(start_utc, window_end - max_span)
        payload = _request_candles(
            url,
            {
                "granularity": granularity,
                "start": _iso(window_start),
                "end": _iso(window_end),
            },
        )
        page = parse_candles(payload)
        lower = int(window_start.timestamp())
        upper = int(window_end.timestamp())
        pages.append(page.loc[page["epoch"].between(lower, upper)].copy())
        if window_start == start_utc:
            break
        window_end = window_start

    result, boundary_checks = _merge_pages(pages)
    result.attrs["boundary_checks"] = boundary_checks
    result.attrs["boundary_conflicts"] = 0
    return result


def _merge_cache(existing: pd.DataFrame, incoming: pd.DataFrame) -> pd.DataFrame:
    merged, _ = _merge_pages([existing, incoming])
    if not merged["epoch"].is_monotonic_increasing or merged["epoch"].duplicated().any():
        raise AssertionError("Coinbase cache must have unique, monotonically increasing epochs")
    return merged


def update_cache(
    product: str,
    granularity: int,
    start: datetime,
    end: datetime,
    path: Path,
    *,
    update: bool = False,
) -> pd.DataFrame:
    """Idempotently write a Coinbase parquet cache, appending only new intervals."""

    existing = pd.read_parquet(path) if path.exists() else parse_candles([])
    fetch_start = start
    if update and not existing.empty:
        fetch_start = datetime.fromtimestamp(int(existing["epoch"].max()), tz=UTC)
        if fetch_start > _as_utc(end):
            return existing
    incoming = fetch_candles(product, granularity, fetch_start, end)
    merged = _merge_cache(existing, incoming) if not existing.empty else incoming
    path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_parquet(path, index=False)

    audit_path = path.parent / "pagination_audit.json"
    audit: dict[str, Any] = {}
    if audit_path.exists():
        try:
            audit = json.loads(audit_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            LOGGER.warning("Replacing unreadable pagination audit file %s", audit_path)
    audit[path.stem] = {
        "boundary_checks": int(incoming.attrs.get("boundary_checks", 0)),
        "boundary_conflicts": int(incoming.attrs.get("boundary_conflicts", 0)),
    }
    audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True), encoding="utf-8")
    return merged
