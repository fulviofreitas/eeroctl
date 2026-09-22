# 📖 Usage Examples

Practical examples for common Eero CLI tasks.

---

## Authentication

```bash
# Login to Eero account
eero auth login

# Check if authenticated
eero auth status

# Force new login (even if session exists)
eero auth login --force

# Logout
eero auth logout
```

---

## Network Management

```bash
# List all networks
eero network list

# Set preferred network
eero network use <network-id>

# Show network details
eero network show

# Show as JSON (for scripting)
eero --output json network show

# Rename network (requires confirmation)
eero network rename --name "Home WiFi"

# Rename without confirmation
eero network rename --name "Home WiFi" --force

# What can this account do on the network? (role + capability map)
eero network permissions

# Recent app events, one page at a time
eero network events --page-size 50
eero network events --page-size 50 --cursor "$(eero -o json network events --page-size 50 | jq -r '.meta.next_cursor')"

# Wi-Fi channel utilization for one day on the 5 GHz band
eero network channels --start 2026-09-20T00:00:00Z --end 2026-09-21T00:00:00Z --band band_5GHz_full
```

---

## Eero Plus Entitlements

```bash
# Features this network is entitled to
eero network entitlements show

# Features available via upgrade
eero network entitlements upsell

# Which features each eero model supports
eero network entitlements capabilities

# Account-wide subscription status (not network-scoped)
eero account premium

# DNS content-filter allow/block lists (Eero Plus; read-only, no reboot)
eero network dns policy show
```

---

## Members

```bash
# Who has access to the network
eero network members list

# Pending invites (some accounts get "Not permitted for this account", exit 4)
eero network members invites

# Script-friendly: role of the caller
eero -o json network permissions | jq -r '.data.role'
```

### Invites and admin changes

All of these are unverified writes. `invite create` takes a **role, not an email** —
the API mints an invite code/link rather than emailing someone; share the result
yourself. `invite update` only changes the **nickname** (there is no role update), and
`cancel-pending-admin` takes **no id** because it acts on the caller's own request.

```bash
# Create an invite for a role, then read back what the API minted
eero network members invite create --role admin
eero network members invites

# Rename an invite, or withdraw it
eero network members invite update <invite-id> --nickname "Spare key"
eero network members invite delete <invite-id>

# Respond to an invite you received (exactly one of --accept/--decline)
eero network members invite respond <invite-id> --accept
eero network members invite respond <invite-id> --decline

# Promote a member to admin (Y/N)
eero network members promote <member-id>

# Withdraw your own pending admin request (no id — it is always yours)
eero network members cancel-pending-admin
```

Removing someone's admin role is the only members command with a typed phrase,
because this command cannot undo it — restoring admin needs a fresh invite or
promotion:

```
$ eero network members remove-admin <user-id>
This write has not been verified against a live network by the SDK; check the result with `eero network members list`.

⚠ Warning: You are about to network members remove-admin <user-id>.
This is a high-impact operation that may cause service disruption.

To confirm, type REMOVE and press Enter:
Confirmation: REMOVE
Admin role removed.
Verify with `eero network members list`.
```

Anything other than `REMOVE` exits `8` with "Confirmation phrase mismatch. Expected
'REMOVE'." and writes nothing.

---

## Account

Account commands are **not** network-scoped — they take no `--network-id`. Email and
phone changes are two-step: `set` sends a verification code and prints the follow-up
command; nothing changes until `verify` succeeds.

```bash
# Who am I / what am I subscribed to
eero auth status
eero account premium

# Name (read-first: skipped when it already matches)
eero account name set "Jane Doe"

# Email: step 1 sends a code to the new address, step 2 applies the change
eero account email set jane@example.com
eero account email verify 123456

# Phone: same two-step flow
eero account phone set +15551234567
eero account phone verify 123456

# Marketing consent — exactly one of the two flags is required
eero account consents --marketing-emails
eero account consents --no-marketing-emails

# Push notifications: repeat --set per key. There is no read for these,
# so this always writes (no read-first skip).
eero account push set --set device_offline=true --set weekly_digest=false
```

---

## DNS & Security

> **Every DNS write reboots the network.** All eeros restart and clients lose
> Wi-Fi and internet for a few minutes, starting shortly *after* the command
> returns. These commands require typing `REBOOT` to confirm; `--force` skips
> the prompt and also rewrites when the configuration already matches.
> Without `--force`, a command that would change nothing exits 0 and does not
> write.

