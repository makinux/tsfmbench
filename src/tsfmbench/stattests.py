"""Pure statistical tests and resampling utilities used by the benchmark."""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TypeVar

import numpy as np
import pandas as pd
from arch.bootstrap import MCS
from scipy.special import xlogy
from scipy.stats import binomtest, chi2, norm, t

ArrayT = TypeVar("ArrayT", bound=np.ndarray)
Seed = int | np.random.Generator


@dataclass(frozen=True)
class DMResult:
    stat: float
    pvalue: float
    nw_lag: int
    n: int
    reason: str | None = None


@dataclass(frozen=True)
class PTResult:
    stat: float
    pvalue: float
    n: int
    hit_rate: float
    expected_hit_rate: float
    reason: str | None = None


@dataclass(frozen=True)
class SignTestResult:
    stat: float
    pvalue: float
    n: int
    n_positive: int
    n_negative: int
    n_zero: int
    reason: str | None = None


@dataclass(frozen=True)
class BootstrapResult:
    estimate: float
    ci_low: float
    ci_high: float
    pvalue: float
    n: int
    n_dropped: int

    @property
    def ci(self) -> tuple[float, float]:
        return self.ci_low, self.ci_high


@dataclass(frozen=True)
class KupiecResult:
    lr_uc: float
    pvalue: float
    n_viol: int
    n: int
    p: float
    reason: str | None = None


@dataclass(frozen=True)
class ChristoffersenResult:
    lr_ind: float
    pvalue_ind: float
    lr_cc: float
    pvalue_cc: float
    lr_uc: float
    pvalue_uc: float
    n: int
    reason: str | None = None


@dataclass(frozen=True)
class TOSTResult:
    relative_mae: float
    ci_low: float
    ci_high: float
    pvalue: float
    margin: float
    noninferior: bool
    n: int
    n_dropped: int

    @property
    def ci(self) -> tuple[float, float]:
        return self.ci_low, self.ci_high


@dataclass(frozen=True)
class MCSResult:
    included: list[object]
    excluded: list[object]
    pvalues: pd.Series


def _rng(seed: Seed) -> np.random.Generator:
    return seed if isinstance(seed, np.random.Generator) else np.random.default_rng(seed)


def _paired_finite(first: object, second: object) -> tuple[np.ndarray, np.ndarray, int]:
    left = np.asarray(first, dtype="float64").reshape(-1)
    right = np.asarray(second, dtype="float64").reshape(-1)
    if left.shape != right.shape:
        raise ValueError("paired inputs must have identical shapes")
    valid = np.isfinite(left) & np.isfinite(right)
    return left[valid], right[valid], int((~valid).sum())


def newey_west_lag(n: int) -> int:
    """Return the Newey--West (1994) lag rule ``floor(4*(n/100)^(2/9))``."""

    if n <= 0:
        raise ValueError("n must be positive")
    bandwidth = 4.0 * (n / 100.0) ** (2.0 / 9.0)
    # Use the strict left endpoint of an integer cutoff, matching the historical
    # implementation used by this benchmark (in particular, n=100 selects lag 3).
    return max(0, math.floor(np.nextafter(bandwidth, -np.inf)))


def hln_correction(n: int, h_origin: int) -> float:
    """Return the Harvey--Leybourne--Newbold small-sample correction for DM."""

    if n <= 0 or h_origin <= 0:
        raise ValueError("n and h_origin must be positive")
    factor_squared = (n + 1.0 - 2.0 * h_origin + h_origin * (h_origin - 1.0) / n) / n
    return float(np.sqrt(factor_squared)) if factor_squared >= 0.0 else float("nan")


def dm_test(
    loss_a: object,
    loss_b: object,
    h_origin: int = 1,
    lag: int | str = "auto",
) -> DMResult:
    """Run Diebold--Mariano with Newey--West HAC and Harvey--Leybourne--Newbold correction."""

    first, second, _ = _paired_finite(loss_a, loss_b)
    n = int(first.size)
    if h_origin <= 0:
        raise ValueError("h_origin must be positive")
    if lag == "auto":
        nw_lag = newey_west_lag(n) if n else 0
    elif isinstance(lag, (int, np.integer)) and int(lag) >= 0:
        nw_lag = int(lag)
    else:
        raise ValueError("lag must be 'auto' or a non-negative integer")
    if n < 2:
        return DMResult(float("nan"), float("nan"), nw_lag, n, "fewer than two finite pairs")
    nw_lag = min(nw_lag, n - 1)
    differential = first - second
    mean_d = float(np.mean(differential))
    centered = differential - mean_d
    gamma0 = float(centered @ centered / n)
    long_run_variance = gamma0
    for k in range(1, nw_lag + 1):
        gamma_k = float(centered[k:] @ centered[:-k] / n)
        weight = 1.0 - k / (nw_lag + 1.0)
        long_run_variance += 2.0 * weight * gamma_k

    if np.all(differential == 0.0):
        return DMResult(0.0, 1.0, nw_lag, n)
    if long_run_variance < 0.0:
        return DMResult(
            float("nan"),
            float("nan"),
            nw_lag,
            n,
            "negative Newey-West long-run variance",
        )
    if long_run_variance == 0.0:
        return DMResult(
            float("nan"),
            float("nan"),
            nw_lag,
            n,
            "zero Newey-West long-run variance with non-zero mean",
        )
    correction = hln_correction(n, h_origin)
    if not np.isfinite(correction) or correction == 0.0:
        return DMResult(float("nan"), float("nan"), nw_lag, n, "invalid HLN correction")
    statistic = correction * mean_d / math.sqrt(long_run_variance / n)
    pvalue = float(2.0 * t.sf(abs(statistic), df=n - 1))
    return DMResult(float(statistic), pvalue, nw_lag, n)


