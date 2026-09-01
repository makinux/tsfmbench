import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tsfmbench.cli import app
from tsfmbench.mde import load_origin_schedules, write_mde_report


def test_schedule_report_has_known_h22_cell() -> None:
    # Avoid pytest's chmod-based tmp_path on locked-down Windows runners.
    root = Path(".test-work/mde_fixture")
    tasks = root / "tasks"
    tasks.mkdir(parents=True, exist_ok=True)
    (tasks / "volatility.yaml").write_text(
        """
task: V
test_window:
  start: 2025-01-02
  end: 2026-08-31
  frequency: business
horizons:
  - h: 22
    step: 22
""".strip(),
        encoding="utf-8",
    )
    schedules = load_origin_schedules(tasks)
    assert len(schedules) == 1
    assert schedules[0].n_origins == 19

    output = root / "results" / "mde"
    report = write_mde_report(tasks, output)
    row = report["rows"][0]
    assert row["design_effect"] == pytest.approx(1.0)
    assert row["mde_sd"] == pytest.approx(0.68, abs=0.03)
    assert (output / "mde_report.md").exists()
    payload = json.loads((output / "mde_report.json").read_text(encoding="utf-8"))
    assert payload["rows"][0]["n_origins"] == 19


def test_mde_cli_writes_reports_offline() -> None:
    root = Path(".test-work/mde_cli_fixture")
    tasks = root / "missing-tasks"
    output = root / "mde"
    result = CliRunner().invoke(
        app,
        ["mde", "--tasks-dir", str(tasks), "--results-dir", str(output)],
    )
    assert result.exit_code == 0
    assert "MDE cells: 0" in result.stdout
    assert (output / "mde_report.md").exists()
    assert (output / "mde_report.json").exists()
