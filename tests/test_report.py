import json
import uuid
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from tsfmbench.adapters.base import failed_row, make_row
from tsfmbench.backtest import FORECAST_COLUMNS, ForecastStore
from tsfmbench.data.transforms import h_sum_series
from tsfmbench.report import build_actuals, generate_report


@pytest.fixture(name="tmp_path")
def writable_tmp_path() -> Path:
    """tmp_path equivalent for runners where pytest's chmod(0700) is sandboxed."""

    path = Path(".test-work") / f"stage4-{uuid.uuid4().hex}"
    path.mkdir(parents=True)
    return path


def _price_fixture(tmp_path: Path) -> tuple[dict, Path, Path, Path]:
    processed_dir = tmp_path / "processed"
    forecast_dir = tmp_path / "forecasts"
    report_dir = tmp_path / "report"
    processed_dir.mkdir()
    config = {
        "task": "price",
        "panel": "series",
        "value_column": "y",
        "series": ["EURUSD", "BTC-USD", "XRP-USD"],
        "horizons": [
            {"h": 1, "step": 1, "probabilistic": True},
            {"h": 2, "step": 1, "probabilistic": True},
        ],
        "windows": {"dev": {"start": None, "end": "2025-01-08"}},
        "primary_benchmark": "RW",
    }
    dates = pd.date_range("2025-01-01", periods=8)
    panel = pd.concat(
        [
            pd.DataFrame(
                {"unique_id": uid, "ds": dates, "y": np.arange(10.0, 18.0) + offset}
            )
            for uid, offset in (("EURUSD", 0.0), ("BTC-USD", 10.0), ("XRP-USD", 20.0))
        ],
        ignore_index=True,
    )
    panel.to_parquet(processed_dir / "series.parquet", index=False)

    store = ForecastStore(forecast_dir, run_id="synthetic", task="price")
    models = {
        "RW": 2.0,
        "TimesFM3-raw": 1.0,
        "Other": 12.0,
        "Broken": 1.0,
        "Prophet": 1.5,
    }
    expected = {model: 0 for model in models}
    for model, error in models.items():
        for origin_index, origin in enumerate(dates[:4]):
            rows = []
            for uid in config["series"]:
                for h in (1, 2):
                    target = dates[origin_index + h]
                    actual = float(panel.loc[(panel["unique_id"] == uid) & (panel["ds"] == target), "y"].iloc[0])
                    if model == "Broken" and uid == "EURUSD" and origin_index == 0 and h == 1:
                        rows.append(failed_row(uid, h, target, "nonpositive_forecast"))
                    else:
                        quantiles = np.linspace(actual - 0.4, actual + 0.4, 9)
                        rows.append(make_row(uid, h, target, actual + error, actual + error, quantiles))
            frame = (
                pd.DataFrame(rows)
                .assign(
                    run_id="synthetic",
                    task="price",
                    model_variant=model,
                    origin=origin,
                    config_hash="config",
                    data_hash="data",
                    runtime_s=0.25,
                )
                .loc[:, FORECAST_COLUMNS]
            )
            store.write_batch(frame)
            expected[model] += len(frame)
    store.write_manifest(expected, window="dev")
    store.write_model_config(
        {"models": {model: {"reference": model == "Prophet"} for model in models}}
    )
    return config, processed_dir, forecast_dir, report_dir


