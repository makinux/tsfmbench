"""StatsForecast AutoETS and AutoTheta point/interval adapters."""

from __future__ import annotations

import numpy as np
import pandas as pd

from tsfmbench.adapters.base import (
    estimation_series,
    failed_row,
    make_row,
    target_cells,
    validate_forecasts,
)

LEVELS = [20, 40, 60, 80]


def levels_to_deciles(forecast: pd.DataFrame, alias: str, index: int) -> np.ndarray:
    """Reconstruct q10..q90 from StatsForecast central intervals."""

    point = float(forecast[alias].iloc[index])
    columns = [
        f"{alias}-lo-80", f"{alias}-lo-60", f"{alias}-lo-40", f"{alias}-lo-20",
        None,
        f"{alias}-hi-20", f"{alias}-hi-40", f"{alias}-hi-60", f"{alias}-hi-80",
    ]
    values = [point if column is None else float(forecast[column].iloc[index]) for column in columns]
    return np.asarray(values, dtype="float64")


class _StatsAdapter:
    requires_fit = True
    model_class = None
    name = ""

    def _model(self):
        return self.model_class(season_length=7, alias=self.name)

    def predict(self, task_ctx, origin, series_batch: pd.DataFrame) -> pd.DataFrame:
        from statsforecast import StatsForecast

        cells = target_cells(task_ctx, origin, series_batch)
        rows = []
        for uid, uid_cells in cells.groupby("unique_id", sort=False):
            series = estimation_series(task_ctx, series_batch, str(uid))
            max_h = int(uid_cells["h"].max())
            if len(series) < 14:
                rows.extend(
                    failed_row(uid, int(cell.h), cell.ds_target, "insufficient_history")
                    for cell in uid_cells.itertuples(index=False)
                )
                continue
            train = series.assign(unique_id=str(uid))[["unique_id", "ds", "y"]]
            try:
                sf = StatsForecast(models=[self._model()], freq="D", n_jobs=1)
                forecast = sf.forecast(max_h, train, level=LEVELS)
            except Exception as exc:  # noqa: BLE001 - model selection failures become row failures
                rows.extend(
                    failed_row(uid, int(cell.h), cell.ds_target, f"fit_error:{type(exc).__name__}")
                    for cell in uid_cells.itertuples(index=False)
                )
                continue
            for cell in uid_cells.itertuples(index=False):
                index = int(cell.h) - 1
                point = float(forecast[self.name].iloc[index])
                quantiles = levels_to_deciles(forecast, self.name, index)
                rows.append(make_row(uid, int(cell.h), cell.ds_target, point, point, quantiles))
        return validate_forecasts(pd.DataFrame(rows))


class AutoETSAdapter(_StatsAdapter):
    name = "AutoETS"

    @property
    def model_class(self):
        from statsforecast.models import AutoETS

        return AutoETS


class AutoThetaAdapter(_StatsAdapter):
    name = "AutoTheta"

    @property
    def model_class(self):
        from statsforecast.models import AutoTheta

        return AutoTheta


AutoETS = AutoETSAdapter
AutoTheta = AutoThetaAdapter
