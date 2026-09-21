"""Constants for eeroctl."""

from enum import Enum

# Keyring service/account names the eero-api SDK stores credentials under
# (eero.api.auth_storage.KeyringStorage.SERVICE_NAME / ACCOUNT_NAME). Pinned
# by tests/cli/test_sdk_signatures.py::test_eeroctl_keyring_constants_match_the_sdk
# so a future SDK rename fails CI instead of silently breaking the keyring probe.
KEYRING_SERVICE_NAME = "eero-api"
KEYRING_ACCOUNT_NAME = "auth-tokens"

# Key-name substrings that mark a value as sensitive for the generic
# table/text/list renderer (`formatting/generic.py`). A subset of the SDK's
# own redaction pattern set -- see `eero.logging._ZERO_VISIBILITY_PATTERNS`,
# /tmp/eero-api-v8.0.1/src/eero/logging.py:55-75 -- plus contact-info keys
# (email/phone/sms) the SDK's logger doesn't need to worry about but
# eeroctl's generic renderer does, since it prints undocumented API payloads
# verbatim in table/text/list output. `serial`/`mac`/`url` are deliberately
# NOT included: they are the CLI's normal admin identifiers, and dedicated
# (non-generic) views already show them. `json`/`yaml` output is never
# redacted -- it is the user's explicit opt-in to the raw payload.
GENERIC_RENDER_SENSITIVE_KEY_PATTERNS: tuple = (
    "token",
    "password",
    "secret",
    "cookie",
    "authorization",
    "api_key",
    "apikey",
    "email",
    "phone",
    "sms",
)


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
