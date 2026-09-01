import requests
from typer.testing import CliRunner

from tsfmbench.cli import app


def test_probe_reports_failures_but_exits_zero(monkeypatch) -> None:
    def fail(*_args, **_kwargs):
        raise requests.ConnectionError("offline fixture")

    monkeypatch.setattr(requests, "get", fail)
    result = CliRunner().invoke(app, ["probe"])
    assert result.exit_code == 0
    assert "ERROR" in result.stdout
    assert "offline fixture" in result.stdout


def test_stage_two_commands_exit_two() -> None:
    for command in ("run", "report"):
        result = CliRunner().invoke(app, [command])
        assert result.exit_code == 2
        assert "not implemented in stage 1" in result.output
