# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.0.0](https://github.com/fulviofreitas/eeroctl/compare/v2.21.8...v3.0.0) (2026-09-24)

### ⚠ BREAKING CHANGES

* `dns show` structured output (json, yaml, text, list) now emits
only the DNS configuration rather than the entire network object, and the schema
identifier moves to eero.network.dns.show/v2. The previous payload included the
Wi-Fi and guest network passwords in plaintext along with the WAN IP,
geo-location, node serials and LAN topology. Scripts reading non-DNS fields from
`dns show` must use `network show` instead.
* DNS writes now reboot every eero on the network. Commands that
previously changed nothing and exited 0 now cause a brief network-wide outage
beginning a few minutes after the command returns. DNS writes require typing
REBOOT to confirm; --force bypasses the prompt and additionally forces a rewrite
when the configuration already matches. Repeat invocations without --force are
skipped instead of rewriting. The mode argument is no longer a fixed choice: it
accepts auto, custom, or any provider name the network's DNS catalogue serves
(run 'eero network dns providers'), resolved by eeroctl rather than the SDK.
* eero auth status no longer reports session_expiry; the structured schema is eero.auth.status/v2

* fix(cli): back up a pre-v8 credential file before the SDK migrates it

* feat(deps)!: update eero-api to 8.0.1
* network sqm set is removed (the API has no bandwidth fields); network guest set --password now calls the dedicated guest-password endpoint; profile apps block/unblock replace the
whole blocked-application list; profile schedule show returns a list of schedules; speedtest run no longer prints results (use speedtest show).

* fix(cli): map the v8 exception hierarchy to exit codes
* unauthenticated commands exit 3 everywhere (previously 1 via run_with_client); new exit codes 13 (client blocked) and 14 (network error)

* feat(safety): classify writes by verification status and reboot scope
* network security wpa3/band-steering/upnp/ipv6 and network sqm enable/disable now require the REBOOT confirmation phrase

* feat(cli): surface the SDK's unverified-write warning through the renderer

* fix(cli): keep write-confirmation prompts off stdout and name the read command in skip messages

Several require_write_confirmation call sites passed console=cli_ctx.console
(stdout) instead of the stderr console, so the mesh-reboot warning and the
unverified-write note leaked into --output json stdout on device, eero and
network speedtest commands. write_if_changed's "already configured" message
also gets the read_command hint now, matching the "verify with" message on
the write-issued path.

* test(cli): cover the skip-unchanged path and stderr warnings for registry-backed writes

* test(cli): reject malicious ids and foreign-network links before any request

* fix(cli): pass id, path and URL inputs to the SDK unchanged

* test(cli): cover the v8 call shapes for backup, guest, speedtest, led and nightlight

* feat(cli): expose send_legacy_cookie, accept_language and get_retries

Adds the three remaining EeroClient constructor options from the v8
migration plan (§3.4) as global flags/config keys, plumbed through
build_client(cli_ctx). main.py now sets cli(auto_envvar_prefix="EEROCTL")
(both via context_settings, for CliRunner, and explicitly in main(), for
the real entry point) so every global option gets a free EEROCTL_<NAME>
env var with no per-option code.

Two env vars need explicit handling: EEROCTL_CONFIG_DIR overrides
utils.get_config_dir() (expanduser + mkdir, same as today), and
EEROCTL_SESSION_TOKEN puts eeroctl in an ephemeral mode -- build_client
forces cookie_file=None/use_keyring=False (SDK MemoryStorage, never
touching disk or keyring), and the new prepare_client() helper calls the
async EeroClient.set_session_token() right after __aenter__ (both
with_client and run_with_client call it). auth login/logout/clear refuse
with exit 2 under this mode; auth status reports auth_method: "env" and
skips the keyring probe. The token is never printed, logged, or included
in any output.

--debug now only raises the `eero` and `eeroctl` loggers to DEBUG (each
with their own stderr handler); the root logger stays at WARNING so
aiohttp never logs the raw X-User-Token header (R11).

* fix(cli): remove the pre-v8 credential backup on auth clear

`auth clear` promised to remove "all stored credentials" but never
deleted the plaintext pre-v8 backup written by backup_legacy_cookie_file,
leaving a readable copy of the token behind indefinitely (and, in keyring
mode, re-creating the exact plaintext copy the SDK's own migration
deletes). auth clear and auth logout now unlink
<cookie_file>.pre-v8.bak if present, reporting "removed pre-v8 credential
backup" on stderr; auth status surfaces its presence via
storage.cookie_file.legacy_backup_present (table row "Legacy Backup") so
it is visible even when the CLI doesn't remove it.

Also: backup_legacy_cookie_file now unlinks a partially written backup
file on a write failure, so a truncated file never masquerades as a good
backup.

* fix(cli): reject --offline together with --check in auth status

--offline skips the live account probe entirely, so a session_valid of
None (unverified) previously satisfied --check's "ok" condition
unconditionally -- `auth status --offline --check` exited 0 for any
locally-stored token, including one that had been revoked server-side.
The two flags are now mutually exclusive (click.UsageError, exit 2,
before any client is built), and both --help strings say so.

* fix(cli): escape API-supplied text in rendered error messages

* test(cli): add shared mock_client and mock_client_raising fixtures

* fix(cli): send write_if_changed messages to stderr

write_if_changed(console=console) at seven call sites (network/sqm.py,
network/security.py, network/guest.py, network/backup.py, device.py x2,
eero/led.py) -- plus profile.py's pause/unpause, found during the same
sweep -- passed cli_ctx.console (stdout) instead of stderr, so "Write
accepted. Verify with ..." and "Already configured ..." landed on stdout
and broke --output json | jq. All eight now pass cli_ctx.err_console.

Also narrows network/backup.py's two except Exception blocks in the
read()/write() closures to except EeroException with the existing
isinstance(e, EeroPremiumRequiredException) check, restoring this file's
parity with commit 6's exception-handling style.

* test(cli): make the write-registry guard see getattr dispatch

The source-walking completeness test only matches literal
`await client.<verb>(`, so the five security toggles (wpa3, band-steering,
upnp, ipv6, thread) dispatched via `method = getattr(client, api_method);
await method(...)` in network/security.py were invisible to it -- the same
shape of blind spot that let a mypy string-dispatch issue ship in the
eero-api 7->8 migration.

Adds TestSecurityToggleDispatchCoverage: extracts the (setting_name,
sdk_method) pairs from the literal _make_security_toggle(...) registration
calls (the one place the toggle inventory is textual, grounding the test in
source rather than a hand-maintained list), asserts every extracted toggle
has both enable/disable WriteSpecs, pins the toggle count, and proves the
enforcement mechanism itself: an unregistered toggle raises KeyError from
get_write_spec before any confirmation prompt or SDK call, so it can never
silently reach an unconfirmed, unregistered write.

* fix(cli): keep names with ? and # resolvable while forwarding paths and URLs

* feat(options): shared time-window option group

Add time_window_options(), a decorator factory adding --start/--end
(ISO-8601 UTC, Z-suffixed, format-validated by a click.ParamType so a
bad value is a Click usage error -- exit 2 -- before any request),
--cadence (click.Choice, required/optional/choices all configurable),
and an optional --timezone (IANA name, validated via zoneinfo.ZoneInfo)
to any command.

Also add resolve_time_window(start, end, cadence), a helper that fills
in sensible defaults when --start/--end are omitted (end = now UTC;
start = end - 24h for hourly, end - 7d otherwise) and raises
click.UsageError (exit 2) on an inverted window, so phase-A command
bodies that wire this up can resolve the window in one line.

This lands the shared group described in the eero-api 8.0.1 migration
plan (S4, phase A) ahead of the per-family read commits that will call
it (network channels, activity *, network usage *); no commands are
rewired here.

* feat(network): add entitlements and premium read commands

