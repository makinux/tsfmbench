"""ARCH-backed GARCH and GJR-GARCH realized-variance adapters."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from tsfmbench.adapters.base import (
    clean_series,
    ctx_config,
    failed_row,
    horizon_detail,
    make_row,
    series_group,
    target_cells,
    validate_forecasts,
)
from tsfmbench.adapters.calibration import calibrated_rv_quantiles
from tsfmbench.adapters.ewma import _calibration_pairs, returns_for_series


def fit_garch(returns: np.ndarray | pd.Series, *, o: int = 0):
    """Fit a zero-mean GARCH(1,1), scaling decimal returns by 100."""

    from arch import arch_model

    values = np.asarray(returns, dtype="float64")
    values = values[np.isfinite(values)]
    if values.size < 30:
        raise ValueError("insufficient_return_history")
    model = arch_model(values * 100.0, mean="Zero", vol="GARCH", p=1, o=int(o), q=1, rescale=False)
    return model.fit(disp="off", show_warning=False)


def garch_persistence(result) -> float:
    """Return alpha + beta (+ gamma/2 for symmetric GJR innovations)."""

    params = result.params
    value = float(params.get("alpha[1]", 0.0) + params.get("beta[1]", 0.0))
    if "gamma[1]" in params:
        value += 0.5 * float(params["gamma[1]"])
    return value


@dataclass
class _CachedFit:
    origin: pd.Timestamp
    params: pd.Series


class GARCH:
    """GARCH(1,1) variance forecasts and empirical variance-ratio intervals."""

    name = "GARCH"
    requires_fit = True
    auxiliary_names = ("returns",)
    o = 0

    def __init__(self, *, refit_every: int | None = None) -> None:
        self.refit_every = refit_every
        self._fits: dict[str, _CachedFit] = {}

    def supports(self, unique_id: str) -> bool:
        return unique_id.startswith("RV_")

    def _window(self, task_ctx, uid: str, returns: pd.DataFrame) -> pd.DataFrame:
        config = ctx_config(task_ctx)
        if getattr(task_ctx, "estimation", "rolling") == "expanding":
            return returns
        windows = config.get("estimation_windows", {})
        group = series_group(uid)
        size = windows.get(group, windows.get("crypto" if "crypto" in group else group))
        return returns.tail(int(size)).reset_index(drop=True) if size else returns

    def _result(self, uid: str, origin, returns: pd.DataFrame, refit_every: int):
        from arch import arch_model

        values = returns["return"].to_numpy(dtype="float64")
        cached = self._fits.get(uid)
        should_refit = cached is None or cached.origin > pd.Timestamp(origin)
        if cached is not None and not should_refit:
            new_count = int((returns["ds"] > cached.origin).sum())
            should_refit = new_count >= refit_every
        if should_refit:
            result = fit_garch(values, o=self.o)
            self._fits[uid] = _CachedFit(pd.Timestamp(origin), result.params.copy())
            return result
        model = arch_model(values * 100.0, mean="Zero", vol="GARCH", p=1, o=self.o, q=1, rescale=False)
        return model.fix(cached.params)

    def predict(self, task_ctx, origin, series_batch: pd.DataFrame) -> pd.DataFrame:
        rows = []
        config = ctx_config(task_ctx)
        refit_every = int(self.refit_every or config.get("refit_every", 5))
        for cell in target_cells(task_ctx, origin, series_batch).itertuples(index=False):
            uid, h = str(cell.unique_id), int(cell.h)
            if not self.supports(uid):
                continue
            rv = clean_series(series_batch, uid)
            returns = self._window(task_ctx, uid, returns_for_series(task_ctx, uid, origin))
            try:
                result = self._result(uid, origin, returns, refit_every)
                variance = result.forecast(horizon=h, reindex=False).variance.iloc[-1].to_numpy(dtype="float64") / 10000.0
            except (ValueError, RuntimeError, np.linalg.LinAlgError) as exc:
                rows.append(failed_row(uid, h, cell.ds_target, str(exc)))
                continue
            target = str(horizon_detail(task_ctx, h).get("target", "direct"))
            point = float(variance.sum()) if target == "sum" else float(variance[h - 1])
            conditional = np.square(np.asarray(result.conditional_volatility, dtype="float64")) / 10000.0
            past_f, realized = _calibration_pairs(rv, returns["ds"], conditional, h, target)
            quantiles = calibrated_rv_quantiles(point, past_f, realized)
            rows.append(make_row(uid, h, cell.ds_target, point, point, quantiles))
        return validate_forecasts(pd.DataFrame(rows), positive=True)


class GJRGARCH(GARCH):
    """GJR-GARCH(1,1,1), registered only for the Nikkei RV series."""

    name = "GJR-GARCH"
    o = 1

    def supports(self, unique_id: str) -> bool:
        return unique_id == "RV_N225_GK"


GARCHAdapter = GARCH
GJR_GARCH = GJRGARCH
