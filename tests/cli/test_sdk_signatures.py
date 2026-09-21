"""Signature-binding tests for every SDK call site eeroctl exercises today.

These tests bind the exact positional/keyword shape each command passes against
`inspect.signature` of the **real, installed** `eero.EeroClient` (no mocks). They
exist to catch signature drift that mypy cannot see (e.g. the string-dispatch
call sites in ``network/security.py``) and to give a single, auditable inventory
of every facade method eeroctl depends on.

This module is pinned to eero-api **7.0.0** (the version installed today). The
``feat(deps)!: update eero-api to 8.0.1`` commit rewrites the rows that change
and removes the ones that go away; see
``eero-api-8-migration-plan.md`` §1.3/§2.3/§2.4 for the v8 target shape.
"""

from __future__ import annotations

import inspect
from typing import Any

import pytest
from eero import EeroClient
from eero.api.auth_storage import KeyringStorage
from eero.exceptions import (
    EeroAPIException,
    EeroAuthenticationException,
    EeroException,
    EeroFeatureUnavailableException,
    EeroNetworkException,
    EeroNotFoundException,
    EeroPremiumRequiredException,
    EeroRateLimitException,
    EeroTimeoutException,
    EeroValidationException,
)

# ---------------------------------------------------------------------------
# 1. Facade call-site inventory
# ---------------------------------------------------------------------------
# One row per distinct (method, args, kwargs) shape eeroctl passes today, taken
# from a grep of `client.` / `await client` across `src/eeroctl/commands/**`,
# cross-checked against the migration plan's §1.3 call inventory. Where the
# same method is called with the same shape from multiple sites, one
# representative row is kept (the binding is against the method signature, not
# the call site).
#
# Rows use placeholder values of the correct type/shape; the point is to bind
# the call shape, not to exercise real behaviour.
SDK_CALL_SITES: list[tuple[str, tuple[Any, ...], dict[str, Any], str]] = [
    # -- auth.py --------------------------------------------------------
    ("get_networks", (), {}, "auth.py:114,164,214; network/base.py:78"),
    ("login", ("user@example.com",), {}, "auth.py:192"),
    ("verify", ("123456",), {}, "auth.py:208"),
    ("logout", (), {}, "auth.py:271"),
    ("get_account", (), {}, "auth.py:412"),
    # `client.is_authenticated` (auth.py:111,265,399) is a property, not a
    # callable signature, and `client._api.auth.clear_auth_data()` /
    # `resend_verification_code()` are private SDK access (moved into
    # `sdk_private.py` by a later commit) — out of scope for this facade table.
    # -- activity.py ------------------------------------------------------
    (
        "get_insights",
        ("nid",),
        {"start": "2024-01-01", "end": "2024-01-31", "insight_type": "usage", "cadence": "daily"},
        "activity.py:91-97",
    ),
    (
        "get_insights",
        ("nid",),
        {
            "start": "2024-01-01",
            "end": "2024-01-31",
            "insight_type": "blocked",
            "cadence": "daily",
        },
        "activity.py:167-173",
    ),
    # -- device.py --------------------------------------------------------
    ("get_devices", ("nid",), {}, "device.py:108,192,255,326,417; dhcp.py:93"),
    ("get_device", ("did", "nid"), {}, "device.py:204"),
    ("set_device_nickname", ("did", "New Name", "nid"), {}, "device.py:266"),
    ("block_device", ("did", True, "nid"), {}, "device.py:358"),
    ("pause_device", ("did", True, "nid"), {}, "device.py:449"),
    # -- profile.py ---------------------------------------------------------
    ("get_profiles", ("nid",), {}, "profile.py:95,176,287,349,443,516,586,641,708,788,845"),
    ("get_profile", ("pid", "nid"), {}, "profile.py:187"),
    ("create_profile", ("New Profile", "nid"), {}, "profile.py:233"),
    ("rename_profile", ("pid", "New Name", "nid"), {}, "profile.py:312"),
    ("delete_profile", ("pid", "nid"), {}, "profile.py:375"),
    ("pause_profile", ("pid", True, "nid"), {}, "profile.py:468"),
    ("get_blocked_applications", ("pid", "nid"), {}, "profile.py:528"),
    ("enable_bedtime", ("pid", "22:00", "07:00", ["mon", "tue"], "nid"), {}, "profile.py:813"),
    ("get_profile_schedule", ("pid", "nid"), {}, "profile.py:719"),
    ("clear_profile_schedule", ("pid", "nid"), {}, "profile.py:870"),
    # -- troubleshoot.py ------------------------------------------------
    (
        "get_network",
        ("nid",),
        {},
        "troubleshoot.py:72,256; network/base.py:94,181,212; speedtest.py:77",
    ),
    ("get_diagnostics", ("nid",), {}, "troubleshoot.py:73,146,207,294; network/advanced.py:183"),
    ("get_routing", ("nid",), {}, "troubleshoot.py:208; network/advanced.py:35"),
    ("get_eeros", ("nid",), {}, "troubleshoot.py:268; eero/base.py:54,116"),
    # `is_premium` (troubleshoot.py:302) never existed on 7.0.0 or 8.0.0 — see
    # KNOWN_DEAD_CALL_SITES below.
    # -- eero/base.py, led.py, updates.py, nightlight.py -----------------
    ("get_eero", ("eid", "nid"), {}, "eero/base.py:46"),
    ("reboot_eero", ("eid", "nid"), {}, "eero/base.py:272"),
    ("get_led_status", ("eid", "nid"), {}, "eero/led.py:64"),
    ("set_led", ("eid", True, "nid"), {}, "eero/led.py:126"),
    ("set_led_brightness", ("eid", 50, "nid"), {}, "eero/led.py:165"),
    ("get_nightlight", ("eid", "nid"), {}, "eero/nightlight.py:67"),
    ("set_nightlight", ("eid",), {"enabled": True, "network_id": "nid"}, "eero/nightlight.py:142"),
    ("get_updates", ("nid",), {}, "eero/updates.py:43,77"),
    # `set_nightlight_brightness` (eero/nightlight.py:191) and
    # `set_nightlight_schedule` (eero/nightlight.py:243) never existed on
    # 7.0.0 — see KNOWN_DEAD_CALL_SITES below.
    # -- network/base.py --------------------------------------------------
    ("set_preferred_network", ("nid",), {}, "network/base.py:176"),
    ("set_network_name", ("New Name", "nid"), {}, "network/base.py:279"),
    ("get_premium_status", ("nid",), {}, "network/base.py:314"),
    # -- network/dns.py -----------------------------------------------------
    ("get_dns_settings", ("nid",), {}, "network/dns.py:409,493,670,732"),
    ("clear_custom_dns", ("ipv4", "nid"), {}, "network/dns.py:504,752"),
    ("set_dns_mode", ("custom", None, "nid"), {}, "network/dns.py:514"),
    ("set_custom_dns_ipv4", (["1.1.1.1"], "nid"), {}, "network/dns.py:604"),
    ("set_custom_dns_ipv6", (["2606:4700:4700::1111"], "nid"), {}, "network/dns.py:613"),
    ("set_custom_dns", (["1.1.1.1", "2606:4700:4700::1111"], "nid"), {}, "network/dns.py:630"),
    ("set_dns_caching", (True, "nid"), {}, "network/dns.py:804"),
    # -- network/advanced.py, dhcp.py, forwards.py -------------------------
    ("get_thread", ("nid",), {}, "network/advanced.py:80"),
    ("get_support", ("nid",), {}, "network/advanced.py:127,182"),
    ("get_reservations", ("nid",), {}, "network/dhcp.py:45"),
    ("get_forwards", ("nid",), {}, "network/forwards.py:48,97"),
    # -- network/sqm.py -----------------------------------------------------
    ("get_sqm_settings", ("nid",), {}, "network/sqm.py:56"),
    ("set_sqm_enabled", (True, "nid"), {}, "network/sqm.py:121"),
    (
        "configure_sqm",
        (),
        {"enabled": True, "upload_mbps": 10, "download_mbps": 20, "network_id": "nid"},
        "network/sqm.py:176",
    ),
    # -- network/backup.py --------------------------------------------------
    ("get_backup_network", ("nid",), {}, "network/backup.py:51"),
    ("set_backup_network", (True, "nid"), {}, "network/backup.py:114"),
    ("get_backup_status", ("nid",), {}, "network/backup.py:144"),
    # `is_using_backup` (network/backup.py:146) never existed on 7.0.0 — see
    # KNOWN_DEAD_CALL_SITES below.
    # -- network/guest.py -----------------------------------------------
    (
        "set_guest_network",
        (),
        {"enabled": True, "name": "Guest", "password": "hunter2", "network_id": "nid"},
        "network/guest.py:153",
    ),
    # -- network/security.py: dynamic dispatch, invisible to mypy -----------
    ("get_security_settings", ("nid",), {}, "network/security.py:59"),
    ("set_wpa3", (True, "nid"), {}, "network/security.py:138 (getattr dispatch)"),
    ("set_band_steering", (True, "nid"), {}, "network/security.py:138 (getattr dispatch)"),
    ("set_upnp", (True, "nid"), {}, "network/security.py:138 (getattr dispatch)"),
    ("set_ipv6", (True, "nid"), {}, "network/security.py:138 (getattr dispatch)"),
    ("set_thread_enabled", (True, "nid"), {}, "network/security.py:138 (getattr dispatch)"),
    # -- network/speedtest.py ------------------------------------------------
    ("run_speed_test", ("nid",), {}, "network/speedtest.py:43"),
]