Commands:
- network entitlements show          -- get_entitlement_features (client.py:2292)
- network entitlements upsell        -- get_upsell_features (client.py:2300)
- network entitlements capabilities  -- get_model_capabilities (client.py:2305)
- account premium                    -- get_premium_customer (client.py:2310, no network_id)

Adds a new top-level `account` group (commands/account.py, registered in
main.py) for the one eero-api 8.0.1 facade method that takes no network_id at
all. Rewires troubleshoot doctor's premium check onto get_entitlement_features,
replacing the dead is_premium reference the plan calls out. Response shapes are
undocumented, so all four commands render through a new shared generic
key/value renderer (formatting/generic.py) with a raw data passthrough for
json/yaml, per the phase-A conventions; dedicated tables land later once a
live sample is captured.

* feat(network): add events, scan and channel-utilization reads

Commands:
- network events    -- get_app_events (client.py:2316), --page-size/--cursor,
  next-page cursor surfaced in meta.next_cursor for json/yaml
- network scan      -- get_network_scan (client.py:2332)
- network channels  -- get_channel_utilization (client.py:2339), --start/--end
  (required), --band (choices from eero.api.events.CHANNEL_UTILIZATION_BANDS),
  --eero, --granularity, --busy-threshold

network channels uses bare --start/--end rather than time_window_options:
get_channel_utilization has no cadence parameter, unlike the insights/
data-usage families that decorator targets. Extends OutputMeta with an
`extra` dict so the generic renderer can surface a pagination cursor in the
json/yaml envelope's meta object without a bespoke table.

* feat(network): add permissions read

Command:
- network permissions -- get_permissions (client.py:2369)

Plain, live-verified GET; also usable as a pre-flight hint for 403s from
other commands. Unlike most phase-A families, the SDK documents this shape
(eero/api/permissions.py:38-41: "Returns permissions (a per-capability
mapping) and role"), so table output gets a small dedicated role +
capability-map view; json/yaml/text/list still pass data through unchanged
via the generic renderer.

* feat(network): add notification reads

Commands:
- network notifications show    -- get_notification_settings (client.py:2378)
- network notifications unread  -- has_unread_notifications (client.py:2399)
- network notifications history -- get_notification_history (client.py:2413), --cursor

show and unread have SDK-documented shapes (eero/api/notifications.py:41-43,
114-115: one boolean per event key; data.has_unread), so table output gets a
small dedicated view for each. history's shape is undocumented and reuses the
same best-effort pagination-cursor heuristic as network events, surfaced in
meta.next_cursor for json/yaml via render_generic_with_cursor.

* feat(network): add dns policy read

Command:
- network dns policy show -- get_advanced_content_filter (client.py:2428),
  premium, data.allowed_list/blocked_list

Adds a new `policy` subgroup under the existing `network dns` group,
appended at the end of dns.py to avoid touching the DNS write commands
(confirmation flow there is being rewired concurrently). Only the top-level
key names are documented, so this goes through the generic key/value
renderer for every output format.

* feat(network): add members read commands

Commands:
- network members list    -- get_members (client.py:2572, verified,
  data.members)
- network members invites -- get_invites (client.py:2579, unverified read;
  403 seen live)

`invites` maps EeroAccessDeniedException -- and the pre-commit-6 403
EeroAPIException fallback -- to a friendly "not permitted for this account"
message and exit 4, instead of the generic "Permission denied" text, since
some accounts see a 403 here even though they can list members.

Adds SDK_CALL_SITES rows for get_members/get_invites per the new standing
rule (test-audit); the eleven batch-1 methods plus commit 15's
get_advanced_content_filter are deferred to the catch-up commit after
commit 18. Reuses test_events.py's _mock_client/_mock_client_raising
helpers instead of redefining them.

* feat(network): add dhcp, wpa3, fast-transition and extended security reads

Commands:
- network dhcp show -- data.dhcp/lease/connection/ip_settings/wan_type read
  straight from get_network (client.py:487); dhcp reservations/leases unchanged
- network wpa3 show -- get_wpa3_per_band (client.py:2736), a new top-level
  group distinct from the existing network security wpa3 enable/disable toggle
- network security fast-transition show -- get_fast_transition (client.py:2770),
  new subgroup of network security
- network security show (extend) -- adds mlo_mode/passpoint/proxied_nodes/ddns,
  read from the get_network envelope alongside the existing get_security_settings
  fields (no dedicated GETs exist for these)

security.py hunks are limited to the show view and the new fast-transition
subgroup; the enable/disable toggle factory is untouched (commit 7 is
rewriting its confirmation calls concurrently). dns.py is untouched by this
commit. Adds SDK_CALL_SITES rows for get_wpa3_per_band/get_fast_transition and
extends the existing get_network row's citations for the two new call sites.

* feat(network): add power-saving schedule reads

Command:
- network power-saving schedules list -- get_power_saving_schedules
  (client.py:2830, verified)

Creates the power-saving group (schedules subgroup); phase C adds
create/update/delete and the set_power_saving toggle. Response shape is
undocumented beyond the envelope, so this goes through the generic key/value
renderer for every format. Adds an SDK_CALL_SITES row for
get_power_saving_schedules.

* test(cli): bind the phase-A batch 1 read call sites

Adds the twelve SDK_CALL_SITES rows batch 1 (commits 11-14) and commit 15
skipped: get_entitlement_features, get_upsell_features,
get_model_capabilities, get_premium_customer, get_app_events,
get_network_scan, get_channel_utilization, get_permissions,
get_notification_settings, has_unread_notifications,
get_notification_history, get_advanced_content_filter. Catch-up per the
test-audit standing rule; no production code changes, no rewriting of the
batch-1/commit-15 commits themselves.

* fix(output): stop truncating dotted string values in table and text output

OutputManager._format_value() treated any string containing exactly one dot
as a stringified enum ("EeroNetworkStatus.ONLINE" -> "online") and truncated
it to the text after the last dot. That heuristic fired on any plain string
with a single dot: an email (victim@example.com -> com), an API path
(/2.2/networks/123 -> 2/networks/123), a version string (6.2 -> 2).

Restrict the flattening to real Enum instances (isinstance(value, Enum) ->
value.name.lower()), which also covers every eeroctl.const enum
(EeroDeviceType/EeroNetworkStatus/EeroDeviceStatus, all `str, Enum`
subclasses). Plain strings, including ones that merely look like a
stringified enum, now always pass through unchanged.

Security-review finding (batch 1/2 review); Medium severity.

* fix(output): redact credential and contact keys in generic table and text rendering

