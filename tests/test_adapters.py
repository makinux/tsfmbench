import numpy as np
import pandas as pd
import pytest

from tsfmbench.adapters.base import TaskContext
from tsfmbench.adapters.calibration import calibrated_rv_quantiles, variance_ratio_sample
from tsfmbench.adapters.ewma import EWMA
from tsfmbench.adapters.garch import fit_garch, garch_persistence
from tsfmbench.adapters.har import HARRV, fit_har
from tsfmbench.adapters.ml import LightGBMGlobal
from tsfmbench.adapters.naive import RandomWalk, SeasonalMedian4, SeasonalNaive7
from tsfmbench.adapters.timesfm3 import TimesFM3
from tsfmbench.backtest import slice_asof


def _context(task: str, uid: str, origin, target, *, auxiliary=None, h=1, kind="direct"):
    config = {
        "task": task,
        "series": [uid],
        "horizons": [{"h": h, "target": kind}],
        "windows": {"main": {"start": "2020-01-01", "end": None}},
        "primary_benchmark": "x",
        "estimation_windows": {"rv_crypto": 1000, "crypto": 1000, "volume": 1000},
        "refit_every": 5,
    }
    cells = pd.DataFrame(
        {"unique_id": [uid], "origin": [origin], "h": [h], "ds_target": [target]}
    )
    return TaskContext(config, cells, auxiliary or {})


def test_ratio_calibration_known_quantiles_and_minimum_pairs() -> None:
    ratios = np.arange(1.0, 101.0)
    calibrated = calibrated_rv_quantiles(2.0, np.ones(100), ratios)
    assert calibrated == pytest.approx(2 * np.quantile(ratios, np.arange(0.1, 1.0, 0.1)))
    assert np.isnan(calibrated_rv_quantiles(1.0, np.ones(59), np.ones(59))).all()


def test_ratio_calibration_excludes_post_division_overflow() -> None:
    forecasts = np.r_[np.ones(60), np.full(60, np.nextafter(0.0, 1.0))]
    realized = np.ones(120)
    ratios = variance_ratio_sample(forecasts, realized)
    assert ratios.shape == (60,)
    assert np.isfinite(ratios).all()
    np.testing.assert_array_equal(
        calibrated_rv_quantiles(2.0, forecasts, realized), np.full(9, 2.0)
    )


def test_naive_manual_values() -> None:
    dates = pd.date_range("2025-01-01", periods=35)
    panel = pd.DataFrame({"unique_id": "x", "ds": dates, "y": np.arange(35.0)})
    ctx = _context("price", "x", dates[-1], dates[-1] + pd.offsets.Day())
    rw = RandomWalk().predict(ctx, dates[-1], panel).iloc[0]
    assert rw.yhat_mean == 34.0
    assert rw.q10 == pytest.approx(35.0)
    future = pd.concat(
        [panel, pd.DataFrame({"unique_id": ["x"], "ds": ["2030-01-01"], "y": [999.0]})],
        ignore_index=True,
    )
    pd.testing.assert_frame_equal(
        RandomWalk().predict(ctx, dates[-1], panel),
        RandomWalk().predict(ctx, dates[-1], slice_asof(future, dates[-1])),
    )
    seasonal = SeasonalNaive7().predict(ctx, dates[-1], panel).iloc[0]
    assert seasonal.yhat_mean == 28.0
    median4 = SeasonalMedian4().predict(ctx, dates[-1], panel).iloc[0]
    assert median4.yhat_mean == np.median([7.0, 14.0, 21.0, 28.0])


def test_har_log_ar_smearing_and_future_invariance() -> None:
    rng = np.random.default_rng(4)
    log_rv = np.empty(500)
    log_rv[0] = -8.0
    for index in range(1, len(log_rv)):
        log_rv[index] = -2.0 + 0.75 * log_rv[index - 1] + rng.normal(0, 0.08)
    dates = pd.date_range("2023-01-01", periods=len(log_rv))
    panel = pd.DataFrame({"unique_id": "RV_BTC", "ds": dates, "y": np.exp(log_rv)})
    fitted = fit_har(panel[["ds", "y"]])
    assert np.isfinite(fitted.coefficients).all()
    origin = dates[-20]
    ctx = _context("rv", "RV_BTC", origin, origin + pd.offsets.Day())
    base = HARRV().predict(ctx, origin, slice_asof(panel, origin))
    future = pd.concat(
        [
            panel,
            pd.DataFrame(
                {"unique_id": ["RV_BTC"], "ds": [pd.Timestamp("2030-01-01")], "y": [999.0]}
            ),
        ],
        ignore_index=True,
    )
    appended = HARRV().predict(ctx, origin, slice_asof(future, origin))
    pd.testing.assert_frame_equal(base, appended)
    assert base.loc[0, "yhat_mean"] > base.loc[0, "yhat_median"] > 0


