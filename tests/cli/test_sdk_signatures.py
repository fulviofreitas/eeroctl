"""Signature-binding tests for every SDK call site eeroctl exercises today.

These tests bind the exact positional/keyword shape each command passes against
`inspect.signature` of the **real, installed** `eero.EeroClient` (no mocks). They
exist to catch signature drift that mypy cannot see (e.g. the string-dispatch
call sites in ``network/security.py``) and to give a single, auditable inventory
of every facade method eeroctl depends on.

This module is pinned to eero-api **8.0.1** (the version installed since the
``feat(deps)!: update eero-api to 8.0.1`` commit). Signatures are cited against
``/tmp/eero-api-v8.0.1/src/eero/client.py`` (see the DIGEST at
``/tmp/eero-api-v8.0.1/DIGEST.md``) and the migration plan's
``eero-api-8-migration-plan.md`` §1.3/§2.3/§2.4.
"""

from __future__ import annotations

import inspect
from typing import Any

import pytest
from eero import EeroClient
from eero.api.auth_storage import KeyringStorage
from eero.exceptions import (
    EeroAccessDeniedException,
    EeroAPIException,
    EeroAuthenticationException,
    EeroClientBlockedException,
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
    # `block_device`/`unblock_device` split in eero-api 8.0.1 -- no more
    # `blocked: bool` param (client.py:768,788).
    ("block_device", ("did", "nid"), {}, "device.py:358"),
    ("unblock_device", ("did", "nid"), {}, "device.py:358"),
    ("pause_device", ("did", True, "nid"), {}, "device.py:449"),
    # `set_device_type` is on the SDK's live-verified allowlist (client.py:866;
    # migration plan §4 phase B row 25).
    ("set_device_type", ("did", "router", "nid"), {}, "device.py:type_set"),
    # -- profile.py ---------------------------------------------------------
    ("get_profiles", ("nid",), {}, "profile.py:95,176,287,349,443,516,586,641,708,788,845"),
    ("get_profile", ("pid", "nid"), {}, "profile.py:187"),
    # `create_profile` gains keyword-only params in 8.0.1; `network_id` must be
    # passed by keyword (client.py:1038).
    ("create_profile", ("New Profile",), {"network_id": "nid"}, "profile.py:233"),
    ("rename_profile", ("pid", "New Name", "nid"), {}, "profile.py:312"),
    ("delete_profile", ("pid", "nid"), {}, "profile.py:375"),
    ("pause_profile", ("pid", True, "nid"), {}, "profile.py:468"),
    # `get_blocked_applications` was removed in 8.0.0; replaced by
    # `get_dns_policy_applications` (client.py:2552).
    ("get_dns_policy_applications", ("pid", "nid"), {}, "profile.py:528,586,641"),
    (
        "set_profile_blocked_applications",
        ("pid", ["app1", "app2"], "nid"),
        {},
        "profile.py:600,655 (client.py:2559)",
    ),
    ("enable_bedtime", ("pid", "22:00", "07:00", ["mon", "tue"], "nid"), {}, "profile.py:813"),
    ("get_profile_devices", ("pid", "nid"), {}, "profile.py:devices_set (client.py:2271)"),
    (
        "set_profile_devices",
        ("pid", ["/2.2/networks/nid/devices/did"], "nid"),
        {},
        "profile.py:devices_set (client.py:2278)",
    ),
    (
        "allow_domain_for_profiles",
        ("example.com", "nid"),
        {"profiles": ["pid"], "override": None, "is_delete": None},
        "profile.py:profile_dns_allow (client.py:2493)",
    ),
    (
        "block_domain_for_profiles",
        ("example.com", "nid"),
        {"profiles": ["pid"], "override": None, "is_delete": None},
        "profile.py:profile_dns_block (client.py:2530)",
    ),
    # `get_profile_schedule` was removed in 8.0.0; replaced by `get_schedules`,
    # which returns a *list* of pause sub-resources (client.py:1983).
    ("get_schedules", ("pid", "nid"), {}, "profile.py:719"),
    ("clear_profile_schedule", ("pid", "nid"), {}, "profile.py:870"),
    # `delete_schedule` takes the schedule envelope/URL, not a bare id
    # (migration plan §2.5 decision 4; client.py:2042).
    (
        "delete_schedule",
        ({"url": "/2.2/networks/nid/profiles/pid/schedules/sid"},),
        {},
        "profile.py:schedule_delete",
    ),
    # -- troubleshoot.py ------------------------------------------------
    (
        "get_network",
        ("nid",),
        {},
        "troubleshoot.py:72,256; network/base.py:94,181,212; speedtest.py:77; "
        "network/dhcp.py:56 (dhcp show, commit 17); "
        "network/security.py:73 (security show extras, commit 17)",
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
    # `set_nightlight_brightness` now exists on 8.0.1: `(eero_id,
    # brightness_percentage, network_id=None)` (client.py:1920).
    ("set_nightlight_brightness", ("eid", 50, "nid"), {}, "eero/nightlight.py:191"),
    # `set_nightlight_schedule` now exists on 8.0.1: `(eero_id, schedule: Dict,
    # network_id=None)` (client.py:1935); the schedule dict is forwarded to the
    # API verbatim, uninterpreted by the SDK (DIGEST §10). This pins the v7
    # field shape the CLI still sends (Q4, unverified -- no Beacon available).
    (
        "set_nightlight_schedule",
        ("eid", {"enabled": True, "on": "20:00", "off": "06:00"}, "nid"),
        {},
        "eero/nightlight.py:243",
    ),
    ("get_updates", ("nid",), {}, "eero/updates.py:43,77"),
    ("apply_update", ("nid",), {}, "eero/updates.py:updates_apply (client.py:1832)"),
    # -- eero: location/pppoe/ports/port/led-cycle/nightlight-override,
    # migration plan §4 phase C row 36. --
    ("set_location", ("eid", "Office", "nid"), {}, "eero/base.py:location_set (client.py:643)"),
    # `set_pppoe` has no `network_id` parameter (client.py:2726).
    (
        "set_pppoe",
        ("eid",),
        {"username": "user", "password": "pw"},
        "eero/pppoe.py:pppoe_set (client.py:2726)",
    ),
    ("node_action", ("eid", "POWER_CYCLE_ALL_PORTS", "nid"), {}, "eero/base.py:ports_cycle"),
    (
        "port_action",
        ("eid", "1", "ENABLE_PORT", "nid"),
        {},
        "eero/base.py:port_action_cmd (client.py:3086)",
    ),
    # `led_cycle` has no `network_id` parameter and addresses the eero by
    # serial (client.py:3095).
    (
        "led_cycle",
        ("SERIAL123",),
        {"colors": ["red", "blue"], "duration": "10s", "time_per_color": "1s"},
        "eero/led.py:led_cycle (client.py:3095)",
    ),
    (
        "nightlight_override",
        ("eid",),
        {"brightness_percentage": 50, "network_id": "nid"},
        "eero/nightlight.py:nightlight_override (client.py:3103)",
    ),
    # -- network/base.py --------------------------------------------------
    ("set_preferred_network", ("nid",), {}, "network/base.py:176"),
    ("set_network_name", ("New Name", "nid"), {}, "network/base.py:279"),
    (
        "set_network_password",
        ("hunter2", "nid"),
        {},
        "network/base.py:password_set (client.py:529)",
    ),
    (
        "clear_network_password",
        ("nid",),
        {},
        "network/base.py:password_clear (client.py:546)",
    ),
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
    (
        "update_thread",
        (),
        {"enable_credential_syncing": True, "network_id": "nid"},
        "network/advanced.py:thread_set (client.py:1441)",
    ),
    (
        "regenerate_thread_credentials",
        ("nid",),
        {},
        "network/advanced.py:thread_set (client.py:1465)",
    ),
    (
        "run_diagnostics",
        ("nid",),
        {"device": "did", "symptom": "no_internet"},
        "troubleshoot.py:diagnostics_run (client.py:1251)",
    ),
    ("get_support", ("nid",), {}, "network/advanced.py:127,182"),
    ("get_reservations", ("nid",), {}, "network/dhcp.py:45"),
    (
        "create_reservation",
        ({"mac": "AA:BB:CC:DD:EE:FF", "ip": "10.0.0.5"}, "nid"),
        {},
        "network/dhcp.py:reservation_create",
    ),
    (
        "update_reservation",
        ("rid", {"ip": "10.0.0.6"}, "nid"),
        {},
        "network/dhcp.py:reservation_update",
    ),
    (
        "delete_reservation",
        ("rid", "nid"),
        {"delete_forwards": True},
        "network/dhcp.py:reservation_delete",
    ),
    (
        "set_dhcp",
        ("nid",),
        {"mode": "manual", "custom": {"start_ip": "10.0.0.10"}, "custom_v2": None},
        "network/dhcp.py:dhcp_set (client.py:2680)",
    ),
    (
        "set_connection_mode",
        ("BRIDGE", "nid"),
        {},
        "network/dhcp.py:connection_mode_set (client.py:2704)",
    ),
    (
        "set_nat_port_randomization",
        (True, "nid"),
        {},
        "network/dhcp.py:nat_randomization (client.py:2715)",
    ),
    ("get_forwards", ("nid",), {}, "network/forwards.py:48,97"),
    # `forward_data`/`forward_id` are plain values (client.py:1543,1552,1562),
    # not an envelope -- unlike schedules, `update_forward`/`delete_forward`
    # take the forward's own id directly.
    ("create_forward", ({"name": "SSH"}, "nid"), {}, "network/forwards.py:create"),
    ("update_forward", ("fid", {"name": "SSH"}, "nid"), {}, "network/forwards.py:update"),
    ("delete_forward", ("fid", "nid"), {}, "network/forwards.py:delete"),
    # -- network/sqm.py -----------------------------------------------------
    ("get_sqm_settings", ("nid",), {}, "network/sqm.py:56"),
    # `set_sqm_enabled`/`configure_sqm` were removed in 8.0.0; `set_sqm`
    # replaces `set_sqm_enabled` (client.py:2174). `configure_sqm` has no
    # replacement -- `network sqm set` is removed (BREAKING CHANGE).
    ("set_sqm", (True, "nid"), {}, "network/sqm.py:121"),
    # -- network/backup.py --------------------------------------------------
    # `get_backup_network`/`set_backup_network`/`get_backup_status`/
    # `is_using_backup` were all removed in 8.0.0; replaced by the backup
    # internet + cellular backup family (client.py:1950-1976).
    ("get_backup_internet", ("nid",), {}, "network/backup.py:51"),
    ("enable_ddns", ("nid",), {}, "network/ddns.py:ddns_enable (client.py:2890)"),
    ("disable_ddns", ("nid",), {}, "network/ddns.py:ddns_disable (client.py:2899)"),
    ("set_backup_internet", (True, "nid"), {}, "network/backup.py:114"),
    ("get_cellular_backup_usage", ("nid",), {}, "network/backup.py:144"),
    ("get_cellular_backup_events", ("nid",), {}, "network/backup.py:144"),
    # -- network/guest.py -----------------------------------------------
    # `set_guest_network` drops `password` in 8.0.1; password writes go
    # through the dedicated `set_guest_password` endpoint (client.py:1125,1157).
    (
        "set_guest_network",
        (),
        {"enabled": True, "name": "Guest", "network_id": "nid"},
        "network/guest.py:153",
    ),
    ("set_guest_password", ("hunter2", "nid"), {}, "network/guest.py:153"),
    ("clear_guest_password", ("nid",), {}, "network/guest.py:password_clear (client.py:1171)"),
    # -- network/security.py: dynamic dispatch, invisible to mypy -----------
    ("get_security_settings", ("nid",), {}, "network/security.py:59"),
    ("set_wpa3", (True, "nid"), {}, "network/security.py:138 (getattr dispatch)"),
    ("set_band_steering", (True, "nid"), {}, "network/security.py:138 (getattr dispatch)"),
    ("set_upnp", (True, "nid"), {}, "network/security.py:138 (getattr dispatch)"),
    ("set_ipv6", (True, "nid"), {}, "network/security.py:138 (getattr dispatch)"),
    ("set_thread_enabled", (True, "nid"), {}, "network/security.py:138 (getattr dispatch)"),
    ("set_mlo_mode", ("single", "nid"), {}, "network/security.py:mlo_set (client.py:2761)"),
    (
        "set_passpoint_enabled",
        (True, "nid"),
        {},
        "network/security.py:passpoint (getattr dispatch, client.py:2788)",
    ),
    (
        "set_proxied_nodes",
        (True, "nid"),
        {},
        "network/security.py:proxied_nodes (getattr dispatch, client.py:2799)",
    ),
    # -- network/speedtest.py ------------------------------------------------
    ("run_speed_test", ("nid",), {}, "network/speedtest.py:43"),
    # `run_speed_test` returns 202 with `data: null` (8.0.1); `speedtest show`
    # now reads `get_speed_tests(limit=1)` (client.py:1206).
    ("get_speed_tests", ("nid",), {"limit": 1}, "network/speedtest.py:81"),
    # -- phase-A batch 1 catch-up (commits 11-15; see the "test(cli): bind the
    # phase-A batch 1 read call sites" commit for why these lag their family
    # commits) --------------------------------------------------------------
    # -- network/entitlements.py, commands/account.py (commit 11) -----------
    ("get_entitlement_features", ("nid",), {}, "network/entitlements.py:61 (client.py:2292)"),
    ("get_upsell_features", ("nid",), {}, "network/entitlements.py:81 (client.py:2300)"),
    ("get_model_capabilities", ("nid",), {}, "network/entitlements.py:101 (client.py:2305)"),
    ("get_premium_customer", (), {}, "commands/account.py:50 (client.py:2310, no network_id)"),
    # -- network/events.py (commit 12) ---------------------------------------
    (
        "get_app_events",
        ("nid",),
        {"page_size": None, "timestamp": None},
        "network/events.py:61 (client.py:2316)",
    ),
    ("get_network_scan", ("nid",), {}, "network/events.py:82 (client.py:2332)"),
    (
        "get_channel_utilization",
        ("nid",),
        {
            "start": "2024-01-01T00:00:00Z",
            "end": "2024-01-02T00:00:00Z",
            "busy_threshold": None,
            "eero_id": None,
            "band": None,
            "granularity": None,
        },
        "network/events.py:148 (client.py:2339)",
    ),
    # -- network/permissions.py (commit 13) ----------------------------------
    ("get_permissions", ("nid",), {}, "network/permissions.py:35 (client.py:2369)"),
    # -- network/notifications.py (commit 14) --------------------------------
    (
        "get_notification_settings",
        ("nid",),
        {},
        "network/notifications.py:64 (client.py:2378)",
    ),
    (
        "has_unread_notifications",
        ("nid",),
        {},
        "network/notifications.py:84 (client.py:2399)",
    ),
    (
        "get_notification_history",
        ("nid",),
        {"timestamp": None},
        "network/notifications.py:112 (client.py:2413)",
    ),
    # -- network/dns.py: policy subgroup (commit 15) -------------------------
    ("get_advanced_content_filter", ("nid",), {}, "network/dns.py:851 (client.py:2428)"),
    # -- network/members.py (phase A, commit 16) ----------------------------
    ("get_members", ("nid",), {}, "network/members.py:47 (client.py:2572, verified)"),
    ("get_invites", ("nid",), {}, "network/members.py:71 (client.py:2579, unverified)"),
    # -- network/wpa3.py, network/security.py: fast-transition (commit 17) --
    ("get_wpa3_per_band", ("nid",), {}, "network/wpa3.py:47 (client.py:2736)"),
    ("get_fast_transition", ("nid",), {}, "network/security.py:221 (client.py:2770)"),
    # -- network/wpa3.py: set, network/security.py: fast-transition writes
    # (commit 43) --
    (
        "set_wpa3_per_band",
        ("nid",),
        {"band_2_4_ghz": "WPA3", "band_5_ghz": "WPA3"},
        "network/wpa3.py:wpa3_per_band_set (client.py:2743)",
    ),
    (
        "set_fast_transition",
        (True, "nid"),
        {},
        "network/security.py:_set_fast_transition (client.py:2777)",
    ),
    # -- network/power_saving.py (phase A, commit 18) -----------------------
    (
        "get_power_saving_schedules",
        ("nid",),
        {},
        "network/power_saving.py:61 (client.py:2830, verified)",
    ),
    # -- network/backup.py: access-points subgroup (phase A, commit 19) -----
    (
        "list_backup_access_points",
        ("nid",),
        {},
        "network/backup.py:218 (client.py:2910)",
    ),
    (
        "discover_backup_ssids",
        ("nid",),
        {},
        "network/backup.py:236 (client.py:2974, GET, verified)",
    ),
    # -- network/subnets.py (phase A, commit 20) -----------------------------
    ("get_subnets_config", ("nid",), {}, "network/subnets.py:50 (client.py:2991)"),
    (
        "get_subnet_content_filters",
        ("sid", "nid"),
        {},
        "network/subnets.py:88 (client.py:3023)",
    ),
    # -- network/wan.py (phase A, commit 21) ---------------------------------
    ("get_multistaticip", ("nid",), {}, "network/wan.py:81 (client.py:3032)"),
    # -- eero/connections.py, device.py, network/ouicheck.py (commit 22) ----
    ("get_connections", ("eid", "nid"), {}, "eero/connections.py:65 (client.py:661)"),
    ("get_eero_support", ("serial",), {}, "eero/connections.py:115 (client.py:3114)"),
    ("get_device_labels", ("did", "nid"), {}, "device.py:521 (client.py:879)"),
    (
        "get_ouicheck",
        ("nid",),
        {"serial": "serial", "version": "1.0"},
        "network/ouicheck.py:69 (client.py:1805)",
    ),
    # -- network/speedtest.py: history, network/transfer.py (commit 23) -----
    (
        "get_speed_tests",
        ("nid",),
        {"limit": None, "start_time": None, "end_time": None},
        "network/speedtest.py:144 (client.py:1206)",
    ),
    ("get_transfer_stats", ("nid", None), {}, "network/transfer.py:41 (client.py:1569)"),
    # -- activity.py: devices/profiles insights (phase A, commit 24) --------
    (
        "get_devices_insights",
        ("nid",),
        {
            "start": "2024-01-01T00:00:00Z",
            "end": "2024-01-02T00:00:00Z",
            "cadence": "daily",
            "insight_type": "inspected",
        },
        "activity.py:283 (client.py:1308)",
    ),
    (
        "get_device_insights",
        ("did", "nid"),
        {
            "start": "2024-01-01T00:00:00Z",
            "end": "2024-01-02T00:00:00Z",
            "cadence": "daily",
            "insight_type": "inspected",
        },
        "activity.py:340 (client.py:1328)",
    ),
    (
        "get_profiles_insights",
        ("nid",),
        {
            "start": "2024-01-01T00:00:00Z",
            "end": "2024-01-02T00:00:00Z",
            "cadence": "daily",
            "insight_type": "inspected",
        },
        "activity.py:381 (client.py:1349)",
    ),
    (
        "get_profile_insights",
        ("pid", "nid"),
        {
            "start": "2024-01-01T00:00:00Z",
            "end": "2024-01-02T00:00:00Z",
            "cadence": "daily",
            "insight_type": "inspected",
        },
        "activity.py:462 (client.py:1369)",
    ),
    (
        "get_profile_devices_insights",
        ("pid", "nid"),
        {
            "start": "2024-01-01T00:00:00Z",
            "end": "2024-01-02T00:00:00Z",
            "cadence": "daily",
            "insight_type": "inspected",
        },
        "activity.py:451 (client.py:1390)",
    ),
    # -- network/usage.py: data-usage family (phase A, commit 24b, closes #46) --
    (
        "get_data_usage",
        ("nid",),
        {
            "start": "2024-01-01T00:00:00Z",
            "end": "2024-01-02T00:00:00Z",
            "cadence": "daily",
            "timezone": None,
        },
        "network/usage.py:92 (client.py:1578)",
    ),
    (
        "get_data_usage_breakdown",
        ("nid",),
        {
            "start": "2024-01-01T00:00:00Z",
            "end": "2024-01-02T00:00:00Z",
            "cadence": None,
            "timezone": None,
        },
        "network/usage.py:126 (client.py:1605)",
    ),
    (
        "get_devices_data_usage",
        ("nid",),
        {
            "start": "2024-01-01T00:00:00Z",
            "end": "2024-01-02T00:00:00Z",
            "cadence": None,
            "timezone": None,
            "profile_id": None,
        },
        "network/usage.py:162 (client.py:1624)",
    ),
    (
        "get_device_data_usage",
        ("mac", "nid"),
        {
            "start": "2024-01-01T00:00:00Z",
            "end": "2024-01-02T00:00:00Z",
            "cadence": "daily",
            "timezone": None,
        },
        "network/usage.py:204 (client.py:1649)",
    ),
    (
        "get_eeros_data_usage_summary",
        ("nid",),
        {
            "start": "2024-01-01T00:00:00Z",
            "end": "2024-01-02T00:00:00Z",
            "cadence": "daily",
            "timezone": None,
        },
        "network/usage.py:239 (client.py:1669)",
    ),
    (
        "get_eero_data_usage",
        ("eid", "nid"),
        {
            "start": "2024-01-01T00:00:00Z",
            "end": "2024-01-02T00:00:00Z",
            "cadence": "daily",
            "timezone": None,
        },
        "network/usage.py:280 (client.py:1688)",
    ),
    (
        "get_profile_data_usage",
        ("pid", "nid"),
        {
            "start": "2024-01-01T00:00:00Z",
            "end": "2024-01-02T00:00:00Z",
            "cadence": "daily",
            "timezone": None,
        },
        "network/usage.py:322 (client.py:1708)",
    ),
    (
        "get_unprofiled_devices_data_usage",
        ("nid",),
        {
            "start": "2024-01-01T00:00:00Z",
            "end": "2024-01-02T00:00:00Z",
            "cadence": "daily",
            "timezone": None,
        },
        "network/usage.py:381 (client.py:1728)",
    ),
    (
        "get_unprofiled_data_usage_summary",
        ("nid",),
        {
            "start": "2024-01-01T00:00:00Z",
            "end": "2024-01-02T00:00:00Z",
            "cadence": "daily",
            "timezone": None,
        },
        "network/usage.py:371 (client.py:1747)",
    ),
    (
        "get_data_usage_report_settings",
        ("nid",),
        {},
        "network/usage.py:417 (client.py:1766)",
    ),
    # -- network/guest.py: show rewired onto the dedicated endpoint (24c) ----
    ("get_guest_network", ("nid",), {}, "network/guest.py:68 (client.py:1118)"),
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
# These methods do not exist on the installed SDK (8.0.1) and never did on
# 7.0.0 either. `is_premium`, `is_using_backup`, `add_blocked_application` and
# `remove_blocked_application` were rewired to their v8 replacements by this
# commit (see SDK_CALL_SITES above and migration plan §1.3/§2.2).
# `set_nightlight_brightness`/`set_nightlight_schedule` were dead on 7.0.0 but
# are now real facade methods (moved into SDK_CALL_SITES above).
# `configure_sqm`/`set_sqm_bandwidth`/`set_sqm_auto` were removed in 8.0.0
# with no replacement -- `network sqm set` is deleted (BREAKING CHANGE).
KNOWN_DEAD_CALL_SITES: list[tuple[str, str]] = [
    ("is_premium", "removed on 7.0.0 and 8.0.1 -- no `network sqm set` equivalent either"),
    ("is_using_backup", "removed on 7.0.0 and 8.0.1"),
    ("add_blocked_application", "removed on 7.0.0 and 8.0.1"),
    ("remove_blocked_application", "removed on 7.0.0 and 8.0.1"),
    ("set_sqm_enabled", "removed in eero-api 8.0.0 -- see set_sqm"),
    ("configure_sqm", "removed in eero-api 8.0.0; no bandwidth-limit replacement exists"),
    ("set_sqm_bandwidth", "removed in eero-api 8.0.0; no bandwidth-limit replacement exists"),
    ("set_sqm_auto", "removed in eero-api 8.0.0; no bandwidth-limit replacement exists"),
    ("get_blocked_applications", "removed in eero-api 8.0.0 -- see get_dns_policy_applications"),
    ("get_profile_schedule", "removed in eero-api 8.0.0 -- see get_schedules"),
    ("get_backup_network", "removed in eero-api 8.0.0 -- see get_backup_internet"),
    ("set_backup_network", "removed in eero-api 8.0.0 -- see set_backup_internet"),
    ("get_backup_status", "removed in eero-api 8.0.0 -- see get_cellular_backup_usage/events"),
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
    """`EeroClient(cookie_file=..., use_keyring=...)` binds on 8.0.1."""
    signature = inspect.signature(EeroClient.__init__)
    signature.bind(object(), cookie_file="x", use_keyring=True)


def test_eeroclient_constructor_binds_v8_keyword_only_args() -> None:
    """`EeroClient` gained three keyword-only kwargs in 8.0.1 (DIGEST §1,
    `client.py:49-59`): `send_legacy_cookie`, `accept_language`, `get_retries`.

    They are not wired into eeroctl's CLI/config surface yet (that is a later
    phase-C commit, migration plan §6.4 row 9); this test only pins that the
    installed SDK still accepts them.
    """
    signature = inspect.signature(EeroClient.__init__)
    signature.bind(
        object(),
        cookie_file="x",
        use_keyring=True,
        send_legacy_cookie=True,
        accept_language="en-US",
        get_retries=0,
    )


# ---------------------------------------------------------------------------
# 4. Exception import / hierarchy
# ---------------------------------------------------------------------------
def test_exception_names_import_and_subclass_eero_exception() -> None:
    """Every name `errors.py` imports from `eero.exceptions` subclasses `EeroException`.

    Covers the nine names `errors.py` imports today plus `EeroNetworkException`
    (not imported by `errors.py` yet; added to the isinstance chain by commit 6,
    per migration plan §2.6) and the two new 8.0.0 classes,
    `EeroAccessDeniedException`/`EeroClientBlockedException`
    (DIGEST §2, exceptions.py:101,113), also wired up by commit 6.
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
        "EeroAccessDeniedException": EeroAccessDeniedException,
        "EeroClientBlockedException": EeroClientBlockedException,
    }
    for name, cls in names_and_classes.items():
        if name == "EeroException":
            continue
        assert issubclass(cls, EeroException), f"{name} must subclass EeroException"


def test_v8_exception_hierarchy_rebases_three_classes_under_api_exception() -> None:
    """Pin the installed (8.0.1) hierarchy shape (DIGEST §2, `exceptions.py`):

    ```
    EeroException
    +-- EeroAuthenticationException / EeroRateLimitException /
    |   EeroNetworkException / EeroTimeoutException
    +-- EeroValidationException            (NOT an EeroAPIException)
    +-- EeroAPIException
        +-- EeroAccessDeniedException      (new in 8.0.0)
        +-- EeroClientBlockedException     (new in 8.0.0)
        +-- EeroNotFoundException          (re-based in 8.0.0)
        +-- EeroPremiumRequiredException   (re-based in 8.0.0)
        +-- EeroFeatureUnavailableException (re-based in 8.0.0)
    ```

    Unlike on 7.0.0 (flat hierarchy, every exception a direct `EeroException`
    subclass), `EeroNotFoundException`, `EeroPremiumRequiredException` and
    `EeroFeatureUnavailableException` are now `EeroAPIException` subclasses;
    `EeroValidationException` stays a direct `EeroException` subclass in both
    versions.
    """
    assert issubclass(EeroValidationException, EeroException)
    assert not issubclass(EeroValidationException, EeroAPIException)
    for cls in (
        EeroNotFoundException,
        EeroPremiumRequiredException,
        EeroFeatureUnavailableException,
        EeroAccessDeniedException,
        EeroClientBlockedException,
    ):
        assert issubclass(cls, EeroAPIException)


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