```bash
# Show DNS settings
eero network dns show

# List the DNS providers this network offers
eero network dns providers

# Set DNS to a provider from that list (IPv4 only by default)
eero network dns mode set cloudflare

# Same, including the provider's IPv6 servers
eero network dns mode set cloudflare --family both

# Set custom DNS servers (mixed families; up to 2 per family)
eero network dns mode set custom --servers 1.1.1.1 --servers 2606:4700:4700::1111

# Back to ISP-assigned DNS, keeping the stored servers for later
eero network dns clear

# Enable WPA3
eero network security wpa3 enable --force

# Disable UPnP
eero network security upnp disable --force
```

---

## Guest Network

```bash
# Enable the guest network with a name (disconnects guest clients; Y/N prompt)
eero network guest set --name "Guest WiFi"

# Set the guest password (prompted, never echoed; or pass --password)
eero network guest password set

# Clear the guest password (open network)
eero network guest password clear

# Show guest network settings
eero network guest show

# Disable guest network
eero network guest disable --force
```

---

## Eero Mesh Nodes

```bash
# List all Eeros
eero eero list

# Show specific Eero
eero eero show "Living Room"

# Reboot one Eero (Y/N prompt; only that node restarts)
eero eero reboot "Living Room"

# Turn off LED (no prompt)
eero eero led off "Living Room"

# LED brightness (0-100)
eero eero led brightness "Living Room" 40

# Set the nightlight schedule (Beacon only; --on-time/--off-time became --on/--off in 3.0.0)
eero eero nightlight schedule "Bedroom" --on 22:00 --off 06:00
eero eero nightlight schedule "Bedroom" --disable
eero eero nightlight override "Bedroom" --brightness 30     # one-shot override

# Rename the node's location label (no prompt)
eero eero location set "Living Room" "Lounge"

# Power-cycle every port on a node (Y/N); add --reboot to restart the node as well
eero eero ports cycle "Office"
eero eero ports cycle "Office" --reboot

# One port: interface number and action (Y/N)
eero eero port "Office" 2 DISABLE_POE

# Apply a pending software update — every node reboots; type REBOOT
eero eero updates check
eero eero updates apply
```

---

## Devices

```bash
# List all connected devices
eero device list

# Show device as JSON
eero --output json device show "iPhone"

# Rename a device
eero device rename "00:11:22:33:44:55" --name "Work Laptop"

# Block a device
eero device block "Smart TV" --force

# Unblock a device
eero device unblock "Smart TV" --force

# Pause internet access for a device
eero device pause "Kids Tablet" --force

# Unpause internet access for a device
eero device unpause "Kids Tablet"

# Set a device's type (no prompt; skipped when it already matches)
eero device type set "Kids Tablet" tablet
```

---

## Profiles & Parental Controls

```bash
# List profiles
eero profile list

# Pause internet for a profile
eero profile pause "Kids" --force

# Unpause
eero profile unpause "Kids"

# Block applications (Eero Plus)
eero profile apps block "Kids" TikTok YouTube

# Unblock applications
eero profile apps unblock "Kids" YouTube

# Replace the profile's device list (Y/N; every device must resolve)
eero profile devices set "Kids" "Kids Tablet" aa:bb:cc:dd:ee:ff

# Per-profile domain policy (Eero Plus; Y/N)
eero profile dns block "Kids" example.com
eero profile dns allow "Kids" example.com --override     # allow despite a block
eero profile dns block "Kids" example.com --delete       # remove from the block list
```

### Schedules

`profile schedule set` manages one entry named **Bedtime**; it reads the current
list first and skips the write when nothing would change.

```bash
# Show the profile's schedules (a list; each entry has an id and a url)
eero profile schedule show "Kids"

# Bedtime every day, 21:00–07:00 (Y/N prompt; unverified note)
eero profile schedule set "Kids" --start 21:00 --end 07:00

# School nights only
eero profile schedule set "Kids" --start 21:00 --end 07:00 --days mon,tue,wed,thu,sun

# Delete one entry by its id (from `schedule show`)
eero profile schedule delete "Kids" 123456

# Remove every schedule
eero profile schedule clear "Kids"
```

---

## Activity (Eero Plus)

