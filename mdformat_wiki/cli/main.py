"""Command-line interface for ``mdformat_wiki``."""

from __future__ import annotations

from typing import Any

import typer

from . import cmd

__all__ = ['cli']


def cli(**kwargs: Any) -> None:
    """Run the ``mdformat_wiki`` CLI."""
    # construct app
    kwargs.setdefault('pretty_exceptions_enable', False)
    app = typer.Typer(name='mdformat_wiki', **kwargs)
    # version callback
    cmd.version(app)
    # mdformat_wiki commands
    cmd.install(app)
    # run app
    app()


if __name__ == '__main__':
    cli()
