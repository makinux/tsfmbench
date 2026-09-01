"""Optional point-only Prophet reference adapter for Task U."""

from __future__ import annotations

import pandas as pd

from tsfmbench.adapters.base import (
    estimation_series,
    failed_row,
    make_row,
    target_cells,
    validate_forecasts,
)


class Prophet:
    name = "Prophet"
    requires_fit = True
    reference = True

    def supports(self, unique_id: str) -> bool:
        return unique_id.startswith("VOL_")

    def predict(self, task_ctx, origin, series_batch: pd.DataFrame) -> pd.DataFrame:
        cells = target_cells(task_ctx, origin, series_batch)
        rows = []
        for uid, uid_cells in cells.groupby("unique_id", sort=False):
            if not self.supports(str(uid)):
                continue
            series = estimation_series(task_ctx, series_batch, str(uid))
            try:
                from prophet import Prophet as _Prophet

                model = _Prophet(daily_seasonality=False, weekly_seasonality=True, yearly_seasonality=True)
                model.fit(series.rename(columns={"y": "y"})[["ds", "y"]])
                future = uid_cells[["ds_target"]].rename(columns={"ds_target": "ds"})
                point = model.predict(future)["yhat"].to_numpy(dtype="float64")
            except ImportError:
                rows.extend(
                    failed_row(uid, int(cell.h), cell.ds_target, "missing_optional_dependency:prophet")
                    for cell in uid_cells.itertuples(index=False)
                )
                continue
            except Exception as exc:  # noqa: BLE001 - third-party optimizer failures become row failures
                rows.extend(
                    failed_row(uid, int(cell.h), cell.ds_target, f"fit_error:{type(exc).__name__}")
                    for cell in uid_cells.itertuples(index=False)
                )
                continue
            for cell, value in zip(uid_cells.itertuples(index=False), point, strict=True):
                rows.append(make_row(uid, int(cell.h), cell.ds_target, float(value), float(value)))
        return validate_forecasts(pd.DataFrame(rows))


ProphetAdapter = Prophet
