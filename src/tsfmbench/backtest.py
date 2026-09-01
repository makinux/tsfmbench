"""Leakage-safe origin scheduling, forecast persistence, and task execution."""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, is_dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from tsfmbench.adapters.base import (
    Adapter,
    TaskContext,
    validate_forecasts,
)
from tsfmbench.tasks import load_task_config

FORECAST_COLUMNS = (
    "run_id", "task", "model_variant", "unique_id", "origin", "h", "ds_target",
    "config_hash", "data_hash", "yhat_mean", "yhat_median",
    "q10", "q20", "q30", "q40", "q50", "q60", "q70", "q80", "q90",
    "runtime_s", "fail", "fail_reason",
)
UNIQUE_KEY = (
    "run_id", "task", "model_variant", "unique_id", "origin", "h", "ds_target",
    "config_hash", "data_hash",
)
KEY_COLUMNS = UNIQUE_KEY
DEFAULT_FORECAST_DIR = Path("results/forecasts")
FORECAST_ORIGIN_CHUNK = 256


def _timestamp(value: Any) -> pd.Timestamp:
    result = pd.Timestamp(value)
    if result.tzinfo is not None:
        result = result.tz_convert(None)
    return result.normalize()


def slice_asof(panel: pd.DataFrame, origin: Any) -> pd.DataFrame:
    """Return the sole legal adapter input: rows whose ``ds <= origin``."""

    if "ds" not in panel:
        raise ValueError("as-of slicing requires a ds column")
    timestamp = _timestamp(origin)
    dates = pd.to_datetime(panel["ds"], errors="coerce")
    if getattr(dates.dt, "tz", None) is not None:
        dates = dates.dt.tz_localize(None)
    work = panel.copy()
    # Positional assignment also handles concatenated frames with duplicate
    # index labels; as-of semantics must never depend on caller index hygiene.
    work["ds"] = dates.to_numpy()
    result = work.loc[work["ds"] <= timestamp].copy()
    sort = [column for column in ("unique_id", "ds") if column in result]
    return result.sort_values(sort).reset_index(drop=True) if sort else result.reset_index(drop=True)


@dataclass
class OriginSchedule:
    """Generate per-series native-calendar forecast cells for one task."""

    task_config: Mapping[str, Any]

    def __post_init__(self) -> None:
        self.task_config = load_task_config(self.task_config)

    def generate(self, panel: pd.DataFrame, window: str = "main") -> pd.DataFrame:
        if window not in self.task_config["windows"]:
            raise ValueError(f"unknown window {window!r}")
        bounds = self.task_config["windows"][window]
        configured_start = _timestamp(bounds["start"]) if bounds.get("start") else None
        end = _timestamp(bounds["end"]) if bounds.get("end") else None
        rows: list[dict[str, Any]] = []
        for uid in self.task_config["series"]:
            group = panel.loc[panel["unique_id"].astype(str) == str(uid)].copy()
            if group.empty:
                continue
            value = "y" if "y" in group else "rv"
            group["ds"] = pd.to_datetime(group["ds"]).dt.tz_localize(None)
            group = group.loc[group[value].notna()].sort_values("ds").drop_duplicates("ds")
            dates = pd.DatetimeIndex(group["ds"])
            start = configured_start if configured_start is not None else dates.min()
            for detail in self.task_config["horizons"]:
                h = int(detail["h"])
                step = int(detail.get("step", h))
                candidates: list[tuple[int, pd.Timestamp]] = []
                for index, origin in enumerate(dates):
                    if origin < start or (end is not None and origin > end):
                        continue
                    target_index = index + h
                    if target_index >= len(dates):
                        continue
                    ds_target = dates[target_index]
                    if end is not None and ds_target > end:
                        continue
                    candidates.append((index, origin))
                # Step on each series' native observed calendar, not weekdays
                # synthesized by pandas and not another series' dates.
                for index, origin in candidates[::step]:
                    rows.append(
                        {
                            "unique_id": str(uid), "origin": origin, "h": h,
                            "ds_target": dates[index + h],
                            "target": str(detail.get("target", "direct")),
                            "probabilistic": bool(detail.get("probabilistic", True)),
                            "quantiles_written_not_evaluated": bool(
                                detail.get("quantiles_written_not_evaluated", False)
                            ),
                        }
                    )
        columns = [
            "unique_id", "origin", "h", "ds_target", "target", "probabilistic",
            "quantiles_written_not_evaluated",
        ]
        return pd.DataFrame(rows, columns=columns).sort_values(
            ["origin", "unique_id", "h"]
        ).reset_index(drop=True)

    build = generate

    def origins(self, panel: pd.DataFrame, window: str = "main") -> pd.DatetimeIndex:
        frame = self.generate(panel, window)
        return pd.DatetimeIndex(frame["origin"].drop_duplicates())


