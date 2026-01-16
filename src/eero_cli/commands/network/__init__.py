"""Network commands package for the Eero CLI.

This package contains all network-related commands, split into logical submodules:
- base: Core commands (list, show, use, rename, premium)
- dns: DNS management commands
- security: Security settings commands
- sqm: SQM/QoS commands
- guest: Guest network commands
- backup: Backup network commands (Eero Plus)
- speedtest: Speed test commands
- forwards: Port forwarding commands
- dhcp: DHCP management commands
- advanced: Routing, Thread, Support commands
"""

from .base import network_group

__all__ = ["network_group"]