@pytest.mark.parametrize(
    "method_name,args,kwargs,source_ref",
    SDK_CALL_SITES,
    ids=[f"{row[0]}::{row[3].split(';')[0].split(',')[0]}" for row in SDK_CALL_SITES],
)
def test_sdk_call_site_binds(
    method_name: str,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    source_ref: str,
) -> None:
    """Every facade call eeroctl makes today must bind against the real SDK.

    Binds a dummy ``self`` plus the exact args/kwargs the command passes
    against ``inspect.signature`` of the unbound method on the real,
    installed ``eero.EeroClient`` — no mocks, no monkeypatching.
    """
    method = getattr(EeroClient, method_name, None)
    assert method is not None, (
        f"{method_name!r} (called from {source_ref}) does not exist on the "
        f"installed eero.EeroClient"
    )
    signature = inspect.signature(method)
    try:
        signature.bind(object(), *args, **kwargs)
    except TypeError as exc:  # pragma: no cover - failure path, asserted below
        pytest.fail(
            f"{method_name}(*{args!r}, **{kwargs!r}) (called from {source_ref}) "
            f"does not bind against the installed signature {signature}: {exc}"
        )


# ---------------------------------------------------------------------------
# 2. Known-dead call sites
# ---------------------------------------------------------------------------
# eeroctl calls these methods today (masked by broad `except Exception` /
# `type: ignore[attr-defined]`), but they never existed on the SDK, on 7.0.0
# or 8.0.0/8.0.1. Commit 5 (`feat(deps)!: update eero-api to 8.0.1`) rewires
# each of these to its real v8 replacement (see migration plan §1.3/§2.2).
KNOWN_DEAD_CALL_SITES: list[tuple[str, str]] = [
    (
        "is_premium",
        "troubleshoot.py:302 -> replaced by get_premium_status / get_entitlement_features",
    ),
    ("is_using_backup", "network/backup.py:146 -> replaced by get_cellular_backup_usage/events"),
    ("add_blocked_application", "profile.py:600 -> replaced by set_profile_blocked_applications"),
    (
        "remove_blocked_application",
        "profile.py:655 -> replaced by set_profile_blocked_applications",
    ),
    (
        "set_nightlight_brightness",
        "eero/nightlight.py:191 -> replaced by set_nightlight(brightness_percentage=)",
    ),
    (
        "set_nightlight_schedule",
        "eero/nightlight.py:243 -> gains a real signature on v8: (eero_id, schedule, network_id)",
    ),
]


