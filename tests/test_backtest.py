import uuid
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from tsfmbench.adapters.base import make_row, target_cells, validate_forecasts
from tsfmbench.backtest import (
    FORECAST_COLUMNS,
    ForecastStore,
    OriginSchedule,
    run_task,
    slice_asof,
)


def _stored(rows: list[dict], *, origin="2025-01-01") -> pd.DataFrame:
    return (
        pd.DataFrame(rows)
        .assign(
            run_id="run",
            task="price",
            model_variant="mock",
            origin=pd.Timestamp(origin),
            config_hash="config",
            data_hash="data",
            runtime_s=0.01,
        )
        .loc[:, FORECAST_COLUMNS]
    )


def test_slice_asof_is_future_append_invariant() -> None:
    history = pd.DataFrame(
        {"unique_id": "x", "ds": pd.date_range("2025-01-01", periods=4), "y": range(4)}
    )
    origin = pd.Timestamp("2025-01-03")
    expected = slice_asof(history, origin)
    appended = pd.concat(
        [history, pd.DataFrame({"unique_id": ["x"], "ds": [pd.Timestamp("2030-01-01")], "y": [999]})]
    )
    pd.testing.assert_frame_equal(expected, slice_asof(appended, origin))


def test_native_origin_schedule_and_sum_target_date() -> None:
    panel = pd.DataFrame(
        {"unique_id": "x", "ds": pd.bdate_range("2025-01-01", periods=12), "y": 1.0}
    )
    config = {
        "task": "rv",
        "series": ["x"],
        "horizons": [{"h": 5, "target": "sum", "step": 5}],
        "windows": {"main": {"start": "2025-01-01", "end": "2025-01-31"}},
        "primary_benchmark": "EWMA",
    }
    result = OriginSchedule(config).generate(panel)
    assert result["origin"].tolist() == [panel.ds.iloc[0], panel.ds.iloc[5]]
    assert result["ds_target"].tolist() == [panel.ds.iloc[5], panel.ds.iloc[10]]


def test_store_collision_atomic_replace_and_ignores_temporary_residue() -> None:
    root = Path(".test-work") / f"stage3-store-{uuid.uuid4().hex}"
    store = ForecastStore(root, run_id="run", task="price")
    row = make_row("x", 1, "2025-01-02", 1.0, 1.0, np.arange(1, 10))
    frame = _stored([row])
    with pytest.raises(ValueError, match="collision"):
        store.write_batch(pd.concat([frame, frame], ignore_index=True))
    path = store.write_batch(frame)
    residue = path.with_name(".origin_20250101.tmp-dead.parquet")
    residue.write_bytes(b"interrupted parquet")
    store.write_batch(frame.assign(yhat_mean=2.0))
    assert store.read().loc[0, "yhat_mean"] == 2.0


class _CountingAdapter:
    name = "mock"
    requires_fit = False

    def __init__(self) -> None:
        self._calls = 0

    @property
    def calls(self) -> int:
        return self._calls

    def predict(self, task_ctx, origin, series_batch):
        self._calls += 1
        rows = [
            make_row(cell.unique_id, int(cell.h), cell.ds_target, 1.0, 1.0)
            for cell in target_cells(task_ctx, origin, series_batch).itertuples(index=False)
        ]
        return validate_forecasts(pd.DataFrame(rows))


def test_resume_reexecutes_partial_origins_without_losing_chunk_interior() -> None:
    root = Path(".test-work") / f"stage3-resume-{uuid.uuid4().hex}"
    processed, results = root / "processed", root / "forecasts"
    processed.mkdir(parents=True, exist_ok=True)
    dates = pd.date_range("2025-01-01", periods=5)
    panel = pd.concat(
        [pd.DataFrame({"unique_id": uid, "ds": dates, "y": np.arange(5.0)}) for uid in ("a", "b")]
    )
    panel.to_parquet(processed / "series.parquet", index=False)
    config = {
        "task": "price",
        "panel": "series",
        "value_column": "y",
        "series": ["a", "b"],
        "horizons": [{"h": 1, "target": "direct", "step": 1}],
        "windows": {"main": {"start": "2025-01-01", "end": "2025-01-05"}},
        "primary_benchmark": "RW",
    }
    first = _CountingAdapter()
    run_task(config, models=[first], processed_dir=processed, results_dir=results, run_id="resume")
    store = ForecastStore(results, run_id="resume", task="price")
    assert len(store.parquet_paths()) == 1
    assert store.parquet_paths()[0].name.startswith("chunk_")
    first_path = store.parquet_paths()[0]
    stored = pd.read_parquet(first_path)
    first_origin = pd.to_datetime(stored["origin"]).min()
    last_origin = pd.to_datetime(stored["origin"]).max()
    partial_indices = [
        stored.index[pd.to_datetime(stored["origin"]) == origin][0]
        for origin in (first_origin, last_origin)
    ]
    stored.drop(index=partial_indices).to_parquet(first_path, index=False)

    resumed = _CountingAdapter()
    run_task(config, models=[resumed], processed_dir=processed, results_dir=results, run_id="resume")
    assert resumed.calls == 2
    assert len(store.read()) == 8