```bash
# Show historical inspected-traffic data for a date range
eero activity history --start 2026-07-01 --end 2026-07-22

# Weekly cadence, blocked insight type
eero activity history --start 2026-07-01 --end 2026-07-22 --insight-type blocked --cadence weekly

# Show blocked-traffic categories for a date range
eero activity categories --start 2026-07-01 --end 2026-07-22

# Weekly cadence for categories
eero activity categories --start 2026-07-01 --end 2026-07-22 --cadence weekly

# JSON output for scripting
eero --output json activity history --start 2026-07-01 --end 2026-07-22
```

### Insights (Eero Plus)

`--start`/`--end` are ISO-8601 UTC; `--end` defaults to now. `--cadence` (`hourly`|`daily`)
and `--insight-type` (`adblock`|`blocked`|`inspected`) are required.

```bash
# Blocked traffic per device, daily buckets, last week
eero activity devices --start 2026-09-14T00:00:00Z --cadence daily --insight-type blocked

# One device, hourly
eero activity device "Kids Tablet" --start 2026-09-20T00:00:00Z --end 2026-09-21T00:00:00Z --cadence hourly --insight-type inspected

# Per profile, and one profile's per-device breakdown
eero activity profiles --start 2026-09-14T00:00:00Z --cadence daily --insight-type adblock
eero activity profile "Kids" --devices --start 2026-09-14T00:00:00Z --cadence daily --insight-type blocked
```

---

## Data Usage

Same `--start`/`--end` flags; `--cadence` is required except for `breakdown` and
`devices`; `--timezone` takes an IANA name and defaults to UTC.

```bash
# Network-wide, daily, in local time
eero network usage summary --start 2026-09-01T00:00:00Z --cadence daily --timezone Europe/Lisbon

# Breakdown and per-device (cadence optional here)
eero network usage breakdown --start 2026-09-01T00:00:00Z
eero network usage devices --start 2026-09-01T00:00:00Z --profile <profile-id>

# One device / one eero / one profile
eero network usage device aa:bb:cc:dd:ee:ff --start 2026-09-01T00:00:00Z --cadence daily
eero network usage eero <eero-id> --start 2026-09-01T00:00:00Z --cadence daily
eero network usage profile <profile-id> --start 2026-09-01T00:00:00Z --cadence daily

# Devices not in any profile (list, or --summary)
eero network usage unprofiled --start 2026-09-01T00:00:00Z --cadence daily --summary

# Report settings
eero network usage report show

# Transfer statistics (whole network, or one device)
eero network transfer
eero network transfer --device <device-id>
```

---

## Port Forwards & DHCP Reservations

The API does not document the payload fields, so `create` and `update` take the
object as JSON and send it unchanged. Copy field names from `forwards show <id>` /
`dhcp reservations --output json`. Malformed or empty JSON exits `2` before any
prompt. All six commands are Y/N (MEDIUM) and unverified.

```bash
# Port forwards
eero network forwards list
eero network forwards show <forward-id> --output json          # copy the field names from here
eero network forwards create --config-json '{"<field>": "<value>", …}'
eero network forwards update <forward-id> --config-json '{"<field>": "<new value>"}'
eero network forwards delete <forward-id>

# DHCP reservations (note: `reservation` singular for writes, `reservations` to list)
eero network dhcp reservations --output json
eero network dhcp reservation create --config-json '{"mac": "aa:bb:cc:dd:ee:ff", "ip": "192.168.4.10"}'
eero network dhcp reservation update <reservation-id> --config-json '{"ip": "192.168.4.11"}'
eero network dhcp reservation delete <reservation-id> --delete-forwards   # or --keep-forwards
```

---

## Mesh-wide Writes (`REBOOT`)

`network dhcp set`, `dhcp connection-mode set`, `dhcp nat-randomization *`,
`security mlo set`, `network reboot`, `eero updates apply` and the DNS/SQM/security
toggles all restart every eero. The prompt looks like this (warnings and prompt on
stderr, the last two lines on stdout):

```
$ eero network dhcp connection-mode set BRIDGE
Warning: Applying this change reboots every eero on the network. All clients lose Wi-Fi and internet while the mesh restarts. The outage begins a few minutes after this command returns, not immediately.
This write has not been verified against a live network by the SDK; check the result with `eero network show`.

⚠ Warning: You are about to network dhcp connection-mode set (reboots every eero on the network) BRIDGE.
This is a high-impact operation that may cause service disruption.

To confirm, type REBOOT and press Enter:
Confirmation: REBOOT
Connection mode set to 'BRIDGE'.
Verify with `eero network show`.
```

Anything other than `REBOOT` exits `8` with "Confirmation phrase mismatch. Expected
'REBOOT'." and writes nothing. `--force` skips the prompt but the first two lines are
still printed.