def _json_default(value: Any) -> Any:
    if isinstance(value, (Path, pd.Timestamp, datetime)):
        return str(value)
    if isinstance(value, np.generic):
        return value.item()
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, set | tuple):
        return list(value)
    return repr(value)


def sha12(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=_json_default)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def config_hash(task_config: Mapping[str, Any], model_config: Mapping[str, Any] | None = None) -> str:
    """Hash a fully resolved task plus model configuration."""

    resolved_task = dict(task_config)
    resolved_task.pop("_source", None)
    return sha12({"task": resolved_task, "model": dict(model_config or {})})


def data_hash(panel: pd.DataFrame) -> str:
    """Hash per-series identity/range/count and canonical float64 values."""

    value = "y" if "y" in panel else "rv" if "rv" in panel else None
    if value is None:
        raise ValueError("data hash requires y or rv")
    records = []
    for uid, group in panel.groupby("unique_id", sort=True):
        ordered = group.sort_values("ds")
        values = pd.to_numeric(ordered[value], errors="coerce").to_numpy(dtype="<f8")
        digest = hashlib.sha256(values.tobytes(order="C")).hexdigest()
        records.append(
            {
                "unique_id": str(uid),
                "first_ds": str(pd.Timestamp(ordered["ds"].iloc[0])) if len(ordered) else None,
                "last_ds": str(pd.Timestamp(ordered["ds"].iloc[-1])) if len(ordered) else None,
                "n_obs": int(np.isfinite(values).sum()),
                "y_sha256": digest,
            }
        )
    payload = json.dumps(records, sort_keys=True, separators=(",", ":"), default=_json_default)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _safe(value: Any) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value))


def _atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{uuid.uuid4().hex}")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, default=_json_default)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


