"""Generate the five figures used by the benchmark blog post.

All plotted numbers are loaded from the checked benchmark summaries.  The
constants named ``EXPECTED_*`` are independently verified regression anchors:
they deliberately make the script fail rather than publish stale figures.
"""

from __future__ import annotations

import json
import warnings
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = ROOT / "results" / "report"
OUTPUT_DIR = ROOT / "blog" / "img"

BACKGROUND = "#FFFFFF"
TEXT = "#1C2330"
GRID = "#D9DEE7"
VALUE_TEXT = "#5A6474"
TIMESFM_BLUE = "#2a78d6"
BASELINE_ORANGE = "#eb6834"
# Source: the user-provided, validated blog specification.  summary.json records
# the series counts, but not the human-readable BTC/ETH and Nikkei coverage scopes.
PARTIAL_MODELS = {"DVOL", "GJR-GARCH"}
TOLERANCE = 0.01

# These are the values independently verified for the blog specification.  They
# are validation-only constants; the figures use the values read from summary.json.
EXPECTED_RV_RATIO = {
    "h1": {
        "TimesFM3-log": 0.694,
        "TimesFM3-raw": 0.811,
        "HAR-RV": 0.775,
        "LightGBM": 0.710,
        "GARCH": 0.911,
        "NaivePrev": 1.096,
        "GJR-GARCH": 0.829,
        "DVOL": 0.984,
    },
    "h5": {
        "TimesFM3-log": 0.726,
        "TimesFM3-raw": 0.928,
        "HAR-RV": 0.718,
        "LightGBM": 0.871,
        "GARCH": 0.828,
        "NaivePrev": 0.953,
        "GJR-GARCH": 0.684,
        "DVOL": 0.876,
    },
    "h22": {
        "TimesFM3-log": 0.545,
        "TimesFM3-raw": 0.882,
        "HAR-RV": 0.617,
        "LightGBM": 0.743,
        "GARCH": 0.667,
        "NaivePrev": 0.703,
        "GJR-GARCH": 0.494,
        "DVOL": 0.478,
    },
}
EXPECTED_SPEED = {
    "NaivePrev": 0.022,
    "EWMA": 0.043,
    "GARCH": 0.122,
    "HAR-RV": 0.128,
    "DVOL": 0.150,
    "TimesFM3-raw": 0.356,
    "TimesFM3-log": 0.365,
    "LightGBM": 1.145,
}
EXPECTED_COVERAGE = {
    "EWMA": 0.821,
    "HAR-RV": 0.816,
    "NaivePrev": 0.811,
    "TimesFM3-raw": 0.806,
    "GARCH": 0.801,
    "DVOL": 0.798,
    "TimesFM3-log": 0.789,
    "GJR-GARCH": 0.762,
    "LightGBM": 0.512,
}
EXPECTED_PRICE_RATIO = {
    "AutoTheta": 0.998,
    "AutoETS": 1.001,
    "TimesFM3-raw": 1.014,
    "TimesFM3-log": 1.017,
    "LightGBM": 34.87,
}
EXPECTED_VOLUME_RATIO = {
    "TimesFM3-raw": 0.607,
    "TimesFM3-log": 0.609,
    "LightGBM": 0.639,
    "AutoETS": 0.647,
    "AutoTheta": 0.649,
    "SeasonalMedian4": 0.889,
    "SeasonalNaive7": 1.000,
}
EXPECTED_RV_MCS = {
    "h1": {"TimesFM3-log"},
    "h5": {"HAR-RV"},
    "h22": {"GARCH", "HAR-RV", "TimesFM3-log"},
}


