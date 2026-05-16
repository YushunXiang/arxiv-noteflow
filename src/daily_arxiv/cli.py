import typer

app = typer.Typer(help="Download LaTeX source archives from arXiv recent pages.")


@app.command("list")
def list_papers(category: str) -> None:
    typer.echo(f"Listing recent papers for {category}")


@app.command()
def download(category: str) -> None:
    typer.echo(f"Downloading recent source archives for {category}")
