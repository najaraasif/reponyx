"""Command-line entry points for local repository intake."""

import json

import typer

from reponyx.config import get_settings
from reponyx.repositories.service import RepositoryService

cli = typer.Typer(help="Reponyx repository operations.")


@cli.command()
def analyze(url: str) -> None:
    """Clone and statically analyze a GitHub repository."""

    service = RepositoryService(get_settings())
    result = service.create(url)
    analysis = service.analyze(result["id"])
    typer.echo(json.dumps(analysis, indent=2, default=str))


if __name__ == "__main__":
    cli()
