"""New command structure for the Eero CLI.

This package contains the new noun-first command tree:
- auth: Authentication management
- network: Network configuration and settings
- eero: Mesh node management
- client: Connected device management
- profile: Profile/parental controls management
- activity: Network activity data (Eero Plus)
- troubleshoot: Diagnostics and troubleshooting
- completion: Shell completion
"""

from .activity import activity_group
from .auth import auth_group
from .client import client_group
from .completion import completion_group
from .eero import eero_group
from .network import network_group
from .profile import profile_group
from .troubleshoot import troubleshoot_group

__all__ = [
    "auth_group",
    "network_group",
    "eero_group",
    "client_group",
    "profile_group",
    "activity_group",
    "troubleshoot_group",
    "completion_group",
]
