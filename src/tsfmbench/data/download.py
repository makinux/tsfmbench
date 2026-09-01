"""Idempotent raw-cache orchestration."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from tsfmbench.data.config import load_data_config
from tsfmbench.data.sources import coinbase, deribit, ecb, mof, nikkei

LOGGER = logging.getLogger(__name__)
SOURCES = ("coinbase", "ecb", "mof", "nikkei", "deribit", "hf-checkpoint")
TIMESFM_CHECKPOINT = "google/timesfm-3.0-pytorch"


def download_hf_checkpoint(
    repo_id: str = TIMESFM_CHECKPOINT, *, revision: str | None = None
) -> Path:
    """Download TimesFM in a fresh process that never imports torch."""

    script = (
        "from huggingface_hub import snapshot_download\n"
        "import sys\n"
        "print(snapshot_download(repo_id=sys.argv[1], revision=None if sys.argv[2] == '' else sys.argv[2]))\n"
    )
    environment = os.environ.copy()
    environment["HF_HUB_OFFLINE"] = "0"
    environment.setdefault("HF_HUB_DISABLE_XET", "1")
    completed = subprocess.run(
        [sys.executable, "-c", script, repo_id, revision or ""],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )
    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError("huggingface_hub.snapshot_download returned no cache path")
    return Path(lines[-1])


def _datetime(value: str, *, end_of_day: bool = False) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    if end_of_day and parsed.hour == parsed.minute == parsed.second == 0:
        parsed = parsed.replace(hour=23, minute=59, second=59)
    return parsed.astimezone(UTC)


def download_sources(
    *,
    raw_dir: Path | str = Path("data/raw"),
    source: str | None = None,
    update: bool = False,
    config_path: Path | str | None = None,
) -> list[Path]:
    """Download all or one configured source into idempotent raw caches."""

    if source is not None and source not in SOURCES:
        raise ValueError(f"unknown source {source!r}; choose from {', '.join(SOURCES)}")
    selected = (source,) if source else tuple(item for item in SOURCES if item != "hf-checkpoint")
    if selected == ("hf-checkpoint",):
        return [download_hf_checkpoint()]
    root = Path(raw_dir)
    config = load_data_config(config_path)
    end = _datetime(str(config["end"]))
    written: list[Path] = []

    if "coinbase" in selected:
        rv_start = _datetime(str(config["coinbase"]["rv_start"]))
        for entry in config["coinbase"]["products"]:
            product = str(entry["product"])
            listing = _datetime(str(entry["listing_date"]))
            for granularity in config["coinbase"]["granularities"]:
                granularity = int(granularity)
                start = max(listing, rv_start) if granularity == 300 else listing
                path = root / "coinbase" / f"{product}_{granularity}.parquet"
                LOGGER.info("Downloading Coinbase %s at %ss", product, granularity)
                coinbase.update_cache(
                    product, granularity, start, end, path, update=update
                )
                written.append(path)

    if "ecb" in selected:
        path = root / "ecb" / "eurofxref-hist.csv"
        ecb.download_raw(path)
        written.append(path)

    if "mof" in selected:
        paths = mof.download_raw(root / "mof")
        written.extend(paths)

    if "nikkei" in selected:
        path = root / "nikkei" / "nikkei_stock_average_daily_jp.csv"
        nikkei.download_raw(path)
        written.append(path)

    if "deribit" in selected:
        start = _datetime(str(config["deribit"]["start"]))
        for currency in config["deribit"]["currencies"]:
            path = root / "deribit" / f"{currency}.parquet"
            deribit.update_cache(str(currency), start, end, path, update=update)
            written.append(path)

    return written
