"""Offline-first TimesFM 3.0 batch adapter."""

from __future__ import annotations

import os

# These must be set before either huggingface_hub or timesfm is imported.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from typing import Any

import numpy as np
import pandas as pd

from tsfmbench.adapters.base import (
    TaskContext,
    clean_series,
    ctx_config,
    failed_row,
    horizon_detail,
    make_row,
    target_cells,
    task_name,
    validate_forecasts,
)


class TimesFM3:
    """TimesFM3 raw or log variant, with exactly one predict_batch call."""

    requires_fit = False
    # An RV origin has at most nine series, so eight origins produce roughly
    # the preregistered/operational 64-context inference chunk (at most 72).
    origin_batch_size = 8

    def __init__(
        self,
        variant: str = "raw",
        *,
        forecaster: Any | None = None,
        checkpoint: str = "google/timesfm-3.0-pytorch",
        revision: str | None = None,
        device: str | None = None,
        per_core_batch_size: int = 8,
    ) -> None:
        normalized = variant.lower().removeprefix("timesfm3-")
        if normalized not in {"raw", "log"}:
            raise ValueError("TimesFM3 variant must be raw or log")
        self.variant = normalized
        self.name = f"TimesFM3-{normalized}"
        self.checkpoint = checkpoint
        self.revision = revision
        self.device = device
        self.per_core_batch_size = int(per_core_batch_size)
        self._forecaster = forecaster
        self._smearing: dict[str, float] = {}
        self._last_context_lengths: dict[str, int] = {}
        self._last_horizon = 0

    def _load(self):
        if self._forecaster is not None:
            return self._forecaster
        try:
            import torch
            from timesfm import TimesFM3Forecaster

            device = self.device or ("cuda" if torch.cuda.is_available() else "cpu")
            self._forecaster = TimesFM3Forecaster.from_pretrained(
                self.checkpoint,
                device=device,
                revision=self.revision,
                local_files_only=True,
                per_core_batch_size=self.per_core_batch_size,
            )
        except Exception as exc:
            raise RuntimeError(
                "TimesFM 3 checkpoint is not available offline; run "
                "`tsfmbench download --source hf-checkpoint` first"
            ) from exc
        return self._forecaster

    def _context_length(self, task_ctx, length: int) -> int:
        config = ctx_config(task_ctx)
        configured = int(config.get("context_length", {}).get("default", 1024 if task_name(task_ctx) == "rv" else 2048))
        return min(length, configured)

    def _sigma2(
        self,
        uid: str,
        series: pd.DataFrame,
        origin,
        q10_log: float,
        q90_log: float,
    ) -> float:
        if np.isfinite(q10_log) and np.isfinite(q90_log) and q90_log >= q10_log:
            sigma_log = (q90_log - q10_log) / (2.0 * 1.281552)
            return float(sigma_log**2)

        if uid in self._smearing:
            return self._smearing[uid]
        end = min(pd.Timestamp(origin), pd.Timestamp("2024-12-31"))
        values = series.loc[series["ds"] <= end, "y"].to_numpy(dtype="float64")
        if len(values) < 3 or np.any(values <= 0):
            sigma2 = 0.0
        else:
            sigma2 = float(np.var(np.diff(np.log(values)), ddof=1))
        # Freeze only once the full development window is visible.
        if pd.Timestamp(origin) >= pd.Timestamp("2024-12-31"):
            self._smearing[uid] = sigma2
        return sigma2

    def model_config(self) -> dict[str, Any]:
        config: dict[str, Any] = {
            "model_variant": self.name,
            "checkpoint": self.checkpoint,
            "revision": self.revision,
            "device": self.device or "auto(cuda->cpu)",
            "per_core_batch_size": self.per_core_batch_size,
            "context_lengths": self._last_context_lengths,
            "return_quantiles": True,
            "make_positive": False,
            "quantiles": [q / 10 for q in range(1, 10)],
        }
        if self.variant == "log":
            config["log_smearing"] = (
                "model-implied quantile spread (fallback: dev-window diff-variance)"
            )
        try:
            from huggingface_hub import scan_cache_dir

            repository = next(
                repo for repo in scan_cache_dir().repos if repo.repo_id == self.checkpoint
            )
            revisions = list(repository.revisions)
            selected = next(
                (
                    revision
                    for revision in revisions
                    if self.revision is not None and self.revision in revision.refs
                ),
                max(revisions, key=lambda revision: revision.last_modified),
            )
            config["resolved_commit_hash"] = selected.commit_hash
        except (OSError, StopIteration, ValueError):
            config["resolved_commit_hash"] = None
        backend_config = getattr(self._forecaster, "config", None)
        if backend_config is not None and is_dataclass(backend_config):
            config["backend_config"] = asdict(backend_config)
        try:
            from timesfm import ForecastConfig

            config["ForecastConfig"] = asdict(
                ForecastConfig(
                    max_context=max(self._last_context_lengths.values(), default=0),
                    max_horizon=self._last_horizon,
                    per_core_batch_size=self.per_core_batch_size,
                    fix_quantile_crossing=False,
                )
            )
        except Exception:  # noqa: BLE001 - sidecar generation must work without timesfm import
            config["ForecastConfig"] = {"per_core_batch_size": self.per_core_batch_size}
        return config

    @staticmethod
    def _outputs(raw: Any) -> list[Any]:
        if isinstance(raw, tuple) and len(raw) == 2:
            points, quantiles = raw
            return [
                type("ForecastOutput", (), {"forecast": point, "quantiles": quantile})
                for point, quantile in zip(points, quantiles, strict=True)
            ]
        return list(raw)

    @staticmethod
    def _monotone_quantiles(values: np.ndarray) -> np.ndarray:
        """Apply quantile rearrangement and retain missing-edge rows as all-null."""

        result = np.asarray(values, dtype="float64").copy()
        edge_invalid = ~np.isfinite(result[:, 0]) | ~np.isfinite(result[:, -1])
        if not np.isfinite(result[~edge_invalid]).all():
            raise AssertionError("TimesFM returned non-finite quantile output")
        # TimesFM can have tiny numerical crossings even with nominally ordered
        # quantile heads.  Rearrangement is the standard crossing correction;
        # it preserves the empirical distribution rather than clipping or
        # converting only some quantiles to null.
        result[~edge_invalid] = np.sort(result[~edge_invalid], axis=-1)
        # The adapter contract permits all-null quantile rows.  Keeping invalid
        # edge rows all-null lets log smearing use its development-window fallback.
        result[edge_invalid] = np.nan
        return result

    def predict_many(
        self,
        requests: list[tuple[TaskContext | Mapping[str, Any], pd.Timestamp, pd.DataFrame]],
    ) -> list[pd.DataFrame]:
        """Forecast several origins in one flattened ``predict_batch`` call."""

        cells_by_request: list[pd.DataFrame] = []
        series_by_label: dict[tuple[int, str], pd.DataFrame] = {}
        invalid_labels: set[tuple[int, str]] = set()
        contexts: list[np.ndarray] = []
        labels: list[tuple[int, str]] = []
        ts_ids: list[str] = []
        max_h = 0

        for request_index, (task_ctx, origin, series_batch) in enumerate(requests):
            panel = series_batch.loc[pd.to_datetime(series_batch["ds"]) <= pd.Timestamp(origin)].copy()
            cells = target_cells(task_ctx, origin, panel)
            cells_by_request.append(cells)
            if not cells.empty:
                max_h = max(max_h, int(cells["h"].max()))
            ids = cells["unique_id"].astype(str).drop_duplicates().tolist()
            for uid_index, uid in enumerate(ids):
                series = clean_series(panel, uid)
                length = self._context_length(task_ctx, len(series))
                self._last_context_lengths[uid] = length
                values = series["y"].to_numpy(dtype="float64")[-length:]
                if self.variant == "log":
                    values = (
                        np.log(values)
                        if values.size and np.all(values > 0)
                        else np.full_like(values, np.nan)
                    )
                label = (request_index, uid)
                series_by_label[label] = series
                if values.size == 0 or not np.isfinite(values).all():
                    invalid_labels.add(label)
                    continue
                labels.append(label)
                contexts.append(values)
                # Unique backend labels prevent duplicate series ids across
                # origins from being coalesced or reordered by an implementation.
                ts_ids.append(f"origin-{request_index}:series-{uid_index}:{uid}")

        self._last_horizon = max_h
        outputs: list[Any] = []
        prediction_error: str | None = None
        if contexts:
            try:
                raw_outputs = self._load().predict_batch(
                    contexts,
                    horizon=max_h,
                    ts_ids=ts_ids,
                    return_quantiles=True,
                    make_positive=False,
                    sort_quantiles=True,
                )
                outputs = self._outputs(raw_outputs)
            except RuntimeError:
                raise
            except Exception as exc:  # noqa: BLE001 - backend inference failures become row failures
                prediction_error = f"predict_error:{type(exc).__name__}"
        if prediction_error is None and len(outputs) != len(labels):
            raise AssertionError("TimesFM predict_batch output count does not match input labels")
        if prediction_error is None:
            for expected_id, output in zip(ts_ids, outputs, strict=True):
                output_id = getattr(output, "ts_id", None)
                if output_id is not None and str(output_id) != expected_id:
                    raise AssertionError("TimesFM predict_batch output labels were reordered")
        output_by_label = dict(zip(labels, outputs, strict=True)) if prediction_error is None else {}

        results: list[pd.DataFrame] = []
        for request_index, ((task_ctx, origin, _), cells) in enumerate(
            zip(requests, cells_by_request, strict=True)
        ):
            rows = []
            for cell in cells.itertuples(index=False):
                uid, h = str(cell.unique_id), int(cell.h)
                label = (request_index, uid)
                if label in invalid_labels:
                    rows.append(failed_row(uid, h, cell.ds_target, "invalid_context"))
                    continue
                if prediction_error is not None:
                    rows.append(failed_row(uid, h, cell.ds_target, prediction_error))
                    continue
                output = output_by_label[label]
                point_path = np.asarray(output.forecast, dtype="float64").reshape(-1)
                quantile_path = np.asarray(output.quantiles, dtype="float64")
                if quantile_path.ndim == 3 and quantile_path.shape[0] == 1:
                    quantile_path = quantile_path[0]
                if quantile_path.shape[0] < h or quantile_path.shape[1] != 9 or point_path.size < h:
                    raise AssertionError("TimesFM output horizon or quantile labels do not match request")
                quantile_path = self._monotone_quantiles(quantile_path)
                target = str(horizon_detail(task_ctx, h).get("target", "direct"))
                is_sum = target == "sum" and h > 1
                point = float(point_path[:h].sum()) if is_sum else float(point_path[h - 1])
                quantiles = quantile_path[:h].sum(axis=0) if is_sum else quantile_path[h - 1]
                if self.variant == "log":
                    if is_sum:
                        sigma2_path = np.array(
                            [
                                self._sigma2(
                                    uid,
                                    series_by_label[label],
                                    origin,
                                    step_quantiles[0],
                                    step_quantiles[-1],
                                )
                                for step_quantiles in quantile_path[:h]
                            ]
                        )
                        mean = float(np.exp(point_path[:h] + sigma2_path / 2.0).sum())
                        median = float(np.exp(point_path[:h]).sum())
                        quantiles = np.exp(quantile_path[:h]).sum(axis=0)
                    else:
                        sigma2 = self._sigma2(
                            uid,
                            series_by_label[label],
                            origin,
                            quantiles[0],
                            quantiles[-1],
                        )
                        mean = float(np.exp(point + sigma2 / 2.0))
                        median = float(np.exp(point))
                        quantiles = np.exp(quantiles)
                else:
                    mean = point
                    median = float(quantiles[4])
                rows.append(make_row(uid, h, cell.ds_target, mean, median, quantiles))
            results.append(
                validate_forecasts(pd.DataFrame(rows), positive=task_name(task_ctx) == "rv")
            )
        return results

    def predict(self, task_ctx, origin, series_batch: pd.DataFrame) -> pd.DataFrame:
        return self.predict_many([(task_ctx, pd.Timestamp(origin), series_batch)])[0]


class TimesFM3Raw(TimesFM3):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__("raw", **kwargs)


class TimesFM3Log(TimesFM3):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__("log", **kwargs)


TimesFM3Adapter = TimesFM3