def test_report_known_ratios_failures_holm_reference_and_diagnostics(
    tmp_path: Path, monkeypatch
) -> None:
    config, processed_dir, forecast_dir, report_dir = _price_fixture(tmp_path)
    import tsfmbench.report as report_module

    calls = {"sign": 0, "bootstrap": 0}
    original_sign = report_module.stattests.sign_test
    original_bootstrap = report_module.stattests.moving_block_bootstrap

    def sign_spy(*args, **kwargs):
        calls["sign"] += 1
        return original_sign(*args, **kwargs)

    def bootstrap_spy(*args, **kwargs):
        calls["bootstrap"] += 1
        return original_bootstrap(*args, **kwargs)

    monkeypatch.setattr(report_module.stattests, "sign_test", sign_spy)
    monkeypatch.setattr(report_module.stattests, "moving_block_bootstrap", bootstrap_spy)
    result = generate_report(
        config,
        "dev",
        "synthetic",
        forecast_dir=forecast_dir,
        processed_dir=processed_dir,
        report_dir=report_dir,
        bootstrap_reps=20,
        mcs_reps=10,
        make_plots=False,
    )

    h1 = {row["model"]: row for row in result["leaderboards"]["h1"]}
    assert h1["TimesFM3-raw"]["ratio_median"] == 0.5
    assert h1["TimesFM3-raw"]["ratio_mean"] == 0.5
    assert h1["TimesFM3-raw"]["win_rate"] == 1.0
    assert h1["Broken"]["fail_count"] == 1
    assert h1["Broken"]["n_used"] == 7
    assert h1["Other"]["ratio_median"] == 6.0
    assert h1["Other"]["misconfiguration_warning"] is True
    assert h1["Other"]["footnote_marker"] == "†"
    assert h1["TimesFM3-raw"]["misconfiguration_warning"] is False
    assert "Prophet" not in h1
    assert {row["model"] for row in result["reference_models"]} == {"Prophet"}
    assert calls == {"sign": 2, "bootstrap": 2}
    for test in result["primary_tests"]:
        assert test["holm_pvalue"] >= test["sign_pvalue"]
    assert result["calibration"]["h1"]["coverage"][0]["tercile_shape"] == [3, 3]
    assert {row["period"] for row in result["diagnostics"]["half_split"]} == {
        "first_half",
        "second_half",
    }
    assert {row["unique_id"] for row in result["diagnostics"]["special_series"]} == {
        "XRP-USD"
    }
    assert result["mcs"]["h1"]["status"] == "insufficient data"

    payload = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    markdown = Path(result["markdown_path"]).read_text(encoding="utf-8")
    payload_h1 = {row["model"]: row for row in payload["leaderboards"]["h1"]}
    assert payload_h1["TimesFM3-raw"]["ratio_median"] == 0.5
    assert "0.5" in markdown
    assert "Other†" in markdown
    assert "median ratio > 5 または fail率 > 40%" in markdown
    assert "『誤設定ベースライン』" in markdown
    assert "ratio < 1 が基準より良い" in markdown
    assert "mean dbar < 0 は TimesFM の損失が基準より小さい（勝ち）方向" in markdown
    assert "DM stat < 0 は TimesFM の損失が基準より小さい（勝ち）方向" in markdown
    assert "mcs_universe" in markdown
    assert "excluded_partial_coverage" in markdown
    assert "開発窓 — 最終評価から除外、技術検証のみ" in markdown


def _mcs_frame(coverage: dict[str, list[str]], origins: int = 30) -> pd.DataFrame:
    rows = []
    for model_index, (model, series) in enumerate(coverage.items()):
        for origin_index, origin in enumerate(pd.date_range("2020-01-01", periods=origins)):
            for uid_index, uid in enumerate(series):
                rows.append(
                    {
                        "model_variant": model,
                        "unique_id": uid,
                        "origin": origin,
                        "evaluation_fail": False,
                        "loss": float(model_index + uid_index + origin_index / 100.0),
                    }
                )
    return pd.DataFrame(rows)


