from typer.testing import CliRunner

from daily_arxiv import cli
from daily_arxiv.models import DateGroup, Paper, PaperResult


runner = CliRunner()


def _group() -> DateGroup:
    paper = Paper(
        id="2605.15157",
        title="Hand-in-the-Loop",
        authors=["Zhuohang Li"],
        subjects=["Robotics (cs.RO)"],
        category="cs.RO",
        date="2026-05-15",
        abs_url="https://arxiv.org/abs/2605.15157",
        src_url="https://arxiv.org/src/2605.15157",
    )
    return DateGroup(date="2026-05-15", heading="Fri, 15 May 2026", category="cs.RO", papers=[paper])


def test_help_shows_commands() -> None:
    result = runner.invoke(cli.app, ["--help"])

    assert result.exit_code == 0
    assert "list" in result.output
    assert "download" in result.output


def test_list_prints_selected_group(monkeypatch) -> None:
    monkeypatch.setattr(cli, "fetch_recent_page", lambda category, timeout: "<html></html>")
    monkeypatch.setattr(cli, "parse_recent_page", lambda html, category: [_group()])
    monkeypatch.setattr(cli, "select_date_group", lambda groups, requested_date=None: groups[0])

    result = runner.invoke(cli.app, ["list", "cs.RO"])

    assert result.exit_code == 0
    assert "cs.RO 2026-05-15 Fri, 15 May 2026" in result.output
    assert "2605.15157  Hand-in-the-Loop" in result.output


def test_download_invokes_downloader(monkeypatch, tmp_path) -> None:
    group = _group()
    monkeypatch.setattr(cli, "fetch_recent_page", lambda category, timeout: "<html></html>")
    monkeypatch.setattr(cli, "parse_recent_page", lambda html, category: [group])
    monkeypatch.setattr(cli, "select_date_group", lambda groups, requested_date=None: group)

    def fake_download_group(selected_group, output_root, delay, keep_going):
        assert selected_group == group
        assert output_root == tmp_path
        assert delay == 0.0
        assert keep_going is True
        paper = group.papers[0]
        return [PaperResult(paper, str(tmp_path / "archive.tar.gz"), str(tmp_path / "source"), "downloaded")]

    monkeypatch.setattr(cli, "download_group", fake_download_group)

    result = runner.invoke(
        cli.app,
        ["download", "cs.RO", "--output", str(tmp_path), "--delay", "0", "--keep-going"],
    )

    assert result.exit_code == 0
    assert "Downloaded: 1" in result.output
    assert "Skipped: 0" in result.output
    assert "Failed: 0" in result.output


def test_download_returns_nonzero_when_keep_going_has_failures(monkeypatch, tmp_path) -> None:
    group = _group()
    monkeypatch.setattr(cli, "fetch_recent_page", lambda category, timeout: "<html></html>")
    monkeypatch.setattr(cli, "parse_recent_page", lambda html, category: [group])
    monkeypatch.setattr(cli, "select_date_group", lambda groups, requested_date=None: group)

    def fake_download_group(selected_group, output_root, delay, keep_going):
        paper = selected_group.papers[0]
        return [PaperResult(paper, str(tmp_path / "archive.tar.gz"), str(tmp_path / "source"), "failed", "HTTP 500")]

    monkeypatch.setattr(cli, "download_group", fake_download_group)

    result = runner.invoke(cli.app, ["download", "cs.RO", "--output", str(tmp_path), "--keep-going"])

    assert result.exit_code == 1
    assert "Failed: 1" in result.output