def pt_test(actual_dir: object, pred_dir: object) -> PTResult:
    """Run the Pesaran--Timmermann (1992) directional-accuracy test."""

    actual, predicted, _ = _paired_finite(actual_dir, pred_dir)
    n = int(actual.size)
    if n < 2:
        return PTResult(float("nan"), float("nan"), n, float("nan"), float("nan"), "fewer than two finite pairs")
    actual_up = actual > 0.0
    predicted_up = predicted > 0.0
    hit_rate = float(np.mean(actual_up == predicted_up))
    p_y = float(np.mean(actual_up))
    p_x = float(np.mean(predicted_up))
    expected = p_y * p_x + (1.0 - p_y) * (1.0 - p_x)
    var_hit = expected * (1.0 - expected) / n
    var_expected = (
        (2.0 * p_y - 1.0) ** 2 * p_x * (1.0 - p_x) / n
        + (2.0 * p_x - 1.0) ** 2 * p_y * (1.0 - p_y) / n
        + 4.0 * p_x * p_y * (1.0 - p_x) * (1.0 - p_y) / n**2
    )
    variance = var_hit - var_expected
    if variance <= 0.0:
        return PTResult(
            float("nan"),
            float("nan"),
            n,
            hit_rate,
            expected,
            "non-positive Pesaran-Timmermann variance",
        )
    statistic = (hit_rate - expected) / math.sqrt(variance)
    return PTResult(float(statistic), float(2.0 * norm.sf(abs(statistic))), n, hit_rate, expected)


def sign_test(x: object) -> SignTestResult:
    """Run the exact two-sided binomial sign test of median zero."""

    values = np.asarray(x, dtype="float64").reshape(-1)
    values = values[np.isfinite(values)]
    n_positive = int((values > 0.0).sum())
    n_negative = int((values < 0.0).sum())
    n_zero = int((values == 0.0).sum())
    n = n_positive + n_negative
    if n == 0:
        return SignTestResult(float("nan"), float("nan"), 0, 0, 0, n_zero, "all observations are zero")
    pvalue = float(binomtest(n_positive, n, p=0.5, alternative="two-sided").pvalue)
    return SignTestResult(float(n_positive), pvalue, n, n_positive, n_negative, n_zero)


def _bootstrap_statistics(
    values: np.ndarray,
    stat_fn: Callable[[np.ndarray], float],
    block_len: int,
    B: int,
    seed: Seed,
) -> np.ndarray:
    n = values.shape[0]
    if block_len <= 0 or block_len > n:
        raise ValueError("block_len must lie between 1 and the sample size")
    if B <= 0:
        raise ValueError("B must be positive")
    generator = _rng(seed)
    blocks_per_draw = math.ceil(n / block_len)
    max_start = n - block_len
    starts = generator.integers(0, max_start + 1, size=(B, blocks_per_draw))
    offsets = np.arange(block_len, dtype="int64")
    indices = (starts[..., None] + offsets).reshape(B, -1)[:, :n]
    return np.asarray([stat_fn(values[index]) for index in indices], dtype="float64")