def test_ewma_future_append_invariance_and_positive() -> None:
    rng = np.random.default_rng(5)
    dates = pd.date_range("2024-01-01", periods=150)
    rv = pd.DataFrame({"unique_id": "RV_BTC", "ds": dates, "y": rng.lognormal(-8, 0.3, 150)})
    returns = pd.DataFrame(
        {"unique_id": "BTC-USD", "ds": dates, "return": rng.normal(0, 0.02, 150)}
    )
    origin = dates[-10]
    ctx = _context(
        "rv", "RV_BTC", origin, origin + pd.offsets.Day(),
        auxiliary={"returns": slice_asof(returns, origin)},
    )
    first = EWMA().predict(ctx, origin, slice_asof(rv, origin))
    second = EWMA().predict(ctx, origin, slice_asof(pd.concat([rv, rv.tail(1).assign(ds="2030-01-01")]), origin))
    pd.testing.assert_frame_equal(first, second)
    assert first.loc[0, "yhat_mean"] > 0


def test_garch_recovers_broad_persistence_and_positive_forecast() -> None:
    rng = np.random.default_rng(8)
    n, omega, alpha, beta = 1200, 0.000005, 0.08, 0.88
    variance = np.empty(n)
    returns = np.empty(n)
    variance[0] = omega / (1 - alpha - beta)
    returns[0] = np.sqrt(variance[0]) * rng.normal()
    for index in range(1, n):
        variance[index] = omega + alpha * returns[index - 1] ** 2 + beta * variance[index - 1]
        returns[index] = np.sqrt(variance[index]) * rng.normal()
    fitted = fit_garch(returns)
    assert garch_persistence(fitted) == pytest.approx(alpha + beta, abs=0.15)
    assert fitted.forecast(horizon=5, reindex=False).variance.to_numpy().min() > 0


def test_lightgbm_shape_monotonicity_and_no_future_leakage() -> None:
    rng = np.random.default_rng(11)
    dates = pd.date_range("2024-01-01", periods=180)
    panel = pd.concat(
        [
            pd.DataFrame(
                {"unique_id": uid, "ds": dates, "y": rng.lognormal(-8 + shift, 0.2, len(dates))}
            )
            for uid, shift in (("RV_BTC", 0.0), ("RV_ETH", 0.2))
        ],
        ignore_index=True,
    )
    origin = dates[-10]
    targets = pd.DataFrame(
        {
            "unique_id": ["RV_BTC", "RV_ETH"], "origin": origin, "h": 1,
            "ds_target": origin + pd.offsets.Day(),
        }
    )
    config = _context("rv", "RV_BTC", origin, origin + pd.offsets.Day()).config
    config["series"] = ["RV_BTC", "RV_ETH"]
    ctx = TaskContext(config, targets)
    model = LightGBMGlobal(n_estimators=25, min_child_samples=5)
    first = model.predict(ctx, origin, panel)
    future = panel.copy()
    future.loc[len(future)] = ["RV_BTC", pd.Timestamp("2030-01-01"), 999.0]
    future.loc[len(future)] = ["RV_ETH", pd.Timestamp("2030-01-01"), 999.0]
    second = LightGBMGlobal(n_estimators=25, min_child_samples=5).predict(ctx, origin, future)
    pd.testing.assert_frame_equal(first, second)
    assert first.shape[0] == 2
    assert (np.diff(first[[f"q{i}" for i in range(10, 100, 10)]], axis=1) >= 0).all()
    assert model.prediction_intervals.n_windows == 10
    assert model.last_conformal_dates_.max() <= origin


class _Output:
    def __init__(self, uid, crossing=False):
        self.ts_id = uid
        self.forecast = np.array([2.0])
        quantiles = np.arange(1.0, 10.0)
        if crossing:
            # Minimal reproduction from RV_BTC at origin 2020-07-19: the
            # TimesFM quantile heads crossed by 1.26e-7 at q20/q30.
            quantiles = np.array(
                [
                    0.0000751540,
                    0.0000927879,
                    0.0000926617,
                    0.0001101233,
                    0.0001279344,
                    0.0001484479,
                    0.0001776132,
                    0.0002341531,
                    0.0004509273,
                ]
            )
        self.quantiles = quantiles.reshape(1, 9)


class _Forecaster:
    def __init__(self, crossing=False):
        self.crossing = crossing
        self.calls = 0

    def predict_batch(self, contexts, horizon, ts_ids, **kwargs):
        self.calls += 1
        return [_Output(uid, self.crossing) for uid in ts_ids]


