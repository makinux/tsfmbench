# PREREGISTRATION — TimesFM 3.0 financial-practice benchmark (English translation)

> Courtesy translation. The Japanese original, [PREREGISTRATION.md](PREREGISTRATION.md), is the frozen, authoritative version; in case of any discrepancy the Japanese text governs.

Created 2026-09-01 (frozen before the production run; subsequent changes are append-only and must state a reason).

## 1. Scope of claims (copied verbatim into the report's first sentence)

This benchmark decides only whether **the TimesFM 3.0 configurations specified below beat this panel's practical baselines on the specified tasks and windows**. It makes no claim about time-series foundation models (TSFMs) in general, nor about commercial adoption (the weights are under a non-commercial license).

**Pre-commitment on contamination**: TimesFM 3.0's training-data cutoff is undisclosed (released 2026-08-28), so the main test window (2025-01-02 to 2026-08-31) may be inside its training data. Therefore, **if TimesFM wins on the main window, we do not report that as evidence of forecasting capability**. Strong information comes only from (a) losses on the main window, (b) the clean window (2026-08-31 onward, rerun monthly), and (c) synthetic-DGP / surrogate experiments.

## 2. Subject models (frozen)

| Model name | Definition |
|---|---|
| `TimesFM3-raw` | `google/timesfm-3.0-pytorch` fed the target series as-is |
| `TimesFM3-log` | log-transformed input; the exp back-transform uses a smearing correction from **pre-origin residuals only** |
| `TimesFM3-JGB-cov` (secondary) | each JGB tenor predicted with the other five tenors as past covariates |

- Context length (frozen): `min(len(context), 2048)` for RV and daily series; 1024 for crypto RV
- Quantiles: the native 9 quantiles (0.1–0.9). Point forecasts: separate mean and median (=q50) columns
- Checkpoint revision/hash and the full `ForecastConfig` are recorded with the results
- raw / log are **reported as two separate models**; choosing one after seeing test results is prohibited

## 3. Series panel (frozen)

- FX: 8 ECB EUR legs (EURUSD, EURJPY, EURGBP, EURCHF, EURAUD; reported separately as managed/intervened currencies: EURCNY, EURKRW, EURMXN)
- Rates: JGB 2/5/10/20/30/40y (evaluated in bp differences)
- Equity: Nikkei 225 (open-to-close track)
- Crypto: BTC, ETH, SOL, XRP, ADA, DOGE, LTC, LINK (Coinbase; XRP re-listed 2023-08, short history recorded in meta)
- RV: crypto = realized variance from 5-min candles (depth back to 2020 verified on 2026-09-01); Nikkei = Garman-Klass
- Volume: crypto only, series named `Coinbase {X}-USD base volume`
- DVOL: BTC and ETH (Deribit; depth from 2022-01 verified on 2026-09-01 → **adopted**)

## 4. Tasks, metrics, tests (frozen)

- **Task P**: TOST non-inferiority (margin: relative MAE vs RW of 1.05) is the primary frame for FX, equity, and crypto. Superiority testing for JGB only. h=1/5/20, origins every 5 business days. Direction via Pesaran–Timmermann (descriptive)
- **Task V**: RV-only track. QLIKE (positive link mandatory; non-positive forecasts counted as failures) + MSE/MAE. h=1 (daily, full probabilistic evaluation), h=5 (5-day sums, non-overlapping origins, full probabilistic evaluation), h=22 (22-day sums, non-overlapping origins, **point QLIKE only, descriptive**). Summing quantiles across horizons is prohibited outright
- **Task U**: log1p volume. SeasonalNaive(7) / SeasonalMedian(4 same weekdays) / MSTL / AutoETS / AutoTheta / LightGBM. Prophet is reference-only
- **Primary comparisons (the only tested family, Holm-corrected)**: per task×h, `TimesFM3-raw` vs the benchmark (P: RW / V: EWMA(0.94) / U: SeasonalNaive(7))
- DM: Newey–West automatic bandwidth (floor 0, selected lag reported), HLN with h in **origin units**. Cross-series inference is two-stage (per-series mean loss diff → sign test + moving-block bootstrap)
- MCS (per task×h, B=1000, α=0.10) as a secondary analysis
- Calibration: 80% coverage (overall + by volatility tercile); q10 as 10% VaR with Kupiec + Christoffersen (BTC/ETH/Nikkei)
- **Pre-run MDE**: minimum detectable effects computed from the origin schedule via block bootstrap and published before running; cells whose 80%-power MDE exceeds a 10% ratio-to-benchmark are demoted to descriptive in advance