class ForecastStore:
    """Atomic parquet batches plus exact-key resumability and manifests."""

    def __init__(
        self,
        root: Path | str = DEFAULT_FORECAST_DIR,
        run_id: str | None = None,
        task: str | None = None,
    ) -> None:
        self.root = Path(root)
        self.run_id = run_id
        self.task = task

    @property
    def manifest_path(self) -> Path:
        if not self.run_id:
            raise ValueError("run_id is required for a manifest")
        return self.root / f"manifest_{self.run_id}.json"

    @property
    def model_config_path(self) -> Path:
        if not self.run_id:
            raise ValueError("run_id is required for a model-config sidecar")
        return self.root / f"model_config_{self.run_id}.json"

    def _batch_path(self, model_variant: str, origin: Any, task: str | None = None) -> Path:
        task_name = task or self.task
        if not task_name or not self.run_id:
            raise ValueError("task and run_id are required for batch paths")
        stamp = _timestamp(origin).strftime("%Y%m%d")
        return self.root / _safe(task_name) / _safe(self.run_id) / _safe(model_variant) / f"origin_{stamp}.parquet"

    def _chunk_path(
        self,
        model_variant: str,
        first_origin: Any,
        last_origin: Any,
        origin_token: str,
        task: str | None = None,
    ) -> Path:
        task_name = task or self.task
        if not task_name or not self.run_id:
            raise ValueError("task and run_id are required for chunk paths")
        first = _timestamp(first_origin).strftime("%Y%m%d")
        last = _timestamp(last_origin).strftime("%Y%m%d")
        return (
            self.root
            / _safe(task_name)
            / _safe(self.run_id)
            / _safe(model_variant)
            / f"chunk_{first}_{last}_{_safe(origin_token)}.parquet"
        )

    def parquet_paths(self) -> list[Path]:
        base = self.root
        if self.task and self.run_id:
            base = base / _safe(self.task) / _safe(self.run_id)
        return sorted(path for path in base.rglob("*.parquet") if ".tmp-" not in path.name) if base.exists() else []

    def read(
        self, *, detect_collisions: bool = True, columns: Sequence[str] | None = None
    ) -> pd.DataFrame:
        paths = self.parquet_paths()
        selected = list(columns) if columns is not None else list(FORECAST_COLUMNS)
        if not paths:
            return pd.DataFrame(columns=selected)
        result = pd.concat(
            [pd.read_parquet(path, columns=selected) for path in paths], ignore_index=True
        )
        for column in ("origin", "ds_target"):
            if column in result:
                result[column] = pd.to_datetime(result[column])
        if (
            detect_collisions
            and set(UNIQUE_KEY).issubset(result.columns)
            and result.duplicated(list(UNIQUE_KEY), keep=False).any()
        ):
            duplicates = result.loc[result.duplicated(list(UNIQUE_KEY), keep=False), list(UNIQUE_KEY)]
            raise ValueError(f"forecast unique-key collision: {duplicates.iloc[0].to_dict()}")
        return result.reindex(columns=selected)

    load = read

    def existing_keys(self) -> set[tuple[Any, ...]]:
        # Load the exact resume key once per run, without decoding forecast
        # payload columns.  Both legacy origin files and new chunk files use
        # the same immutable key schema.
        frame = self.read(columns=UNIQUE_KEY)
        return set(frame.loc[:, UNIQUE_KEY].itertuples(index=False, name=None))

    def write_batch(
        self,
        frame: pd.DataFrame,
        *,
        model_variant: str | None = None,
        origin: Any | None = None,
    ) -> Path:
        """Atomically replace one ``(model_variant, origin)`` parquet batch."""

        missing = set(FORECAST_COLUMNS).difference(frame.columns)
        if missing:
            raise ValueError(f"forecast batch missing columns: {sorted(missing)}")
        output = frame.loc[:, FORECAST_COLUMNS].copy()
        if output.duplicated(list(UNIQUE_KEY)).any():
            raise ValueError("forecast unique-key collision within batch")
        variants = output["model_variant"].astype(str).unique()
        origins = pd.to_datetime(output["origin"]).unique()
        if len(variants) != 1 or len(origins) != 1:
            raise ValueError("write unit must contain one model_variant and one origin")
        variant = model_variant or variants[0]
        batch_origin = _timestamp(origin if origin is not None else origins[0])
        task = str(output["task"].iloc[0])
        frame_run = str(output["run_id"].iloc[0])
        if str(variant) != str(variants[0]) or batch_origin != _timestamp(origins[0]):
            raise ValueError("batch path labels do not match forecast row labels")
        if self.run_id is not None and self.run_id != frame_run:
            raise ValueError("forecast run_id does not match store run_id")
        if self.task is not None and self.task != task:
            raise ValueError("forecast task does not match store task")
        self.run_id = self.run_id or frame_run
        self.task = self.task or task
        path = self._batch_path(variant, batch_origin, task)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.stem}.tmp-{uuid.uuid4().hex}.parquet")
        output.to_parquet(temporary, index=False)
        os.replace(temporary, path)
        return path

    write = write_batch

    @staticmethod
    def _atomic_parquet(path: Path, frame: pd.DataFrame) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.stem}.tmp-{uuid.uuid4().hex}.parquet")
        frame.to_parquet(temporary, index=False)
        os.replace(temporary, path)

    def write_chunk(self, frame: pd.DataFrame) -> Path:
        """Atomically persist one model and many complete origin batches.

        Existing files that contain one of the replacement origins are first
        atomically rewritten without those origins.  Therefore a killed
        upsert can leave work missing (which exact-key resume recomputes), but
        can never leave colliding old/new keys.  Legacy ``origin_*.parquet``
        files remain readable and are handled by the same upsert path.
        """

        missing = set(FORECAST_COLUMNS).difference(frame.columns)
        if missing:
            raise ValueError(f"forecast chunk missing columns: {sorted(missing)}")
        output = frame.loc[:, FORECAST_COLUMNS].copy()
        if output.empty:
            raise ValueError("forecast chunk cannot be empty")
        if output.duplicated(list(UNIQUE_KEY)).any():
            raise ValueError("forecast unique-key collision within chunk")
        variants = output["model_variant"].astype(str).unique()
        tasks = output["task"].astype(str).unique()
        runs = output["run_id"].astype(str).unique()
        if len(variants) != 1 or len(tasks) != 1 or len(runs) != 1:
            raise ValueError("write chunk must contain one model_variant, task, and run_id")
        variant, task, frame_run = str(variants[0]), str(tasks[0]), str(runs[0])
        if self.run_id is not None and self.run_id != frame_run:
            raise ValueError("forecast run_id does not match store run_id")
        if self.task is not None and self.task != task:
            raise ValueError("forecast task does not match store task")
        self.run_id = self.run_id or frame_run
        self.task = self.task or task
        normalized_origins = pd.DatetimeIndex(pd.to_datetime(output["origin"])).normalize()
        origins = set(normalized_origins)
        output["origin"] = normalized_origins

        model_dir = self.root / _safe(task) / _safe(frame_run) / _safe(variant)
        if model_dir.exists():
            for old_path in sorted(model_dir.glob("*.parquet")):
                if ".tmp-" in old_path.name:
                    continue
                old = pd.read_parquet(old_path)
                old_origins = pd.DatetimeIndex(pd.to_datetime(old["origin"])).normalize()
                overlap = np.fromiter((origin in origins for origin in old_origins), dtype=bool)
                if not overlap.any():
                    continue
                remaining = old.loc[~overlap].copy()
                if remaining.empty:
                    old_path.unlink()
                else:
                    self._atomic_parquet(old_path, remaining.loc[:, FORECAST_COLUMNS])

        first, last = normalized_origins.min(), normalized_origins.max()
        origin_token = sha12([int(origin.value) for origin in sorted(origins)])
        path = self._chunk_path(variant, first, last, origin_token, task)
        self._atomic_parquet(path, output)
        return path

    def write_manifest(self, expected: Mapping[Any, int], **metadata: Any) -> Path:
        normalized: dict[str, int] = {}
        entry_tasks: dict[str, str | None] = {}
        for key, value in expected.items():
            if isinstance(key, tuple) and len(key) == 2:
                entry_task, model = str(key[0]), str(key[1])
            else:
                entry_task, model = self.task, str(key)
            normalized[model] = int(value)
            entry_tasks[model] = entry_task
        entries = [
            {"task": entry_tasks[model], "model_variant": model, "expected_rows": count}
            for model, count in sorted(normalized.items())
        ]
        payload = {
            "run_id": self.run_id,
            "task": self.task,
            "expected_rows": normalized,
            "entries": entries,
            "created_at": datetime.now(UTC).isoformat(),
            **metadata,
        }
        if self.manifest_path.exists():
            previous = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            if previous.get("expected_rows") != payload["expected_rows"]:
                raise ValueError("resume manifest does not match expected row counts")
            return self.manifest_path
        _atomic_json(self.manifest_path, payload)
        return self.manifest_path

    def validate_manifest(self) -> None:
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        expected = {str(key): int(value) for key, value in manifest["expected_rows"].items()}
        frame = self.read()
        actual = frame.groupby("model_variant").size().to_dict() if not frame.empty else {}
        actual = {str(key): int(value) for key, value in actual.items()}
        if expected != actual:
            raise RuntimeError(f"forecast manifest mismatch: expected={expected}, actual={actual}")

    validate_complete = validate_manifest

    def write_model_config(self, payload: Mapping[str, Any]) -> Path:
        _atomic_json(self.model_config_path, payload)
        return self.model_config_path

    key_columns = UNIQUE_KEY
    columns = FORECAST_COLUMNS


