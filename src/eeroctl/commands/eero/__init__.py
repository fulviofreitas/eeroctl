"""Eero commands package for the Eero CLI.

This package contains all Eero mesh node-related commands, split into logical submodules:
- base: Core commands (list, show, reboot)
- led: LED management commands
- nightlight: Nightlight commands (Beacon only)
- updates: Update management commands
"""

from .base import eero_group

__all__ = ["eero_group"]
