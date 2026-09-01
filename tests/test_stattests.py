import numpy as np
import pandas as pd
import pytest

from tsfmbench.stattests import (
    christoffersen,
    design_effect_overlap,
    dm_test,
    hln_correction,
    holm,
    kupiec_pof,
    mcs,
    mde_analytic,
    moving_block_bootstrap,
    newey_west_lag,
    pt_test,
    sign_test,
    tost_relative_mae,
)


def test_hln_historical_coefficient_and_newey_west_lag() -> None:
    assert hln_correction(21, 20) == pytest.approx(0.0673, abs=0.001)
    assert newey_west_lag(100) == 3


def test_overlap_design_effect_known_values() -> None:
    assert design_effect_overlap(22, 5) == pytest.approx(4.4545, abs=0.01)
    assert design_effect_overlap(20, 20) == pytest.approx(1.0)
    assert design_effect_overlap(5, 5) == pytest.approx(1.0)


def test_analytic_mde_known_value_uses_t_quantiles() -> None:
    assert mde_analytic(19, 1.0) == pytest.approx(0.68, abs=0.03)


def test_dm_identical_losses() -> None:
    result = dm_test(np.arange(21.0), np.arange(21.0))
    assert result.stat == pytest.approx(0.0)
    assert result.pvalue == pytest.approx(1.0)


def test_dm_detects_ar1_mean_shift() -> None:
    rng = np.random.default_rng(2026)
    innovations = rng.normal(size=200)
    differential = np.empty(200)
    differential[0] = innovations[0]
    for index in range(1, 200):
        differential[index] = 0.4 * differential[index - 1] + innovations[index]
    differential = (differential - differential.mean()) / differential.std(ddof=0) + 1.0
    result = dm_test(differential, np.zeros_like(differential))
    assert result.pvalue < 0.01


def test_dm_auto_lag_for_one_hundred_observations() -> None:
    result = dm_test(np.arange(100.0), np.zeros(100))
    assert result.n == 100
    assert result.nw_lag == 3


def test_pt_perfect_match_and_independent_directions() -> None:
    directions = np.tile([-1.0, 1.0], 100)
    perfect = pt_test(directions, directions)
    assert perfect.stat > 10.0
    assert perfect.pvalue < 0.001

    rng = np.random.default_rng(42)
    independent = pt_test(
        rng.choice([-1.0, 1.0], size=5000),
        rng.choice([-1.0, 1.0], size=5000),
    )
    assert abs(independent.stat) < 3.0


def test_sign_test_exact_known_result() -> None:
    result = sign_test([1.0, 2.0, 3.0, -1.0, 0.0])
    assert result.n == 4
    assert result.n_positive == 3
    assert result.pvalue == pytest.approx(0.625)


def test_moving_block_bootstrap_is_seeded_and_finite() -> None:
    values = np.arange(1.0, 21.0)
    first = moving_block_bootstrap(values, np.mean, block_len=4, B=200, seed=7)
    second = moving_block_bootstrap(values, np.mean, block_len=4, B=200, seed=7)
    assert first == second
    assert first.estimate == pytest.approx(10.5)
    assert first.ci_low < first.estimate < first.ci_high


def test_kupiec_known_values() -> None:
    calibrated = kupiec_pof(25, 250, 0.1)
    assert calibrated.lr_uc == pytest.approx(0.0)
    assert calibrated.pvalue == pytest.approx(1.0)
    assert kupiec_pof(50, 250, 0.1).pvalue < 0.01


def test_christoffersen_distinguishes_transition_patterns() -> None:
    alternating = christoffersen(np.tile([0, 1], 50), p=0.2)
    clustered = christoffersen(np.r_[np.zeros(80), np.ones(20)], p=0.2)
    assert alternating.lr_ind > clustered.lr_ind > 0.0
    degenerate = christoffersen(np.zeros(100), p=0.1)
    assert np.isnan(degenerate.lr_ind)
    assert degenerate.reason is not None


def test_holm_known_vector() -> None:
    adjusted = holm([0.01, 0.04, 0.03])
    assert adjusted == pytest.approx([0.03, 0.06, 0.06])


def test_tost_relative_mae_noninferiority_decision() -> None:
    rng = np.random.default_rng(11)
    benchmark = np.abs(rng.normal(loc=1.0, scale=0.2, size=300))
    same = benchmark + rng.normal(scale=0.002, size=300)
    noninferior = tost_relative_mae(same, benchmark, block_len=5, B=500, seed=91)
    inferior = tost_relative_mae(1.2 * benchmark, benchmark, block_len=5, B=500, seed=91)
    assert noninferior.noninferior
    assert noninferior.ci_high < 1.05
    assert not inferior.noninferior


def test_mcs_excludes_clearly_inferior_model() -> None:
    rng = np.random.default_rng(7)
    common = rng.normal(size=250)
    losses = pd.DataFrame(
        {
            "good": common + rng.normal(scale=0.1, size=250),
            "near": common + 0.05 + rng.normal(scale=0.1, size=250),
            "bad": common + 1.0 + rng.normal(scale=0.1, size=250),
        }
    )
    result = mcs(losses, reps=200, block_size=10, seed=123)
    assert "bad" in result.excluded
    assert "good" in result.included
    assert set(result.pvalues.index) == set(losses.columns)