def _adapter_settings(adapter: Adapter) -> dict[str, Any]:
    settings: dict[str, Any] = {
        "class": type(adapter).__name__,
        "name": adapter.name,
        "requires_fit": bool(adapter.requires_fit),
        "reference": bool(getattr(adapter, "reference", False)),
    }
    for key, value in vars(adapter).items():
        if key.startswith("_") or key == "forecaster":
            continue
        if isinstance(value, (str, int, float, bool, type(None), list, tuple, dict)):
            settings[key] = value
    return settings


def default_adapters(task: str) -> list[Adapter]:
    """Instantiate the preregistered model set for a task."""

    from tsfmbench.adapters.dvol import DVOLRegression
    from tsfmbench.adapters.ewma import EWMA
    from tsfmbench.adapters.garch import GARCH, GJRGARCH
    from tsfmbench.adapters.har import HARRV
    from tsfmbench.adapters.ml import LightGBMGlobal
    from tsfmbench.adapters.naive import NaivePrev, RandomWalk, SeasonalMedian4, SeasonalNaive7
    from tsfmbench.adapters.prophet_ import Prophet
    from tsfmbench.adapters.stats import AutoETSAdapter, AutoThetaAdapter
    from tsfmbench.adapters.timesfm3 import TimesFM3

    if task == "price":
        return [RandomWalk(), AutoETSAdapter(), AutoThetaAdapter(), LightGBMGlobal(), TimesFM3("raw"), TimesFM3("log")]
    if task == "rv":
        return [
            NaivePrev(), EWMA(), GARCH(), GJRGARCH(), HARRV(), DVOLRegression(),
            LightGBMGlobal(), TimesFM3("raw"), TimesFM3("log"),
        ]
    if task == "volume":
        return [
            SeasonalNaive7(), SeasonalMedian4(), AutoETSAdapter(), AutoThetaAdapter(),
            LightGBMGlobal(), Prophet(), TimesFM3("raw"), TimesFM3("log"),
        ]
    raise ValueError(f"unknown task {task!r}")