```bash
# DHCP: mode, or a custom lease range, or a raw custom_v2 object
eero network dhcp set --mode manual --start-ip 192.168.4.10 --end-ip 192.168.4.200 --subnet-ip 192.168.4.0 --subnet-mask 255.255.255.0
eero network dhcp set --config-json '{…}'
eero network dhcp nat-randomization enable

# Multi-link operation (read-first: skipped when already set)
eero network security mlo set single

# Wi-Fi password: type DISCONNECT; the hidden password prompt comes after
eero network password set
eero network password clear

# Reboot every eero (type REBOOT)
eero network reboot

# Per-band WPA3 and 802.11r (at least one --band-* flag, or exit 2)
eero network wpa3 set --band-2-4 WPA2_WPA3 --band-5 WPA3
eero network security fast-transition enable

# Power saving for the whole mesh
eero network power-saving enable --schedule-enabled

# One device's access to the secondary WAN (settings-class → whole mesh restarts)
eero device wan-access "Kids Tablet" --deny

# Smaller writes in the same families (Y/N)
eero network ddns enable
eero network security passpoint disable
eero network thread set --regenerate
eero troubleshoot diagnostics run --device "Kids Tablet"      # no prompt (LOW)
```

---

## Power-Saving Schedules

`power-saving enable/disable` restarts the mesh (type `REBOOT`); the schedule CRUD
commands do not and only ask Y/N. Days are collected as a **repeated `--day`**, not a
comma-separated list.

```bash
# What is configured today
eero network power-saving schedules list

# Create a schedule (name, days, start and end are all required)
eero network power-saving schedules create \
  --name "Overnight" --day mon --day tue --day wed --day thu --day fri \
  --start-time 23:00 --end-time 06:00

# Change one field (at least one flag, or exit 2), or turn it off without deleting
eero network power-saving schedules update <schedule-id> --end-time 07:00
eero network power-saving schedules update <schedule-id> --no-enabled

# Remove it
eero network power-saving schedules delete <schedule-id>
```

---

## Subnets & WAN (`--config-json`)

The SDK types these payloads as opaque dictionaries and documents no field names, so
eeroctl forwards your JSON object to the API verbatim. Anything that is not a
non-empty JSON object exits `2` before any prompt or request.

```bash
# Read first — the shapes below are whatever `show` returned
eero -o json network subnets show
eero -o json network wan multistaticip show

# Subnet configuration and deletion both restart the mesh (type REBOOT)
eero network subnets set --config-json '{"subnets": [{"subnet_type": "guest", "…": "…"}]}'
eero network subnets delete guest        # SUBNET_TYPE, not a subnet id

# Per-subnet content filters: MEDIUM (Y/N), no reboot.
# The endpoint is network-scoped — SUBNET_ID is only used to read the result back,
# so the subnet must ALSO be named inside --config-json itself.
eero network subnets filters set <subnet-id> \
  --config-json '{"subnets": ["<subnet-id>"], "content_filters": {"…": "…"}}'
eero network subnets filters show <subnet-id>

# WAN configuration — both restart the mesh (type REBOOT)
eero network wan multistaticip set --config-json '{"…": "…"}'
eero network wan secondary set --config-json '{"…": "…"}'
```

---

## Content Policy, Notifications & Reports

```bash
# Network-wide domain policy (Eero Plus). Unlike the rest of `network dns`,
# these do NOT reboot the mesh — they are a Y/N prompt.
eero network dns policy show
eero network dns policy allow example.com
eero network dns policy block ads.example.com
eero network dns policy block ads.example.com --delete          # undo the block
eero network dns policy allow cdn.example.com --keep-profiles <id> --keep-profiles <id>
eero network dns policy allow-cnames cdn1.example.com cdn2.example.com

# Notification settings: every KEY must already exist in `show`,
# otherwise the command exits 2 rather than inventing a setting.
eero network notifications show
eero network notifications set --set weekly_digest=false --set device_offline=true
eero network notifications mark-read

# Data-usage report settings: BOTH flags are required (full replace, not a patch),
# and the cadence set is daily|hourly — there is no weekly or monthly.
eero network usage report show
eero network usage report set --cadence daily --notification-day 1

# Backup access points (Eero Plus). --start launches a scan; re-run without it to read.
eero network backup access-points discover --start
eero network backup access-points discover
eero network backup access-points add --ssid "Neighbour-Guest"   # password prompted, hidden
eero network backup access-points update <id> --no-enabled
eero network backup access-points rearrange <id-a> <id-b>
eero network backup access-points check
```

