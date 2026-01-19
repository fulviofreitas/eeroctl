"""Command-line interface for Eero client.

This package provides the CLI for managing Eero networks.

Entry point: eeroctl.main:cli
"""

from .main import cli, main

__version__ = "1.1.1"


def get_version() -> str:
    """Return the current version of eeroctl."""
    return __version__


__all__ = ["cli", "main", "__version__", "get_version"]