def resolve_adapters(task: str, models: Sequence[str | Adapter] | str | None) -> list[Adapter]:
    available = default_adapters(task)
    if models is None:
        return available
    requested: Sequence[str | Adapter] = models.split(",") if isinstance(models, str) else models
    lookup: dict[str, Adapter] = {}
    for adapter in available:
        for alias in {adapter.name, type(adapter).__name__}:
            lookup[alias.lower()] = adapter
    resolved = []
    for item in requested:
        if not isinstance(item, str):
            resolved.append(item)
            continue
        key = item.strip().lower()
        if key not in lookup:
            raise ValueError(f"unknown model {item!r} for task {task}")
        resolved.append(lookup[key])
    names = [adapter.name for adapter in resolved]
    if len(names) != len(set(names)):
        raise ValueError("model variants must be unique")
    return resolved


def _load_panel(
    config: Mapping[str, Any], processed_dir: Path
) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    path = processed_dir / f"{config['panel']}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"processed panel not found: {path}; run `tsfmbench build` first")
    full = pd.read_parquet(path)
    value = str(config.get("value_column", "y"))
    panel = full.loc[full["unique_id"].astype(str).isin(config["series"]), ["unique_id", "ds", value]].copy()
    panel = panel.rename(columns={value: "y"})
    panel["ds"] = pd.to_datetime(panel["ds"]).dt.tz_localize(None)
    panel["y"] = pd.to_numeric(panel["y"], errors="coerce").astype("float64")
    panel = panel.dropna(subset=["ds", "y"]).sort_values(["unique_id", "ds"]).reset_index(drop=True)
    source_digest = data_hash(panel)
    if config.get("transform") == "log1p":
        panel["y"] = np.log1p(panel["y"])
        config["_panel_transformed"] = True
    return panel, full, source_digest


