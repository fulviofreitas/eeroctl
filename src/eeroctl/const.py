"""Constants for eeroctl."""

from enum import Enum

# Keyring service/account names the eero-api SDK stores credentials under
# (eero.api.auth_storage.KeyringStorage.SERVICE_NAME / ACCOUNT_NAME). Pinned
# by tests/cli/test_sdk_signatures.py::test_eeroctl_keyring_constants_match_the_sdk
# so a future SDK rename fails CI instead of silently breaking the keyring probe.
KEYRING_SERVICE_NAME = "eero-api"
KEYRING_ACCOUNT_NAME = "auth-tokens"


class EeroDeviceType(str, Enum):
    """Enum for Eero device types."""

    GATEWAY = "gateway"
    BEACON = "beacon"
    EERO = "eero"
    BRIDGE = "bridge"
    UNKNOWN = "unknown"


class EeroNetworkStatus(str, Enum):
    """Enum for Eero network status."""

    ONLINE = "online"
    OFFLINE = "offline"
    UPDATING = "updating"
    UNKNOWN = "unknown"


class EeroDeviceStatus(str, Enum):
    """Enum for Eero device status."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"
