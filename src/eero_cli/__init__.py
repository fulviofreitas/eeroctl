"""Command-line interface for Eero client.

This package provides the CLI for managing Eero networks.

Entry point: eero_cli.main:cli
"""

from .main import cli, main

__all__ = ["cli", "main"]
