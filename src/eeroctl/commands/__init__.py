"""New command structure for the Eero CLI.

This package contains the new noun-first command tree:
- auth: Authentication management
- network: Network configuration and settings
- eero: Mesh node management
- device: Connected device management
- profile: Profile/parental controls management
- activity: Network activity data (Eero Plus)
- troubleshoot: Diagnostics and troubleshooting
- completion: Shell completion
"""

from .activity import activity_group
from .auth import auth_group
from .completion import completion_group
from .device import device_group
from .eero import eero_group
from .network import network_group
from .profile import profile_group
from .troubleshoot import troubleshoot_group

__all__ = [
    "auth_group",
    "network_group",
    "eero_group",
    "device_group",
    "profile_group",
    "activity_group",
    "troubleshoot_group",
    "completion_group",
]
