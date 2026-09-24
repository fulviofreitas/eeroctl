# 🧪 Testing Checklist

Manual verification scenarios before releasing.

---

## Pre-Release Checklist

### Authentication

- [ ] `eero auth login` — Complete login flow
- [ ] `eero auth status` — Status **Valid**; no Session Expiry row; Credential Schema row present
- [ ] `eero auth status --offline` — **Stored, not verified**; no API call
- [ ] `eero auth status --check` — Exit 0 when valid, 3 when not
- [ ] `eero auth status --offline --check` — Exit 2, "--offline and --check cannot be used together"
- [ ] `eero auth status --output list` — `legacy_backup` row present; no `session_expiry`
- [ ] `eero auth logout` — Successfully logs out; `.pre-v8.bak` removed if present ("removed pre-v8 credential backup" on stderr)
- [ ] `eero auth clear` — Clears stored credentials, `config.json` and `.pre-v8.bak`
- [ ] `EEROCTL_SESSION_TOKEN=x eero auth login` — Exit 2, "session comes from EEROCTL_SESSION_TOKEN; unset it to manage stored credentials"

### Output Formats

- [ ] `eero network list --output table` — Table output format
- [ ] `eero network list --output json` — JSON output format; stdout is the envelope only
- [ ] `eero network list --output list` — List output format

### Core Commands

- [ ] `eero network show` — Shows network details
- [ ] `eero eero list` — Lists Eero nodes
- [ ] `eero device list` — Lists connected devices
- [ ] `eero profile list` — Lists profiles

### Safety Rails

- [ ] `eero eero reboot <id>` — Y/N prompt ("reboots this eero")
- [ ] `eero eero reboot <id> --force` — Skips confirmation
- [ ] `eero eero reboot <id> --non-interactive` — Exits with code 8
- [ ] `eero profile delete <id>` — Prompts for `DELETE`
- [ ] `eero network sqm disable` — Prompts for `REBOOT`; "Applying this change reboots every eero on the network…" and the unverified line precede the prompt (do **not** type the phrase)
- [ ] `eero network sqm disable --force` — Do not run live. Non-live check: reboot warning still on stderr under `--force`
- [ ] `EEROCTL_FORCE=1 eero network list` — `note: confirmation prompts disabled by EEROCTL_FORCE` on stderr even on a read; gone with `--quiet`
- [ ] `eero network guest password set --non-interactive` — Exit 2, "--password is required when --non-interactive is set", no prompt
- [ ] `eero network guest password set` then decline the Y/N prompt — Exit 8; the password prompt never appears
- [ ] `eero -o json network guest password clear --force` — stdout is `{"ok": true, …}` under `eero.network.guest.password.clear/v1` (restore the password afterwards)

### Help & Documentation

- [ ] `eero --help` — Clean help output
- [ ] `eero network --help` — Subcommand help
- [ ] `eero network dns --help` — Nested subcommand help
- [ ] `eero network dns mode set --help` — Names no fixed provider list; points at `dns providers`
- [ ] `eero network sqm set` — "No such command", exit 2

### DNS (destructive — every write reboots the network)

- [ ] `eero network dns show` — Real mode/servers/caching, not defaults
- [ ] `eero network dns show --output json` — DNS subtree only; no password, wan_ip or eeros
- [ ] `eero network dns providers` — Lists the network's catalogue
- [ ] `eero network dns mode set <provider>` — Prompts for `REBOOT`
- [ ] `eero network dns mode set <provider>` twice — Second run exits 0, "already configured", no write
- [ ] `eero network dns mode set custom -s 1.1.1.1 -s 1.0.0.1 -s 8.8.8.8` — Exits 2 before prompting
- [ ] `eero --non-interactive network dns clear` — Exits 8, never hangs

### Error Handling

- [ ] Invalid network ID — Shows "not found" error, exit 5
- [ ] No authentication — Shows "login required" message, exit 3
- [ ] Network timeout — Shows timeout error, exit 7
- [ ] Unreachable host (e.g. bad `/etc/hosts` entry for `api-user.e2ro.com`) — exit 14

---

## v8 migration

