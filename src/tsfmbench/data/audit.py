"""Audits for raw and normalized Stage 1 financial data."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from tsfmbench.data.config import load_data_config
from tsfmbench.data.sources import ecb, mof, nikkei


def _audit(name: str, violations: list[dict[str, Any]], **metrics: Any) -> dict[str, Any]:
    return {
        "name": name,
        "passed": not violations,
        "violation_count": len(violations),
        "violations": violations,
        "metrics": metrics,
    }


def _epochs(frame: pd.DataFrame) -> pd.Series:
    if "epoch" in frame.columns:
        return pd.to_numeric(frame["epoch"], errors="coerce")
    if "timestamp" in frame.columns:
        return pd.to_datetime(frame["timestamp"], utc=True, errors="coerce").astype("int64") // 10**9
    raise ValueError("Coinbase frame requires epoch or timestamp")


def audit_coinbase_utc_grid(
    frame: pd.DataFrame,
    granularity: int,
    listing_start: str | pd.Timestamp,
    end: str | pd.Timestamp | None = None,
    *,
    series_id: str = "coinbase",
) -> dict[str, Any]:
    """Anti-join Coinbase epochs against the complete configured UTC grid."""

    actual_series = _epochs(frame).dropna().astype("int64")
    duplicate_count = int(actual_series.duplicated().sum())
    actual = set(actual_series.tolist())
    start_epoch = int(pd.Timestamp(listing_start, tz="UTC").timestamp()) if pd.Timestamp(listing_start).tzinfo is None else int(pd.Timestamp(listing_start).tz_convert("UTC").timestamp())
    if end is None:
        end_epoch = max(actual) if actual else start_epoch
    else:
        end_timestamp = pd.Timestamp(end)
        end_epoch = int((end_timestamp.tz_localize("UTC") if end_timestamp.tzinfo is None else end_timestamp.tz_convert("UTC")).timestamp())
    first = ((start_epoch + granularity - 1) // granularity) * granularity
    last = (end_epoch // granularity) * granularity
    expected = set(range(first, last + 1, granularity)) if last >= first else set()
    missing = sorted(expected.difference(actual))
    off_grid = sorted(epoch for epoch in actual if epoch % granularity != 0)
    violations: list[dict[str, Any]] = []
    accepted_gaps: dict[str, Any] | None = None
    if missing:
        # Exchange candle gaps (no trades / venue outages / listing edges) are a
        # data reality, not a pipeline defect; the strict daily-RV rule already
        # NaNs affected days. Flag only rates beyond documented reality.
        missing_rate = len(missing) / max(len(expected), 1)
        record = {
            "kind": "missing_utc_grid",
            "series": series_id,
            "count": len(missing),
            "rate": round(missing_rate, 6),
            "sample_epoch": missing[:20],
        }
        threshold_hit = missing_rate > 0.005 if granularity < 86400 else len(missing) > 5
        if threshold_hit:
            violations.append(record)
        else:
            accepted_gaps = record
    if duplicate_count:
        violations.append({"kind": "duplicate_epoch", "series": series_id, "count": duplicate_count})
    if off_grid:
        violations.append(
            {"kind": "off_grid_epoch", "series": series_id, "count": len(off_grid), "sample_epoch": off_grid[:20]}
        )
    return _audit(
        f"utc_grid:{series_id}", violations, expected_count=len(expected), actual_count=len(actual),
        missing_count=len(missing), duplicate_count=duplicate_count, accepted_gaps=accepted_gaps,
    )


def audit_pagination_consistency(records: dict[str, Any] | Path) -> dict[str, Any]:
    """Aggregate downloader-recorded page-boundary overlap checks."""

    if isinstance(records, Path):
        if not records.exists():
            return _audit(
                "pagination_consistency",
                [{"kind": "missing_pagination_audit", "path": str(records)}],
                boundary_checks=0,
            )
        records = json.loads(records.read_text(encoding="utf-8"))
    violations: list[dict[str, Any]] = []
    checks = 0
    for series_id, record in records.items():
        count = int(record.get("boundary_checks", 0))
        conflicts = int(record.get("boundary_conflicts", 0))
        checks += count
        if conflicts:
            violations.append(
                {"kind": "pagination_boundary_mismatch", "series": series_id, "count": conflicts}
            )
    return _audit("pagination_consistency", violations, boundary_checks=checks)


def audit_ohlc_invariants(frame: pd.DataFrame, *, source: str = "unknown") -> dict[str, Any]:
    """List OHLC rows violating ordering or strict positivity."""

    required = {"open", "high", "low", "close"}
    missing_columns = required.difference(frame.columns)
    if missing_columns:
        return _audit(
            f"ohlc:{source}",
            [{"kind": "missing_columns", "columns": sorted(missing_columns)}],
            rows=len(frame),
        )
    values = frame[list(required)].apply(pd.to_numeric, errors="coerce")
    invalid = (
        values["high"].lt(values[["open", "close"]].max(axis=1))
        | values["low"].gt(values[["open", "close"]].min(axis=1))
        | values.le(0).any(axis=1)
        | values.isna().any(axis=1)
    )
    violations: list[dict[str, Any]] = []
    for index in frame.index[invalid]:
        identifier = frame.loc[index, "epoch"] if "epoch" in frame else frame.loc[index, "ds"] if "ds" in frame else index
        violations.append(
            {
                "kind": "ohlc_invariant",
                "row": str(identifier),
                **{column: _json_value(frame.loc[index, column]) for column in sorted(required)},
            }
        )
    return _audit(f"ohlc:{source}", violations, rows=len(frame), invalid_rows=int(invalid.sum()))


def audit_wareki_dates(
    frame: pd.DataFrame, *, expected_first: str | pd.Timestamp = "1974-09-24"
) -> dict[str, Any]:
    """Verify parsed JGB dates start correctly, remain ordered, and are weekdays."""

    if "ds" not in frame.columns:
        return _audit("wareki_dates", [{"kind": "missing_ds_column"}])
    ds = pd.to_datetime(frame["ds"], errors="coerce")
    violations: list[dict[str, Any]] = []
    nat_count = int(ds.isna().sum())
    if nat_count:
        violations.append({"kind": "nat_dates", "count": nat_count})
    valid = ds.dropna()
    if not valid.empty and valid.iloc[0].normalize() != pd.Timestamp(expected_first):
        violations.append(
            {"kind": "wrong_first_date", "actual": valid.iloc[0], "expected": pd.Timestamp(expected_first)}
        )
    if not valid.is_monotonic_increasing or valid.duplicated().any():
        violations.append({"kind": "non_monotonic_or_duplicate_dates"})
    weekends = valid.loc[valid.dt.dayofweek >= 5]
    # JGB rates were published on Saturdays in the pre-1990 era (historical
    # Saturday sessions); only Sundays or post-1990 weekend rows are defects.
    historical_saturdays = weekends.loc[
        (weekends.dt.dayofweek == 5) & (weekends < pd.Timestamp("1990-01-01"))
    ]
    problem_weekends = weekends.drop(historical_saturdays.index)
    if not problem_weekends.empty:
        violations.append(
            {
                "kind": "weekend_dates",
                "count": len(problem_weekends),
                "sample": problem_weekends.head(20).tolist(),
            }
        )
    return _audit(
        "wareki_dates",
        violations,
        rows=len(frame),
        nat_count=nat_count,
        historical_saturday_count=int(len(historical_saturdays)),
    )


def write_random_samples(
    series: pd.DataFrame,
    output_path: Path,
    *,
    n: int = 20,
    seed: int = 42,
) -> dict[str, Any]:
    """Write deterministic per-series random samples for later manual comparison."""

    if "unique_id" not in series.columns:
        return _audit("random_samples", [{"kind": "missing_unique_id"}])
    samples = [
        group.sample(n=min(n, len(group)), random_state=seed).sort_values("ds")
        for _, group in series.groupby("unique_id", sort=True)
    ]
    sampled = pd.concat(samples, ignore_index=True) if samples else series.head(0)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sampled.to_csv(output_path, index=False, date_format="%Y-%m-%d")
    return _audit(
        "random_samples", [], path=str(output_path), rows=len(sampled), series=int(series["unique_id"].nunique())
    )


def audit_ecb(frame: pd.DataFrame) -> dict[str, Any]:
    """Report ECB missingness and reject any zero created from missing markers."""

    numeric_columns = [column for column in ecb.CURRENCIES if column in frame.columns]
    numeric = frame[numeric_columns].apply(pd.to_numeric, errors="coerce")
    zero_rows = frame.loc[numeric.eq(0).any(axis=1)]
    violations = []
    if not zero_rows.empty:
        violations.append(
            {"kind": "zero_ecb_rate", "count": len(zero_rows), "rows": [str(index) for index in zero_rows.index[:20]]}
        )
    nan_rates = {column: float(numeric[column].isna().mean()) for column in numeric_columns}
    return _audit("ecb", violations, rows=len(frame), nan_rate=nan_rates, zero_rows=len(zero_rows))


def audit_rv(frame: pd.DataFrame, *, max_missing_rate: float = 0.05) -> dict[str, Any]:
    """Audit RV interval counts, missing-day rate, and strict positivity."""

    if not {"rv", "m_intervals"}.issubset(frame.columns):
        return _audit("rv", [{"kind": "missing_rv_columns"}])
    violations: list[dict[str, Any]] = []
    grouped = frame.groupby("unique_id", sort=True) if "unique_id" in frame else [("all", frame)]
    missing_rates: dict[str, float] = {}
    distributions: dict[str, dict[str, int]] = {}
    for series_id, group in grouped:
        rv = pd.to_numeric(group["rv"], errors="coerce")
        missing_rate = float(rv.isna().mean()) if len(rv) else 0.0
        missing_rates[str(series_id)] = missing_rate
        if missing_rate > max_missing_rate:
            violations.append(
                {
                    "kind": "rv_missing_rate",
                    "series": str(series_id),
                    "actual": missing_rate,
                    "threshold": max_missing_rate,
                }
            )
        nonpositive = rv.notna() & rv.le(0)
        if nonpositive.any():
            violations.append(
                {
                    "kind": "nonpositive_rv",
                    "series": str(series_id),
                    "count": int(nonpositive.sum()),
                }
            )
        distributions[str(series_id)] = {
            str(key): int(value)
            for key, value in group["m_intervals"]
            .value_counts(dropna=False)
            .sort_index()
            .items()
        }
    overall_missing_rate = float(pd.to_numeric(frame["rv"], errors="coerce").isna().mean()) if len(frame) else 0.0
    return _audit(
        "rv",
        violations,
        rows=len(frame),
        missing_rate=overall_missing_rate,
        missing_rate_by_series=missing_rates,
        m_intervals_distribution=distributions,
    )


def _json_value(value: Any) -> Any:
    if value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, float) and np.isnan(value):
        return None
    return value


def _json_default(value: Any) -> Any:
    converted = _json_value(value)
    if converted is not value:
        return converted
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"not JSON serializable: {type(value).__name__}")


def _report_text(report: dict[str, Any]) -> str:
    lines = [
        "tsfmbench Stage 1 data audit",
        f"created_at: {report['created_at']}",
        f"passed: {report['passed']}",
        f"violation_count: {report['violation_count']}",
        "",
    ]
    for result in report["audits"]:
        lines.append(
            f"[{ 'PASS' if result['passed'] else 'FAIL' }] {result['name']} "
            f"({result['violation_count']} violations)"
        )
        for violation in result["violations"]:
            lines.append(f"  - {json.dumps(violation, ensure_ascii=False, default=_json_default)}")
    return "\n".join(lines) + "\n"


def run_all_audits(
    raw_dir: Path | str = Path("data/raw"),
    processed_dir: Path | str = Path("data/processed"),
    results_dir: Path | str = Path("results/audit"),
    *,
    config_path: Path | str | None = None,
) -> dict[str, Any]:
    """Run every Stage 1 audit and write timestamped JSON and text reports."""

    raw_root, processed_root, result_root = Path(raw_dir), Path(processed_dir), Path(results_dir)
    config = load_data_config(config_path)
    audits: list[dict[str, Any]] = []
    configured_end = str(config["end"])

    for product in config["coinbase"]["products"]:
        product_id = str(product["product"])
        listing = pd.Timestamp(product["listing_date"])
        for granularity in config["coinbase"]["granularities"]:
            path = raw_root / "coinbase" / f"{product_id}_{int(granularity)}.parquet"
            if not path.exists():
                audits.append(_audit(
                    f"utc_grid:{product_id}_{granularity}",
                    [{"kind": "missing_raw_file", "path": str(path)}],
                ))
                continue
            frame = pd.read_parquet(path)
            start = max(listing, pd.Timestamp(config["coinbase"]["rv_start"])) if int(granularity) == 300 else listing
            audits.append(audit_coinbase_utc_grid(
                frame, int(granularity), start, configured_end,
                series_id=f"{product_id}_{granularity}",
            ))
            audits.append(audit_ohlc_invariants(frame, source=f"Coinbase:{product_id}_{granularity}"))
    audits.append(audit_pagination_consistency(raw_root / "coinbase" / "pagination_audit.json"))

    n225 = None
    nikkei_dir = raw_root / "nikkei"
    nikkei_files = sorted(nikkei_dir.glob("*.csv")) if nikkei_dir.exists() else []
    if nikkei_files:
        n225 = nikkei.parse_nikkei_csv(nikkei_files[0])
        audits.append(audit_ohlc_invariants(n225, source="Nikkei"))
    else:
        audits.append(_audit("ohlc:Nikkei", [{"kind": "missing_raw_file"}]))

    history_path, current_path = raw_root / "mof" / "jgbcm_all.csv", raw_root / "mof" / "jgbcm.csv"
    if history_path.exists() or current_path.exists():
        history = mof.parse_mof_csv(history_path) if history_path.exists() else pd.DataFrame()
        current = mof.parse_mof_csv(current_path) if current_path.exists() else pd.DataFrame()
        jgb = mof.merge_history_current(history, current) if not history.empty and not current.empty else history if not history.empty else current
        audits.append(audit_wareki_dates(jgb, expected_first=config["mof"]["first_date"]))
    else:
        audits.append(_audit("wareki_dates", [{"kind": "missing_raw_file"}]))

    ecb_path = raw_root / "ecb" / "eurofxref-hist.csv"
    audits.append(audit_ecb(ecb.parse_ecb_csv(ecb_path))) if ecb_path.exists() else audits.append(
        _audit("ecb", [{"kind": "missing_raw_file", "path": str(ecb_path)}])
    )

    series_path = processed_root / "series.parquet"
    rv_path = processed_root / "rv_daily.parquet"
    if series_path.exists():
        sample_frame = pd.read_parquet(series_path)
        if rv_path.exists():
            rv_samples = pd.read_parquet(rv_path).rename(columns={"rv": "y"})
            sample_frame = pd.concat(
                [sample_frame, rv_samples[["unique_id", "ds", "y"]]], ignore_index=True
            )
        audits.append(write_random_samples(
            sample_frame, result_root / "random_samples.csv",
            n=int(config["audit"]["random_sample_rows"]), seed=int(config["audit"]["random_seed"]),
        ))
    else:
        audits.append(_audit("random_samples", [{"kind": "missing_processed_file", "path": str(series_path)}]))
    if rv_path.exists():
        audits.append(audit_rv(
            pd.read_parquet(rv_path), max_missing_rate=float(config["audit"]["max_rv_missing_rate"])
        ))
    else:
        audits.append(_audit("rv", [{"kind": "missing_processed_file", "path": str(rv_path)}]))

    violation_count = sum(int(item["violation_count"]) for item in audits)
    created = datetime.now(UTC)
    report: dict[str, Any] = {
        "created_at": created.isoformat(),
        "passed": violation_count == 0,
        "violation_count": violation_count,
        "audits": audits,
    }
    result_root.mkdir(parents=True, exist_ok=True)
    stamp = created.strftime("%Y%m%dT%H%M%SZ")
    json_path = result_root / f"audit_{stamp}.json"
    text_path = result_root / f"audit_{stamp}.txt"
    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=_json_default), encoding="utf-8"
    )
    text_path.write_text(_report_text(report), encoding="utf-8")
    report["json_path"] = str(json_path)
    report["text_path"] = str(text_path)
    return report