def test_mcs_uses_only_full_coverage_models(monkeypatch) -> None:
    import tsfmbench.report as report_module

    data = _mcs_frame(
        {
            "Full-A": ["S1", "S2"],
            "Partial": ["S1"],
            "Full-B": ["S1", "S2"],
        }
    )
    captured: dict[str, list[str]] = {}

    def fake_mcs(matrix, **kwargs):
        del kwargs
        captured["columns"] = matrix.columns.astype(str).tolist()
        return SimpleNamespace(
            included=["Full-A"],
            excluded=["Full-B"],
            pvalues={"Full-A": 1.0, "Full-B": 0.05},
        )

    monkeypatch.setattr(report_module.stattests, "mcs", fake_mcs)
    result = report_module._mcs_result(
        data,
        ["Full-A", "Partial", "Full-B"],
        reps=10,
        seed=1,
    )

    assert result["status"] == "ok"
    assert result["mcs_universe"] == ["Full-A", "Full-B"]
    assert result["excluded_partial_coverage"] == [
        {"model": "Partial", "reason": "successful coverage missing for: S2"}
    ]
    assert captured["columns"] == ["Full-A", "Full-B"]


def test_mcs_skips_when_no_model_has_full_coverage() -> None:
    import tsfmbench.report as report_module

    data = _mcs_frame({"Partial-A": ["S1"], "Partial-B": ["S2"]})
    result = report_module._mcs_result(
        data,
        ["Partial-A", "Partial-B"],
        reps=10,
        seed=1,
    )

    assert result["status"] == "insufficient data"
    assert result["skip_reason"] == "fewer than two full-coverage models"
    assert result["mcs_universe"] == []
    assert {row["model"] for row in result["excluded_partial_coverage"]} == {
        "Partial-A",
        "Partial-B",
    }


@pytest.mark.parametrize(
    ("ratio_median", "fail_rate", "expected"),
    [
        (5.0001, 0.0, True),
        (1.0, 0.4001, True),
        (5.0, 0.40, False),
        (None, None, False),
    ],
)
def test_broken_baseline_warning_thresholds(
    ratio_median: float | None,
    fail_rate: float | None,
    expected: bool,
) -> None:
    import tsfmbench.report as report_module

    assert report_module._broken_baseline_flag(ratio_median, fail_rate) is expected


def test_timesfm3_log_series_gap_note_uses_invalid_context_failures() -> None:
    import tsfmbench.report as report_module

    notes = report_module._timesfm3_log_coverage_notes(
        {
            "h1": [
                {
                    "model": "TimesFM3-log",
                    "series_used": 16,
                    "fail_reasons": {"invalid_context": 90},
                },
                {"model": "RW", "series_used": 19, "fail_reasons": {}},
            ]
        }
    )

    assert notes == [
        {
            "h": 1,
            "model": "TimesFM3-log",
            "series_used": 16,
            "other_model_max_series": 19,
            "invalid_context_fail_count": 90,
            "reason": (
                "fail_reasons=invalid_context が 90 件。"
                "log 定義不能（非正値を含む金利系列等）のコンテキストは失敗会計となるため。"
            ),
        }
    ]


def test_rv_h5_actual_uses_transform_tail_alignment(tmp_path: Path) -> None:
    dates = pd.date_range("2025-01-01", periods=8)
    panel = pd.DataFrame({"unique_id": "RV_BTC", "ds": dates, "rv": np.arange(1.0, 9.0)})
    forecasts = pd.DataFrame(
        {
            "unique_id": ["RV_BTC"],
            "origin": [dates[1]],
            "h": [5],
            "ds_target": [dates[6]],
        }
    )
    config = {
        "task": "rv",
        "panel": "rv_daily",
        "value_column": "rv",
        "series": ["RV_BTC"],
        "horizons": [{"h": 5, "target": "sum", "step": 5}],
        "windows": {"dev": {"start": None, "end": None}},
        "primary_benchmark": "EWMA",
    }
    actual = build_actuals(panel, forecasts, config).loc[0, "actual"]
    expected_frame = h_sum_series(
        panel.loc[(panel["ds"] > dates[1]) & (panel["ds"] <= dates[6])].rename(
            columns={"rv": "y"}
        ),
        5,
        alignment="end",
    )
    assert actual == expected_frame.loc[0, "y"]