@pytest.mark.parametrize(
    "method_name,note",
    KNOWN_DEAD_CALL_SITES,
    ids=[row[0] for row in KNOWN_DEAD_CALL_SITES],
)
def test_known_dead_call_site_is_absent(method_name: str, note: str) -> None:
    """Document (and pin) that these methods do not exist on the installed SDK.

    If one of these starts existing, this test starts failing — that is the
    signal to move the row into ``SDK_CALL_SITES`` and drop the
    ``except Exception`` / ``type: ignore[attr-defined]`` guard at the call
    site (tracked for commit 5 of the migration plan).
    """
    assert not hasattr(EeroClient, method_name), (
        f"{method_name!r} now exists on EeroClient ({note}); the plan's "
        f"call-site rewrite may already be redundant for this method."
    )


# ---------------------------------------------------------------------------
# 3. Constructor binding
# ---------------------------------------------------------------------------
def test_eeroclient_constructor_binds_cookie_file_and_use_keyring() -> None:
    """`EeroClient(cookie_file=..., use_keyring=...)` binds on 7.0.0.

    The three v8-only kwargs (`send_legacy_cookie`, `accept_language`,
    `get_retries`) are added by commit 9 of the migration plan; they do not
    exist on 7.0.0 and are intentionally not bound here.
    """
    signature = inspect.signature(EeroClient.__init__)
    signature.bind(object(), cookie_file="x", use_keyring=True)


