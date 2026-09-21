"""Constants for eeroctl."""

from enum import Enum
from typing import FrozenSet, Tuple

# Keyring service/account names the eero-api SDK stores credentials under
# (eero.api.auth_storage.KeyringStorage.SERVICE_NAME / ACCOUNT_NAME). Pinned
# by tests/cli/test_sdk_signatures.py::test_eeroctl_keyring_constants_match_the_sdk
# so a future SDK rename fails CI instead of silently breaking the keyring probe.
KEYRING_SERVICE_NAME = "eero-api"
KEYRING_ACCOUNT_NAME = "auth-tokens"

# Key-name substrings that mark a value as sensitive for the generic
# table/text/list renderer (`formatting/generic.py`). Derived from the SDK's
# own redaction pattern set -- `eero.logging._ZERO_VISIBILITY_PATTERNS`,
# eero-api 8.0.1, /tmp/eero-api-v8.0.1/src/eero/logging.py:55-75 -- so a
# future SDK addition (e.g. a new credential-shaped field name) is inherited
# automatically instead of silently missing from eeroctl's own list (the gap
# that let `session_id` -- the SDK's own bearer-token field -- through
# un-redacted). `serial`/`mac`/`url` are excluded: they are the CLI's normal
# admin identifiers, already shown by dedicated (non-generic) views.
# `email`/`phone`/`sms` are added on top: contact-info keys the SDK's logger
# doesn't need to worry about but eeroctl's generic renderer does, since it
# prints undocumented API payloads verbatim in table/text/list output.
# `json`/`yaml` output is never redacted -- it is the user's explicit opt-in
# to the raw payload.
try:
    from eero.logging import _ZERO_VISIBILITY_PATTERNS as _SDK_ZERO_VISIBILITY_PATTERNS
except ImportError:  # pragma: no cover - guards a future SDK rename
    # Literal fallback mirroring eero.logging._ZERO_VISIBILITY_PATTERNS as of
    # eero-api 8.0.1 (/tmp/eero-api-v8.0.1/src/eero/logging.py:55-75), so a
    # future SDK rename of the private constant fails the parity test in
    # tests/cli/test_const.py loudly instead of silently under-redacting.
    _SDK_ZERO_VISIBILITY_PATTERNS = frozenset(
        {
            "token",
            "password",
            "passwd",
            "secret",
            "key",
            "credential",
            "session_id",
            "session",
            "cookie",
            "auth",
            "api_key",
            "apikey",
            "access_token",
            "refresh_token",
            "user_token",
            "bearer",
            "authorization",
            "private",
        }
    )

GENERIC_RENDER_EXCLUDED_KEY_PATTERNS: FrozenSet[str] = frozenset({"serial", "mac", "url"})
"""Patterns deliberately excluded from `GENERIC_RENDER_SENSITIVE_KEY_PATTERNS`.

These are the CLI's normal admin identifiers, already shown by dedicated
(non-generic) views; none currently appear in the SDK's own pattern set, but
the exclusion is explicit so a future SDK addition doesn't silently start
hiding them.
"""

GENERIC_RENDER_CONTACT_INFO_KEY_PATTERNS: Tuple[str, ...] = ("email", "phone", "sms")
"""Contact-info patterns added on top of the SDK's own credential patterns."""

GENERIC_RENDER_SENSITIVE_KEY_PATTERNS: Tuple[str, ...] = (
    tuple(sorted(_SDK_ZERO_VISIBILITY_PATTERNS - GENERIC_RENDER_EXCLUDED_KEY_PATTERNS))
    + GENERIC_RENDER_CONTACT_INFO_KEY_PATTERNS
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
