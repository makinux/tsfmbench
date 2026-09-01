"""Command-line interface for tsfmbench."""

import truststore

truststore.inject_into_ssl()

import io
import logging
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any

import requests
import typer

from tsfmbench.backtest import run_task
from tsfmbench.data.audit import run_all_audits
from tsfmbench.data.build import build_processed
from tsfmbench.data.download import SOURCES, download_sources
from tsfmbench.data.sources import coinbase, deribit, ecb, mof, nikkei
from tsfmbench.mde import DEFAULT_MDE_DIR, DEFAULT_TASKS_DIR, write_mde_report
from tsfmbench.report import DEFAULT_REPORT_DIR, generate_report

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
LOGGER = logging.getLogger(__name__)
app = typer.Typer(help="TimesFM 3.0 financial-practice benchmark harness.", no_args_is_help=True)
DEFAULT_RAW_DIR = Path("data/raw")
DEFAULT_PROCESSED_DIR = Path("data/processed")
DEFAULT_AUDIT_DIR = Path("results/audit")


def _probe_one(
    source: str,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, object]:
    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        status: str | int = response.status_code
        response.raise_for_status()
        rows = 0
        note = "reachable"
        content_type = response.headers.get("content-type", "")
        if "json" in content_type:
            payload = response.json()
            if source == "deribit":
                rows = len(payload.get("result", {}).get("data", []))
            elif isinstance(payload, list):
                rows = len(payload)
        elif response.content:
            if source == "ecb":
                with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
                    csv_name = next(
                        name for name in archive.namelist() if name.lower().endswith(".csv")
                    )
                    rows = len(ecb.parse_ecb_csv(archive.read(csv_name)))
            elif source == "mof":
                rows = len(mof.parse_mof_csv(response.content))
            elif source == "nikkei":
                rows = len(nikkei.parse_nikkei_csv(response.content))
            else:
                rows = 1
            note = f"reachable ({len(response.content)} bytes)"
        return {"source": source, "url": response.url, "status": status, "rows": rows, "note": note}
    except Exception as exc:  # noqa: BLE001 - probe is explicitly report-only
        return {"source": source, "url": url, "status": "ERROR", "rows": 0, "note": str(exc)}


@app.command()
def probe() -> None:
    """Issue one minimal request per source and report reachability (always exit 0)."""

    end = datetime.now(UTC).replace(microsecond=0)
    start = end - timedelta(days=1)
    rows = [
        _probe_one(
            "coinbase", f"{coinbase.BASE_URL}/products/BTC-USD/candles",
            params={"granularity": 86400, "start": start.isoformat(), "end": end.isoformat()},
        ),
        _probe_one("ecb", ecb.URL),
        _probe_one("mof", mof.CURRENT_URL),
        _probe_one("nikkei", nikkei.URL, headers={"User-Agent": nikkei.USER_AGENT}),
        _probe_one(
            "deribit", deribit.URL,
            params={
                "currency": "BTC", "resolution": "1D",
                "start_timestamp": int(start.timestamp() * 1000),
                "end_timestamp": int(end.timestamp() * 1000),
            },
        ),
    ]
    columns = ("source", "url", "status", "rows", "note")
    widths = {
        column: min(90, max(len(column), *(len(str(row[column])) for row in rows)))
        for column in columns
    }
    typer.echo("  ".join(column.ljust(widths[column]) for column in columns))
    typer.echo("  ".join("-" * widths[column] for column in columns))
    for row in rows:
        typer.echo("  ".join(str(row[column])[: widths[column]].ljust(widths[column]) for column in columns))


@app.command()
def download(
    source: Annotated[
        str | None, typer.Option("--source", help=f"One of: {', '.join(SOURCES)}")
    ] = None,
    update: Annotated[
        bool, typer.Option("--update", help="Fetch only data after the cached final timestamp.")
    ] = False,
    raw_dir: Annotated[Path, typer.Option(hidden=True)] = DEFAULT_RAW_DIR,
) -> None:
    """Download raw source caches."""

    try:
        paths = download_sources(raw_dir=raw_dir, source=source, update=update)
    except ValueError as exc:
        raise typer.BadParameter(str(exc), param_hint="--source") from exc
    typer.echo(f"saved {len(paths)} raw cache file(s)")


@app.command("build")
def build_command(
    raw_dir: Annotated[Path, typer.Option(hidden=True)] = DEFAULT_RAW_DIR,
    processed_dir: Annotated[Path, typer.Option(hidden=True)] = DEFAULT_PROCESSED_DIR,
) -> None:
    """Build normalized series, metadata, and daily realized variance."""

    outputs = build_processed(raw_dir, processed_dir)
    typer.echo(
        f"built series={len(outputs['series'])}, meta={len(outputs['meta'])}, "
        f"rv_daily={len(outputs['rv_daily'])}"
    )


