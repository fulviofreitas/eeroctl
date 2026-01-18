"""Command-line interface for Eero client.

This package provides the CLI for managing Eero networks.

Entry point: eeroctl.main:cli
"""

from .main import cli, main

__version__ = "1.0.1"
__all__ = ["cli", "main", "__version__"]