def configure_style() -> None:
    """Apply the shared, deliberately small visual system."""
    matplotlib.rcParams["font.family"] = ["Meiryo", "Yu Gothic", "MS Gothic"]
    matplotlib.rcParams.update(
        {
            "figure.facecolor": BACKGROUND,
            "axes.facecolor": BACKGROUND,
            "savefig.facecolor": BACKGROUND,
            "text.color": TEXT,
            "axes.labelcolor": TEXT,
            "axes.edgecolor": GRID,
            "xtick.color": VALUE_TEXT,
            "ytick.color": TEXT,
            "font.size": 9,
            "axes.labelsize": 9,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8.5,
            "legend.fontsize": 7.5,
            "figure.dpi": 160,
            "savefig.dpi": 160,
        }
    )


def load_summary(task: str) -> dict[str, Any]:
    path = REPORT_ROOT / f"{task}_main" / "summary.json"
    summary = json.loads(path.read_text(encoding="utf-8"))
    assert summary["task"] == task, f"Task mismatch in {path}"
    assert summary["window"] == "main", f"Window mismatch in {path}"
    return summary


def rows_by_model(rows: Iterable[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    indexed: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        model = str(row["model"])
        assert model not in indexed, f"Duplicate model row: {model}"
        indexed[model] = row
    return indexed


def leaderboard_values(
    summary: Mapping[str, Any],
    horizon: str,
    models: Iterable[str],
    field: str,
) -> dict[str, float]:
    rows = rows_by_model(summary["leaderboards"][horizon])
    return {model: float(rows[model][field]) for model in models}


def coverage_values(summary: Mapping[str, Any], models: Iterable[str]) -> dict[str, float]:
    rows = rows_by_model(summary["calibration"]["h1"]["coverage"])
    return {model: float(rows[model]["overall"]) for model in models}


def assert_close_values(
    label: str,
    actual: Mapping[str, float],
    expected: Mapping[str, float],
) -> None:
    assert actual.keys() == expected.keys(), (
        f"{label}: model mismatch: actual={sorted(actual)}, expected={sorted(expected)}"
    )
    for model, expected_value in expected.items():
        actual_value = actual[model]
        assert abs(actual_value - expected_value) <= TOLERANCE, (
            f"{label}/{model}: summary value {actual_value:.6f} differs from "
            f"verified value {expected_value:.6f} by more than {TOLERANCE:.2f}"
        )


def model_color(model: str) -> str:
    return TIMESFM_BLUE if model.startswith("TimesFM") else BASELINE_ORANGE


def display_model(model: str) -> str:
    return f"{model}※" if model in PARTIAL_MODELS else model


def style_axis(ax: Axes, *, grid_axis: str = "x") -> None:
    ax.set_facecolor(BACKGROUND)
    ax.set_axisbelow(True)
    ax.grid(axis=grid_axis, color=GRID, linewidth=0.7)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(GRID)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(length=0)


def reference_line(ax: Axes, value: float, label: str) -> None:
    ax.axvline(value, color=GRID, linewidth=1.1, zorder=0)
    ax.annotate(
        label,
        xy=(value, 0.99),
        xycoords=("data", "axes fraction"),
        xytext=(3, -1),
        textcoords="offset points",
        color=VALUE_TEXT,
        fontsize=7,
        ha="left",
        va="top",
    )


def line_legend_handles() -> list[Line2D]:
    return [
        Line2D(
            [0],
            [0],
            color=TIMESFM_BLUE,
            marker="o",
            markersize=6,
            linewidth=1.2,
            label="TimesFM系",
        ),
        Line2D(
            [0],
            [0],
            color=BASELINE_ORANGE,
            marker="o",
            markersize=6,
            linewidth=1.2,
            label="実務ベースライン",
        ),
    ]


def bar_legend_handles() -> list[Patch]:
    return [
        Patch(facecolor=TIMESFM_BLUE, label="TimesFM系"),
        Patch(facecolor=BASELINE_ORANGE, label="実務ベースライン"),
    ]


def draw_lollipops(
    ax: Axes,
    models: Sequence[str],
    values: Mapping[str, float],
    *,
    reference: float,
    mcs_models: set[str] | None = None,
    label_offset: tuple[float, float] = (5, 3),
) -> None:
    mcs_models = mcs_models or set()
    for y, model in enumerate(models):
        value = values[model]
        color = model_color(model)
        partial = model in PARTIAL_MODELS
        linestyle = (0, (3, 2)) if partial else "-"
        ax.hlines(
            y,
            min(reference, value),
            max(reference, value),
            color=color,
            linewidth=1.15,
            linestyle=linestyle,
            zorder=2,
        )
        ax.plot(
            value,
            y,
            marker="o",
            markersize=8,
            markerfacecolor=BACKGROUND if partial else color,
            markeredgecolor=color,
            markeredgewidth=1.5 if partial else 0,
            linestyle="none",
            zorder=3,
        )
        suffix = "  ✓MCS" if model in mcs_models else ""
        ax.annotate(
            f"{value:.3f}{suffix}",
            xy=(value, y),
            xytext=label_offset,
            textcoords="offset points",
            color=VALUE_TEXT,
            fontsize=7.2,
            va="bottom",
            ha="left",
            clip_on=False,
        )


def save_figure(fig: Figure, filename: str) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / filename
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        fig.canvas.draw()
        fig.savefig(path, dpi=160, bbox_inches="tight", facecolor=BACKGROUND)
    glyph_warnings = [warning for warning in caught if "Glyph" in str(warning.message)]
    assert not glyph_warnings, f"Missing-glyph warning(s) for {filename}: {glyph_warnings}"
    assert not caught, f"Rendering warning(s) for {filename}: {[str(w.message) for w in caught]}"
    plt.close(fig)
    return path


def make_fig1(rv_summary: Mapping[str, Any]) -> Path:
    models = list(EXPECTED_RV_RATIO["h1"])
    values_by_horizon: dict[str, dict[str, float]] = {}
    for horizon, expected in EXPECTED_RV_RATIO.items():
        values = leaderboard_values(rv_summary, horizon, models, "ratio_median")
        assert_close_values(f"rv/{horizon}/ratio_median", values, expected)
        values_by_horizon[horizon] = values

    mcs_by_horizon = {
        horizon: set(rv_summary["mcs"][horizon]["included"])
        for horizon in EXPECTED_RV_MCS
    }
    assert mcs_by_horizon == EXPECTED_RV_MCS, (
        f"RV MCS mismatch: actual={mcs_by_horizon}, expected={EXPECTED_RV_MCS}"
    )
    h1_rows = rows_by_model(rv_summary["leaderboards"]["h1"])
    assert h1_rows["DVOL"]["series_used"] == 2
    assert h1_rows["GJR-GARCH"]["series_used"] == 1

    fig, axes = plt.subplots(1, 3, figsize=(7.5, 4.55))
    panel_labels = {"h1": "h = 1", "h5": "h = 5", "h22": "h = 22（記述的）"}
    y = np.arange(len(models))
    for panel, (ax, horizon) in enumerate(zip(axes, EXPECTED_RV_RATIO, strict=True)):
        style_axis(ax)
        reference_line(ax, 1.0, "1.0（EWMA）")
        draw_lollipops(
            ax,
            models,
            values_by_horizon[horizon],
            reference=1.0,
            mcs_models=mcs_by_horizon[horizon],
            label_offset=(4, 3),
        )
        ax.set_xlim(0.42, 1.14)
        ax.set_ylim(len(models) - 0.5, -0.7)
        ax.set_xticks([0.5, 0.7, 0.9, 1.1])
        ax.set_yticks(y)
        ax.set_yticklabels([display_model(model) for model in models] if panel == 0 else [])
        ax.set_xlabel("QLIKE比（対EWMA）")
        ax.text(
            0.5,
            1.025,
            panel_labels[horizon],
            transform=ax.transAxes,
            color=TEXT,
            fontsize=9,
            ha="center",
            va="bottom",
        )

    fig.legend(
        handles=line_legend_handles(),
        loc="upper center",
        bbox_to_anchor=(0.62, 0.995),
        ncol=2,
        frameon=False,
    )
    fig.text(
        0.01,
        0.015,
        "※部分カバレッジ：DVOLはBTC/ETHのみ、GJR-GARCHは日経のみ",
        color=VALUE_TEXT,
        fontsize=7,
    )
    fig.subplots_adjust(left=0.17, right=0.99, top=0.86, bottom=0.20, wspace=0.20)
    return save_figure(fig, "fig1_rv_qlike.png")


def make_fig2(rv_summary: Mapping[str, Any]) -> Path:
    values = leaderboard_values(rv_summary, "h1", EXPECTED_SPEED, "runtime_per_origin_s")
    assert_close_values("rv/h1/runtime_per_origin_s", values, EXPECTED_SPEED)
    models = sorted(values, key=values.__getitem__)

    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    style_axis(ax)
    y = np.arange(len(models))
    colors = [model_color(model) for model in models]
    bars = ax.barh(y, [values[model] for model in models], height=0.58, color=colors, zorder=2)
    ax.set_yticks(y, [display_model(model) for model in models])
    ax.set_ylim(len(models) - 0.25, -0.75)
    ax.set_xlim(0, 1.28)
    ax.set_xlabel("推論コスト（秒 / origin）")
    for bar, model in zip(bars, models, strict=True):
        ax.annotate(
            f"{values[model]:.3f}",
            xy=(bar.get_width(), bar.get_y() + bar.get_height() / 2),
            xytext=(5, 3),
            textcoords="offset points",
            color=VALUE_TEXT,
            fontsize=7.5,
            ha="left",
            va="bottom",
        )

    ax.legend(
        handles=bar_legend_handles(),
        loc="lower right",
        frameon=False,
        ncol=2,
    )
    ax.text(
        0.985,
        0.98,
        # Source: the user-provided, validated blog specification; execution
        # hardware and retraining cadence are not fields in summary.json.
        "TimesFM：zero-shot（再学習なし・GPU）\n学習系：5営業日毎に再学習（CPU）",
        transform=ax.transAxes,
        color=VALUE_TEXT,
        fontsize=7.2,
        ha="right",
        va="top",
        linespacing=1.5,
    )
    fig.text(
        0.01,
        0.012,
        "※部分カバレッジ：DVOLはBTC/ETHのみ。GJR-GARCHは1系列のみで非可比のため除外。",
        color=VALUE_TEXT,
        fontsize=7,
    )
    fig.subplots_adjust(left=0.20, right=0.98, top=0.95, bottom=0.17)
    return save_figure(fig, "fig2_speed.png")


def make_fig3(rv_summary: Mapping[str, Any]) -> Path:
    values = coverage_values(rv_summary, EXPECTED_COVERAGE)
    assert_close_values("rv/h1/coverage", values, EXPECTED_COVERAGE)
    models = sorted(values, key=values.__getitem__, reverse=True)

    fig, ax = plt.subplots(figsize=(7.5, 4.65))
    style_axis(ax)
    reference_line(ax, 0.80, "0.80（名目水準）")
    draw_lollipops(ax, models, values, reference=0.80)
    y = np.arange(len(models))
    ax.set_yticks(y, [display_model(model) for model in models])
    ax.set_ylim(len(models) - 0.5, -0.7)
    ax.set_xlim(0.47, 0.86)
    ax.set_xticks([0.5, 0.6, 0.7, 0.8])
    ax.set_xlabel("実測カバレッジ（80%区間）")
    fig.legend(
        handles=line_legend_handles(),
        loc="upper center",
        bbox_to_anchor=(0.61, 0.995),
        frameon=False,
        ncol=2,
    )
    fig.text(
        0.01,
        0.012,
        "※部分カバレッジ：DVOLはBTC/ETHのみ、GJR-GARCHは日経のみ",
        color=VALUE_TEXT,
        fontsize=7,
    )
    fig.subplots_adjust(left=0.20, right=0.96, top=0.87, bottom=0.17)
    return save_figure(fig, "fig3_coverage.png")


def make_fig4(price_summary: Mapping[str, Any]) -> Path:
    values = leaderboard_values(
        price_summary, "h1", EXPECTED_PRICE_RATIO, "ratio_median"
    )
    assert_close_values("price/h1/ratio_median", values, EXPECTED_PRICE_RATIO)

    rows = rows_by_model(price_summary["leaderboards"]["h1"])
    assert rows["LightGBM"]["misconfiguration_warning"], (
        "price/h1/LightGBM must retain its misconfiguration warning"
    )
    models = list(EXPECTED_PRICE_RATIO)
    in_range_models = models[:-1]

    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    style_axis(ax)
    reference_line(ax, 1.0, "1.0（RW）")
    draw_lollipops(ax, in_range_models, values, reference=1.0)

    lightgbm_y = len(models) - 1
    ax.hlines(
        lightgbm_y,
        1.0,
        1.055,
        color=BASELINE_ORANGE,
        linewidth=1.15,
        zorder=2,
    )
    ax.annotate(
        f"→ {values['LightGBM']:.1f}（誤設定ベースライン）",
        xy=(1.058, lightgbm_y),
        xytext=(1.013, lightgbm_y),
        color=VALUE_TEXT,
        fontsize=7.5,
        ha="left",
        va="center",
        clip_on=False,
        bbox={"facecolor": BACKGROUND, "edgecolor": "none", "pad": 1.0},
    )

    y = np.arange(len(models))
    ax.set_yticks(y, models)
    ax.set_ylim(len(models) - 0.45, -0.7)
    ax.set_xlim(0.95, 1.06)
    ax.set_xticks([0.96, 0.98, 1.00, 1.02, 1.04, 1.06])
    ax.set_xlabel("MAE比（対RW）")
    ax.legend(
        handles=line_legend_handles(),
        loc="upper left",
        frameon=False,
        ncol=2,
    )
    fig.subplots_adjust(left=0.20, right=0.97, top=0.96, bottom=0.20)
    return save_figure(fig, "fig4_price.png")


def make_fig5(volume_summary: Mapping[str, Any]) -> Path:
    values = leaderboard_values(
        volume_summary, "h1", EXPECTED_VOLUME_RATIO, "ratio_median"
    )
    assert_close_values("volume/h1/ratio_median", values, EXPECTED_VOLUME_RATIO)
    mcs_models = set(volume_summary["mcs"]["h1"]["included"])
    assert mcs_models == {"TimesFM3-raw"}, f"Volume h1 MCS mismatch: {mcs_models}"
    models = list(EXPECTED_VOLUME_RATIO)

    fig, ax = plt.subplots(figsize=(7.5, 4.25))
    style_axis(ax)
    reference_line(ax, 1.0, "1.0（SeasonalNaive7）")
    draw_lollipops(ax, models, values, reference=1.0, mcs_models=mcs_models)
    y = np.arange(len(models))
    ax.set_yticks(y, models)
    ax.set_ylim(len(models) - 0.5, -0.7)
    ax.set_xlim(0.55, 1.06)
    ax.set_xticks([0.6, 0.7, 0.8, 0.9, 1.0])
    ax.set_xlabel("MAE比（対SeasonalNaive7）")
    fig.legend(
        handles=line_legend_handles(),
        loc="upper center",
        bbox_to_anchor=(0.61, 0.995),
        frameon=False,
        ncol=2,
    )
    fig.subplots_adjust(left=0.22, right=0.96, top=0.86, bottom=0.18)
    return save_figure(fig, "fig5_volume.png")


def main() -> None:
    configure_style()
    rv_summary = load_summary("rv")
    price_summary = load_summary("price")
    volume_summary = load_summary("volume")

    outputs = [
        make_fig1(rv_summary),
        make_fig2(rv_summary),
        make_fig3(rv_summary),
        make_fig4(price_summary),
        make_fig5(volume_summary),
    ]
    for path in outputs:
        print(f"generated {path.relative_to(ROOT)} ({path.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