# ---------------------------------------------------------------------------
# 4. Exception import / hierarchy
# ---------------------------------------------------------------------------
def test_exception_names_import_and_subclass_eero_exception() -> None:
    """Every name `errors.py` imports from `eero.exceptions` subclasses `EeroException`.

    Covers the nine names `errors.py` imports plus `EeroNetworkException`
    (not imported today; added to the isinstance chain in a later commit,
    per migration plan §2.6).
    """
    names_and_classes = {
        "EeroAPIException": EeroAPIException,
        "EeroAuthenticationException": EeroAuthenticationException,
        "EeroException": EeroException,
        "EeroFeatureUnavailableException": EeroFeatureUnavailableException,
        "EeroNotFoundException": EeroNotFoundException,
        "EeroPremiumRequiredException": EeroPremiumRequiredException,
        "EeroRateLimitException": EeroRateLimitException,
        "EeroTimeoutException": EeroTimeoutException,
        "EeroValidationException": EeroValidationException,
        "EeroNetworkException": EeroNetworkException,
    }
    for name, cls in names_and_classes.items():
        if name == "EeroException":
            continue
        assert issubclass(cls, EeroException), f"{name} must subclass EeroException"


def test_validation_exception_is_not_an_api_exception_on_installed_sdk() -> None:
    """Pin the installed (7.0.0) hierarchy shape: `EeroValidationException` is a
    direct `EeroException` subclass, NOT an `EeroAPIException` subclass.

    On 7.0.0 the hierarchy is flat: every exception subclasses `EeroException`
    directly. v8 re-bases `EeroNotFoundException`, `EeroPremiumRequiredException`
    and `EeroFeatureUnavailableException` under `EeroAPIException`, but
    `EeroValidationException` stays a direct `EeroException` subclass in both
    versions (verified against the plan's §2.6 v8 hierarchy diagram). The v8
    migration commit (`fix(cli): map the v8 exception hierarchy to exit codes`)
    re-pins this test for the re-based classes.
    """
    assert issubclass(EeroValidationException, EeroException)
    assert not issubclass(EeroValidationException, EeroAPIException)
    # On 7.0.0 the three "re-based in v8" classes are still flat siblings of
    # EeroAPIException, not subclasses of it.
    for cls in (
        EeroNotFoundException,
        EeroPremiumRequiredException,
        EeroFeatureUnavailableException,
    ):
        assert not issubclass(cls, EeroAPIException)


# ---------------------------------------------------------------------------
# 5. Keyring constants
# ---------------------------------------------------------------------------
def test_keyring_storage_constants_match_expected_values() -> None:
    """Pin the SDK's keyring service/account names.

    `commands/auth.py:373` still probes the wrong, pre-SDK service name
    (`"eero"`/`"user_token"`) — see migration plan §2.1. This test pins the
    values a later commit (`fix(cli): stop deriving session validity from the
    cookie file`) must read the real constants from instead of hardcoding a
    literal.
    """
    assert KeyringStorage.SERVICE_NAME == "eero-api"
    assert KeyringStorage.ACCOUNT_NAME == "auth-tokens"


def test_eeroctl_keyring_constants_match_the_sdk() -> None:
    """`eeroctl.const.KEYRING_*` must track the SDK's own storage constants.

    `_check_keyring_available()` probes the keyring under these names; if the
    SDK ever renames its service/account, this test fails loudly instead of
    the probe silently always returning ``False``.
    """
    from eeroctl.const import KEYRING_ACCOUNT_NAME, KEYRING_SERVICE_NAME

    assert KEYRING_SERVICE_NAME == KeyringStorage.SERVICE_NAME
    assert KEYRING_ACCOUNT_NAME == KeyringStorage.ACCOUNT_NAME
