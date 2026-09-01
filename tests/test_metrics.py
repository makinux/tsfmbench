import numpy as np
import pandas as pd
import pytest

from tsfmbench.metrics import (
    coverage,
    coverage_by_tercile,
    mae,
    mse,
    pinball,
    qlike,
    relative_mae,
    rmse,
    wql,
)


def test_qlike_known_values_and_positive_forecast_contract() -> None:
    assert qlike([1.0, 2.0], [1.0, 2.0]).value == pytest.approx(0.0)
    assert qlike([0.1], [1.0]).value == pytest.approx(1.402585, abs=1e-6)
    with pytest.raises(ValueError, match="f > 0"):
        qlike([1.0], [0.0])
    with pytest.raises(ValueError, match="f > 0"):
        qlike([1.0], [-1.0])


def test_metrics_drop_nonfinite_rows_and_report_counts() -> None:
    result = qlike([1.0, np.nan, 2.0, np.inf], [1.0, 3.0, 1.0, 1.0])
    assert result.value == pytest.approx((0.0 + 2.0 - np.log(2.0) - 1.0) / 2.0)
    assert result.n_used == 2
    assert result.n_dropped == 2


def test_pinball_hand_calculation() -> None:
    result = pinball([10.0], [8.0], 0.9)
    assert result.value == pytest.approx(1.8)
    assert result.n_used == 1


def test_wql_small_known_value() -> None:
    quantiles = pd.DataFrame({0.1: [8.0, 18.0], 0.9: [12.0, 22.0]})
    # Each tau has mean pinball loss 0.2; (2/2) * (0.2+0.2) / mean([10,20]).
    result = wql([10.0, 20.0], quantiles, taus=(0.1, 0.9))
    assert result.value == pytest.approx(0.4 / 15.0)
    assert result.n_used == 2
    assert result.n_dropped == 0


def test_coverage_and_volatility_terciles() -> None:
    actual = np.arange(6.0)
    lower = np.array([-1.0, 0.0, 1.0, 2.5, 3.5, 5.5])
    upper = np.array([0.0, 2.0, 1.5, 4.5, 4.5, 6.0])
    assert coverage(actual, lower, upper).value == pytest.approx(4.0 / 6.0)
    by_tercile = coverage_by_tercile(actual, lower, upper, np.arange(6.0))
    assert by_tercile.loc["low", "value"] == pytest.approx(1.0)
    assert by_tercile.loc["middle", "value"] == pytest.approx(0.5)
    assert by_tercile.loc["high", "value"] == pytest.approx(0.5)
    assert by_tercile["n_used"].tolist() == [2, 2, 2]


def test_basic_errors_and_paired_relative_mae() -> None:
    assert mae([1.0, 3.0], [2.0, 1.0]).value == pytest.approx(1.5)
    assert mse([1.0, 3.0], [2.0, 1.0]).value == pytest.approx(2.5)
    assert rmse([1.0, 3.0], [2.0, 1.0]).value == pytest.approx(np.sqrt(2.5))
    result = relative_mae([1.0, np.nan, 4.0], [2.0, 100.0, 2.0])
    assert result.value == pytest.approx(1.25)
    assert (result.n_used, result.n_dropped) == (2, 1)
