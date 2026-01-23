"""Command-line interface for Eero client.

This package provides the CLI for managing Eero networks.

Entry point: eeroctl.main:cli
"""

from .main import cli, main

__version__ = "2.0.1"
__version_info__ = tuple(int(x) for x in __version__.split(".")[:3])


def get_version() -> str:
    """Return the current version of eeroctl."""
    return __version__


__all__ = ["cli", "main", "__version__", "__version_info__", "get_version"]
