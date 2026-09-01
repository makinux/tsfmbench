"""Stage 4 aggregation, statistical comparison, diagnostics, and reports."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from tsfmbench import metrics, stattests
from tsfmbench.backtest import DEFAULT_FORECAST_DIR, ForecastStore
from tsfmbench.data.transforms import h_sum_series
from tsfmbench.mde import OriginSchedule as MDEOriginSchedule
from tsfmbench.mde import build_mde_rows
from tsfmbench.tasks import DEFAULT_TASKS_DIR, horizon_config, load_task_config

DEFAULT_PROCESSED_DIR = Path("data/processed")
DEFAULT_REPORT_DIR = Path("results/report")
SEED = 20260901
QUANTILE_COLUMNS = tuple(f"q{value}" for value in range(10, 100, 10))
PRIMARY_MODEL = "TimesFM3-raw"
SPECIAL_SERIES = {"EURCNY", "EURKRW", "EURMXN"}
BROKEN_BASELINE_RATIO_THRESHOLD = 5.0
BROKEN_BASELINE_FAIL_RATE_THRESHOLD = 0.40

LEADERBOARD_RATIO_LEGEND = "凡例: ratio < 1 が基準より良い。"
PRIMARY_DIFFERENCE_LEGEND = (
    "符号凡例: d = TimesFM の損失 − 基準モデルの損失。"
    "mean dbar < 0 は TimesFM の損失が基準より小さい（勝ち）方向、> 0 は負け方向。"
)
DM_SIGN_LEGEND = (
    "符号凡例: DM 検定の d = TimesFM の損失 − 基準モデルの損失。"
    "DM stat < 0 は TimesFM の損失が基準より小さい（勝ち）方向、> 0 は負け方向。"
)
BROKEN_BASELINE_NOTE = (
    "† 自動注記（機械的判定閾値: median ratio > 5 または fail率 > 40%）: "
    "この構成のこのタスクへの適用は不適切であることが実行結果から判明した"
    "（例: グローバル LightGBM をスケールの異なる価格レベルに適用）。"
    "事前登録により本番後の再設定は行わない。このモデルのこのタスクでの数値は"
    "『誤設定ベースライン』として解釈し、モデル一般の能力の証拠としないこと。"
)

CLAIM_SCOPE = (
    "本ベンチマークが判定するのは「**TimesFM 3.0 の下記指定構成が、本パネルの実務"
    "ベースラインに、指定タスク・指定窓で勝つか**」のみである。TSFM（時系列基盤"
    "モデル）一般の優劣、および商用導入可否（重みは非商用ライセンス）には及ばない。"
)
MAIN_DISCLAIMER = (
    "学習済みの可能性があるため、本窓での TimesFM の勝ちは能力の証拠として報告しない。"
)
DEV_DISCLAIMER = "開発窓 — 最終評価から除外、技術検証のみ。"


def _finite(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, np.ndarray, pd.Index)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (pd.Timestamp, Path)):
        return str(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return _finite(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def _fmt(value: Any) -> str:
    if value is None:
        return "NA"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.6g}" if math.isfinite(value) else "NA"
    if isinstance(value, Mapping):
        return ", ".join(f"{key}={_fmt(item)}" for key, item in value.items()) or "—"
    if isinstance(value, (list, tuple)):
        return ", ".join(_fmt(item) for item in value) or "—"
    return str(value).replace("|", "\\|").replace("\n", " ")


def _markdown_table(rows: Sequence[Mapping[str, Any]], columns: Sequence[tuple[str, str]]) -> list[str]:
    headers = [label for _, label in columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    if not rows:
        lines.append("| " + " | ".join(["—", *("NA" for _ in headers[1:])]) + " |")
        return lines
    for row in rows:
        lines.append("| " + " | ".join(_fmt(row.get(key)) for key, _ in columns) + " |")
    return lines


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_run_id(
    forecast_dir: Path | str,
    task: str,
    window: str,
    run_id: str | None = None,
) -> str:
    """Resolve the newest matching manifest, or validate an explicit run id."""

    root = Path(forecast_dir)
    if run_id is not None:
        manifest = root / f"manifest_{run_id}.json"
        if manifest.exists():
            payload = _read_json(manifest)
            if payload.get("task") not in (None, task):
                raise ValueError(f"run {run_id!r} belongs to task {payload.get('task')!r}")
            if payload.get("window") not in (None, window):
                raise ValueError(f"run {run_id!r} belongs to window {payload.get('window')!r}")
        return run_id

    candidates: list[tuple[str, str]] = []
    for path in root.glob("manifest_*.json") if root.exists() else []:
        try:
            payload = _read_json(path)
        except (json.JSONDecodeError, OSError):
            continue
        if payload.get("task") == task and payload.get("window") == window:
            candidates.append((str(payload.get("created_at", path.stat().st_mtime_ns)), str(payload["run_id"])))
    if candidates:
        return max(candidates)[1]

    task_root = root / task
    directories = [path for path in task_root.iterdir() if path.is_dir()] if task_root.exists() else []
    if len(directories) == 1:
        return directories[0].name
    raise FileNotFoundError(f"no forecast run found for task={task}, window={window}")


def _normalized_panel(processed: pd.DataFrame, config: Mapping[str, Any]) -> pd.DataFrame:
    value = str(config.get("value_column", "y"))
    required = {"unique_id", "ds", value}
    missing = required.difference(processed.columns)
    if missing:
        raise ValueError(f"processed panel missing columns: {sorted(missing)}")
    panel = processed.loc[:, ["unique_id", "ds", value]].rename(columns={value: "actual"}).copy()
    panel["unique_id"] = panel["unique_id"].astype(str)
    panel["ds"] = pd.to_datetime(panel["ds"], errors="coerce").dt.tz_localize(None)
    panel["actual"] = pd.to_numeric(panel["actual"], errors="coerce")
    panel = panel.loc[panel["unique_id"].isin(config["series"])].dropna(subset=["ds"])
    panel = panel.sort_values(["unique_id", "ds"]).drop_duplicates(["unique_id", "ds"], keep="last")
    if config.get("transform") == "log1p":
        panel["actual"] = np.log1p(panel["actual"])
    panel["vol_proxy"] = panel.groupby("unique_id", sort=False)["actual"].transform(
        lambda values: values.diff().rolling(21, min_periods=1).std(ddof=0).fillna(0.0)
    )
    return panel.reset_index(drop=True)


def build_actuals(
    processed: pd.DataFrame,
    forecasts: pd.DataFrame,
    task_config: str | Path | Mapping[str, Any],
) -> pd.DataFrame:
    """Build actual targets keyed exactly like forecasts.

    Direct targets are a processed-panel ``(unique_id, ds_target)`` lookup.  RV
    sum targets call :func:`h_sum_series` on the post-origin slice with end
    alignment, so the realized block ends at the forecast target date.
    """

    config = load_task_config(task_config)
    panel = _normalized_panel(processed, config)
    keys = forecasts.loc[:, ["unique_id", "origin", "h", "ds_target"]].drop_duplicates().copy()
    keys["unique_id"] = keys["unique_id"].astype(str)
    keys["origin"] = pd.to_datetime(keys["origin"], errors="coerce").dt.tz_localize(None)
    keys["ds_target"] = pd.to_datetime(keys["ds_target"], errors="coerce").dt.tz_localize(None)
    direct = panel.rename(columns={"ds": "ds_target"})[
        ["unique_id", "ds_target", "actual", "vol_proxy"]
    ]
    result = keys.merge(direct, on=["unique_id", "ds_target"], how="left", validate="many_to_one")

    if config["task"] == "rv":
        by_id = {uid: group for uid, group in panel.groupby("unique_id", sort=False)}
        sum_horizons = {
            int(detail["h"])
            for detail in config["horizons"]
            if int(detail["h"]) > 1 and str(detail.get("target", "direct")) == "sum"
        }
        for index, row in result.loc[result["h"].astype(int).isin(sum_horizons)].iterrows():
            group = by_id.get(str(row["unique_id"]))
            if group is None:
                result.at[index, "actual"] = np.nan
                continue
            future = group.loc[
                (group["ds"] > row["origin"]) & (group["ds"] <= row["ds_target"]),
                ["unique_id", "ds", "actual"],
            ].rename(columns={"actual": "y"})
            blocks = h_sum_series(future, int(row["h"]), alignment="end")
            match = blocks.loc[pd.to_datetime(blocks["block_end_ds"]) == row["ds_target"]]
            result.at[index, "actual"] = float(match["y"].iloc[-1]) if len(match) else np.nan
    return result


build_actual_targets = build_actuals


def join_forecasts_actuals(
    forecasts: pd.DataFrame,
    processed: pd.DataFrame,
    task_config: str | Path | Mapping[str, Any],
) -> pd.DataFrame:
    """Join forecasts to processed actuals and attach the canonical row loss."""

    config = load_task_config(task_config)
    actuals = build_actuals(processed, forecasts, config)
    key = ["unique_id", "origin", "h", "ds_target"]
    result = forecasts.copy()
    for column in ("origin", "ds_target"):
        result[column] = pd.to_datetime(result[column], errors="coerce").dt.tz_localize(None)
    result["unique_id"] = result["unique_id"].astype(str)
    result = result.merge(actuals, on=key, how="left", validate="many_to_one")

    panel = _normalized_panel(processed, config)
    at_origin = panel.rename(columns={"ds": "origin", "actual": "origin_actual"})[
        ["unique_id", "origin", "origin_actual"]
    ]
    result = result.merge(at_origin, on=["unique_id", "origin"], how="left", validate="many_to_one")
    result["yhat_mean"] = pd.to_numeric(result["yhat_mean"], errors="coerce")
    stored_fail = result["fail"].fillna(False).astype(bool)
    reason = result["fail_reason"].fillna("").astype(str)
    missing_actual = ~np.isfinite(result["actual"])
    missing_forecast = ~np.isfinite(result["yhat_mean"])
    if config["task"] == "rv":
        nonpositive = (result["actual"] <= 0.0) | (result["yhat_mean"] <= 0.0)
    else:
        nonpositive = pd.Series(False, index=result.index)
    result["evaluation_fail"] = stored_fail | missing_actual | missing_forecast | nonpositive
    reason = reason.mask((reason == "") & nonpositive, "nonpositive_forecast")
    reason = reason.mask((reason == "") & missing_actual, "missing_actual")
    reason = reason.mask((reason == "") & missing_forecast, "missing_forecast")
    result["evaluation_fail_reason"] = reason.mask(~result["evaluation_fail"], "")

    valid = ~result["evaluation_fail"]
    result["error"] = np.nan
    result["loss"] = np.nan
    result["loss_metric"] = "qlike" if config["task"] == "rv" else "mae"
    if valid.any():
        actual = result.loc[valid, "actual"].to_numpy(dtype="float64")
        forecast = result.loc[valid, "yhat_mean"].to_numpy(dtype="float64")
        if config["task"] == "rv":
            result.loc[valid, "loss"] = metrics.qlike_losses(actual, forecast)
            result.loc[valid, "error"] = forecast - actual
        else:
            scale = np.where(result.loc[valid, "unique_id"].str.startswith("JGB_"), 100.0, 1.0)
            result.loc[valid, "loss"] = metrics.absolute_errors(actual, forecast) * scale
            result.loc[valid, "error"] = (forecast - actual) * scale
    return result


join_actuals = join_forecasts_actuals


def series_group(unique_id: str) -> str:
    """Return the preregistered broad asset group for a series id."""

    uid = str(unique_id)
    if uid.startswith("JGB_"):
        return "rates"
    if uid in {"N225", "RV_N225_GK"}:
        return "equity"
    if uid.startswith("EUR"):
        return "fx"
    return "crypto"


def is_special_series(unique_id: str) -> bool:
    uid = str(unique_id)
    return uid in SPECIAL_SERIES or "XRP" in uid


def _reference_models(store: ForecastStore, forecasts: pd.DataFrame) -> set[str]:
    references = {"Prophet"}
    if store.model_config_path.exists():
        payload = _read_json(store.model_config_path)
        for model, settings in payload.get("models", {}).items():
            if isinstance(settings, Mapping) and settings.get("reference") is True:
                references.add(str(model))
    return references.intersection(set(forecasts["model_variant"].astype(str)))


def _successful(data: pd.DataFrame, model: str) -> pd.DataFrame:
    return data.loc[
        (data["model_variant"].astype(str) == model)
        & ~data["evaluation_fail"]
        & np.isfinite(data["loss"])
    ].copy()


def _paired_losses(data: pd.DataFrame, model: str, benchmark: str) -> pd.DataFrame:
    key = ["unique_id", "origin"]
    left = _successful(data, model)[key + ["loss", "error"]].rename(
        columns={"loss": "loss_model", "error": "error_model"}
    )
    right = _successful(data, benchmark)[key + ["loss", "error"]].rename(
        columns={"loss": "loss_benchmark", "error": "error_benchmark"}
    )
    return left.merge(right, on=key, how="inner", validate="one_to_one")


def _series_ratios(data: pd.DataFrame, model: str, benchmark: str) -> pd.DataFrame:
    paired = _paired_losses(data, model, benchmark)
    rows: list[dict[str, Any]] = []
    for uid, group in paired.groupby("unique_id", sort=True):
        denominator = float(group["loss_benchmark"].mean())
        numerator = float(group["loss_model"].mean())
        source = data.loc[data["unique_id"].astype(str) == str(uid), "loss_metric"]
        if len(source) and source.iloc[0] == "mae":
            ratio = metrics.relative_mae(group["error_model"], group["error_benchmark"]).value
        else:
            ratio = numerator / denominator if denominator > 0.0 else np.nan
        rows.append(
            {
                "unique_id": str(uid),
                "model_loss": numerator,
                "benchmark_loss": denominator,
                "ratio": ratio,
                "dbar": float((group["loss_model"] - group["loss_benchmark"]).mean()),
                "n": len(group),
            }
        )
    return pd.DataFrame(rows, columns=["unique_id", "model_loss", "benchmark_loss", "ratio", "dbar", "n"])


def _runtime(data: pd.DataFrame, model: str) -> tuple[float | None, float | None]:
    batches = data.loc[data["model_variant"].astype(str) == model, ["origin", "runtime_s"]].copy()
    batches["runtime_s"] = pd.to_numeric(batches["runtime_s"], errors="coerce")
    batches = batches.dropna().drop_duplicates(["origin"])
    if batches.empty:
        return None, None
    return float(batches["runtime_s"].sum()), float(batches["runtime_s"].mean())


def _broken_baseline_flag(ratio_median: Any, fail_rate: Any) -> bool:
    """Apply the mechanical preregistered-result warning thresholds."""

    ratio = _finite(ratio_median)
    failures = _finite(fail_rate)
    return bool(
        (ratio is not None and ratio > BROKEN_BASELINE_RATIO_THRESHOLD)
        or (failures is not None and failures > BROKEN_BASELINE_FAIL_RATE_THRESHOLD)
    )


def _leaderboard_rows(data: pd.DataFrame, benchmark: str, models: Sequence[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for model in models:
        model_data = data.loc[data["model_variant"].astype(str) == model]
        ratios = _series_ratios(data, model, benchmark)
        values = ratios["ratio"].to_numpy(dtype="float64") if len(ratios) else np.array([])
        values = values[np.isfinite(values)]
        failures = model_data.loc[model_data["evaluation_fail"]]
        reasons = failures["evaluation_fail_reason"].replace("", "unspecified").value_counts().to_dict()
        runtime_total, runtime_mean = _runtime(data, model)
        ratio_median = float(np.median(values)) if values.size else None
        fail_rate = float(len(failures) / len(model_data)) if len(model_data) else None
        warning = _broken_baseline_flag(ratio_median, fail_rate)
        rows.append(
            {
                "model": model,
                "ratio_median": ratio_median,
                "ratio_mean": float(np.mean(values)) if values.size else None,
                "win_rate": float(np.mean(values < 1.0)) if values.size else None,
                "series_used": int(values.size),
                "fail_count": len(failures),
                "fail_rate": fail_rate,
                "n_used": int((~model_data["evaluation_fail"] & np.isfinite(model_data["loss"])).sum()),
                "fail_reasons": {str(key): int(value) for key, value in reasons.items()},
                "runtime_total_s": runtime_total,
                "runtime_per_origin_s": runtime_mean,
                "misconfiguration_warning": warning,
                "footnote_marker": "†" if warning else "",
            }
        )
    return rows


def _mde_context(config: Mapping[str, Any], h: int, n_origins: int) -> dict[str, Any]:
    detail = horizon_config(config, h)
    schedule = MDEOriginSchedule(
        str(config["task"]), h, int(detail.get("step", h)), max(1, n_origins), "observed report rows"
    )
    return dict(build_mde_rows([schedule])[0])


def _primary_test(
    data: pd.DataFrame,
    config: Mapping[str, Any],
    h: int,
    *,
    bootstrap_reps: int,
    seed: int,
) -> dict[str, Any]:
    benchmark = str(config["primary_benchmark"])
    ratios = _series_ratios(data, PRIMARY_MODEL, benchmark)
    values = ratios["dbar"].to_numpy(dtype="float64") if len(ratios) else np.array([])
    values = values[np.isfinite(values)]
    paired = _paired_losses(data, PRIMARY_MODEL, benchmark)
    n_origins = int(paired["origin"].nunique()) if len(paired) else 0
    mde = _mde_context(config, h, n_origins)
    if not values.size:
        return {
            "task": config["task"], "h": h, "model": PRIMARY_MODEL, "benchmark": benchmark,
            "status": "missing comparison data", "series_count": 0, "sign_pvalue": None,
            "bootstrap_ci_low": None, "bootstrap_ci_high": None, "bootstrap_pvalue": None,
            "standardized_effect": None, "mde_sd": mde["mde_sd"], "power_note": "判別不能",
        }
    sign = stattests.sign_test(values)
    boot = stattests.moving_block_bootstrap(
        values, np.mean, block_len=1, B=bootstrap_reps, seed=seed
    )
    standard_deviation = float(np.std(values, ddof=1)) if values.size > 1 else np.nan
    effect = float(np.mean(values) / standard_deviation) if standard_deviation > 0.0 else np.nan
    underpowered = not np.isfinite(effect) or abs(effect) < float(mde["mde_sd"])
    return {
        "task": str(config["task"]),
        "h": int(h),
        "model": PRIMARY_MODEL,
        "benchmark": benchmark,
        "status": "ok",
        "series_count": int(values.size),
        "mean_dbar": float(np.mean(values)),
        "sign_stat": sign.stat,
        "sign_pvalue": sign.pvalue,
        "sign_n": sign.n,
        "bootstrap_estimate": boot.estimate,
        "bootstrap_ci_low": boot.ci_low,
        "bootstrap_ci_high": boot.ci_high,
        "bootstrap_pvalue": boot.pvalue,
        "standardized_effect": effect,
        "mde_sd": float(mde["mde_sd"]),
        "mde_n_origins": int(mde["n_origins"]),
        "power_note": "検出力不足 — 判別不能" if underpowered else "MDE 以上",
    }


def _mcs_result(
    data: pd.DataFrame,
    models: Sequence[str],
    *,
    reps: int,
    seed: int,
    required_series: Sequence[str] | None = None,
) -> dict[str, Any]:
    target_series = (
        sorted({str(value) for value in required_series})
        if required_series is not None
        else sorted(data["unique_id"].dropna().astype(str).unique())
    )
    required_set = set(target_series)
    universe: list[str] = []
    partial: list[dict[str, str]] = []
    for model in models:
        covered = set(_successful(data, model)["unique_id"].astype(str).unique())
        missing = sorted(required_set.difference(covered))
        if missing:
            partial.append(
                {
                    "model": str(model),
                    "reason": "successful coverage missing for: " + ", ".join(missing),
                }
            )
        else:
            universe.append(str(model))

    context: dict[str, Any] = {
        "mcs_universe": universe,
        "excluded_partial_coverage": partial,
    }
    if len(universe) < 2:
        return {
            **context,
            "status": "insufficient data",
            "skip_reason": "fewer than two full-coverage models",
            "origin_count": 0,
            "common_rows": 0,
            "included": [],
        }

    clean = data.loc[
        data["model_variant"].astype(str).isin(universe)
        & ~data["evaluation_fail"]
        & np.isfinite(data["loss"])
    ]
    matrix = clean.pivot(index=["unique_id", "origin"], columns="model_variant", values="loss")
    matrix = matrix.reindex(columns=universe).dropna(axis=0, how="any")
    origin_count = (
        int(matrix.index.get_level_values("origin").nunique()) if matrix.shape[0] else 0
    )
    if origin_count < 30:
        return {
            **context,
            "status": "insufficient data",
            "skip_reason": "fewer than 30 common origins",
            "origin_count": origin_count,
            "common_rows": int(matrix.shape[0]),
            "included": [],
        }
    try:
        result = stattests.mcs(matrix, size=0.10, reps=reps, seed=seed)
    except (ValueError, RuntimeError, np.linalg.LinAlgError) as exc:
        return {
            **context,
            "status": f"failed: {exc}", "origin_count": origin_count,
            "common_rows": int(matrix.shape[0]), "included": [],
        }
    return {
        **context,
        "status": "ok",
        "origin_count": origin_count,
        "common_rows": int(matrix.shape[0]),
        "included": [str(value) for value in result.included],
        "excluded": [str(value) for value in result.excluded],
        "pvalues": {str(key): float(value) for key, value in result.pvalues.items()},
    }


def _probabilistic_full(config: Mapping[str, Any], h: int) -> bool:
    detail = horizon_config(config, h)
    sub = config.get("sub_horizons", {}).get(str(detail.get("name", f"h{h}")), {})
    value = sub.get("probabilistic", detail.get("probabilistic", False))
    return value == "full" or value is True


def _calibration(
    data: pd.DataFrame,
    config: Mapping[str, Any],
    h: int,
    models: Sequence[str],
) -> dict[str, Any]:
    coverage_rows: list[dict[str, Any]] = []
    wql_rows: list[dict[str, Any]] = []
    var_rows: list[dict[str, Any]] = []
    for model in models:
        frame = data.loc[
            (data["model_variant"].astype(str) == model) & ~data["evaluation_fail"]
        ].sort_values(["unique_id", "origin"])
        interval = frame.dropna(subset=["actual", "q10", "q90", "vol_proxy"])
        if len(interval):
            overall = metrics.coverage(interval["actual"], interval["q10"], interval["q90"])
            terciles = metrics.coverage_by_tercile(
                interval["actual"], interval["q10"], interval["q90"], interval["vol_proxy"]
            )
            coverage_rows.append(
                {
                    "model": model,
                    "overall": overall.value,
                    "low": terciles.loc["low", "value"],
                    "middle": terciles.loc["middle", "value"],
                    "high": terciles.loc["high", "value"],
                    "n_used": overall.n_used,
                    "tercile_shape": list(terciles.shape),
                }
            )
        quantiles = frame.dropna(subset=["actual", *QUANTILE_COLUMNS])
        if len(quantiles):
            result = metrics.wql(quantiles["actual"], quantiles.loc[:, QUANTILE_COLUMNS])
            wql_rows.append({"model": model, "wql": result.value, "n_used": result.n_used})

        if config["task"] == "rv" and h == 1:
            for uid in ("RV_BTC", "RV_ETH", "RV_N225_GK"):
                selected = frame.loc[frame["unique_id"] == uid].dropna(subset=["actual", "q10"])
                if selected.empty:
                    continue
                violations = (selected["actual"].to_numpy() < selected["q10"].to_numpy()).astype(int)
                kupiec = stattests.kupiec_pof(int(violations.sum()), len(violations), 0.10)
                christoffersen = stattests.christoffersen(violations, 0.10)
                var_rows.append(
                    {
                        "model": model, "unique_id": uid, "n": len(violations),
                        "violations": int(violations.sum()), "kupiec_pvalue": kupiec.pvalue,
                        "christoffersen_ind_pvalue": christoffersen.pvalue_ind,
                        "christoffersen_cc_pvalue": christoffersen.pvalue_cc,
                        "reason": christoffersen.reason,
                    }
                )
    return {"coverage": coverage_rows, "wql": wql_rows, "var_tests": var_rows}


def _task_p_tables(
    data_by_h: Mapping[int, pd.DataFrame],
    config: Mapping[str, Any],
    models: Sequence[str],
    *,
    bootstrap_reps: int,
    seed: int,
) -> dict[str, Any]:
    benchmark = str(config["primary_benchmark"])
    tost_rows: list[dict[str, Any]] = []
    dm_rows: list[dict[str, Any]] = []
    pt_rows: list[dict[str, Any]] = []
    for h, data in data_by_h.items():
        for group in ("fx", "equity", "crypto"):
            selected = data.loc[data["unique_id"].map(series_group) == group]
            paired = _paired_losses(selected, PRIMARY_MODEL, benchmark)
            if len(paired):
                result = stattests.tost_relative_mae(
                    paired["error_model"], paired["error_benchmark"], margin=1.05,
                    block_len=max(1, min(h, len(paired))), B=bootstrap_reps, seed=seed,
                )
                tost_rows.append({"h": h, "group": group, **asdict(result)})
        rates = data.loc[data["unique_id"].map(series_group) == "rates"]
        for uid in sorted(rates["unique_id"].unique()):
            paired = _paired_losses(rates.loc[rates["unique_id"] == uid], PRIMARY_MODEL, benchmark)
            if len(paired):
                detail = horizon_config(config, h)
                result = stattests.dm_test(
                    paired["loss_model"], paired["loss_benchmark"],
                    h_origin=max(1, math.ceil(h / int(detail.get("step", h)))),
                )
                dm_rows.append({"h": h, "unique_id": uid, **asdict(result)})

        for model in models:
            successful = _successful(data, model)
            for group, selected in successful.groupby(successful["unique_id"].map(series_group)):
                actual_direction = selected["actual"] - selected["origin_actual"]
                predicted_direction = selected["yhat_mean"] - selected["origin_actual"]
                result = stattests.pt_test(actual_direction, predicted_direction)
                pt_rows.append({"h": h, "model": model, "group": group, **asdict(result)})
    return {"tost": tost_rows, "jgb_dm": dm_rows, "pesaran_timmermann": pt_rows}


def _diagnostics(
    data_by_h: Mapping[int, pd.DataFrame], benchmark: str, models: Sequence[str]
) -> dict[str, Any]:
    halves: list[dict[str, Any]] = []
    groups: list[dict[str, Any]] = []
    special: list[dict[str, Any]] = []
    for h, data in data_by_h.items():
        main_data = data.loc[~data["unique_id"].map(is_special_series)]
        origins = sorted(pd.DatetimeIndex(main_data["origin"].dropna().unique()))
        midpoint = len(origins) // 2
        periods = {"first_half": set(origins[:midpoint]), "second_half": set(origins[midpoint:])}
        for label, period_origins in periods.items():
            selected = main_data.loc[main_data["origin"].isin(period_origins)]
            for model in models:
                ratios = _series_ratios(selected, model, benchmark)
                values = ratios["ratio"].to_numpy(dtype="float64") if len(ratios) else np.array([])
                values = values[np.isfinite(values)]
                halves.append(
                    {
                        "h": h, "period": label, "model": model,
                        "win_rate": float(np.mean(values < 1.0)) if values.size else None,
                        "ratio_median": float(np.median(values)) if values.size else None,
                        "series_used": int(values.size),
                    }
                )
        for group in ("fx", "rates", "equity", "crypto"):
            selected = main_data.loc[main_data["unique_id"].map(series_group) == group]
            for model in models:
                ratios = _series_ratios(selected, model, benchmark)
                values = ratios["ratio"].to_numpy(dtype="float64") if len(ratios) else np.array([])
                values = values[np.isfinite(values)]
                groups.append(
                    {
                        "h": h, "group": group, "model": model,
                        "ratio_median": float(np.median(values)) if values.size else None,
                        "ratio_mean": float(np.mean(values)) if values.size else None,
                        "win_rate": float(np.mean(values < 1.0)) if values.size else None,
                        "series_used": int(values.size),
                    }
                )
        special_data = data.loc[data["unique_id"].map(is_special_series)]
        for uid in sorted(special_data["unique_id"].unique()):
            for model in models:
                ratios = _series_ratios(special_data.loc[special_data["unique_id"] == uid], model, benchmark)
                ratio = _finite(ratios["ratio"].iloc[0]) if len(ratios) else None
                special.append({"h": h, "unique_id": uid, "model": model, "ratio": ratio})
    return {"half_split": halves, "group_breakdown": groups, "special_series": special}


def _timesfm3_log_coverage_notes(
    leaderboards: Mapping[str, Sequence[Mapping[str, Any]]],
) -> list[dict[str, Any]]:
    """Explain TimesFM3-log series-count gaps backed by invalid-context failures."""

    notes: list[dict[str, Any]] = []
    for horizon, rows in leaderboards.items():
        log_row = next((row for row in rows if row.get("model") == "TimesFM3-log"), None)
        if log_row is None:
            continue
        other_counts = [
            int(row.get("series_used", 0))
            for row in rows
            if row.get("model") != "TimesFM3-log"
        ]
        comparison_count = max(other_counts, default=int(log_row.get("series_used", 0)))
        series_count = int(log_row.get("series_used", 0))
        reasons = log_row.get("fail_reasons", {})
        invalid_count = int(reasons.get("invalid_context", 0)) if isinstance(reasons, Mapping) else 0
        if series_count == comparison_count or invalid_count == 0:
            continue
        notes.append(
            {
                "h": int(str(horizon).removeprefix("h")),
                "model": "TimesFM3-log",
                "series_used": series_count,
                "other_model_max_series": comparison_count,
                "invalid_context_fail_count": invalid_count,
                "reason": (
                    f"fail_reasons=invalid_context が {invalid_count} 件。"
                    "log 定義不能（非正値を含む金利系列等）のコンテキストは失敗会計となるため。"
                ),
            }
        )
    return notes


def _manifest_reconciliation(store: ForecastStore, forecasts: pd.DataFrame) -> dict[str, Any]:
    actual = {str(key): int(value) for key, value in forecasts.groupby("model_variant").size().items()}
    if not store.manifest_path.exists():
        return {"status": "manifest missing", "expected": {}, "actual": actual, "rows": []}
    payload = _read_json(store.manifest_path)
    expected = {str(key): int(value) for key, value in payload.get("expected_rows", {}).items()}
    models = sorted(set(expected) | set(actual))
    rows = [
        {
            "model": model, "expected_rows": expected.get(model, 0),
            "actual_rows": actual.get(model, 0), "match": expected.get(model, 0) == actual.get(model, 0),
        }
        for model in models
    ]
    return {"status": "ok" if expected == actual else "mismatch", "expected": expected, "actual": actual, "rows": rows}


def _write_plots(
    output: Path,
    data_by_h: Mapping[int, pd.DataFrame],
    config: Mapping[str, Any],
    models: Sequence[str],
) -> list[str]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plot_dir = output / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []

    calibration_points: dict[str, list[tuple[float, float]]] = {model: [] for model in models}
    for data in data_by_h.values():
        for model in models:
            frame = data.loc[
                (data["model_variant"].astype(str) == model) & ~data["evaluation_fail"]
            ]
            for lower in range(10, 50, 10):
                upper = 100 - lower
                complete = frame.dropna(subset=["actual", f"q{lower}", f"q{upper}"])
                if len(complete):
                    observed = metrics.coverage(
                        complete["actual"], complete[f"q{lower}"], complete[f"q{upper}"]
                    ).value
                    calibration_points[model].append(((upper - lower) / 100.0, observed))
    if any(calibration_points.values()):
        fig, axis = plt.subplots(figsize=(6.4, 4.8))
        axis.plot([0, 1], [0, 1], "--", color="0.5", label="ideal")
        for model, points in calibration_points.items():
            if points:
                grouped = pd.DataFrame(points, columns=["nominal", "observed"]).groupby("nominal").mean()
                axis.plot(grouped.index, grouped["observed"], marker="o", label=model)
        axis.set(xlabel="Nominal coverage", ylabel="Observed coverage", xlim=(0, 1), ylim=(0, 1))
        axis.legend(fontsize="small")
        fig.tight_layout()
        path = plot_dir / "calibration.png"
        fig.savefig(path, dpi=150)
        plt.close(fig)
        paths.append(path.relative_to(output).as_posix())

    if config["task"] == "rv":
        ratio_values: list[np.ndarray] = []
        labels: list[str] = []
        benchmark = str(config["primary_benchmark"])
        for h, data in data_by_h.items():
            for model in models:
                ratios = _series_ratios(data, model, benchmark)
                values = (
                    ratios["ratio"].dropna().to_numpy(dtype="float64")
                    if len(ratios)
                    else np.array([])
                )
                if values.size:
                    ratio_values.append(values)
                    labels.append(f"{model} h={h}")
        if ratio_values:
            fig, axis = plt.subplots(figsize=(max(6.4, len(labels) * 0.8), 4.8))
            axis.boxplot(ratio_values, tick_labels=labels)
            axis.axhline(1.0, linestyle="--", color="0.5")
            axis.set(ylabel="Per-series QLIKE ratio vs EWMA")
            axis.tick_params(axis="x", rotation=35)
            fig.tight_layout()
            path = plot_dir / "qlike_ratio_distribution.png"
            fig.savefig(path, dpi=150)
            plt.close(fig)
            paths.append(path.relative_to(output).as_posix())

    benchmark = str(config["primary_benchmark"])
    time_rows: list[pd.DataFrame] = []
    for h, data in data_by_h.items():
        paired = _paired_losses(data, PRIMARY_MODEL, benchmark)
        if len(paired):
            series = paired.assign(d=lambda frame: frame["loss_model"] - frame["loss_benchmark"])
            series = series.groupby("origin", as_index=False)["d"].mean().assign(h=h)
            time_rows.append(series)
    if time_rows:
        fig, axis = plt.subplots(figsize=(8, 4.8))
        for h, frame in pd.concat(time_rows).groupby("h"):
            axis.plot(frame["origin"], frame["d"], label=f"h={h}", linewidth=1)
        axis.axhline(0.0, linestyle="--", color="0.5")
        axis.set(xlabel="Origin", ylabel=f"Loss difference ({PRIMARY_MODEL} - {benchmark})")
        axis.legend()
        fig.autofmt_xdate()
        fig.tight_layout()
        path = plot_dir / "primary_loss_difference.png"
        fig.savefig(path, dpi=150)
        plt.close(fig)
        paths.append(path.relative_to(output).as_posix())
    return paths


def _render_markdown(summary: Mapping[str, Any]) -> str:
    lines = [CLAIM_SCOPE, ""]
    if summary["window"] == "main":
        lines.extend([MAIN_DISCLAIMER, ""])
    elif summary["window"] == "dev":
        lines.extend([DEV_DISCLAIMER, ""])
    lines.extend(
        [
            f"# {summary['task']} / {summary['window']} report",
            "",
            f"Run ID: `{summary['run_id']}`. 主指標: {summary['primary_metric']}.",
            "",
            "## リーダーボード",
            "",
            LEADERBOARD_RATIO_LEGEND,
            "",
        ]
    )
    leaderboard_columns = [
        ("model_display", "model"), ("ratio_median", "median ratio"), ("ratio_mean", "mean ratio"),
        ("win_rate", "win rate"), ("series_used", "series"), ("fail_count", "fail"),
        ("fail_rate", "fail rate"), ("n_used", "rows used"), ("fail_reasons", "fail reasons"),
        ("runtime_total_s", "runtime total (s)"),
        ("runtime_per_origin_s", "runtime/origin (s)"),
    ]
    tests = {int(row["h"]): row for row in summary["primary_tests"]}
    for horizon, rows in summary["leaderboards"].items():
        h = int(str(horizon).removeprefix("h"))
        display_rows = [
            {**row, "model_display": f"{row['model']}{row.get('footnote_marker', '')}"}
            for row in rows
        ]
        lines.extend(
            [f"### h={h}", "", *_markdown_table(display_rows, leaderboard_columns), ""]
        )
        if any(row.get("misconfiguration_warning") for row in rows):
            lines.extend([BROKEN_BASELINE_NOTE, ""])
        test = tests[h]
        lines.append(
            f"MDE footnote: MDE={_fmt(test.get('mde_sd'))} SD; "
            f"standardized effect={_fmt(test.get('standardized_effect'))}; {test.get('power_note')}."
        )
        mcs = summary["mcs"][horizon]
        lines.extend(
            [
                (
                    f"MCS: {mcs['status']}; origins={mcs['origin_count']}; "
                    f"mcs_universe={_fmt(mcs.get('mcs_universe', []))}; "
                    "excluded_partial_coverage="
                    f"{_fmt(mcs.get('excluded_partial_coverage', []))}; "
                    f"included={_fmt(mcs.get('included', []))}; "
                    f"pvalues={_fmt(mcs.get('pvalues', {}))}."
                ),
                "",
            ]
        )

    lines.extend(["## 主要比較の二段階検定", ""])
    lines.extend(
        _markdown_table(
            summary["primary_tests"],
            [
                ("h", "h"), ("model", "model"), ("benchmark", "benchmark"),
                ("mean_dbar", "mean dbar"), ("sign_pvalue", "sign p"),
                ("holm_pvalue", "Holm p"), ("bootstrap_ci_low", "bootstrap CI low"),
                ("bootstrap_ci_high", "bootstrap CI high"), ("bootstrap_pvalue", "bootstrap p"),
                ("power_note", "MDE context"),
            ],
        )
    )
    lines.extend(["", PRIMARY_DIFFERENCE_LEGEND, ""])

    if summary["calibration"]:
        lines.extend(["## 較正", ""])
        for horizon, section in summary["calibration"].items():
            lines.extend([f"### {horizon}: 80% coverage", ""])
            lines.extend(
                _markdown_table(
                    section["coverage"],
                    [
                        ("model", "model"), ("overall", "overall"), ("low", "low vol"),
                        ("middle", "middle vol"), ("high", "high vol"), ("n_used", "n"),
                    ],
                )
            )
            lines.extend(["", "WQL:", ""])
            lines.extend(_markdown_table(section["wql"], [("model", "model"), ("wql", "WQL"), ("n_used", "n")]))
            if section["var_tests"]:
                lines.extend(["", "q10 → 10% VaR:", ""])
                lines.extend(
                    _markdown_table(
                        section["var_tests"],
                        [
                            ("model", "model"), ("unique_id", "series"), ("n", "n"),
                            ("violations", "violations"), ("kupiec_pvalue", "Kupiec p"),
                            ("christoffersen_ind_pvalue", "Christoffersen ind p"),
                            ("christoffersen_cc_pvalue", "Christoffersen cc p"),
                        ],
                    )
                )
            lines.append("")

    if summary.get("task_p"):
        task_p = summary["task_p"]
        lines.extend(["## Task P 専用", "", "### TOST 非劣性（margin 1.05）", ""])
        lines.extend(
            _markdown_table(
                task_p["tost"],
                [
                    ("h", "h"), ("group", "group"), ("relative_mae", "relative MAE"),
                    ("ci_low", "CI low"), ("ci_high", "CI high"), ("pvalue", "p"),
                    ("noninferior", "noninferior"), ("n", "n"),
                ],
            )
        )
        lines.extend(["", "### JGB 優越 DM", ""])
        lines.extend(
            _markdown_table(
                task_p["jgb_dm"],
                [("h", "h"), ("unique_id", "series"), ("stat", "DM stat"), ("pvalue", "p"), ("n", "n")],
            )
        )
        lines.extend(["", DM_SIGN_LEGEND, "", "### Pesaran–Timmermann（記述的）", ""])
        lines.extend(
            _markdown_table(
                task_p["pesaran_timmermann"],
                [
                    ("h", "h"), ("model", "model"), ("group", "group"),
                    ("stat", "stat"), ("pvalue", "p"), ("hit_rate", "hit rate"), ("n", "n"),
                ],
            )
        )
        lines.append("")

    diagnostic = summary["diagnostics"]
    lines.extend(["## 診断", ""])
    if diagnostic.get("timesfm3_log_coverage"):
        lines.extend(["### TimesFM3-log 系列数差異", ""])
        lines.extend(
            _markdown_table(
                diagnostic["timesfm3_log_coverage"],
                [
                    ("h", "h"), ("model", "model"), ("series_used", "series"),
                    ("other_model_max_series", "other-model max series"),
                    ("invalid_context_fail_count", "invalid_context failures"),
                    ("reason", "reason"),
                ],
            )
        )
        lines.extend(["", "### 前半・後半", ""])
    else:
        lines.extend(["### 前半・後半", ""])
    lines.extend(
        _markdown_table(
            diagnostic["half_split"],
            [
                ("h", "h"), ("period", "period"), ("model", "model"),
                ("win_rate", "win rate"), ("ratio_median", "median ratio"),
                ("series_used", "series"),
            ],
        )
    )
    lines.extend(["", "### 系列グループ別", ""])
    lines.extend(
        _markdown_table(
            diagnostic["group_breakdown"],
            [
                ("h", "h"), ("group", "group"), ("model", "model"),
                ("ratio_median", "median ratio"), ("ratio_mean", "mean ratio"),
                ("win_rate", "win rate"), ("series_used", "series"),
            ],
        )
    )
    lines.extend(["", "### 管理通貨・XRP（本表から分離）", ""])
    lines.extend(
        _markdown_table(
            diagnostic["special_series"],
            [("h", "h"), ("unique_id", "series"), ("model", "model"), ("ratio", "ratio")],
        )
    )

    lines.extend(["", "## 参考別掲（reference=True、本表・勝率・MCS から除外）", ""])
    lines.extend(
        _markdown_table(
            summary["reference_models"],
            [
                ("h", "h"), ("model", "model"), ("ratio_median", "median ratio"),
                ("ratio_mean", "mean ratio"), ("fail_count", "fail"), ("n_used", "rows used"),
            ],
        )
    )

    lines.extend(["", "## Manifest 照合", "", f"Status: **{summary['manifest']['status']}**", ""])
    lines.extend(
        _markdown_table(
            summary["manifest"]["rows"],
            [
                ("model", "model"), ("expected_rows", "expected rows"),
                ("actual_rows", "actual rows"), ("match", "match"),
            ],
        )
    )
    lines.append("")
    return "\n".join(lines)


def generate_report(
    task: str | Mapping[str, Any],
    window: str,
    run_id: str | None = None,
    *,
    forecast_dir: Path | str = DEFAULT_FORECAST_DIR,
    processed_dir: Path | str = DEFAULT_PROCESSED_DIR,
    report_dir: Path | str = DEFAULT_REPORT_DIR,
    tasks_dir: Path | str = DEFAULT_TASKS_DIR,
    bootstrap_reps: int = 2000,
    mcs_reps: int = 1000,
    seed: int = SEED,
    make_plots: bool = True,
) -> dict[str, Any]:
    """Generate ``summary.md``, ``summary.json``, and plots for one task/window."""

    config = load_task_config(task, tasks_dir=tasks_dir)
    task_name = str(config["task"])
    if window not in config["windows"]:
        raise ValueError(f"unknown window {window!r}")
    selected_run = resolve_run_id(forecast_dir, task_name, window, run_id)
    store = ForecastStore(forecast_dir, run_id=selected_run, task=task_name)
    forecasts = store.read()
    if forecasts.empty:
        raise ValueError(f"forecast run {selected_run!r} has no rows")
    forecasts = forecasts.loc[
        (forecasts["run_id"].astype(str) == selected_run)
        & (forecasts["task"].astype(str) == task_name)
    ].copy()
    panel_path = Path(processed_dir) / f"{config['panel']}.parquet"
    if not panel_path.exists():
        raise FileNotFoundError(f"processed panel not found: {panel_path}")
    evaluated = join_forecasts_actuals(forecasts, pd.read_parquet(panel_path), config)
    references = _reference_models(store, forecasts)
    all_models = sorted(set(evaluated["model_variant"].astype(str)))
    models = [model for model in all_models if model not in references]
    benchmark = str(config["primary_benchmark"])
    if benchmark not in models:
        raise ValueError(f"primary benchmark {benchmark!r} is absent from run {selected_run!r}")

    data_by_h: dict[int, pd.DataFrame] = {}
    main_data_by_h: dict[int, pd.DataFrame] = {}
    leaderboards: dict[str, list[dict[str, Any]]] = {}
    primary_tests: list[dict[str, Any]] = []
    mcs_results: dict[str, dict[str, Any]] = {}
    calibration: dict[str, Any] = {}
    reference_rows: list[dict[str, Any]] = []
    main_series = [str(uid) for uid in config["series"] if not is_special_series(str(uid))]
    for detail in config["horizons"]:
        h = int(detail["h"])
        horizon_all = evaluated.loc[evaluated["h"].astype(int) == h].copy()
        main = horizon_all.loc[~horizon_all["unique_id"].map(is_special_series)].copy()
        data_by_h[h] = horizon_all
        main_data_by_h[h] = main
        key = f"h{h}"
        leaderboards[key] = _leaderboard_rows(main, benchmark, models)
        primary_tests.append(
            _primary_test(main, config, h, bootstrap_reps=bootstrap_reps, seed=seed + h)
        )
        mcs_results[key] = _mcs_result(
            main,
            models,
            reps=mcs_reps,
            seed=seed + h,
            required_series=main_series,
        )
        if _probabilistic_full(config, h):
            calibration[key] = _calibration(main, config, h, models)
        for reference in sorted(references):
            rows = _leaderboard_rows(main, benchmark, [reference])
            if rows:
                row = rows[0]
                reference_rows.append(
                    {
                        "h": h, "model": reference, "ratio_median": row["ratio_median"],
                        "ratio_mean": row["ratio_mean"], "fail_count": row["fail_count"],
                        "n_used": row["n_used"],
                    }
                )

    finite_p = [row.get("sign_pvalue") for row in primary_tests]
    adjusted = stattests.holm(finite_p)
    for row, value in zip(primary_tests, adjusted, strict=True):
        row["holm_pvalue"] = _finite(value)

    diagnostics = _diagnostics(data_by_h, benchmark, models)
    diagnostics["timesfm3_log_coverage"] = _timesfm3_log_coverage_notes(leaderboards)
    summary: dict[str, Any] = {
        "schema_version": 1,
        "task": task_name,
        "window": window,
        "run_id": selected_run,
        "claim_scope": CLAIM_SCOPE,
        "window_disclaimer": MAIN_DISCLAIMER if window == "main" else DEV_DISCLAIMER if window == "dev" else None,
        "primary_benchmark": benchmark,
        "primary_model": PRIMARY_MODEL,
        "primary_metric": (
            "per-series QLIKE ratio vs EWMA" if task_name == "rv"
            else f"per-series MAE ratio vs {benchmark}"
        ),
        "leaderboards": leaderboards,
        "primary_tests": primary_tests,
        "mcs": mcs_results,
        "calibration": calibration,
        "task_p": (
            _task_p_tables(main_data_by_h, config, models, bootstrap_reps=bootstrap_reps, seed=seed)
            if task_name == "price" else None
        ),
        "diagnostics": diagnostics,
        "reference_models": reference_rows,
        "manifest": _manifest_reconciliation(store, forecasts),
        "plots": [],
    }

    output = Path(report_dir) / f"{task_name}_{window}"
    output.mkdir(parents=True, exist_ok=True)
    if make_plots:
        summary["plots"] = _write_plots(output, main_data_by_h, config, models)
    clean_summary = _jsonable(summary)
    markdown = _render_markdown(clean_summary)
    markdown_path = output / "summary.md"
    json_path = output / "summary.json"
    markdown_path.write_text(markdown, encoding="utf-8")
    json_path.write_text(
        json.dumps(clean_summary, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return {
        **clean_summary,
        "markdown_path": str(markdown_path),
        "json_path": str(json_path),
    }


write_report = generate_report
build_report = generate_report
run_report = generate_report
