from typer.testing import CliRunner

from daily_arxiv.cli import app


runner = CliRunner()


def test_help_shows_commands() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "list" in result.output
    assert "download" in result.output