def _load_returns(raw_dir: Path) -> pd.DataFrame:
    rows = []
    coinbase = raw_dir / "coinbase"
    if coinbase.exists():
        for path in coinbase.glob("*_86400.parquet"):
            frame = pd.read_parquet(path)
            if not {"open", "close"}.issubset(frame):
                continue
            if "ds" in frame:
                ds = pd.to_datetime(frame["ds"], utc=True).dt.tz_localize(None)
            elif "epoch" in frame:
                ds = pd.to_datetime(frame["epoch"], unit="s", utc=True).dt.tz_localize(None)
            else:
                continue
            asset = path.stem.removesuffix("_86400")
            rows.append(
                pd.DataFrame(
                    {
                        "unique_id": asset,
                        "ds": ds.dt.normalize(),
                        "return": np.log(pd.to_numeric(frame["close"]) / pd.to_numeric(frame["open"])),
                    }
                )
            )
    nikkei_dir = raw_dir / "nikkei"
    if nikkei_dir.exists():
        from tsfmbench.data.sources.nikkei import parse_nikkei_csv

        paths = sorted([*nikkei_dir.glob("*.csv"), *nikkei_dir.glob("*.parquet")])
        if paths:
            frame = pd.read_parquet(paths[0]) if paths[0].suffix == ".parquet" else parse_nikkei_csv(paths[0])
            if {"open", "close"}.issubset(frame):
                rows.append(
                    pd.DataFrame(
                        {
                            "unique_id": "N225", "ds": pd.to_datetime(frame["ds"]),
                            "return": np.log(pd.to_numeric(frame["close"]) / pd.to_numeric(frame["open"])),
                        }
                    )
                )
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=["unique_id", "ds", "return"])