formatting/generic.py's render_generic() prints every key of an undocumented
API payload verbatim in table/list/text output -- there is no dedicated view
filtering the fields first (that's the whole point of the generic renderer).
A security review found account premium/network events echoing a user token
and an email address that way.

table/list/text now recursively redact any value whose key (case-insensitive,
any nesting level) matches the new const.GENERIC_RENDER_SENSITIVE_KEY_PATTERNS
(token/password/secret/cookie/authorization/api_key/apikey/email/phone/sms) to
"<redacted>", mirroring a subset of the SDK's own eero.logging.
_ZERO_VISIBILITY_PATTERNS (/tmp/eero-api-v8.0.1/src/eero/logging.py:55-75)
plus the contact-info keys eeroctl's generic renderer specifically needs.
serial/mac/url stay visible -- they are the CLI's normal admin identifiers,
already shown by dedicated (non-generic) views. json/yaml keep the raw data
passthrough unchanged: that format is the user's explicit opt-in to the full
payload.

Security-review finding (batch 1/2 review); Medium severity.

* feat(network): add backup access-point reads

Commands:
- network backup access-points list     -- list_backup_access_points
  (client.py:2910)
- network backup access-points discover -- discover_backup_ssids
  (client.py:2974, GET, verified)

New access-points subgroup appended to the existing backup group; backup
show/status (already rewired in commit 5 onto get_backup_internet/
get_cellular_backup_*) are untouched. add/update/delete/rearrange and the
start-discovery/connectivity-check writes are phase C. Response shapes are
undocumented beyond the envelope (no live sample captured yet, §5.3), so
both commands render via the generic renderer.

* fix(output): close the remaining generic-redaction gaps

Three related gaps found in the batch-2 security review (b5446ef BLOCK):

1. const.GENERIC_RENDER_SENSITIVE_KEY_PATTERNS was a hand-maintained literal
   tuple that missed session (-> session_id, the SDK's own bearer-token
   field), credential, passwd, bearer, private, auth. Derive it from the
   SDK's own eero.logging._ZERO_VISIBILITY_PATTERNS
   (/tmp/eero-api-v8.0.1/src/eero/logging.py:55-75) instead, minus the
   documented serial/mac/url exclusions, plus the email/phone/sms contact-info
   keys added on top. A literal fallback (mirroring the same 8.0.1 patterns)
   covers a future SDK rename of the private constant; a parity test
   (tests/cli/test_const.py) asserts every SDK pattern except the three
   exclusions is present.

2. formatting/members.py's print_members() gated on
   EeroCliContext.is_structured_output(), which is True for json/yaml/text
   alike, so `--output text` rendered the raw, unredacted data.members
   payload (email, phone, an unredacted invite_token/session_id). Only
   json/yaml may see the raw payload now; table/list/text go through the
   redacting path. Also gives `members list` a dedicated table view
   (name/email/role/status) -- email shown deliberately, since the command's
   whole purpose is showing who has access.

3. security.py's `security show` extras (mlo_mode/passpoint/proxied_nodes/
   ddns) were rendered with str(...) outside render_generic in both the
   table and list paths, so a planted ddns credential wasn't redacted.
   Both paths now pass extras through formatting.generic.redact_sensitive
   first; json is left as the deliberate raw-payload opt-in.

SDK_CALL_SITES untouched.

* feat(network): add subnet reads

Commands:
- network subnets show                    -- get_subnets_config (client.py:2991)
- network subnets filters show <subnet-id> -- get_subnet_content_filters
  (client.py:3023)

The subnet id for `filters show` names a nested sub-resource and is passed
to the SDK verbatim (no client-side link parsing needed; the SDK validates
it). Response shapes are undocumented beyond the envelope (no live sample
captured yet, §5.3), so both commands render via the generic renderer.
set_subnets_config/delete_subnet/set_subnet_content_filters are phase C.

* feat(network): add wan multistaticip read

Command:
- network wan multistaticip show -- get_multistaticip (client.py:3032)

Q7 (decided 2026-09-21): absent-feature reads exit 0 with a "not configured"
line and data: null in structured output; exit 5 stays reserved for a wrong
id. The SDK documents (eero/api/wan.py:49-51) that a network without the
multi-static-IP feature returns HTTP 404 with error code
error.network.multistaticip_not_found; that specific EeroNotFoundException
.error_code is treated as "not configured", any other EeroNotFoundException
(a wrong network id) propagates to the standard exit-5 mapping. Response
shape is otherwise undocumented, so the configured case renders via the
generic renderer.

* feat(eero): add connections, support, labels and ouicheck reads

Commands:
- eero connections <id>   -- get_connections (client.py:661)
- eero support <id>       -- get_eero_support (client.py:3114, takes a bare
  serial; 404 on some nodes -> "unavailable", exit 0 per Q7)

### ✨ Features