Extends the sections above for the eero-api 8 upgrade. **Default is read-only.** Every
item runs against the maintainer's real network with `--output json` captured to
`tests/fixtures/live/` (redacted via the SDK's secure logger patterns before commit)
so formatters can be written against real shapes.

Read-only (run all, no approval needed):

- [ ] `eero auth status` — Valid; keyring record present; cookie file absent after first run
      (keyring mode) or schema 2 (cookie-file mode)
- [ ] `eero auth status --offline` — no network call (`--debug` shows none)
- [ ] `eero network show`, `eero eero list`, `eero device list`, `eero profile list` — unchanged output
- [ ] `eero network guest show`, `network backup show`, `network backup status` — new reads render
- [ ] `eero network security show` / `sqm show` — fields populated (bug fix in §2.7)
- [ ] `eero eero nightlight show <non-beacon>` — `EeroFeatureUnavailableException` → exit 12
      (**no Beacon available**: the show/on/off/brightness/schedule happy paths cannot be
      captured; they stay unverified and are a §13 follow-up for a community capture)
- [ ] `eero profile schedule show <id>` — list shape captured
- [ ] Every phase-A command once, capturing the envelope:
      `account premium`; `network permissions | events | scan | channels | entitlements show|upsell|capabilities |
      members list|invites | notifications show|unread|history | dns policy show | dhcp show | wpa3 show |
      security fast-transition show | power-saving schedules list | speedtest history | transfer |
      ouicheck <eero> | usage summary|breakdown|devices|device|eeros|eero|profile|unprofiled|report show |
      backup access-points list|discover | subnets show | subnets filters show <id> | wan multistaticip show |
      guest show`; `eero connections <id> | support <id>`; `device labels show <id>`;
      `activity devices | device <id> | profiles | profile <id> [--devices]`
- [ ] For each "shape unverified" command above, copy the captured `data` into
      `tests/fixtures/live/` (redacted) and file the dedicated-formatter follow-up
- [ ] `eero network members invites` — confirm whether the account gets 403 → exit 4 message
- [ ] `eero network wan multistaticip show` — 404 path (Q7)
- [ ] Error paths: bad network id → 5; `eero eero show 'a/b'` → 2 (link validation);
      logged-out → 3 from every entry point (`run_with_client`, `with_client`, `auth status`)

Writes — **only the verified list, each with read-back and restore, and only with the
operator's explicit go-ahead per item:**

- [ ] `eero eero led off <id>` → `led show` reads `led_on: false` → `led on` → restore
- [ ] `eero eero led brightness <id> 50` → "Write accepted. Verify with `eero eero led show`." on stderr → read-back → restore original value
- [ ] `eero eero led brightness <id> <current>` → "Already configured as requested; no change made." on stderr, exit 0, no write
- [ ] `eero device type set <id> <type>` → no prompt → read-back with `device show` → restore original
- [ ] `eero device type set <id> <current-type>` → "Already configured…", exit 0
- [ ] `eero network guest disable` → `guest show` → `guest enable` → restore (note: guest
      clients disconnect)
- [ ] `eero network guest password set` → Y/N prompt first, hidden confirmed prompt second → `guest show` → restore original password
- [ ] `eero network guest password set --password <p> --force` → no prompt at all; password absent from stdout, stderr and `--debug` output
- [ ] `eero network speedtest run` → "Speed test started; results in ~1 min via `eero network speedtest history --limit 1`"; `speedtest history --limit 1` ~60 s later
- [ ] `eero eero reboot <least-used-eero>` → "Proceed with eero reboot (reboots this eero) on <name>?" → only that node's reboot marker moves
- [ ] `eero device unblock <mac>` on a device blocked via the app (unblock is verified;
      **do not** run `device block` — its form encoding is unverified)

Explicitly **not** run live in this plan: any DNS write, SQM, security toggles (incl.
`mlo`, `passpoint`, `proxied-nodes`, `thread`), DHCP (`set`, `connection-mode`,
`nat-randomization`, reservations), port forwards, `ddns`, `network password *`,
`network reboot`, `network thread set`, `eero updates apply`, `eero pppoe/location/
ports/port/led cycle`, nightlight writes, `profile schedule set/delete`, `profile
devices set`, `profile dns allow/block`, `troubleshoot diagnostics run`, subnets, WAN,
power-saving, members/invites writes, account writes. Each stays behind confirmation
with the unverified note until the SDK verifies it. Their prompts can be exercised
safely: run the command and answer `n` (or type anything but the phrase) — exit `8`,
nothing written.

---

## Exit Code Verification

| Scenario | Expected Code |
|----------|---------------|
| Successful command | 0 |
| Rate limited (HTTP 429) | 1 |
| Invalid arguments / malformed id | 2 |
| Not authenticated (any command) | 3 |
| Forbidden for this role | 4 |
| Resource not found | 5 |
| Timeout | 7 |
| Safety rail triggered | 8 |
| Eero Plus required | 11 |
| Feature unavailable (nightlight on non-Beacon) | 12 |
| Client version blocked | 13 |
| API unreachable | 14 |

```bash
# Test exit codes
eero auth status --check; echo "Exit: $?"
eero network show --network-id invalid; echo "Exit: $?"
eero eero show 'a/b'; echo "Exit: $?"
eero eero reboot test --non-interactive; echo "Exit: $?"
```

---

## 🔗 Related Pages

- [CLI Reference](CLI-Reference) — Exit codes reference
- [Migration](Migration) — 3.0.0 changes
- [Usage Examples](Usage-Examples) — Command examples