---

## Speed Test

```bash
# Start a speed test (the API answers 202; results are not returned here)
eero network speedtest run

# Latest result, about a minute later
eero network speedtest show            # same as: history --limit 1

# Last ten results, or a window
eero network speedtest history --limit 10
eero network speedtest history --start 2026-09-01T00:00:00Z --end 2026-09-21T00:00:00Z
```

---

## Node & Subnet Reads

```bash
# Connections and support data for one eero
eero eero connections "Living Room"
eero eero support "Living Room"        # "unavailable" (exit 0) on nodes without it

# OUI check for one eero
eero network ouicheck "Living Room"

# Device labels (read only)
eero device labels show "Kids Tablet"

# Subnets and per-subnet content filters
eero network subnets show
eero network subnets filters show <subnet-id>

# Multi-static-IP WAN config ("not configured", exit 0 when absent)
eero network wan multistaticip show

# Backup access points (Eero Plus)
eero network backup access-points list
eero network backup access-points discover
```

---

## Security & DHCP reads

```bash
# Security settings, now including mlo_mode, passpoint, proxied_nodes, ddns
eero network security show

# Per-band WPA3 mode and 802.11r fast transition
eero network wpa3 show
eero network security fast-transition show

# DHCP, lease, connection and WAN type
eero network dhcp show

# Notifications
eero network notifications show
eero network notifications unread
eero network notifications history

# Power-saving schedules
eero network power-saving schedules list
```

---

## Troubleshooting

```bash
# Network connectivity status
eero troubleshoot connectivity

# Ping a host from a specific Eero
eero troubleshoot ping --target 1.1.1.1 --from "Living Room"

# Trace route to a host
eero troubleshoot trace --target example.com

# Run every check and summarise
eero troubleshoot doctor
```

---

## Flexible Option Placement

Options like `--output`, `--network-id`, and `--force` can be placed **anywhere** in the command line — before or after subcommands.

```bash
# These are all equivalent:
eero --output json network show
eero network show --output json
eero network --output json show

# Network ID can be placed at the end:
eero device list --network-id abc123
eero eero show "Living Room" -n abc123

# Force can be placed after the action:
eero device block "iPhone" --force
eero --force device block "iPhone"

# Combine multiple options:
eero device list --output json --network-id abc123
```

---

## Scripting & Automation

```bash
# JSON output for parsing
eero network show --output json | jq '.data.name'

# YAML output (human-readable structured format)
eero network list --output yaml

# Non-interactive mode (fails if confirmation needed)
eero network rename --name "NewSSID" --non-interactive
# Exit code 8: safety rail triggered

# Force mode skips confirmations
eero network rename --name "NewSSID" --force

# Quiet mode for cleaner output
eero device list --quiet --output json
```

### Bash Script Example

```bash
#!/bin/bash
set -e

# Get network name
NETWORK=$(eero --output json network show | jq -r '.data.name')
echo "Managing network: $NETWORK"

# List offline devices
eero --output json device list | jq -r '.data[] | select(.connected == false) | .display_name'
```

### Using with cron

Set the global flags once through the environment so every job line stays short.
`EEROCTL_NON_INTERACTIVE` guarantees a job never hangs on a prompt (it exits `8`
instead); `EEROCTL_SESSION_TOKEN` keeps the token out of the keyring on a server.

```bash
EEROCTL_OUTPUT=json
EEROCTL_NON_INTERACTIVE=1
EEROCTL_NETWORK_ID=<network-id>
# EEROCTL_SESSION_TOKEN=<token>   # headless hosts without a keyring

# Start a speed test at 03:00; record the result at 03:02
0 3 * * * /usr/local/bin/eero network speedtest run >/dev/null
2 3 * * * /usr/local/bin/eero network speedtest show >> /var/log/eero-speedtest.jsonl

# Hourly connectivity snapshot
0 * * * * /usr/local/bin/eero troubleshoot connectivity >> /var/log/eero-connectivity.jsonl

# Daily check that the stored session still works (exit 3 alerts via cron mail)
30 6 * * * /usr/local/bin/eero auth status --check >/dev/null
```

---

## 🔗 Related Pages

- [CLI Reference](CLI-Reference) — Complete command structure and flags
- [Configuration](Configuration) — `EEROCTL_*` environment variables
- [Migration](Migration) — Changes in 3.0.0


