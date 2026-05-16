from __future__ import annotations

from pathlib import Path

import typer

from daily_arxiv.arxiv_recent import fetch_recent_page, parse_recent_page, select_date_group
from daily_arxiv.downloader import download_group

app = typer.Typer(help="Download LaTeX source archives from arXiv recent pages.")


@app.command("list")
def list_papers(
    category: str,
    date: str | None = typer.Option(None, "--date", help="Visible recent-page date in YYYY-MM-DD format."),
    timeout: float = typer.Option(30.0, "--timeout", help="HTTP timeout in seconds."),
) -> None:
    html = fetch_recent_page(category, timeout=timeout)
    group = select_date_group(parse_recent_page(html, category), requested_date=date)
    typer.echo(f"{group.category} {group.date} {group.heading}")
    for paper in group.papers:
        typer.echo(f"{paper.id}  {paper.title}")


@app.command()
def download(
    category: str,
    date: str | None = typer.Option(None, "--date", help="Visible recent-page date in YYYY-MM-DD format."),
    output: Path = typer.Option(Path("downloads"), "--output", help="Output root directory."),
    delay: float = typer.Option(3.0, "--delay", help="Delay between source archive downloads in seconds."),
    timeout: float = typer.Option(30.0, "--timeout", help="HTTP timeout in seconds."),
    keep_going: bool = typer.Option(False, "--keep-going", help="Continue after individual paper failures."),
) -> None:
    html = fetch_recent_page(category, timeout=timeout)
    group = select_date_group(parse_recent_page(html, category), requested_date=date)
    results = download_group(group, output, delay=delay, keep_going=keep_going)
    downloaded = sum(1 for result in results if result.status == "downloaded")
    skipped = sum(1 for result in results if result.status == "skipped")
    failed = sum(1 for result in results if result.status == "failed")
    typer.echo(f"{group.category} {group.date} {group.heading}")
    typer.echo(f"Downloaded: {downloaded}")
    typer.echo(f"Skipped: {skipped}")
    typer.echo(f"Failed: {failed}")
    if failed:
        raise typer.Exit(1)
