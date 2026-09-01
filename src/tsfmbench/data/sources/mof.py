"""Japanese Ministry of Finance JGB par-yield ingestion."""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from tsfmbench.data.wareki import parse_wareki

ALL_URL = "https://www.mof.go.jp/jgbs/reference/interest_rate/data/jgbcm_all.csv"
CURRENT_URL = "https://www.mof.go.jp/jgbs/reference/interest_rate/jgbcm.csv"
MATURITIES = (2, 5, 10, 20, 30, 40)
_DATA_ROW = re.compile(r"^\s*[MTSHR]\d+\.\d{1,2}\.\d{1,2}\s*$", re.IGNORECASE)


def _decode(data: str | bytes | Path) -> str:
    if isinstance(data, Path):
        return data.read_bytes().decode("cp932")
    if isinstance(data, bytes):
        return data.decode("cp932")
    return data


def parse_mof_csv(data: str | bytes | Path) -> pd.DataFrame:
    """Parse cp932 MOF rows beginning with a strict Japanese era date."""

    rows = list(csv.reader(io.StringIO(_decode(data))))
    header_map: dict[int, str] = {}
    for row in rows:
        for index, cell in enumerate(row):
            normalized = cell.strip().replace(" ", "")
            for maturity in MATURITIES:
                if normalized == f"{maturity}年":
                    header_map[index] = f"JGB_{maturity}Y"
        if header_map:
            break
    if not header_map:
        # Official fallback order: date, 1..10Y, 15Y, 20Y, 25Y, 30Y, 40Y.
        header_map = {2: "JGB_2Y", 5: "JGB_5Y", 10: "JGB_10Y", 12: "JGB_20Y", 14: "JGB_30Y", 15: "JGB_40Y"}

    parsed_rows: list[dict[str, object]] = []
    for row in rows:
        if not row or not _DATA_ROW.fullmatch(row[0]):
            continue
        record: dict[str, object] = {"ds": pd.Timestamp(parse_wareki(row[0].strip()))}
        for index, column in header_map.items():
            cell = row[index].strip() if index < len(row) else ""
            record[column] = np.nan if cell in {"", "-", "N/A"} else float(cell)
        parsed_rows.append(record)
    columns = ["ds", *(f"JGB_{maturity}Y" for maturity in MATURITIES)]
    frame = pd.DataFrame(parsed_rows).reindex(columns=columns)
    for column in columns[1:]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").astype("float64")
    return frame.sort_values("ds").drop_duplicates("ds", keep="last").reset_index(drop=True)


def merge_history_current(history: pd.DataFrame, current: pd.DataFrame) -> pd.DataFrame:
    """Merge MOF history/current frames with the current-month row taking priority."""

    return (
        pd.concat([history, current], ignore_index=True)
        .drop_duplicates("ds", keep="last")
        .sort_values("ds")
        .reset_index(drop=True)
    )


def download_raw(directory: Path, *, session: requests.Session | None = None) -> tuple[Path, Path]:
    """Download both cp932 MOF source files without transcoding the raw bytes."""

    client = session or requests.Session()
    directory.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for url, name in ((ALL_URL, "jgbcm_all.csv"), (CURRENT_URL, "jgbcm.csv")):
        response = client.get(url, timeout=60)
        response.raise_for_status()
        path = directory / name
        path.write_bytes(response.content)
        paths.append(path)
    return paths[0], paths[1]


parse_csv = parse_mof_csv
