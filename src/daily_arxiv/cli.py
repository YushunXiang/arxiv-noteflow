from __future__ import annotations

from collections.abc import Callable
from datetime import date as dt_date
from pathlib import Path

import typer

from daily_arxiv.arxiv_recent import RecentPageError, fetch_recent_page, parse_recent_page, select_date_group
from daily_arxiv.downloader import DownloadError, download_group
from daily_arxiv.extractor import UnsafeArchiveError

app = typer.Typer(help="Download LaTeX source archives from arXiv recent pages.")

EXPECTED_CLI_ERRORS = (RecentPageError, DownloadError, UnsafeArchiveError, RuntimeError)


def _run_cli(command: Callable[[], None]) -> None:
    try:
        command()
    except EXPECTED_CLI_ERRORS as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc


def _validate_requested_date(requested_date: str | None) -> str | None:
    if requested_date is None:
        return None
    try:
        parsed_date = dt_date.fromisoformat(requested_date)
    except ValueError as exc:
        raise RuntimeError("--date must use YYYY-MM-DD format") from exc
    if parsed_date.isoformat() != requested_date:
        raise RuntimeError("--date must use YYYY-MM-DD format")
    return requested_date


@app.command("list")
def list_papers(
    category: str,
    date: str | None = typer.Option(None, "--date", help="Visible recent-page date in YYYY-MM-DD format."),
    timeout: float = typer.Option(30.0, "--timeout", help="HTTP timeout in seconds."),
) -> None:
    def command() -> None:
        requested_date = _validate_requested_date(date)
        html = fetch_recent_page(category, timeout=timeout)
        group = select_date_group(parse_recent_page(html, category), requested_date=requested_date)
        typer.echo(f"{group.category} {group.date} {group.heading}")
        for paper in group.papers:
            typer.echo(f"{paper.id}  {paper.title}")

    _run_cli(command)


@app.command()
def download(
    category: str,
    date: str | None = typer.Option(None, "--date", help="Visible recent-page date in YYYY-MM-DD format."),
    output: Path = typer.Option(Path("downloads"), "--output", help="Output root directory."),
    delay: float = typer.Option(3.0, "--delay", help="Delay between source archive downloads in seconds."),
    timeout: float = typer.Option(30.0, "--timeout", help="HTTP timeout in seconds."),
    keep_going: bool = typer.Option(False, "--keep-going", help="Continue after individual paper failures."),
) -> None:
    def command() -> None:
        requested_date = _validate_requested_date(date)
        html = fetch_recent_page(category, timeout=timeout)
        group = select_date_group(parse_recent_page(html, category), requested_date=requested_date)
        results = download_group(group, output, delay=delay, keep_going=keep_going, timeout=timeout)
        downloaded = sum(1 for result in results if result.status == "downloaded")
        skipped = sum(1 for result in results if result.status == "skipped")
        failed = sum(1 for result in results if result.status == "failed")
        typer.echo(f"{group.category} {group.date} {group.heading}")
        typer.echo(f"Downloaded: {downloaded}")
        typer.echo(f"Skipped: {skipped}")
        typer.echo(f"Failed: {failed}")
        if failed:
            raise typer.Exit(1)

    _run_cli(command)