@app.command("audit")
def audit_command(
    raw_dir: Annotated[Path, typer.Option(hidden=True)] = DEFAULT_RAW_DIR,
    processed_dir: Annotated[Path, typer.Option(hidden=True)] = DEFAULT_PROCESSED_DIR,
    results_dir: Annotated[Path, typer.Option(hidden=True)] = DEFAULT_AUDIT_DIR,
) -> None:
    """Run all raw/processed audits and write JSON plus text reports."""

    report = run_all_audits(raw_dir, processed_dir, results_dir)
    typer.echo(f"audit violations: {report['violation_count']}")
    typer.echo(f"text: {report['text_path']}")
    typer.echo(f"json: {report['json_path']}")
    if not report["passed"]:
        raise typer.Exit(code=1)


def _stage_two() -> None:
    typer.echo("not implemented in stage 1", err=True)
    raise typer.Exit(code=2)


@app.command("mde")
def mde_command(
    tasks_dir: Annotated[
        Path,
        typer.Option("--tasks-dir", "--config-dir", help="Directory containing task YAML files."),
    ] = DEFAULT_TASKS_DIR,
    results_dir: Annotated[
        Path,
        typer.Option("--results-dir", help="Directory for the Markdown and JSON MDE reports."),
    ] = DEFAULT_MDE_DIR,
) -> None:
    """Compute schedule-based analytic MDEs and write Markdown plus JSON reports."""

    report = write_mde_report(tasks_dir, results_dir)
    typer.echo(f"MDE cells: {len(report['rows'])}")
    typer.echo(f"markdown: {report['markdown_path']}")
    typer.echo(f"json: {report['json_path']}")


@app.command("run")
def run_command(
    task: Annotated[
        str | None, typer.Option("--task", help="One of: price, rv, volume")
    ] = None,
    window: Annotated[
        str, typer.Option("--window", help="One of: dev, main, clean")
    ] = "main",
    models: Annotated[
        str | None, typer.Option("--models", help="Comma-separated model variants")
    ] = None,
    estimation: Annotated[
        str, typer.Option("--estimation", help="rolling or expanding")
    ] = "rolling",
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Resolve the schedule and print row counts only")
    ] = False,
    processed_dir: Annotated[Path, typer.Option(hidden=True)] = DEFAULT_PROCESSED_DIR,
    raw_dir: Annotated[Path, typer.Option(hidden=True)] = DEFAULT_RAW_DIR,
    results_dir: Annotated[Path, typer.Option(hidden=True)] = Path("results/forecasts"),
) -> None:
    """Run a Stage 3 leakage-safe backtest task."""

    # Preserve the Stage 1 no-argument command contract while making the
    # explicit Stage 3 form fully operational.
    if task is None:
        _stage_two()
    if task not in {"price", "rv", "volume"}:
        raise typer.BadParameter("choose price, rv, or volume", param_hint="--task")
    if window not in {"dev", "main", "clean"}:
        raise typer.BadParameter("choose dev, main, or clean", param_hint="--window")
    if estimation not in {"rolling", "expanding"}:
        raise typer.BadParameter("choose rolling or expanding", param_hint="--estimation")
    try:
        report = run_task(
            task,
            window,
            models,
            dry_run,
            estimation=estimation,
            processed_dir=processed_dir,
            raw_dir=raw_dir,
            results_dir=results_dir,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"run_id: {report['run_id']}")
    for model, count in report["expected_rows"].items():
        typer.echo(f"{model}: {count}")
    typer.echo(f"total: {report['total_rows']}")


@app.command("report")
def report_command(
    task: Annotated[
        str | None, typer.Option("--task", help="One of: price, rv, volume")
    ] = None,
    window: Annotated[
        str, typer.Option("--window", help="One of: dev, main, clean")
    ] = "main",
    run_id: Annotated[
        str | None, typer.Option("--run-id", help="Forecast run id; newest matching run by default")
    ] = None,
    processed_dir: Annotated[Path, typer.Option(hidden=True)] = DEFAULT_PROCESSED_DIR,
    forecast_dir: Annotated[
        Path, typer.Option("--forecast-dir", hidden=True)
    ] = Path("results/forecasts"),
    report_dir: Annotated[Path, typer.Option("--report-dir", hidden=True)] = DEFAULT_REPORT_DIR,
    tasks_dir: Annotated[Path, typer.Option("--tasks-dir", hidden=True)] = DEFAULT_TASKS_DIR,
) -> None:
    """Aggregate a forecast run and write the Stage 4 Markdown/JSON report."""

    if task is None:
        _stage_two()
    if task not in {"price", "rv", "volume"}:
        raise typer.BadParameter("choose price, rv, or volume", param_hint="--task")
    if window not in {"dev", "main", "clean"}:
        raise typer.BadParameter("choose dev, main, or clean", param_hint="--window")
    try:
        result = generate_report(
            task,
            window,
            run_id,
            forecast_dir=forecast_dir,
            processed_dir=processed_dir,
            report_dir=report_dir,
            tasks_dir=tasks_dir,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"run_id: {result['run_id']}")
    typer.echo(f"markdown: {result['markdown_path']}")
    typer.echo(f"json: {result['json_path']}")