## 5. Baseline panel (frozen)

RW / SeasonalNaive / EWMA(λ=0.94) / GARCH(1,1) / GJR-GARCH (Nikkei only) / HAR-RV / AutoETS / AutoTheta / LightGBM (mlforecast, conformal intervals) / DVOL regression (BTC & ETH, log RV_{t+h} = a + b·log DVOL_t) / Prophet (reference-only).

- Fitted models use **fixed-width rolling estimation as the main analysis**: crypto 1000 calendar days / Nikkei 400 business days / FX & JGB 1250 business days. Expanding windows are a sensitivity analysis
- All hyperparameters, features, n_windows etc. are **decided only on the development window (through 2024-12-31) and frozen**; final values are appended to §7 before the production run
- GARCH is estimated on open-to-close returns to match the target (close-to-close is a sensitivity track). Squaring return quantiles into RV quantiles is prohibited. GARCH/HAR quantiles are calibrated from pre-origin residuals

### 5.1 Operational details (pre-frozen 2026-09-01, synced with the implementation spec)

- Task V h=1 uses **daily origins** (for power and calibration curves); h=5/h=22 use non-overlapping sum origins. Fitted models **re-estimate every 5 business days** and filter with the latest data in between
- GARCH/EWMA/Naive RV quantiles are calibrated from the empirical quantiles of (forecast variance, realized RV) ratios within the pre-origin rolling window (no quantiles if fewer than 60 pairs). Squaring return quantiles into RV quantiles is prohibited at the implementation level
- HAR / DVOL regression / LightGBM (RV & volume) are estimated in log space; mean = smearing-corrected exp(μ̂+σ̂²/2), median = exp(μ̂), quantiles from empirical residuals
- LightGBM uses two objectives (L2 → mean column, quantile α=0.5 → median column) + conformal (n_windows=10) applied to the median model
- TimesFM3-log smearing σ̂² is estimated per series on the development window (≤2024-12-31) and frozen
- The DVOL regressor is x = log((DVOL/100)²/365) (daily-variance scale)
- Initial hyperparameters (finalized on the dev window and copied to §7): LightGBM num_leaves=31, lr=0.05, n_estimators=300, min_child_samples=20

## 6. Windows (frozen)

- Development window (tuning, pilot, implementation checks): through 2024-12-31. **Excluded from the final evaluation**
- Main test window: 2025-01-02 to 2026-08-31
- Clean window: origins from 2026-09-01 onward. Monthly reruns (first meaningful read around 2026-12)

## 7. Values frozen on the development window (appended before production)

(After implementation, record the final LightGBM hyperparameters, feature list, conformal n_windows, fixed window widths, and the TimesFM ForecastConfig here before the production run.)

## 8. Deviation log

(Any design change after the production run starts is appended here with date and reason.)

- 2026-09-01: TimesFM3-log smearing σ² changed from the dev-window Δlog variance to a per-forecast estimate from the model's own log-quantile spread ((q90−q10)/2.5631), with the previous method as fallback. Reason: the Δlog variance is an inflated proxy for the model's residual variance and therefore an inaccurate retransformation-bias correction. TimesFM3-log had not been run at this point; this is not a change made after seeing test-window results.

### Stage 3 implementation-frozen values (2026-09-01; PREREGISTRATION section 7)

- LightGBM: `num_leaves=31`, `learning_rate=0.05`, `n_estimators=300`, `min_child_samples=20`.
- MLForecast conformal configuration: median/quantile-objective model, `PredictionIntervals(n_windows=10)`, central levels `[20, 40, 60, 80]`.
- LightGBM features: lags `1..14, 21, 28`, rolling means `7, 28`, weekday, month, and month-end flag.
- TimesFM 3: `per_core_batch_size=8`; RV context 1024; other contexts at most 2048; quantiles 0.1 through 0.9; offline checkpoint `google/timesfm-3.0-pytorch` (revision recorded per run).