def moving_block_bootstrap(
    x: object,
    stat_fn: Callable[[np.ndarray], float],
    block_len: int,
    B: int = 2000,
    seed: Seed = 0,
) -> BootstrapResult:
    """Return a moving-block bootstrap percentile CI and inverted two-sided p-value for H0=0."""

    values = np.asarray(x, dtype="float64")
    if values.ndim == 0:
        values = values.reshape(1)
    finite = np.isfinite(values) if values.ndim == 1 else np.isfinite(values).all(axis=tuple(range(1, values.ndim)))
    n_dropped = int((~finite).sum())
    values = values[finite]
    n = int(values.shape[0])
    if n == 0:
        return BootstrapResult(float("nan"), float("nan"), float("nan"), float("nan"), 0, n_dropped)
    estimate = float(stat_fn(values))
    draws = _bootstrap_statistics(values, stat_fn, block_len, B, seed)
    draws = draws[np.isfinite(draws)]
    if not draws.size:
        return BootstrapResult(estimate, float("nan"), float("nan"), float("nan"), n, n_dropped)
    ci_low, ci_high = np.percentile(draws, (2.5, 97.5))
    lower_tail = (np.count_nonzero(draws <= 0.0) + 1.0) / (draws.size + 1.0)
    upper_tail = (np.count_nonzero(draws >= 0.0) + 1.0) / (draws.size + 1.0)
    pvalue = min(1.0, 2.0 * min(lower_tail, upper_tail))
    return BootstrapResult(estimate, float(ci_low), float(ci_high), float(pvalue), n, n_dropped)


def _bernoulli_loglik(successes: int, total: int, probability: float) -> float:
    failures = total - successes
    return float(xlogy(successes, probability) + xlogy(failures, 1.0 - probability))


def kupiec_pof(n_viol: int, n: int, p: float) -> KupiecResult:
    """Run Kupiec's proportion-of-failures LR_uc likelihood-ratio test."""

    if n <= 0 or not 0 <= n_viol <= n:
        raise ValueError("require n > 0 and 0 <= n_viol <= n")
    if not 0.0 < p < 1.0:
        raise ValueError("p must lie strictly between 0 and 1")
    fitted = n_viol / n
    null_loglik = _bernoulli_loglik(n_viol, n, p)
    fitted_loglik = _bernoulli_loglik(n_viol, n, fitted)
    lr_uc = max(0.0, -2.0 * (null_loglik - fitted_loglik))
    return KupiecResult(float(lr_uc), float(chi2.sf(lr_uc, 1)), n_viol, n, p)


def christoffersen(viol_seq: object, p: float) -> ChristoffersenResult:
    """Run Christoffersen's conditional-coverage LR_ind and LR_cc Markov tests."""

    values = np.asarray(viol_seq, dtype="float64").reshape(-1)
    values = values[np.isfinite(values)]
    if not np.isin(values, (0.0, 1.0)).all():
        raise ValueError("viol_seq must contain only 0/1 values")
    sequence = values.astype("int8")
    n = int(sequence.size)
    n_viol = int(sequence.sum())
    empty = (float("nan"),) * 6
    if n < 2:
        return ChristoffersenResult(*empty, n, "fewer than two finite observations")
    if n_viol in (0, n):
        return ChristoffersenResult(*empty, n, "all observations have the same violation state")

    previous, current = sequence[:-1], sequence[1:]
    n00 = int(((previous == 0) & (current == 0)).sum())
    n01 = int(((previous == 0) & (current == 1)).sum())
    n10 = int(((previous == 1) & (current == 0)).sum())
    n11 = int(((previous == 1) & (current == 1)).sum())
    total0, total1 = n00 + n01, n10 + n11
    if total0 == 0 or total1 == 0:
        return ChristoffersenResult(*empty, n, "one Markov transition row is empty")
    pi01 = n01 / total0
    pi11 = n11 / total1
    pi = (n01 + n11) / (n - 1)
    independent_loglik = _bernoulli_loglik(n01 + n11, n - 1, pi)
    markov_loglik = _bernoulli_loglik(n01, total0, pi01) + _bernoulli_loglik(n11, total1, pi11)
    lr_ind = max(0.0, -2.0 * (independent_loglik - markov_loglik))
    uc = kupiec_pof(n_viol, n, p)
    lr_cc = uc.lr_uc + lr_ind
    return ChristoffersenResult(
        float(lr_ind),
        float(chi2.sf(lr_ind, 1)),
        float(lr_cc),
        float(chi2.sf(lr_cc, 2)),
        uc.lr_uc,
        uc.pvalue,
        n,
    )


def holm(pvals: Sequence[float] | pd.Series) -> np.ndarray | pd.Series:
    """Return Holm step-down family-wise-error adjusted p-values."""

    values = np.asarray(pvals, dtype="float64")
    adjusted = np.full(values.shape, np.nan, dtype="float64")
    finite_locations = np.flatnonzero(np.isfinite(values))
    if finite_locations.size:
        order = finite_locations[np.argsort(values[finite_locations], kind="stable")]
        scaled = (order.size - np.arange(order.size)) * values[order]
        adjusted[order] = np.minimum(1.0, np.maximum.accumulate(scaled))
    if isinstance(pvals, pd.Series):
        return pd.Series(adjusted, index=pvals.index, name=pvals.name)
    return adjusted


