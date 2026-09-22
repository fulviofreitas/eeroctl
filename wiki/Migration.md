# 🚚 Migrating to eeroctl 3.0.0

eeroctl 3.0.0 moves from eero-api 6.0.0 to **eero-api 8.0.1**. The SDK changed how it
authenticates, how it stores credentials, which methods exist, and how errors are
classified. Most of that is invisible day to day; this page lists everything that is
not.

If you only run interactive commands, read **Behaviour changes** and **Credentials**.
If you script against eeroctl, read the whole page — exit codes, `auth status` output
and environment-variable names all changed.

---

## Who is affected

| You… | Read |
|------|------|
| run eeroctl interactively | [Behaviour changes](#behaviour-changes), [Credentials](#credentials) |
| script `eero auth status --output list` or `--output json` | [Renamed / rewired](#renamed--rewired) (`auth status`) |
| script on exit codes | [Exit codes](#exit-codes) — auth is now `3` everywhere, rate-limit is `1` |
| set `EERO_*` environment variables | [Environment variables](#environment-variables) — they never worked; the real names are `EEROCTL_*` |
| run `network security … --force` or `network sqm … --force` unattended | [Behaviour changes](#behaviour-changes) — these writes reboot the mesh, and now say so |
| use `network sqm set` | [Removed commands](#removed-commands) |
| use `network guest set --password` | [Renamed / rewired](#renamed--rewired) |
| script `eero eero nightlight schedule --on-time/--off-time` | [Renamed / rewired](#renamed--rewired) — the flags are now `--on`/`--off` |
| share a machine with `rusteero` or another eero-api user | [Credentials](#credentials) — the keyring record is rewritten to schema 2 |

---

## Removed commands

| Command | Why | What to do |
|---------|-----|------------|
| `eero network sqm set --upload <mbps> --download <mbps>` | The eero API exposes no bandwidth fields on SQM. eero-api 8 dropped `configure_sqm`, `set_sqm_bandwidth` and `set_sqm_auto` with no replacement. | Nothing to migrate to. `network sqm show`, `enable` and `disable` remain. The old invocation is now a Click usage error (exit `2`). |

---

## Renamed / rewired

### `network guest set --password` → `network guest password set`

eero-api 8 splits the guest-network write in two: `set_guest_network(enabled, name)`
and a dedicated `set_guest_password(password)` endpoint (plus `clear_guest_password`).

- On 3.0.0, `network guest set --name … --password …` still works: it calls both
  endpoints in sequence.
- The dedicated commands are `network guest password set [--password]` and
  `network guest password clear`. Prefer them in new scripts — the password is read
  from a hidden, confirmed prompt when `--password` is omitted and is never echoed;
  `--non-interactive` without `--password` exits `2` before any prompt. Both are
  MEDIUM tier (guest clients disconnect) and SDK-verified. `guest set --password`
  issues the same write through the same helper.
- `network guest enable --name … --password …` was never valid on any release; the old
  wiki example was wrong.

### `network backup status` shows different content

The SDK's `get_backup_network`/`get_backup_status` are gone. `network backup status`
now renders the two cellular-backup reads together — **usage** and **events** — as a
key/value dump (`table`/`text`) or `{"usage": …, "events": …}` under schema
`eero.network.backup.status/v1` (`json`/`yaml`/`list`). The shapes are undocumented by
the API; a dedicated table formatter will follow once a live sample is captured.
`network backup show` reads `get_backup_internet` instead of the network envelope.

### `profile schedule show` returns a list; `set` and `delete` work on entries

Schedules are sub-resources in eero-api 8. `profile schedule show <profile>` now
returns a **list** of schedule objects (`name`, `days`, `start`, `end`, `enabled`)
instead of the old `{"schedule": [...]}` object. Structured output is
`{"schedules": [...]}` under `eero.profile.schedule.show/v1`. `profile schedule clear`
handles the list return and reports success only when every element was accepted.

`profile schedule set <profile> --start HH:MM --end HH:MM [--days mon,tue,…]` is
rewired to the SDK's Bedtime helper: it creates or replaces the entry named
**Bedtime**, reads the current list first and skips the write when start, end and days
already match (`--days` omitted means every day). New: `profile schedule delete
<profile> <schedule-id>` removes one entry by its `id` or by the tail of its `url`
as printed by `schedule show`. Both are MEDIUM tier and unverified.

### `eero nightlight schedule`: `--on-time`/`--off-time` → `--on`/`--off`

The two required flags are renamed, and the command gains two alternative modes.
Exactly one of these is required; none or more than one exits `2`:

| 2.x | 3.0.0 |
|-----|-------|
| `--on-time HH:MM --off-time HH:MM` | `--on HH:MM --off HH:MM` (both together) |
| — | `--disable` — sends `{"enabled": false}` |
| — | `--schedule-json '{…}'` — a raw non-empty JSON object, forwarded to the API unchanged |

`--on/--off` build the v7 payload `{"enabled": true, "on": …, "off": …}`. No Beacon was
available to confirm that shape against a live device, so every nightlight write is
marked unverified. Success prints "Nightlight schedule updated." instead of the old
"Schedule set: …".

### `network guest password set` and `network password set` prompt after confirming

Both read the password from a hidden, confirmed prompt when `--password` is omitted —
but only **after** the confirmation (Y/N, or the `DISCONNECT` phrase) has been
answered, so declining never asks for the secret. `--non-interactive` without
`--password` exits `2` with "--password is required when --non-interactive is set"
before any prompt. `eero pppoe set` follows the same pattern. `network guest password
set|clear` return `{"ok": true, "command": "…"}` under `eero.network.guest.password.set/v1`
(`…clear/v1`) for `json`/`yaml`.

### `auth status` — schema `eero.auth.status/v2`

Session validity is no longer derived from the cookie file (eero-api 8 dropped the
client-side 30-day expiry, `session_expiry` and `refresh_token`). `auth status` now
makes one live `GET /account` call to confirm the stored token works.

Structured output (`--output json|yaml`):

```json
{
  "authenticated": true,
  "session_valid": true,
  "auth_method": "keyring",
  "storage": {
    "keyring": {"present": true},
    "cookie_file": {"path": "~/.config/eeroctl/cookies.json", "present": false, "schema_version": null, "legacy_backup_present": false}
  },
  "account": { "id": "…", "name": "…", "premium_status": "…", "premium_expiry": null, "created_at": "…", "users": [ … ] }
}
```

| Field | Meaning |
|-------|---------|
| `authenticated` | A token is stored (keyring or file). |
| `session_valid` | `true` — live probe succeeded; `false` — no token, or the API rejected it; `null` — `--offline` skipped the probe. |
| `auth_method` | The configured value, verbatim: `keyring`, `cookie_file`, or `env` when the session comes from `EEROCTL_SESSION_TOKEN`. |
| `storage.keyring.present` | The SDK record `eero-api` / `auth-tokens` exists in the system keyring (`false` under `EEROCTL_SESSION_TOKEN`, whatever the keyring holds). |
| `storage.cookie_file.schema_version` | `2` for a migrated file, `null` when the file is absent or still schema 1. |
| `storage.cookie_file.legacy_backup_present` | `cookies.json.pre-v8.bak` exists next to the cookie file. |
| `account` | Unchanged from v1; `null` unless the live probe ran and succeeded. |

Table output: the *Status* row reads **Valid**, **Stored, not verified** (`--offline`),
**Invalid** (probe rejected the token) or **Not authenticated**. The *Session Expiry*
row is gone; *Credential Schema* and *Legacy Backup* rows are new.

`--output list` (scripting-visible break): `session_expiry` is **removed**;
`schema_version` and `legacy_backup` are **added**; `status` is one of `valid`,
`stored_not_verified`, `invalid`, `not_authenticated`.

New flags:

| Flag | Effect |
|------|--------|
| `--offline` | Report stored state only; no API call. `session_valid` becomes `null`. |
| `--check` | Exit `3` when not authenticated or the stored session is invalid; exit `0` otherwise (including `--offline` with a stored token). Output is still printed. |

`--offline` and `--check` are mutually exclusive: together they exit `2` with
"--offline and --check cannot be used together" (an unverified token must never read
as OK).

---

## Behaviour changes

### LED commands now really apply

`eero eero led on|off|brightness` reached a verified endpoint on eero-api 8 for the
first time; on earlier releases the call returned 200 without changing the LED. If you
have a script that "sets" the LED and read-back shows the same value, that script is now
doing what it says. `led brightness` rejects values outside `0–100` before any request
(the SDK no longer clamps).

### `speedtest run` starts a test; it does not return results

The API answers `202` with `data: null`. `network speedtest run` prints
"Speed test started; results in ~1 min via `eero network speedtest history --limit 1`";
`network speedtest show` still prints the latest result and is now literally
`speedtest history --limit 1`; `history` also takes `--start`/`--end`.

### `network guest show` reads the dedicated endpoint

It no longer extracts `guest_network_*` fields from the full network envelope. Output
fields are unchanged; the password stays masked (`********`) in every format,
including `json`/`yaml` — this command never round-trips the real value.

### Absent features are not errors

`network wan multistaticip show` and `eero support <id>` exit `0` with a
"not configured" / "unavailable" line and `data: null` when the network or node lacks
the feature (`404` from the API). Exit `5` is reserved for a wrong id.

### `eero led brightness` is read-first

Like `led on/off`, `led brightness` now reads the current value and skips the write
when it already matches (`--force` writes anyway).

### Security and SQM toggles ask for `REBOOT`

eero-api 8 documents that every settings-class write reboots every eero on the network.
eeroctl now treats those writes the way it already treated DNS writes:

- `network security wpa3|band-steering|upnp|ipv6 enable|disable` and
  `network sqm enable|disable` move from a Y/N prompt to the **HIGH** tier: you type
  `REBOOT` to confirm, and the prompt names the outage ("Warning: Applying this
  change reboots every eero on the network. All clients lose Wi-Fi and internet while
  the mesh restarts. The outage begins a few minutes after this command returns, not
  immediately."). The new mesh-reboot writes — `network security mlo set`,
  `network dhcp set / connection-mode set / nat-randomization *`, `network reboot`,
  `eero updates apply` — start life at this tier.
- `--force` still skips the prompt, but the reboot warning is **still printed to
  stderr**, exactly as `network dns` did in 2.x. Scripts that pass `--force` keep
  working; they just see one extra stderr line.
- Before writing, eeroctl reads the current value and exits `0` with "Already
  configured as requested; no change made. Check with `<read command>`." if nothing
  would change (`--force` writes anyway). The DHCP writes, `network reboot` and
  `updates apply` have nothing to read first and always write.

The full tier table is in [CLI Reference → Safety Rails](CLI-Reference#-safety-rails).

### Unverified writes carry a note

eero-api 8 marks each write as **verified** (exercised against a live network by the
SDK's maintainers) or **unverified**. For an unverified write, eeroctl:

- prints one line before the confirmation prompt — and before `--force` is
  considered, so scripts see it too: *"This write has not been verified against a
  live network by the SDK; check the result with `<read command>`."*;
- prints one stderr line when the SDK issues the request —
  `note: unverified write (<operation>); verify with `<read command>`` — instead of
  the SDK's raw `WARNING:eero.api.…` log line (`<operation>` is the SDK's wording,
  e.g. `set network name for network`);
- adds the same text to `meta.warnings` in `json`/`yaml` output;
- suppresses the stderr line under `--quiet` (`meta.warnings` stays) and, under
  `--debug`, passes the raw log line through instead of the note.

stdout is never touched, so `--output json | jq` keeps working. The list of unverified
commands is at the end of this page.

### `EEROCTL_FORCE` disables every prompt — and says so

`--force` can now come from the environment (`EEROCTL_FORCE=1`). It disables
confirmation at **every** tier, including the HIGH typed-phrase writes (`REBOOT`,
`DISCONNECT`, `DELETE`) — exactly like `--force` on the command line. Because a
forgotten export would silently turn a mesh reboot into a no-questions-asked
operation, eeroctl prints

```
note: confirmation prompts disabled by EEROCTL_FORCE
```

on stderr once per invocation whenever force comes from the environment rather than
the command line — on reads as well as writes, so the export is visible on the very
next command (`--quiet` suppresses the notice only). Where the force came from is
tracked internally only (`force_source`); it is not part of any command's output.
**Do not export `EEROCTL_FORCE` globally in a shell profile** — set it per job or per
command (`EEROCTL_FORCE=1 eero network sqm disable`).

### Generic output masks sensitive keys

Commands whose response shape the API does not document (`account premium`,
`network events`, `network entitlements *`, `network usage *`, …) print the payload
through a generic key/value renderer. In `table`, `list` and `text` output that
renderer replaces, at any nesting depth, the value of any key containing one of the
SDK's own zero-visibility patterns — `access_token`, `api_key`, `apikey`, `auth`,
`authorization`, `bearer`, `cookie`, `credential`, `key`, `passwd`, `password`,
`private`, `refresh_token`, `secret`, `session`, `session_id`, `token`, `user_token` —
plus the contact keys `email`, `phone`, `sms`, with the literal `<redacted>`. The SDK
list is read at import time, so later SDK additions apply automatically. `serial`,
`mac` and `url` are deliberately shown. `json` and `yaml` are the raw payload and are
never masked: choosing them is your opt-in to the full response. See
[CLI Reference → Redaction](CLI-Reference#redaction-in-table-list-and-text).

### Ids, paths and URLs are passed through unchanged

Every id argument accepts what the API prints in structured output: a bare id
(`123456`), a host-relative path (`/2.2/eeros/123456`) or a full
`https://api-user.e2ro.com/…` URL. The rule for what happens to the argument:

- It is **passed to the SDK unchanged** — and validated there — when it starts with
  `/`, `http://` or `https://`, or contains a `/` anywhere. A malformed path or URL
  (`..`, whitespace, a query string or fragment, a host other than
  `api-user.e2ro.com`), or one that belongs to a different network than the command
  addresses, is rejected by the SDK **before any request** and exits `2` with
  `Invalid input for '<field>': <reason>`.
- **Everything else** (names, serial numbers, MAC addresses, numeric ids, even the
  empty string) is resolved by list-and-match exactly as before; no match exits `5`.

Consequences: a nickname containing `?` or `#` (`"Kids' room #2"`) still resolves by
name; a nickname containing `/` (`"TV/Living"`) is treated as a path and must be
addressed by MAC, serial or id instead.

### Error messages

- Every SDK error now renders as the SDK's catalogue message plus
  `(error code: <meta.error>)` when the API supplied one. The response body is never
  printed (it can carry tokens, emails and phone numbers); `--debug` logs it through the
  SDK's redacting logger.
- `auth login` reports a server-rejected email or phone number as an authentication
  failure (exit `3`), not a validation error.

---

## Exit codes

Full table for 3.0.0. Codes marked **changed** or **new** differ from 2.x.

| Code | Name | Raised by | 2.x → 3.0.0 |
|------|------|-----------|-------------|
| 0 | `SUCCESS` | — | |
| 1 | `GENERIC_ERROR` | any other `EeroException`; an API error with an unmapped status; **rate limiting (HTTP 429)** | **changed** — rate-limit was `7` in 2.x |
| 2 | `USAGE_ERROR` | Click usage errors; `EeroValidationException` (bad input, bad id/path/URL, invalid `--accept-language`) | |
| 3 | `AUTH_REQUIRED` | `EeroAuthenticationException` from **every** entry point | **changed** — commands built on `run_with_client` exited `1` when logged out |
| 4 | `FORBIDDEN` | `EeroAccessDeniedException` (403 + `error.access.denied`); any other 403 | |
| 5 | `NOT_FOUND` | `EeroNotFoundException` — a wrong id. *Not* an absent feature: reads such as `wan multistaticip show` or `eero support` print "not configured / unavailable" and exit `0` with `data: null` | |
| 6 | `CONFLICT` | HTTP 409 | |
| 7 | `TIMEOUT` | `EeroTimeoutException` only | **changed** — no longer covers rate limiting |
| 8 | `SAFETY_RAIL` | confirmation declined, phrase mismatch, or `--non-interactive` without `--force` | |
| 9 | *reserved* | — | |
| 10 | `PARTIAL_SUCCESS` | multi-step commands with a failed step | |
| 11 | `PREMIUM_REQUIRED` | `EeroPremiumRequiredException` | (existed in 2.x; undocumented) |
| 12 | `FEATURE_UNAVAILABLE` | `EeroFeatureUnavailableException` (e.g. `nightlight` on a non-Beacon) | (existed in 2.x; undocumented) |
| 13 | `CLIENT_BLOCKED` | `EeroClientBlockedException` — the API refuses this client version. Stop; do not retry | **new** |
| 14 | `NETWORK_ERROR` | `EeroNetworkException` — unreachable host, DNS failure, connection reset. Retry later | **new** |

Why the two auth/rate-limit changes: 2.x mapped a logged-out session to `3` in some
code paths and `1` in others; 3.0.0 is `3` everywhere. Rate limiting had borrowed `7`
(`TIMEOUT`); 3.0.0 keeps `7` timeout-only so a script can tell "retry now" (`7`) from
"wait" (`1` with the *Rate limited* message) from "network down" (`14`) from "stop"
(`13`).

---

## Environment variables

3.0.0 uses one prefix, `EEROCTL_`, applied to every global flag. Precedence is
**flag > environment > `config.json` > default**.

| Variable | Equivalent flag | Notes |
|----------|-----------------|-------|
| `EEROCTL_OUTPUT` | `--output` | `table`, `list`, `json`, `yaml`, `text` |
| `EEROCTL_NETWORK_ID` | `--network-id` | |
| `EEROCTL_FORCE` | `--force` | Prints a stderr notice when it disarms a prompt (see above) |
| `EEROCTL_NON_INTERACTIVE` | `--non-interactive` | |
| `EEROCTL_DEBUG` | `--debug` | |
| `EEROCTL_QUIET` | `--quiet` | |
| `EEROCTL_NO_COLOR` | `--no-color` | The cross-tool `NO_COLOR` convention also still works |
| `EEROCTL_ACCEPT_LANGUAGE` | `--accept-language` | New; invalid value exits `2` at client construction. See [Configuration](Configuration) |
| `EEROCTL_GET_RETRIES` | `--get-retries` | New; GET-only retries on transport error / 5xx; negative exits `2` |
| `EEROCTL_NO_LEGACY_COOKIE` | `--no-legacy-cookie` | New |
| `EEROCTL_CONFIG_DIR` | — | Overrides `~/.config/eeroctl` (and `%APPDATA%\eeroctl`) for `config.json`, `cookies.json` and the backup; `~` is expanded; the directory is created with mode `0700` |
| `EEROCTL_SESSION_TOKEN` | — | Ephemeral session for CI/containers; never written to keyring or disk. `auth login/logout/clear` exit `2` with "session comes from EEROCTL_SESSION_TOKEN; unset it to manage stored credentials". See [Configuration → CI/CD](Configuration#cicd-usage) |

### Renamed (never implemented)

The 2.x wiki documented three variables that no release ever read. If you set them,
they were silently ignored; set the new names instead.

| Old name (never worked) | 3.0.0 name |
|-------------------------|------------|
| `EERO_CONFIG_DIR` | `EEROCTL_CONFIG_DIR` |
| `EERO_SESSION_TOKEN` | `EEROCTL_SESSION_TOKEN` |
| `EERO_NETWORK_ID` | `EEROCTL_NETWORK_ID` |

---

## Credentials

eero-api 8 changes the credential record and where it lives. No re-login is needed;
the migration happens on the first 3.0.0 command that builds a client.

### Record schema 2

The stored record is now `{"session_id": "…", "schema_version": 2}`. A pre-8 record
(no `schema_version` key; `user_token` accepted as a legacy key) is rewritten in place
the first time it is loaded, with a read-back check. `session_expiry` and
`refresh_token` are gone — the SDK sends the token as an `X-User-Token` header and
refreshes server-side.

### Where the token lives

| `auth_method` | Before 3.0.0 | On 3.0.0 |
|---------------|--------------|----------|
| `keyring` (default) | keyring record `eero` / `user_token` **and** `cookies.json` | keyring record **`eero-api` / `auth-tokens`** only. On first load the SDK promotes a file-only token into the keyring, verifies the read-back, and **deletes `cookies.json`**. |
| `cookie_file` | `cookies.json` (schema 1) | `cookies.json` rewritten to schema 2, mode `600` |

`eero auth status` shows both locations (`storage.keyring.present`,
`storage.cookie_file.present`, `schema_version`), so you can see where the token went.

The keyring record is the SDK's, not eeroctl's: any other eero-api 8 user on the
machine (for example `rusteero`) reads and rewrites the same record. Older eero-api
readers see a schema-2 record as *expired* — see Rollback.

### `cookies.json.pre-v8.bak`

Before the SDK touches an existing **schema-1** `cookies.json`, eeroctl copies it once
to `cookies.json.pre-v8.bak` (mode `600`, never overwritten, skipped when the file is
already schema 2). It exists purely so a rollback keeps your session. It contains the
session token in plain text: delete it once you are happy on 3.0.0.

- `eero auth clear` and `eero auth logout` remove the backup along with the live
  record (`logout` removes it even when there was no session to end) and print
  "removed pre-v8 credential backup" on stderr.
- `eero auth status` reports whether the backup is present: the *Legacy Backup* table
  row, the `legacy_backup` list key, `storage.cookie_file.legacy_backup_present` in
  `json`/`yaml`.

The keyring record is never backed up (that would mean writing the token to disk).

---

## Rollback

The release before 3.0.0 is **2.21.8** on eero-api 6.0.0. There is no 7.x-based
release. 2.21.8 carries the DNS defects fixed on this branch
([#119](https://github.com/fulviofreitas/eeroctl/issues/119)): DNS writes are silent
no-ops and `dns show` reads the wrong keys.

```bash
pip install eeroctl==2.21.8
# Homebrew: the tap has no versioned formula yet; install from PyPI to roll back.
```

A schema-2 record read by eero-api 6.0.0 (or 7.0.0) has no `session_expiry`, which
those versions treat as *expired* and clear. So the session must come from the backup:

| Mode on 3.0.0 | Steps |
|---------------|-------|
| `cookie_file` | `mv ~/.config/eeroctl/cookies.json.pre-v8.bak ~/.config/eeroctl/cookies.json`. The old SDK reads its `session_expiry` and continues, provided the server-side session is still valid. |
| `keyring` | `cookies.json` was deleted after promotion. Either restore the backup as above **and** set `"auth_method": "cookie_file"` in `config.json`, or simply run `eero auth login` on 2.21.8. |

If you already deleted the backup, `eero auth login` is the only path.

---

## Unverified commands

Every write below is marked *unverified* by eero-api 8.0.1: the SDK sends the request
the API documents, but nobody has confirmed the side effect against a live network.
eeroctl prints the unverified line before the prompt, prints the `note:` when the
request goes out, and names the read command to check the result with. Tiers:
**HIGH** = typed phrase (`REBOOT` unless stated), **MEDIUM** = Y/N, **LOW** = no
prompt.

| Command | SDK method | Tier | Read-back command |
|---------|------------|------|-------------------|
| `network dns mode set` / `clear` / `caching enable\|disable` | `set_dns_mode`, `set_custom_dns`, `clear_custom_dns`, `set_dns_caching` | HIGH, reboots the mesh | `eero network dns show` |
| `network sqm enable\|disable` | `set_sqm` | HIGH, reboots the mesh | `eero network sqm show` |
| `network security wpa3\|band-steering\|upnp\|ipv6 enable\|disable` | `set_wpa3`, `set_band_steering`, `set_upnp`, `set_ipv6` | HIGH, reboots the mesh | `eero network security show` |
| `network security mlo set` | `set_mlo_mode` | HIGH, reboots the mesh | `eero network security show` |
| `network security thread enable\|disable` | `set_thread_enabled` | MEDIUM | `eero network security show` |
| `network security passpoint enable\|disable` | `set_passpoint_enabled` | MEDIUM | `eero network security show` |
| `network security proxied-nodes enable\|disable` | `set_proxied_nodes` | MEDIUM | `eero network security show` |
| `network rename` | `set_network_name` | MEDIUM, disconnects clients | `eero network show` |
| `network password set` / `clear` | `set_network_password`, `clear_network_password` | HIGH `DISCONNECT`, disconnects every client | `eero network show` |
| `network reboot` | `reboot_network` (via the envelope's `reboot` link) | HIGH, reboots the mesh | `eero network show` |
| `network ddns enable\|disable` | `enable_ddns`, `disable_ddns` | MEDIUM | `eero network show` |
| `network thread set` | `update_thread`, `regenerate_thread_credentials` | MEDIUM | `eero network thread show` |
| `network dhcp set` | `set_dhcp` | HIGH, reboots the mesh | `eero network show` |
| `network dhcp connection-mode set` | `set_connection_mode` | HIGH, reboots the mesh | `eero network show` |
| `network dhcp nat-randomization enable\|disable` | `set_nat_port_randomization` | HIGH, reboots the mesh | `eero network show` |
| `network dhcp reservation create` / `update` / `delete` | `create_reservation`, `update_reservation`, `delete_reservation` | MEDIUM | `eero network dhcp reservations` |
| `network forwards create` / `update` / `delete` | `create_forward`, `update_forward`, `delete_forward` | MEDIUM | `eero network forwards list` |
| `network backup enable\|disable` | `set_backup_internet` | MEDIUM | `eero network backup show` |
| `network support bundle export` | (two reads written to a local file) | MEDIUM | `eero network support show` |
| `device block` | `block_device` | MEDIUM | `eero device list` |
| `profile create` | `create_profile` | LOW | `eero profile list` |
| `profile rename` | `rename_profile` | MEDIUM | `eero profile list` |
| `profile delete` | `delete_profile` | HIGH `DELETE` | `eero profile list` |
| `profile pause\|unpause` | `pause_profile` | MEDIUM | `eero profile list` |
| `profile apps block\|unblock` | `set_profile_blocked_applications` (replaces the whole list) | MEDIUM | `eero profile apps list` |
| `profile devices set` | `set_profile_devices` (replaces the whole assignment) | MEDIUM | `eero profile show <profile>` |
| `profile dns allow\|block` | `allow_domain_for_profiles`, `block_domain_for_profiles` | MEDIUM | `eero profile show <profile>` |
| `profile schedule set` | `enable_bedtime` | MEDIUM | `eero profile schedule show` |
| `profile schedule clear` | `clear_profile_schedule` | MEDIUM | `eero profile schedule show` |
| `profile schedule delete` | `delete_schedule` | MEDIUM | `eero profile schedule show <profile>` |
| `eero location set` | `set_location` | LOW | `eero eero show <id>` |
| `eero pppoe set` | `set_pppoe` | MEDIUM | `eero eero show <id>` |
| `eero ports cycle` | `node_action(POWER_CYCLE_ALL_PORTS)` | MEDIUM | `eero eero list` |
| `eero ports cycle --reboot` | `node_action(POWER_CYCLE_ALL_PORTS_AND_REBOOT)` | MEDIUM, reboots this eero | `eero eero list` |
| `eero port` | `port_action` | MEDIUM | `eero eero show <id>` |
| `eero led cycle` | `led_cycle` | LOW | `eero eero led show` |
| `eero nightlight on\|off\|brightness\|schedule` | `set_nightlight`, `set_nightlight_schedule` | LOW | `eero eero nightlight show` |
| `eero nightlight override` | `nightlight_override` | LOW | `eero eero nightlight show` |
| `eero updates apply` | `apply_update` | HIGH, reboots the mesh | `eero eero updates show` |
| `troubleshoot diagnostics run` | `run_diagnostics` | LOW | `eero troubleshoot doctor` |
| `network wpa3 set` | `set_wpa3_per_band` | HIGH, reboots the mesh | `eero network wpa3 show` |
| `network security fast-transition enable\|disable` | `set_fast_transition` | HIGH, reboots the mesh | `eero network security fast-transition show` |
| `network dns policy allow\|block` | `allow_domain`, `block_domain` | MEDIUM — and, unlike every other `network dns` write, **no reboot** | `eero network dns policy show` |
| `network dns policy allow-cnames` | `allow_cnames` | MEDIUM, no reboot | `eero network dns policy show` |
| `network members invite create` / `update` / `delete` / `respond` | `create_invite`, `update_invite`, `delete_invite`, `respond_to_invite` | MEDIUM | `eero network members invites` |
| `network members promote` | `promote_member` | MEDIUM | `eero network members list` |
| `network members remove-admin` | `remove_admin` | HIGH `REMOVE` | `eero network members list` |
| `network members cancel-pending-admin` | `cancel_pending_admin` (acts on the caller; takes no id) | MEDIUM | `eero network members invites` |
| `network notifications set` / `mark-read` | `set_notification_settings`, `mark_notifications_read` | LOW | `eero network notifications show` |
| `network usage report set` | `set_data_usage_report_settings` (full replace) | LOW | `eero network usage report show` |
| `network power-saving enable\|disable` | `set_power_saving` | HIGH, reboots the mesh | `eero network power-saving schedules list` |
| `network power-saving schedules create` / `update` / `delete` | `create_power_saving_schedule`, `update_power_saving_schedule`, `delete_power_saving_schedule` | MEDIUM | `eero network power-saving schedules list` |
| `network backup access-points add` / `update` / `delete` / `rearrange` | `add_backup_access_point`, `update_backup_access_point`, `delete_backup_access_point`, `rearrange_backup_access_points` | MEDIUM | `eero network backup access-points list` |
| `network backup access-points discover --start` | `start_backup_ssid_discovery` | MEDIUM | `eero network backup access-points discover` |
| `network backup access-points check` | `backup_connectivity_check` | MEDIUM | `eero network backup status` |
| `network subnets set` | `set_subnets_config` | HIGH, reboots the mesh | `eero network subnets show` |
| `network subnets delete <subnet-type>` | `delete_subnet` | HIGH, reboots the mesh | `eero network subnets show` |
| `network subnets filters set` | `set_subnet_content_filters` (network-scoped; the subnet is named in the payload) | MEDIUM | `eero network subnets filters show <subnet-id>` |
| `network wan multistaticip set` | `set_multistaticip` | HIGH, reboots the mesh | `eero network wan multistaticip show` |
| `network wan secondary set` | `set_secondary_wan_config` | HIGH, reboots the mesh | `eero network show` |
| `device wan-access` | `set_device_secondary_wan_access` | HIGH, reboots the mesh | `eero device show <id>` |
| `account name set` | `set_account_name` | MEDIUM | `eero auth status` |
| `account email set` / `verify` | `set_account_email`, `verify_account_email` (two-step) | MEDIUM | `eero auth status` |
| `account phone set` / `verify` | `set_account_phone`, `verify_account_phone` (two-step) | MEDIUM | `eero auth status` |
| `account consents` | `set_account_consents` | MEDIUM | `eero auth status` |
| `account push set` | `set_push_settings` (no read exists, so no read-first) | MEDIUM | — |

One **read** is also unverified: `network members invites` (`get_invites`). It needs
no confirmation; on some accounts it returns `403` and eeroctl exits `4` with
"Not permitted for this account."

Writes **not** in this table are live-verified by the SDK: `eero led on|off|brightness`,
`device type set <id> <type>`, `network guest enable|disable|set`, `network guest password set|clear`,
`network speedtest run`, `eero reboot`, `device pause|unpause`, `device rename`,
`device unblock`.

---

## 🔗 Related Pages

- [CLI Reference](CLI-Reference) — exit codes, global flags, safety tiers
- [Configuration](Configuration) — credential storage, config keys, environment variables
- [Troubleshooting](Troubleshooting) — what each error means