def test_timesfm_mock_batch_labels_store_shape_and_repairs_crossing() -> None:
    dates = pd.date_range("2024-01-01", periods=40)
    panel = pd.concat(
        [pd.DataFrame({"unique_id": uid, "ds": dates, "y": 10.0}) for uid in ("a", "b")]
    )
    targets = pd.DataFrame(
        {
            "unique_id": ["a", "b"], "origin": dates[-1], "h": 1,
            "ds_target": dates[-1] + pd.offsets.Day(),
        }
    )
    config = {
        "task": "price", "series": ["a", "b"], "horizons": [{"h": 1}],
        "windows": {"main": {"start": "2024-01-01", "end": None}}, "primary_benchmark": "RW",
    }
    ctx = TaskContext(config, targets)
    forecaster = _Forecaster()
    result = TimesFM3("raw", forecaster=forecaster).predict(ctx, dates[-1], panel)
    assert forecaster.calls == 1
    assert result["unique_id"].tolist() == ["a", "b"]
    assert result["yhat_median"].tolist() == [5.0, 5.0]
    repaired = TimesFM3("raw", forecaster=_Forecaster(crossing=True)).predict(
        ctx, dates[-1], panel
    )
    quantiles = repaired[[f"q{i}" for i in range(10, 100, 10)]].to_numpy()
    assert (np.diff(quantiles, axis=1) >= 0).all()
    assert repaired["yhat_median"].tolist() == [0.0001279344, 0.0001279344]


def test_timesfm_flattens_multiple_origins_into_one_backend_batch() -> None:
    dates = pd.date_range("2024-01-01", periods=40)
    panel = pd.DataFrame({"unique_id": "a", "ds": dates, "y": 10.0})
    origins = dates[-2:]
    targets = pd.DataFrame(
        {
            "unique_id": ["a", "a"],
            "origin": origins,
            "h": [1, 1],
            "ds_target": origins + pd.offsets.Day(),
        }
    )
    config = {
        "task": "price",
        "series": ["a"],
        "horizons": [{"h": 1}],
        "windows": {"main": {"start": "2024-01-01", "end": None}},
        "primary_benchmark": "RW",
    }
    ctx = TaskContext(config, targets)
    forecaster = _Forecaster()
    results = TimesFM3("raw", forecaster=forecaster).predict_many(
        [(ctx, origin, slice_asof(panel, origin)) for origin in origins]
    )
    assert forecaster.calls == 1
    assert [frame.loc[0, "ds_target"] for frame in results] == list(
        origins + pd.offsets.Day()
    )


class _LogOutput:
    def __init__(self, uid, point_log, sigma_log, *, missing_spread=False):
        self.ts_id = uid
        self.forecast = np.asarray(point_log, dtype="float64")
        offsets = np.linspace(-1.281552, 1.281552, 9)
        self.quantiles = np.array(
            [point + sigma * offsets for point, sigma in zip(point_log, sigma_log, strict=True)]
        )
        if missing_spread:
            self.quantiles[:, [0, -1]] = np.nan


class _LogForecaster:
    def __init__(self, point_log, sigma_log, *, missing_spread=False):
        self.point_log = point_log
        self.sigma_log = sigma_log
        self.missing_spread = missing_spread

    def predict_batch(self, contexts, horizon, ts_ids, **kwargs):
        return [
            _LogOutput(
                uid,
                self.point_log,
                self.sigma_log,
                missing_spread=self.missing_spread,
            )
            for uid in ts_ids
        ]


def test_timesfm_log_uses_model_implied_sigma_for_stepwise_smearing() -> None:
    dates = pd.date_range("2024-01-01", periods=40)
    panel = pd.DataFrame({"unique_id": "RV_BTC", "ds": dates, "y": 1.0})
    ctx = _context(
        "rv",
        "RV_BTC",
        dates[-1],
        dates[-1] + 2 * pd.offsets.Day(),
        h=2,
        kind="sum",
    )
    forecaster = _LogForecaster([0.0, np.log(2.0)], [1.0, 0.5])

    row = TimesFM3("log", forecaster=forecaster).predict(ctx, dates[-1], panel).iloc[0]

    assert row.yhat_mean == pytest.approx(3.915018176833781)
    assert row.yhat_median == pytest.approx(3.0)


def test_timesfm_log_missing_quantile_spread_falls_back_to_dev_diff_variance() -> None:
    dates = pd.date_range("2024-01-01", periods=4)
    panel = pd.DataFrame(
        {"unique_id": "RV_BTC", "ds": dates, "y": np.exp([0.0, 1.0, 3.0, 6.0])}
    )
    model = TimesFM3(
        "log", forecaster=_LogForecaster([0.0], [1.0], missing_spread=True)
    )
    ctx = _context("rv", "RV_BTC", dates[-1], dates[-1] + pd.offsets.Day())

    row = model.predict(ctx, dates[-1], panel).iloc[0]

    assert row.yhat_mean == pytest.approx(1.6487212707001282)
    assert row.yhat_median == pytest.approx(1.0)
    assert row[[f"q{i}" for i in range(10, 100, 10)]].isna().all()
    assert model.model_config()["log_smearing"] == (
        "model-implied quantile spread (fallback: dev-window diff-variance)"
    )