def tost_relative_mae(
    err_model: object,
    err_bench: object,
    margin: float = 1.05,
    block_len: int = 1,
    B: int = 2000,
    seed: Seed = 0,
) -> TOSTResult:
    """Run paired moving-block TOST non-inferiority using the upper bound of a 90% CI."""

    if margin <= 0.0:
        raise ValueError("margin must be positive")
    model, benchmark, n_dropped = _paired_finite(err_model, err_bench)
    paired = np.column_stack((model, benchmark))

    def ratio(sample: np.ndarray) -> float:
        denominator = float(np.mean(np.abs(sample[:, 1])))
        return float(np.mean(np.abs(sample[:, 0])) / denominator) if denominator > 0.0 else float("nan")

    n = int(paired.shape[0])
    if n == 0:
        return TOSTResult(float("nan"), float("nan"), float("nan"), float("nan"), margin, False, 0, n_dropped)
    estimate = ratio(paired)
    draws = _bootstrap_statistics(paired, ratio, block_len, B, seed)
    draws = draws[np.isfinite(draws)]
    if not draws.size or not np.isfinite(estimate):
        return TOSTResult(estimate, float("nan"), float("nan"), float("nan"), margin, False, n, n_dropped)
    ci_low, ci_high = np.percentile(draws, (5.0, 95.0))
    centered = draws - estimate
    observed_null_distance = estimate - margin
    pvalue = (np.count_nonzero(centered <= observed_null_distance) + 1.0) / (draws.size + 1.0)
    return TOSTResult(
        estimate,
        float(ci_low),
        float(ci_high),
        float(pvalue),
        margin,
        bool(ci_high < margin),
        n,
        n_dropped,
    )


def mcs(
    losses: pd.DataFrame,
    size: float = 0.10,
    reps: int = 1000,
    block_size: int | None = None,
    method: str = "R",
    bootstrap: str = "stationary",
    seed: Seed = 0,
) -> MCSResult:
    """Wrap the Hansen--Lunde--Nason MCS implementation in ``arch.bootstrap.MCS``."""

    if not isinstance(losses, pd.DataFrame):
        raise TypeError("losses must be a pandas DataFrame")
    complete = losses.replace([np.inf, -np.inf], np.nan).dropna(axis=0, how="any")
    if complete.shape[0] < 2 or complete.shape[1] < 2:
        raise ValueError("MCS requires at least two complete rows and two models")
    procedure = MCS(
        complete,
        size=size,
        reps=reps,
        block_size=block_size,
        method=method,
        bootstrap=bootstrap,
        seed=_rng(seed),
    )
    procedure.compute()
    pvalues = procedure.pvalues["Pvalue"].copy()
    pvalues.name = "pvalue"
    return MCSResult(list(procedure.included), list(procedure.excluded), pvalues)


def mde_analytic(
    n_origins: int,
    design_effect: float = 1.0,
    alpha: float = 0.05,
    power: float = 0.8,
) -> float:
    """Return two-sided analytic MDE in SD units using finite-sample t quantiles."""

    if n_origins <= 0 or design_effect <= 0.0:
        raise ValueError("n_origins and design_effect must be positive")
    if not 0.0 < alpha < 1.0 or not 0.0 < power < 1.0:
        raise ValueError("alpha and power must lie strictly between 0 and 1")
    effective_n = n_origins / design_effect
    degrees_freedom = max(2, math.floor(effective_n - 1.0))
    critical = t.ppf(1.0 - alpha / 2.0, degrees_freedom) + t.ppf(power, degrees_freedom)
    return float(critical / math.sqrt(effective_n))


def design_effect_overlap(h_days: int, step_days: int) -> float:
    """Return the overlap design effect ``1 + 2*sum(max(0,h-k*step)/h)``."""

    if h_days <= 0 or step_days <= 0:
        raise ValueError("h_days and step_days must be positive")
    k = np.arange(1, math.ceil(h_days / step_days), dtype="float64")
    overlap = np.maximum(0.0, h_days - k * step_days) / h_days
    return float(1.0 + 2.0 * overlap.sum())


def mde_empirical(
    d_series: object,
    block_len: int,
    B: int = 2000,
    seed: Seed = 0,
    alpha: float = 0.05,
    power: float = 0.8,
) -> float:
    """Return an empirical MDE from the moving-block bootstrap SE of mean loss differences."""

    values = np.asarray(d_series, dtype="float64").reshape(-1)
    values = values[np.isfinite(values)]
    if values.size < 2:
        return float("nan")
    draws = _bootstrap_statistics(values, lambda sample: float(np.mean(sample)), block_len, B, seed)
    standard_error = float(np.std(draws, ddof=1))
    degrees_freedom = max(2, values.size - 1)
    critical = t.ppf(1.0 - alpha / 2.0, degrees_freedom) + t.ppf(power, degrees_freedom)
    return float(critical * standard_error)