def _group_asof_source(frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Normalize an auxiliary/panel frame once for cheap repeated as-of slices."""

    if frame.empty or "unique_id" not in frame or "ds" not in frame:
        return {}
    work = frame.copy()
    work["ds"] = pd.to_datetime(work["ds"]).dt.tz_localize(None)
    return {
        str(uid): group.sort_values("ds").reset_index(drop=True)
        for uid, group in work.groupby(work["unique_id"].astype(str), sort=False)
    }


def _grouped_asof(
    groups: Mapping[str, pd.DataFrame], origin: Any, unique_ids: Sequence[str]
) -> pd.DataFrame:
    timestamp = _timestamp(origin)
    parts = []
    for uid in unique_ids:
        group = groups.get(str(uid))
        if group is None:
            continue
        stop = int(pd.DatetimeIndex(group["ds"]).searchsorted(timestamp, side="right"))
        if stop:
            parts.append(group.iloc[:stop])
    if not parts:
        sample = next(iter(groups.values()), pd.DataFrame())
        return sample.head(0).copy()
    return pd.concat(parts, ignore_index=True, copy=False)


def _rv_return_ids(unique_ids: Sequence[str]) -> list[str]:
    result: list[str] = []
    for uid in unique_ids:
        value = str(uid)
        result.append(value)
        result.append("N225" if value == "RV_N225_GK" else value.removeprefix("RV_") + "-USD")
    return list(dict.fromkeys(result))


def _key_tuples(frame: pd.DataFrame) -> set[tuple[Any, ...]]:
    normalized = frame.loc[:, UNIQUE_KEY].copy()
    normalized["origin"] = pd.to_datetime(normalized["origin"])
    normalized["ds_target"] = pd.to_datetime(normalized["ds_target"])
    return set(normalized.itertuples(index=False, name=None))


def run_task(
    task: str | Mapping[str, Any],
    window: str = "main",
    models: Sequence[str | Adapter] | str | None = None,
    dry_run: bool = False,
    *,
    estimation: str = "rolling",
    processed_dir: Path | str = Path("data/processed"),
    raw_dir: Path | str = Path("data/raw"),
    results_dir: Path | str = DEFAULT_FORECAST_DIR,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Run one declarative task over an origin window, atomically by batch."""

    if estimation not in {"rolling", "expanding"}:
        raise ValueError("estimation must be rolling or expanding")
    config = load_task_config(task)
    task_id = str(config["task"])
    adapters = resolve_adapters(task_id, models)
    panel, complete_series, digest = _load_panel(config, Path(processed_dir))
    schedule = OriginSchedule(config).generate(panel, window)
    model_hashes = {
        adapter.name: config_hash(config, {**_adapter_settings(adapter), "estimation": estimation})
        for adapter in adapters
    }
    if run_id is None:
        run_id = f"{task_id}-{window}-{sha12({'models': model_hashes, 'data': digest})}"

    model_schedules: dict[str, pd.DataFrame] = {}
    for adapter in adapters:
        applicable = schedule
        supports = getattr(adapter, "supports", None)
        if callable(supports):
            applicable = schedule.loc[schedule["unique_id"].map(supports)]
        model_schedules[adapter.name] = applicable.reset_index(drop=True)
    expected = {name: len(value) for name, value in model_schedules.items()}
    if dry_run:
        return {
            "run_id": run_id, "task": task_id, "window": window,
            "expected_rows": expected, "total_rows": int(sum(expected.values())),
        }

    store = ForecastStore(results_dir, run_id=run_id, task=task_id)
    store.write_manifest(
        expected,
        window=window,
        estimation=estimation,
        config_hashes=model_hashes,
        data_hash=digest,
    )
    existing = store.existing_keys()
    needed_auxiliary = {
        name for adapter in adapters for name in getattr(adapter, "auxiliary_names", ())
    }
    returns = (
        _load_returns(Path(raw_dir))
        if task_id == "rv" and "returns" in needed_auxiliary
        else pd.DataFrame()
    )
    series_path = Path(processed_dir) / "series.parquet"
    auxiliary_series = (
        pd.read_parquet(series_path)
        if series_path.exists() and {"series", "dvol"}.intersection(needed_auxiliary)
        else complete_series.head(0)
    )
    dvol = auxiliary_series.loc[
        auxiliary_series["unique_id"].astype(str).str.startswith("DVOL_")
    ].copy() if not auxiliary_series.empty else auxiliary_series
    panel_groups = _group_asof_source(panel)
    return_groups = _group_asof_source(returns)
    dvol_groups = _group_asof_source(dvol)
    auxiliary_series_groups = _group_asof_source(auxiliary_series)
    base_contexts = {
        adapter.name: TaskContext(
            config=config,
            target_frame=model_schedules[adapter.name],
            auxiliary={},
            estimation=estimation,
            window=window,
            run_id=run_id,
            config_hash=model_hashes[adapter.name],
            data_hash=digest,
        )
        for adapter in adapters
    }

    def origin_request(adapter: Adapter, origin: pd.Timestamp, active: pd.DataFrame):
        ids = active["unique_id"].astype(str).drop_duplicates().tolist()
        adapter_input = _grouped_asof(panel_groups, origin, ids)
        names = set(getattr(adapter, "auxiliary_names", ()))
        auxiliary: dict[str, pd.DataFrame] = {}
        if "returns" in names:
            auxiliary["returns"] = _grouped_asof(
                return_groups, origin, _rv_return_ids(ids)
            )
        if "dvol" in names:
            auxiliary["dvol"] = _grouped_asof(
                dvol_groups, origin, ["DVOL_" + uid.removeprefix("RV_") for uid in ids]
            )
        if "series" in names:
            auxiliary["series"] = _grouped_asof(
                auxiliary_series_groups,
                origin,
                list(auxiliary_series_groups),
            )
        return base_contexts[adapter.name].with_auxiliary(auxiliary), adapter_input

    def finalize(
        adapter: Adapter,
        origin: pd.Timestamp,
        active: pd.DataFrame,
        predictions: pd.DataFrame,
        runtime: float,
    ) -> pd.DataFrame:
        predictions = validate_forecasts(predictions, positive=task_id == "rv")
        actual_labels = set(
            predictions[["unique_id", "h", "ds_target"]].assign(
                ds_target=lambda x: pd.to_datetime(x["ds_target"])
            ).itertuples(index=False, name=None)
        )
        expected_labels = set(
            active[["unique_id", "h", "ds_target"]].assign(
                ds_target=lambda x: pd.to_datetime(x["ds_target"])
            ).itertuples(index=False, name=None)
        )
        if actual_labels != expected_labels:
            raise AssertionError(
                f"adapter {adapter.name} labels mismatch: "
                f"missing={expected_labels - actual_labels}, extra={actual_labels - expected_labels}"
            )
        return predictions.assign(
            run_id=run_id,
            task=task_id,
            model_variant=adapter.name,
            origin=origin,
            config_hash=model_hashes[adapter.name],
            data_hash=digest,
            runtime_s=float(runtime),
        ).loc[:, FORECAST_COLUMNS]

    for adapter in adapters:
        active_schedule = model_schedules[adapter.name]
        active_by_origin = {
            pd.Timestamp(origin): active_schedule.iloc[np.asarray(indices, dtype="int64")].copy()
            for origin, indices in pd.to_datetime(active_schedule["origin"]).groupby(
                pd.to_datetime(active_schedule["origin"]), sort=True
            ).indices.items()
        }
        pending: list[tuple[pd.Timestamp, pd.DataFrame]] = []
        for origin, active in active_by_origin.items():
            expected_key_frame = active[["unique_id", "h", "ds_target"]].copy().assign(
                run_id=run_id,
                task=task_id,
                model_variant=adapter.name,
                origin=origin,
                config_hash=model_hashes[adapter.name],
                data_hash=digest,
            )
            # Skip only a complete logical origin.  A partial origin in either
            # legacy or chunk storage is recomputed and upserted in full.
            if not _key_tuples(expected_key_frame).issubset(existing):
                pending.append((origin, active))

        buffered: list[pd.DataFrame] = []
        buffered_origins: list[pd.Timestamp] = []

        def flush(
            buffered: list[pd.DataFrame] = buffered,
            buffered_origins: list[pd.Timestamp] = buffered_origins,
            adapter: Adapter = adapter,
        ) -> None:
            if not buffered:
                return
            combined = pd.concat(buffered, ignore_index=True)
            store.write_chunk(combined)
            replaced = set(buffered_origins)
            existing.difference_update(
                {
                    key
                    for key in existing
                    if key[2] == adapter.name and _timestamp(key[4]) in replaced
                }
            )
            existing.update(_key_tuples(combined))
            buffered.clear()
            buffered_origins.clear()

        origin_batch_size = int(getattr(adapter, "origin_batch_size", 1))
        for start in range(0, len(pending), origin_batch_size):
            origin_batch = pending[start : start + origin_batch_size]
            requests = [
                (*origin_request(adapter, origin, active),)
                for origin, active in origin_batch
            ]
            started = time.perf_counter()
            if origin_batch_size > 1 and callable(getattr(adapter, "predict_many", None)):
                predictions_batch = adapter.predict_many(
                    [
                        (context, origin, adapter_input)
                        for (origin, _), (context, adapter_input) in zip(
                            origin_batch, requests, strict=True
                        )
                    ]
                )
            else:
                predictions_batch = [
                    adapter.predict(context, origin, adapter_input)
                    for (origin, _), (context, adapter_input) in zip(
                        origin_batch, requests, strict=True
                    )
                ]
            elapsed = time.perf_counter() - started
            runtime = elapsed / max(1, len(origin_batch))
            if len(predictions_batch) != len(origin_batch):
                raise AssertionError(f"adapter {adapter.name} origin batch output count mismatch")
            for (origin, active), predictions in zip(
                origin_batch, predictions_batch, strict=True
            ):
                buffered.append(finalize(adapter, origin, active, predictions, runtime))
                buffered_origins.append(origin)
                if len(buffered_origins) >= FORECAST_ORIGIN_CHUNK:
                    flush()
        flush()

    sidecar = {
        "run_id": run_id,
        "task": task_id,
        "task_config": config,
        "data_hash": digest,
        "config_hashes": model_hashes,
        "models": {
            adapter.name: (
                adapter.model_config() if callable(getattr(adapter, "model_config", None)) else _adapter_settings(adapter)
            )
            for adapter in adapters
        },
    }
    store.write_model_config(sidecar)
    store.validate_manifest()
    return {
        "run_id": run_id, "task": task_id, "window": window,
        "expected_rows": expected, "total_rows": int(sum(expected.values())),
        "manifest": str(store.manifest_path), "model_config": str(store.model_config_path),
    }