* revamp eeroctl for eero-api 8.0.3 ([#121](https://github.com/fulviofreitas/eeroctl/issues/121)) ([0a05304](https://github.com/fulviofreitas/eeroctl/commit/0a05304a98fd58e671ba1c6f070ef3b3f2e1d152)), closes [#119](https://github.com/fulviofreitas/eeroctl/issues/119) [#119](https://github.com/fulviofreitas/eeroctl/issues/119)

## [2.21.8](https://github.com/fulviofreitas/eeroctl/compare/v2.21.7...v2.21.8) (2026-08-05)

### 🐛 Bug Fixes

* **deps:** bump cryptography from 48.0.1 to 50.0.0 ([#115](https://github.com/fulviofreitas/eeroctl/issues/115)) ([0499b20](https://github.com/fulviofreitas/eeroctl/commit/0499b20874dcf61ddada2075164001e5035fb96e))

## [2.21.7](https://github.com/fulviofreitas/eeroctl/compare/v2.21.6...v2.21.7) (2026-08-05)

### 🐛 Bug Fixes

* **deps:** bump aiohttp from 3.14.1 to 3.14.3 ([#114](https://github.com/fulviofreitas/eeroctl/issues/114)) ([1b00337](https://github.com/fulviofreitas/eeroctl/commit/1b0033729e3184040e5f317b2cd30815d13ab632))

### ♻️ Refactoring

* **ci:** migrate issue-triage and draft-fix to workflow-arsenal reusables ([d6f17f0](https://github.com/fulviofreitas/eeroctl/commit/d6f17f0c258b1eb49da30e06b72efcfadaceb5aa))

## [2.21.6](https://github.com/fulviofreitas/eeroctl/compare/v2.21.5...v2.21.6) (2026-07-22)

### 🐛 Bug Fixes

* **cli:** repair device/activity commands and add device pause ([#111](https://github.com/fulviofreitas/eeroctl/issues/111)) ([eecb6ed](https://github.com/fulviofreitas/eeroctl/commit/eecb6edcd454b4dc092924438c3ef622ad5ac3e9)), closes [#106](https://github.com/fulviofreitas/eeroctl/issues/106) [#107](https://github.com/fulviofreitas/eeroctl/issues/107) [#108](https://github.com/fulviofreitas/eeroctl/issues/108) [#109](https://github.com/fulviofreitas/eeroctl/issues/109)

## [2.21.5](https://github.com/fulviofreitas/eeroctl/compare/v2.21.4...v2.21.5) (2026-07-21)

### 🐛 Bug Fixes

* **ci:** suppress '[aw] No-Op Runs' tracker issue ([5f6be38](https://github.com/fulviofreitas/eeroctl/commit/5f6be38d5e677907a9ce9054d857eca21b8472c6))

## [2.21.4](https://github.com/fulviofreitas/eeroctl/compare/v2.21.3...v2.21.4) (2026-07-21)

### 🐛 Bug Fixes

* **ci:** update triage to gpt-4o-mini + gh-aw v0.80.9 + App token for try-fix chain ([c1bd7b2](https://github.com/fulviofreitas/eeroctl/commit/c1bd7b29d8459961fa2c6c77d4ebad08c4edab82))

## [2.21.3](https://github.com/fulviofreitas/eeroctl/compare/v2.21.2...v2.21.3) (2026-06-22)

### 🐛 Bug Fixes

* **deps:** bump cryptography from 46.0.7 to 48.0.1 ([2d48308](https://github.com/fulviofreitas/eeroctl/commit/2d48308186ac68530531f28ab33664f096abdb54))

## [2.21.2](https://github.com/fulviofreitas/eeroctl/compare/v2.21.1...v2.21.2) (2026-06-22)

### 🐛 Bug Fixes

* **deps:** bump aiohttp from 3.13.5 to 3.14.1 ([7fe1e0c](https://github.com/fulviofreitas/eeroctl/commit/7fe1e0ce08a2b350691f3949acd3ab35781fbbec))

## [2.21.1](https://github.com/fulviofreitas/eeroctl/compare/v2.21.0...v2.21.1) (2026-06-22)

### 🐛 Bug Fixes

* **deps:** bump idna from 3.11 to 3.15 ([d4190a8](https://github.com/fulviofreitas/eeroctl/commit/d4190a80b71895c33dcf3b75125b326ff80028c3))

## [2.21.0](https://github.com/fulviofreitas/eeroctl/compare/v2.20.0...v2.21.0) (2026-06-12)

### ✨ Features

* **deps:** update eero-api to 5.0.0 ([3f3120e](https://github.com/fulviofreitas/eeroctl/commit/3f3120e81c44f49c369b53cb1372ec9b19739632))

## [2.20.0](https://github.com/fulviofreitas/eeroctl/compare/v2.19.0...v2.20.0) (2026-06-06)

### ✨ Features

* **deps:** update eero-api to 4.6.1 ([951e4cb](https://github.com/fulviofreitas/eeroctl/commit/951e4cbf96b4f33665ef637aeea4eff0d5dee96a))

## [2.19.0](https://github.com/fulviofreitas/eeroctl/compare/v2.18.1...v2.19.0) (2026-06-05)

### ✨ Features

* **deps:** update eero-api to 4.6.0 ([2dae779](https://github.com/fulviofreitas/eeroctl/commit/2dae779e422b4772c7d4a050b85be063fc4f81bb))

## [2.18.1](https://github.com/fulviofreitas/eeroctl/compare/v2.18.0...v2.18.1) (2026-05-21)

### 🐛 Bug Fixes

* coerce uptime and numeric eero fields from dict shapes ([#48](https://github.com/fulviofreitas/eeroctl/issues/48)) ([ecbf32e](https://github.com/fulviofreitas/eeroctl/commit/ecbf32e28a6bc8c7e8990d73cadd42c650f8b439))

## [2.18.0](https://github.com/fulviofreitas/eeroctl/compare/v2.17.0...v2.18.0) (2026-05-18)

### ✨ Features

* **deps:** update eero-api to 4.2.0 ([d4e2706](https://github.com/fulviofreitas/eeroctl/commit/d4e2706dfddd6d40eef229c06e720d99ee1dfb9b))

## [2.17.0](https://github.com/fulviofreitas/eeroctl/compare/v2.16.0...v2.17.0) (2026-05-12)

### ✨ Features

* **deps:** update eero-api to 4.1.3 ([fad0650](https://github.com/fulviofreitas/eeroctl/commit/fad0650176948397ca932941610f762e0acad6e7))

## [2.16.0](https://github.com/fulviofreitas/eeroctl/compare/v2.15.0...v2.16.0) (2026-05-11)

### ✨ Features

* **profile:** add create/rename/delete + mutation regression suite ([#43](https://github.com/fulviofreitas/eeroctl/issues/43)) ([a18f676](https://github.com/fulviofreitas/eeroctl/commit/a18f676a5294e59d55e026f5ce64fd08ec67bfde))

## [2.15.0](https://github.com/fulviofreitas/eeroctl/compare/v2.14.0...v2.15.0) (2026-05-11)

### ✨ Features

* **deps:** update eero-api to 4.1.2 ([9a97140](https://github.com/fulviofreitas/eeroctl/commit/9a97140c0e93400a38f2ff4ee9190c298b0be851))

## [2.14.0](https://github.com/fulviofreitas/eeroctl/compare/v2.13.0...v2.14.0) (2026-04-29)

### ✨ Features

* **deps:** update eero-api to 4.0.7 ([bfec70b](https://github.com/fulviofreitas/eeroctl/commit/bfec70b17371437a3e940b1cd24f8ff7de96c54c))

## [2.13.0](https://github.com/fulviofreitas/eeroctl/compare/v2.12.1...v2.13.0) (2026-04-21)

### ✨ Features

* **deps:** update eero-api to 4.0.6 ([14e0313](https://github.com/fulviofreitas/eeroctl/commit/14e03139db212fb736b7dad8ec4655098cd22566))

## [2.12.1](https://github.com/fulviofreitas/eeroctl/compare/v2.12.0...v2.12.1) (2026-04-21)

### 🐛 Bug Fixes

* **ci:** replace deprecated app-id with client-id in create-github-app-token ([#39](https://github.com/fulviofreitas/eeroctl/issues/39)) ([189dbf3](https://github.com/fulviofreitas/eeroctl/commit/189dbf3d8ccf1857b5232981d21051a7a05d197d))

## [2.12.0](https://github.com/fulviofreitas/eeroctl/compare/v2.11.0...v2.12.0) (2026-04-11)

### ✨ Features

* **deps:** update eero-api to 4.0.5 ([93835d8](https://github.com/fulviofreitas/eeroctl/commit/93835d86e7a10cf42c6804ecc148b6df517bc746))

## [2.11.0](https://github.com/fulviofreitas/eeroctl/compare/v2.10.4...v2.11.0) (2026-04-10)

### ✨ Features

* **deps:** update eero-api to 4.0.4 ([86f57c2](https://github.com/fulviofreitas/eeroctl/commit/86f57c2bf6dba304899797996356f50582f4c332))

## [2.10.4](https://github.com/fulviofreitas/eeroctl/compare/v2.10.3...v2.10.4) (2026-04-10)

### 🐛 Bug Fixes

* remove deprecated matchPackageNames and invalid matchDepTypes from renovate config ([c235344](https://github.com/fulviofreitas/eeroctl/commit/c235344f3e0728c64e140e5289379781cfcb7381))

## [2.10.3](https://github.com/fulviofreitas/eeroctl/compare/v2.10.2...v2.10.3) (2026-04-10)

### 🐛 Bug Fixes

* **deps:** bump cryptography from 46.0.6 to 46.0.7 ([7a555a2](https://github.com/fulviofreitas/eeroctl/commit/7a555a20c3cfb46cf9c77e6d1201766f2bf4ffa4))

## [2.10.2](https://github.com/fulviofreitas/eeroctl/compare/v2.10.1...v2.10.2) (2026-04-10)

### 🐛 Bug Fixes

* **ci:** use GitHub App token for semantic-release ([8b9161f](https://github.com/fulviofreitas/eeroctl/commit/8b9161fd01467ff9ea6b153eed8d2ebbe171d1bd))

## [2.10.1](https://github.com/fulviofreitas/eeroctl/compare/v2.10.0...v2.10.1) (2026-04-02)

### 🐛 Bug Fixes

* **deps:** consolidate all dependency updates ([#29](https://github.com/fulviofreitas/eeroctl/issues/29)) ([933db2e](https://github.com/fulviofreitas/eeroctl/commit/933db2ebd9d15ce8ce66ecb08d2be7282e8946f2)), closes [#24](https://github.com/fulviofreitas/eeroctl/issues/24) [#25](https://github.com/fulviofreitas/eeroctl/issues/25) [#26](https://github.com/fulviofreitas/eeroctl/issues/26) [#27](https://github.com/fulviofreitas/eeroctl/issues/27) [#28](https://github.com/fulviofreitas/eeroctl/issues/28)

## [2.10.0](https://github.com/fulviofreitas/eeroctl/compare/v2.9.0...v2.10.0) (2026-01-26)

### ✨ Features

* **deps:** update eero-api to 4.0.1 ([a364aa4](https://github.com/fulviofreitas/eeroctl/commit/a364aa47a780e6dc9cd5c903056cb6992abb8926))

## [2.9.0](https://github.com/fulviofreitas/eeroctl/compare/v2.8.2...v2.9.0) (2026-01-23)

### ✨ Features

* add upstream DNS and location info to network show ([2c6618a](https://github.com/fulviofreitas/eeroctl/commit/2c6618a42921db5a3cf37ce62d6a6f07b2e91299))
* case-insensitive device lookup by name, MAC, or ID ([bef42e1](https://github.com/fulviofreitas/eeroctl/commit/bef42e14aab70ed7bb83403614089fb0f016a04d))
* case-insensitive profile lookup by name or ID ([70a5374](https://github.com/fulviofreitas/eeroctl/commit/70a5374b641a0f1ff8c4b8bce112b8fd2fb73f27))
* enrich eero show with connection, ports, wifi, and clients info ([91b4cde](https://github.com/fulviofreitas/eeroctl/commit/91b4cdefef534fedb5f6696a0a062240f33efc1c))
* expand config.json with default_output and auth_method ([8eae461](https://github.com/fulviofreitas/eeroctl/commit/8eae461ae91cc0b41726e1f7f3af4873f19f7b6c))
* support eero lookup by name, serial, or ID ([2bb1a92](https://github.com/fulviofreitas/eeroctl/commit/2bb1a926d07da9bfbf078f31f4eda77c4d2c7485))

### 🐛 Bug Fixes

* align list output fields exactly with table panel output ([e26da43](https://github.com/fulviofreitas/eeroctl/commit/e26da4376b21fa7e539bb622bcd4cdc461662f37))
* show commands list output now shows curated fields ([ba0eea3](https://github.com/fulviofreitas/eeroctl/commit/ba0eea392cd79eeb4edb27f4f8b308341b86c763))
* show commands now render correctly with --output list ([85af139](https://github.com/fulviofreitas/eeroctl/commit/85af139e4060ad5ee9a8f5a3a19d690a5fca20b5))

### ♻️ Refactoring

* change config directory from eero-api to eeroctl ([715f768](https://github.com/fulviofreitas/eeroctl/commit/715f7688ea4654b184e981d73d6522d444e2e0ab))
* single source of truth for show output fields ([e232324](https://github.com/fulviofreitas/eeroctl/commit/e232324891cd9c557ea7a497a03c0fc301d55133))

## [2.8.2](https://github.com/fulviofreitas/eeroctl/compare/v2.8.1...v2.8.2) (2026-01-23)

### 🐛 Bug Fixes

* network list fetches detailed info and improve DHCP display ([ad6d280](https://github.com/fulviofreitas/eeroctl/commit/ad6d280ed3b0bd374248f2c363334b435abaf621))

## [2.8.1](https://github.com/fulviofreitas/eeroctl/compare/v2.8.0...v2.8.1) (2026-01-23)

### 🐛 Bug Fixes

* auth status shows authenticated after successful login ([bdf752f](https://github.com/fulviofreitas/eeroctl/commit/bdf752f4a30bba91fb79e7ba748e25c7b96d9437))

## [2.8.0](https://github.com/fulviofreitas/eeroctl/compare/v2.7.0...v2.8.0) (2026-01-23)

### ✨ Features

* **deps:** update eero-api to 4.0.0 ([30b20fa](https://github.com/fulviofreitas/eeroctl/commit/30b20fa95cd145d17698d557f88189314db925f0))

## [2.7.0](https://github.com/fulviofreitas/eeroctl/compare/v2.6.0...v2.7.0) (2026-01-23)

### ✨ Features

* manage preferred_network in config.json, not credentials ([209fbe4](https://github.com/fulviofreitas/eeroctl/commit/209fbe4a3cbfcfe943fe4c8bdfd0811388690e4a))

### 🐛 Bug Fixes

* resolve mypy type errors in auth.py ([3cd165d](https://github.com/fulviofreitas/eeroctl/commit/3cd165d0238e9ab56978ee8263796e19634a42c9))

## [2.6.0](https://github.com/fulviofreitas/eeroctl/compare/v2.5.0...v2.6.0) (2026-01-23)

### ✨ Features

* **deps:** update eero-api to 3.0.1 ([fbea9ca](https://github.com/fulviofreitas/eeroctl/commit/fbea9ca2d80193fcad428c9e1bb14a8b782581b8))

## [2.5.0](https://github.com/fulviofreitas/eeroctl/compare/v2.4.0...v2.5.0) (2026-01-23)

### ✨ Features

* **deps:** update eero-api to 3.0.0 ([4d4f6bb](https://github.com/fulviofreitas/eeroctl/commit/4d4f6bb343f23a36162a7e2e7f1dfa0da814ec09))

## [2.4.0](https://github.com/fulviofreitas/eeroctl/compare/v2.3.0...v2.4.0) (2026-01-23)

### ✨ Features

* **deps:** update eero-api to 2.1.4 ([d0a9bb4](https://github.com/fulviofreitas/eeroctl/commit/d0a9bb4e194804188e5c5991f1cb4833f0a62d7b))

## [2.3.0](https://github.com/fulviofreitas/eeroctl/compare/v2.2.1...v2.3.0) (2026-01-23)

### ✨ Features

* **deps:** update eero-api to 2.1.3 ([32b6806](https://github.com/fulviofreitas/eeroctl/commit/32b6806af7d38fcaba60f8827d3199a708932fda))

## [2.2.1](https://github.com/fulviofreitas/eeroctl/compare/v2.2.0...v2.2.1) (2026-01-23)

### 🐛 Bug Fixes

* store and respect use_keyring preference across all commands ([cfc96e0](https://github.com/fulviofreitas/eeroctl/commit/cfc96e0b98c3769d001331982bcb6c299aa70f1e))

## [2.2.0](https://github.com/fulviofreitas/eeroctl/compare/v2.1.0...v2.2.0) (2026-01-23)

### ✨ Features

* **deps:** update eero-api to 2.1.2 ([e1da57d](https://github.com/fulviofreitas/eeroctl/commit/e1da57dbb13932b3b86d84ef78a5e21c0e17f1d9))

### 🐛 Bug Fixes

* **renovate:** migrate from deprecated prTitle to commitMessage ([1fb7371](https://github.com/fulviofreitas/eeroctl/commit/1fb7371d34d7fd15c99a3e007e046a1bf6c74a69))

## [2.1.0](https://github.com/fulviofreitas/eeroctl/compare/v2.0.2...v2.1.0) (2026-01-23)

### ✨ Features

* **deps:** update eero-api to 2.1.1 ([d72b796](https://github.com/fulviofreitas/eeroctl/commit/d72b796e8548a7f72c6f12c43f011281247d66c5))

## [2.0.2](https://github.com/fulviofreitas/eeroctl/compare/v2.0.1...v2.0.2) (2026-01-23)

### 🐛 Bug Fixes

* **renovate:** move eero-api rule to end for precedence ([6486c97](https://github.com/fulviofreitas/eeroctl/commit/6486c974cfdeb98861e3913402835e9dcc425bfa))

## [2.0.1](https://github.com/fulviofreitas/eeroctl/compare/v2.0.0...v2.0.1) (2026-01-23)

### 🐛 Bug Fixes

* **renovate:** disable automerge for eero-api, require review ([d10eca7](https://github.com/fulviofreitas/eeroctl/commit/d10eca7ddf8444cebed614dbb050f6130265aca0))

## [2.0.0](https://github.com/fulviofreitas/eeroctl/compare/v1.8.0...v2.0.0) (2026-01-23)

### ⚠ BREAKING CHANGES

* migrate to eero-api v2.0.0 raw response architecture
* All command modules now use raw API responses
with the transformation layer.

Updated commands:
- device.py: Uses extract_devices, normalize_device
- eero/base.py: Uses extract_eeros, normalize_eero
- eero/led.py, nightlight.py, updates.py: Dict access for eero data
- profile.py: Uses extract_profiles, normalize_profile
- activity.py: Uses extract_data for activity responses
- troubleshoot.py: Uses transformers for network/device data
- network/guest.py, speedtest.py, dhcp.py: Dict access patterns

Updated transformers/__init__.py:
- Added safe_get and normalize_network to __all__

All 383 tests passing.
* Updates eeroctl to work with eero-api v2.0.0 which
returns raw JSON responses instead of Pydantic models.

Changes:
- Add transformers package with base utilities and entity transformers
  - base.py: extract_data, extract_list, extract_id_from_url, safe_get
  - network.py, device.py, eero.py, profile.py: entity-specific transforms
- Update const.py with local enum definitions (moved from eero-api)
- Update formatting modules to use dict access instead of model attrs
- Update network commands to use new transformation layer
- Update tests to use raw API response fixtures

This change is part of Phase 2 of the raw-response-migration-plan.

### ✨ Features

* add transformation layer for eero-api raw responses ([4d27530](https://github.com/fulviofreitas/eeroctl/commit/4d27530bae1851f1a304a71f24ef19336944d05d))
* **ci:** standardize renovate workflow with reusable actions ([0093415](https://github.com/fulviofreitas/eeroctl/commit/0093415fe6a31b3b90c465dc7f6a7a72d676cbaa))
* complete Phase 2 - update all commands for raw responses ([c071d17](https://github.com/fulviofreitas/eeroctl/commit/c071d1708307f0f0dccbb809a06c6be0f4428b87))
* migrate to eero-api v2.0.0 raw response architecture ([cfffccc](https://github.com/fulviofreitas/eeroctl/commit/cfffccc9a939d9ea86bec8d09fffbf91d6079b94))
* **renovate:** treat eero-api as feature release for minor version bumps ([2c35b83](https://github.com/fulviofreitas/eeroctl/commit/2c35b83d925855dbeca1fdd86c8a7a1d8ea63307))

### 🐛 Bug Fixes

* **renovate:** ensure consistent config matching all Python managers ([d29cfa4](https://github.com/fulviofreitas/eeroctl/commit/d29cfa42337767cfcc99c97dc02192bdb0917217))
* **renovate:** restore critical and needs-review labels for eero packages ([96b7a15](https://github.com/fulviofreitas/eeroctl/commit/96b7a157df4295c15b3ed5e9f5d1abdef899ea78))
* **renovate:** wait for PyPI indexing before running Renovate ([d8792c4](https://github.com/fulviofreitas/eeroctl/commit/d8792c4d307f588129ae29c6af6bb10362abc336))
* resolve mypy type errors for raw response migration ([b7830c5](https://github.com/fulviofreitas/eeroctl/commit/b7830c5c13b8626ba146d24e51c2a32f93f5b7b0))
* update test_status_json_output mock to use raw response ([fd72340](https://github.com/fulviofreitas/eeroctl/commit/fd72340dce8817fd8a3e1bedb201cc944425e556))

## [1.8.0](https://github.com/fulviofreitas/eeroctl/compare/v1.7.1...v1.8.0) (2026-01-21)

### ✨ Features

* trigger minor release ([c05c3d2](https://github.com/fulviofreitas/eeroctl/commit/c05c3d214c511f9185d163528e370122cad59c3a))

## [1.7.1](https://github.com/fulviofreitas/eeroctl/compare/v1.7.0...v1.7.1) (2026-01-21)

### 🐛 Bug Fixes

* trigger release ([05294c2](https://github.com/fulviofreitas/eeroctl/commit/05294c2d9da51a92a299a5a86b3ad32900dc8770))

### ♻️ Refactoring

* **formatting:** split God Object into modular package ([a4e082b](https://github.com/fulviofreitas/eeroctl/commit/a4e082bc668c24456fe4d04528f9c55d7b7f4976))

## [1.7.0](https://github.com/fulviofreitas/eeroctl/compare/v1.6.0...v1.7.0) (2026-01-21)

### ✨ Features

* **formatting:** enrich device show output with detailed panels ([b46dcb0](https://github.com/fulviofreitas/eeroctl/commit/b46dcb04782d42dc3ad670f75645f7d808814ba7))
* **formatting:** enrich eero show output with detailed panels ([53a39a9](https://github.com/fulviofreitas/eeroctl/commit/53a39a999731111c27d78bafa28cbdf80b05893d))
* **formatting:** enrich network show output with detailed panels ([caa895b](https://github.com/fulviofreitas/eeroctl/commit/caa895b4e3a71ad3ce7b087197fd8c9735e5a59d))
* **formatting:** enrich profile show output with detailed panels ([526afa9](https://github.com/fulviofreitas/eeroctl/commit/526afa9f136f71c459f2668a7724ab6db7f719b0))

## [1.6.0](https://github.com/fulviofreitas/eeroctl/compare/v1.5.0...v1.6.0) (2026-01-21)

### ✨ Features

* **cli:** add eeroctl command alias ([58a9503](https://github.com/fulviofreitas/eeroctl/commit/58a9503ecfc7d409a55f6baa79eaf59c2b7039eb))

### 🐛 Bug Fixes

* **cli:** display network status value instead of enum representation ([f4be157](https://github.com/fulviofreitas/eeroctl/commit/f4be157a39af790e317a90a28184f9ee3f5b347a))

### ♻️ Refactoring

* **formatting:** simplify format_network_status for clean values ([f7d51f7](https://github.com/fulviofreitas/eeroctl/commit/f7d51f74bb45989ad747e6bd28e7f18f4edd674b))

## [1.5.0](https://github.com/fulviofreitas/eeroctl/compare/v1.4.0...v1.5.0) (2026-01-21)

### ✨ Features

* **cli:** add display option decorators for debug/quiet/color (Phase 5) ([c1783a5](https://github.com/fulviofreitas/eeroctl/commit/c1783a5a642518704303db0783cf298ceebf8dab))
* **cli:** add shared option decorators for flexible option placement ([ef9b2df](https://github.com/fulviofreitas/eeroctl/commit/ef9b2df07129c5804a6322e9d105ea08b81ff6e3))
* **cli:** apply --force option to destructive commands (Phase 4) ([2e12dcb](https://github.com/fulviofreitas/eeroctl/commit/2e12dcbccecb4055f0cea39a31a9d54fe7b83fe5))
* **cli:** apply --network-id option to network-dependent commands (Phase 3) ([66572b9](https://github.com/fulviofreitas/eeroctl/commit/66572b99c488d4ca7df7918830e688f32e8151b1))
* **cli:** apply --output option to list/show commands (Phase 2) ([ddb2a2d](https://github.com/fulviofreitas/eeroctl/commit/ddb2a2d1e0d03ff7ec41fe966402ceb8dc347b33))

### 📚 Documentation

* update documentation for flexible option placement (Phase 6) ([164f9b3](https://github.com/fulviofreitas/eeroctl/commit/164f9b3ef0458aed1746b72dc309d6e80d21dda9))

## [Unreleased]

### ♻️ Refactoring

* **formatting:** split God Object `formatting.py` (2,810 lines) into modular package
  * New package structure: `src/eeroctl/formatting/`
  * `base.py` - Shared utilities (console, field helpers, status formatters)
  * `network.py` - Network formatting (659 lines)
  * `eero.py` - Eero device formatting (591 lines)
  * `device.py` - Connected device formatting (430 lines)
  * `profile.py` - Profile formatting (443 lines)
  * `misc.py` - Speed test and blacklist formatting (87 lines)
  * Backward compatible via `__init__.py` re-exports

### 🐛 Bug Fixes

* **auth:** add debug logging to exception handlers (resolves Bandit B110 warnings)

### 🔧 Maintenance

* **dev:** add pre-commit hooks configuration (`.pre-commit-config.yaml`)

### ✨ Features

* **cli:** flexible option placement - options can now appear anywhere in commands
  * `--output/-o` can be placed after subcommands: `eero device list --output json`
  * `--network-id/-n` works at any level: `eero eero show "Living Room" -n abc123`
  * `--force/-y` can be placed after subcommands: `eero device block "iPhone" --force`
  * New display options: `--debug`, `--quiet/-q`, `--no-color` work per-command
* **cli:** add shared option decorators for reusable option definitions
  * `output_option`, `network_option`, `force_option`, `non_interactive_option`
  * `debug_option`, `quiet_option`, `no_color_option`
  * Combined decorators: `common_options`, `safety_options`, `display_options`, `all_options`

### 🧪 Tests

* add 54 tests for option decorators and `apply_options` helper

### 🧹 Maintenance

* remove legacy `eero_cli/` package (orphaned since v1.0.0 rename to eeroctl)

## [1.4.0](https://github.com/fulviofreitas/eeroctl/compare/v1.3.1...v1.4.0) (2026-01-20)

### ✨ Features

* switch eero-api to PyPI and enhance --version output ([fb75814](https://github.com/fulviofreitas/eeroctl/commit/fb7581424b43e2bcd8c53fa447f8f1cdf5730af5))

## [1.3.1](https://github.com/fulviofreitas/eeroctl/compare/v1.3.0...v1.3.1) (2026-01-20)

### 🐛 Bug Fixes

* **ci:** add prTitle config for squash merge commitlint compliance ([dd6c890](https://github.com/fulviofreitas/eeroctl/commit/dd6c890442d459da8e4570be3302ebbcee570636))

## [1.3.0](https://github.com/fulviofreitas/eeroctl/compare/v1.2.2...v1.3.0) (2026-01-20)

### ✨ Features

* add version_info tuple for programmatic version access ([7de5a37](https://github.com/fulviofreitas/eeroctl/commit/7de5a37e86c5e11cf5b6b2f18da4346c6dbe002a))

## [1.2.2](https://github.com/fulviofreitas/eeroctl/compare/v1.2.1...v1.2.2) (2026-01-20)

### 🐛 Bug Fixes

* **ci:** prevent commitlint body-max-line-length failures on Renovate PRs ([422938f](https://github.com/fulviofreitas/eeroctl/commit/422938fd328b794f142b97fd78b0b3ba201b22ea))

## [1.2.1](https://github.com/fulviofreitas/eeroctl/compare/v1.2.0...v1.2.1) (2026-01-19)

### 🐛 Bug Fixes

* update PyPI badge to include SVG format ([03040ad](https://github.com/fulviofreitas/eeroctl/commit/03040ad6d4560b1fc3bdb98a2e2ae049f68c2605))

## [1.2.0](https://github.com/fulviofreitas/eeroctl/compare/v1.1.1...v1.2.0) (2026-01-19)

### ✨ Features

* add get_version() helper function ([26c11cf](https://github.com/fulviofreitas/eeroctl/commit/26c11cf28d4a9ad7e674305da5d52b2a427f2f64))

## [1.1.1](https://github.com/fulviofreitas/eeroctl/compare/v1.1.0...v1.1.1) (2026-01-19)

### 🐛 Bug Fixes

* **release:** add full build steps to PyPI publish jobs ([eb6a844](https://github.com/fulviofreitas/eeroctl/commit/eb6a844c021107260ddac57444e007db375b2b96))

## [1.1.0](https://github.com/fulviofreitas/eeroctl/compare/v1.0.5...v1.1.0) (2026-01-19)

### ✨ Features

* add PyPI and Homebrew publishing to release workflow ([4572158](https://github.com/fulviofreitas/eeroctl/commit/4572158bf27b11b70cea7d2f900834d2c5032634))

## [1.0.5](https://github.com/fulviofreitas/eeroctl/compare/v1.0.4...v1.0.5) (2026-01-19)

### 🐛 Bug Fixes

* **deps:** update eero-api to v1.3.1 with type compatibility fixes ([3997e9d](https://github.com/fulviofreitas/eeroctl/commit/3997e9dd6c4c983d9a030bffaa770526d4eb6df8))

## [1.0.4](https://github.com/fulviofreitas/eeroctl/compare/v1.0.3...v1.0.4) (2026-01-19)

### 🐛 Bug Fixes

* **ci:** remove invalid workflows permission from auto-merge ([489276d](https://github.com/fulviofreitas/eeroctl/commit/489276d8d106145ceba638ada28402c0ed2028ce))

## [1.0.3](https://github.com/fulviofreitas/eeroctl/compare/v1.0.2...v1.0.3) (2026-01-18)

### 🐛 Bug Fixes

* **ci:** use GitHub App for auto-merge to support workflow file changes ([3e7b679](https://github.com/fulviofreitas/eeroctl/commit/3e7b679f3a828f266ad8ce137703ed88ba82fa8b))

### ♻️ Refactoring

* rename eero-client to eero-api in GitHub workflows ([0f84d36](https://github.com/fulviofreitas/eeroctl/commit/0f84d3668429d6e014ae23424c5c74083c923697))

## [1.0.2](https://github.com/fulviofreitas/eeroctl/compare/v1.0.1...v1.0.2) (2026-01-18)

### 🐛 Bug Fixes

* correct repository_dispatch event type for eero-api ([a8a0e3d](https://github.com/fulviofreitas/eeroctl/commit/a8a0e3dadfe9520ae9f0de528b39f6d29fd8c40c))

## [1.0.1](https://github.com/fulviofreitas/eeroctl/compare/v1.0.0...v1.0.1) (2026-01-18)

### 🐛 Bug Fixes

* correct Renovate config validation errors ([114eb19](https://github.com/fulviofreitas/eeroctl/commit/114eb1918b4bef17f3a75ef12a269d29ce2ab9d8))

## 1.0.0 (2026-01-18)

### ⚠ BREAKING CHANGES

* Package import path changed from eero_cli to eeroctl
* Python 3.10 and 3.11 are no longer supported

- Update requires-python to >=3.12
- Update classifiers to 3.12, 3.13, 3.14
- Update mypy python_version to 3.12
- Update ruff/black target-version to py312

### ✨ Features

* add __version__ to package ([27e1c04](https://github.com/fulviofreitas/eeroctl/commit/27e1c04bfa47709eb67340ae81e9219a50385223))
* add Bandit security scanning workflow 🔒 ([cb13ae2](https://github.com/fulviofreitas/eeroctl/commit/cb13ae2e94a80ba042a90ff8ec66d33e03383a33))
* **ci:** add Renovate for automated eero-client dependency updates ([067e9ca](https://github.com/fulviofreitas/eeroctl/commit/067e9ca4b2665cd6029abf9af22557a65b4e857f))
* **ci:** migrate workflows to use reusable actions from eero-client ([c23c961](https://github.com/fulviofreitas/eeroctl/commit/c23c961f0e2bec3fb1ddd4b10b6f82a2d417e11f))
* require Python 3.12 minimum ([1839deb](https://github.com/fulviofreitas/eeroctl/commit/1839deb0032984e471e5cda409fef2107aedf1ea))
* **security:** migrate from Bandit to Semgrep ([c1085d1](https://github.com/fulviofreitas/eeroctl/commit/c1085d197d7775081d476506b2e577108e20d575))

### 🐛 Bug Fixes

* auth flow improvements and client list output consistency ([f9d8379](https://github.com/fulviofreitas/eeroctl/commit/f9d8379063ce5b485a7571e7e781bfe19e4b59ea))
* **ci:** correct matrix syntax for macOS test jobs ([5185f99](https://github.com/fulviofreitas/eeroctl/commit/5185f99f0f997f908951ad51724f9cb0d96d07a3))
* **ci:** properly report type-check and security job status ([b270dc0](https://github.com/fulviofreitas/eeroctl/commit/b270dc06d10ac1bf82ffb42c57520c769fd1d31a))
* **ci:** require ALL jobs to pass for CI Success ([ad85a5d](https://github.com/fulviofreitas/eeroctl/commit/ad85a5d2fbd20b8a687568ca8bc12cc8fd6126ca))
* **ci:** use master branch consistently in all workflows ([5fa591f](https://github.com/fulviofreitas/eeroctl/commit/5fa591f353fe3f0736d4271dbbe6a7083c3a6fc9))
* consistent columns between list and table output formats ([336bfad](https://github.com/fulviofreitas/eeroctl/commit/336bfad098a210520a564181b1f5e57f2e745230))
* improve concurrency group for PR workflows ([c38d6b0](https://github.com/fulviofreitas/eeroctl/commit/c38d6b0066300b3a640d1386e57f4ccf7882f649))
* improve Renovate and auto-merge configuration ([5cc6b0e](https://github.com/fulviofreitas/eeroctl/commit/5cc6b0ebcf3658bd8d98d9eca6f30f16e34a9945))
* remove unused variable and import (ruff F841, F401) ([db81e1a](https://github.com/fulviofreitas/eeroctl/commit/db81e1ae112a438aa07b206fadb3ed45c3eebac7))
* suppress status messages for parseable output formats ([0e054cc](https://github.com/fulviofreitas/eeroctl/commit/0e054cc59572f19a4aae40caafabcfcf3fc8345b))
* use lowercase values for Bandit confidence/severity levels ([f8ace21](https://github.com/fulviofreitas/eeroctl/commit/f8ace218602cfd3861a274856cabfed84543d164))

### 📚 Documentation

* improve installation instructions with venv details ([a2b5b4a](https://github.com/fulviofreitas/eeroctl/commit/a2b5b4a053d510aedb882838bf39318bb5497053))
* modernize README with emojis and wiki links ([c48f546](https://github.com/fulviofreitas/eeroctl/commit/c48f546572b97ff7c1e07e8c582d2afa0fa569fe))
* simplify main CLI help message ([c2ae74f](https://github.com/fulviofreitas/eeroctl/commit/c2ae74f913bd0d303a880c7643c11be122e95e3d))

### ♻️ Refactoring

* **auth:** improve auth status command with accurate session info ([c0531f6](https://github.com/fulviofreitas/eeroctl/commit/c0531f6beed70763e10b7d32da490e96fc680b78))
* **ci:** standardize pipeline chain format ([36f7f96](https://github.com/fulviofreitas/eeroctl/commit/36f7f9646f3e9ab93355e63d62042b1bb934c8f9))
* rename project from eero-cli to eeroctl ([40ca250](https://github.com/fulviofreitas/eeroctl/commit/40ca2505de92ef317ca9ecd10329c27e659a27ab))
* split network.py and eero.py into modular packages ([f89422d](https://github.com/fulviofreitas/eeroctl/commit/f89422d7127760d5564c469c1eb6d3d80007fcce))
* update repository_dispatch event type name ([62b7dbe](https://github.com/fulviofreitas/eeroctl/commit/62b7dbeb97ab6cb34703db49eb94f9838736caf3))

## [1.2.2](https://github.com/fulviofreitas/eeroctl/compare/v1.2.1...v1.2.2) (2026-01-18)

### 🐛 Bug Fixes

* improve Renovate and auto-merge configuration ([5cc6b0e](https://github.com/fulviofreitas/eeroctl/commit/5cc6b0ebcf3658bd8d98d9eca6f30f16e34a9945))

## [1.2.1](https://github.com/fulviofreitas/eeroctl/compare/v1.2.0...v1.2.1) (2026-01-18)

### 🐛 Bug Fixes

* improve concurrency group for PR workflows ([c38d6b0](https://github.com/fulviofreitas/eeroctl/commit/c38d6b0066300b3a640d1386e57f4ccf7882f649))

## [1.2.0](https://github.com/fulviofreitas/eeroctl/compare/v1.1.0...v1.2.0) (2026-01-17)

### ✨ Features

* **security:** migrate from Bandit to Semgrep ([c1085d1](https://github.com/fulviofreitas/eeroctl/commit/c1085d197d7775081d476506b2e577108e20d575))

## [1.1.0](https://github.com/fulviofreitas/eeroctl/compare/v1.0.0...v1.1.0) (2026-01-17)

### ✨ Features

* add __version__ to package ([27e1c04](https://github.com/fulviofreitas/eeroctl/commit/27e1c04bfa47709eb67340ae81e9219a50385223))

## 1.0.0 (2026-01-17)

### ⚠ BREAKING CHANGES

* Python 3.10 and 3.11 are no longer supported

- Update requires-python to >=3.12
- Update classifiers to 3.12, 3.13, 3.14
- Update mypy python_version to 3.12
- Update ruff/black target-version to py312

### ✨ Features

* add Bandit security scanning workflow 🔒 ([cb13ae2](https://github.com/fulviofreitas/eeroctl/commit/cb13ae2e94a80ba042a90ff8ec66d33e03383a33))
* **ci:** add Renovate for automated eero-api dependency updates ([067e9ca](https://github.com/fulviofreitas/eeroctl/commit/067e9ca4b2665cd6029abf9af22557a65b4e857f))
* **ci:** migrate workflows to use reusable actions from eero-api ([c23c961](https://github.com/fulviofreitas/eeroctl/commit/c23c961f0e2bec3fb1ddd4b10b6f82a2d417e11f))
* require Python 3.12 minimum ([1839deb](https://github.com/fulviofreitas/eeroctl/commit/1839deb0032984e471e5cda409fef2107aedf1ea))

### 🐛 Bug Fixes

* auth flow improvements and client list output consistency ([f9d8379](https://github.com/fulviofreitas/eeroctl/commit/f9d8379063ce5b485a7571e7e781bfe19e4b59ea))
* **ci:** correct matrix syntax for macOS test jobs ([5185f99](https://github.com/fulviofreitas/eeroctl/commit/5185f99f0f997f908951ad51724f9cb0d96d07a3))
* **ci:** properly report type-check and security job status ([b270dc0](https://github.com/fulviofreitas/eeroctl/commit/b270dc06d10ac1bf82ffb42c57520c769fd1d31a))
* **ci:** require ALL jobs to pass for CI Success ([ad85a5d](https://github.com/fulviofreitas/eeroctl/commit/ad85a5d2fbd20b8a687568ca8bc12cc8fd6126ca))
* **ci:** use master branch consistently in all workflows ([5fa591f](https://github.com/fulviofreitas/eeroctl/commit/5fa591f353fe3f0736d4271dbbe6a7083c3a6fc9))
* consistent columns between list and table output formats ([336bfad](https://github.com/fulviofreitas/eeroctl/commit/336bfad098a210520a564181b1f5e57f2e745230))
* remove unused variable and import (ruff F841, F401) ([db81e1a](https://github.com/fulviofreitas/eeroctl/commit/db81e1ae112a438aa07b206fadb3ed45c3eebac7))
* suppress status messages for parseable output formats ([0e054cc](https://github.com/fulviofreitas/eeroctl/commit/0e054cc59572f19a4aae40caafabcfcf3fc8345b))
* use lowercase values for Bandit confidence/severity levels ([f8ace21](https://github.com/fulviofreitas/eeroctl/commit/f8ace218602cfd3861a274856cabfed84543d164))

### 📚 Documentation

* improve installation instructions with venv details ([a2b5b4a](https://github.com/fulviofreitas/eeroctl/commit/a2b5b4a053d510aedb882838bf39318bb5497053))
* modernize README with emojis and wiki links ([c48f546](https://github.com/fulviofreitas/eeroctl/commit/c48f546572b97ff7c1e07e8c582d2afa0fa569fe))
* simplify main CLI help message ([c2ae74f](https://github.com/fulviofreitas/eeroctl/commit/c2ae74f913bd0d303a880c7643c11be122e95e3d))

### ♻️ Refactoring

* **auth:** improve auth status command with accurate session info ([c0531f6](https://github.com/fulviofreitas/eeroctl/commit/c0531f6beed70763e10b7d32da490e96fc680b78))
* **ci:** standardize pipeline chain format ([36f7f96](https://github.com/fulviofreitas/eeroctl/commit/36f7f9646f3e9ab93355e63d62042b1bb934c8f9))
* split network.py and eero.py into modular packages ([f89422d](https://github.com/fulviofreitas/eeroctl/commit/f89422d7127760d5564c469c1eb6d3d80007fcce))
* update repository_dispatch event type name ([62b7dbe](https://github.com/fulviofreitas/eeroctl/commit/62b7dbeb97ab6cb34703db49eb94f9838736caf3))
