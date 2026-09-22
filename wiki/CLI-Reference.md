# 📋 CLI Reference

Complete command reference for the Eero CLI (3.0.0, eero-api 8.0.1).

---

## Command Structure

The CLI uses a **noun-first** command structure for consistency and discoverability.

```
eero
├── auth             # Authentication management
│   ├── login        # Login to Eero account (--force, --no-keyring)
│   ├── logout       # Logout from account
│   ├── clear        # Clear stored credentials (--force)
│   └── status       # Check authentication status (--offline, --check)
│
├── network          # Network management
│   ├── list         # List all networks
│   ├── use <id>     # Set preferred network
│   ├── show         # Show network details
│   ├── rename       # Rename network (SSID)
│   ├── password     # Wi-Fi password (every client disconnects)
│   │   ├── set [--password <pass>]          # Type DISCONNECT; prompts (hidden) when omitted
│   │   └── clear                            # Type DISCONNECT
│   ├── reboot       # Reboot every eero (type REBOOT)
│   ├── ddns <enable|disable>                # Dynamic DNS; unverified
│   ├── premium      # Check Eero Plus status
│   ├── permissions  # Your role and per-capability permissions on this network
│   ├── events [--page-size N] [--cursor C]   # Recent app events (paginated)
│   ├── scan         # Latest channel/neighbour scan
│   ├── channels --start T --end T [--band B] [--eero ID] [--granularity M] [--busy-threshold P]
│   ├── entitlements # Eero Plus entitlements
│   │   ├── show                             # Features entitled to this network
│   │   ├── upsell                           # Features available via upgrade
│   │   └── capabilities                     # Per-model device capabilities
│   ├── members      # Network members
│   │   ├── list
│   │   ├── invites                          # Pending invites (403 → exit 4 on some accounts)
│   │   ├── invite   # Invite writes; all unverified
│   │   │   ├── create --role <owner|admin>  # No email: the API returns a code/link
│   │   │   ├── update <invite-id> --nickname <name>
│   │   │   ├── delete <invite-id>
│   │   │   └── respond <invite-id> (--accept | --decline)
│   │   ├── promote <member>                 # Promote a member to admin; unverified
│   │   ├── remove-admin <user>              # Type REMOVE; irreversible from here
│   │   └── cancel-pending-admin             # Cancels the caller's own request; takes no id
│   ├── notifications
│   │   ├── show                             # Per-event notification settings
│   │   ├── unread                           # Whether unread notifications exist
│   │   ├── history [--cursor C]
│   │   ├── set --set KEY=VALUE…             # Keys must already exist in `show`; unverified
│   │   └── mark-read                        # Mark everything read; unverified
│   ├── dns          # DNS settings (every write reboots the network, except `policy`)
│   │   ├── show
│   │   ├── providers                        # List the network's DNS catalogue
│   │   ├── mode set <auto|custom|PROVIDER>  # PROVIDER from `dns providers`
│   │   ├── caching <enable|disable>
│   │   ├── clear [--family ipv4|ipv6]       # Back to automatic, servers kept
│   │   └── policy   # Content filtering (Eero Plus); no reboot, all writes unverified
│   │       ├── show                         # Allow/block lists
│   │       ├── allow <domain> [--delete] [--keep-profiles ID]…
│   │       ├── block <domain> [--delete] [--keep-profiles ID]…
│   │       └── allow-cnames <domain>…       # One or more CNAME domains
│   ├── security     # Security settings
│   │   ├── show                             # + mlo_mode, passpoint, proxied_nodes, ddns
│   │   ├── wpa3 <enable|disable>            # reboots the network
│   │   ├── band-steering <enable|disable>   # reboots the network
│   │   ├── upnp <enable|disable>            # reboots the network
│   │   ├── ipv6 <enable|disable>            # reboots the network
│   │   ├── thread <enable|disable>          # unverified
│   │   ├── mlo set <disabled|single|multi>  # reboots the network
│   │   ├── passpoint <enable|disable>       # unverified
│   │   ├── proxied-nodes <enable|disable>   # unverified
│   │   └── fast-transition                  # 802.11r
│   │       ├── show                         # Current setting
│   │       ├── enable                       # reboots the network
│   │       └── disable                      # reboots the network
│   ├── wpa3         # Per-band WPA3 (distinct from `security wpa3`)
│   │   ├── show                             # Per-band WPA3 mode
│   │   └── set [--band-2-4 M] [--band-5 M]  # M ∈ WPA2|WPA2_WPA3|WPA3; reboots the network
│   ├── sqm          # Smart Queue Management
│   │   ├── show
│   │   ├── enable                           # reboots the network
│   │   └── disable                          # reboots the network
│   ├── guest        # Guest network (writes disconnect guest clients)
│   │   ├── show
│   │   ├── enable
│   │   ├── disable
│   │   ├── set --name <name> [--password <pass>]
│   │   └── password
│   │       ├── set [--password <pass>]      # prompts (hidden) when omitted
│   │       └── clear
│   ├── speedtest    # Speed testing
│   │   ├── run                              # Starts a test (202); results ~1 min later
│   │   ├── show                             # Latest result (= history --limit 1)
│   │   └── history [--limit N] [--start T] [--end T]
│   ├── transfer [--device ID]               # Transfer statistics (network or one device)
│   ├── ouicheck <eero>                      # OUI check for one eero (serial/version from the node)
│   ├── usage        # Data usage (closes #46); --start/--end/--cadence/--timezone
│   │   ├── summary                          # --cadence required
│   │   ├── breakdown                        # --cadence optional
│   │   ├── devices [--profile ID]           # --cadence optional
│   │   ├── device <mac>                     # --cadence required
│   │   ├── eeros                            # --cadence required
│   │   ├── eero <id>                        # --cadence required
│   │   ├── profile <id>                     # --cadence required
│   │   ├── unprofiled [--summary]           # --cadence required
│   │   └── report   # Data-usage report settings (no time window)
│   │       ├── show
│   │       └── set --cadence <daily|hourly> --notification-day <value>
│   │                                        # Both required: full replace; unverified
│   ├── backup       # Backup internet (Eero Plus)
│   │   ├── show
│   │   ├── enable                           # unverified
│   │   ├── disable                          # unverified
│   │   ├── status                           # Cellular usage + events
│   │   └── access-points                    # All writes unverified
│   │       ├── list                         # Configured backup access points
│   │       ├── discover [--start]           # Read the last scan; --start launches a new one
│   │       ├── check                        # Run a backup connectivity check
│   │       ├── add --ssid <s> [--password <p>] [--uuid <u>]   # prompts (hidden) when omitted
│   │       ├── update <id> [--ssid] [--password] [--enabled|--no-enabled] [--uuid]
│   │       ├── delete <id>
│   │       └── rearrange <id>…              # Ids in the desired order
│   ├── subnets
│   │   ├── show                             # Subnet configuration
│   │   ├── set --config-json <json>         # reboots the network
│   │   ├── delete <subnet-type>             # `subnet_type` from `subnets show`; reboots the network
│   │   └── filters                          # Per-subnet content filters
│   │       ├── show <subnet-id>
│   │       └── set <subnet-id> --config-json <json>   # endpoint is network-scoped; unverified
│   ├── wan
│   │   ├── multistaticip
│   │   │   ├── show                         # "not configured" → exit 0, data: null
│   │   │   └── set --config-json <json>     # reboots the network
│   │   └── secondary
│   │       └── set --config-json <json>     # reboots the network
│   ├── forwards     # Port forwards
│   │   ├── list
│   │   ├── show <id>
│   │   ├── create --config-json <json>      # unverified; payload shape undocumented
│   │   ├── update <id> --config-json <json> # unverified
│   │   └── delete <id>                      # unverified
│   ├── dhcp         # DHCP
│   │   ├── show                             # dhcp, lease, connection, ip_settings, wan_type
│   │   ├── reservations                     # List reservations
│   │   ├── leases
│   │   ├── reservation                      # One reservation (singular)
│   │   │   ├── create --config-json <json>  # unverified; payload shape undocumented
│   │   │   ├── update <id> --config-json <json>
│   │   │   └── delete <id> [--delete-forwards|--keep-forwards]
│   │   ├── set [--mode automatic|manual] [--start-ip] [--end-ip] [--subnet-ip] [--subnet-mask] [--config-json]
│   │   │                                    # reboots the network
│   │   ├── connection-mode set <BRIDGE|NAT> # reboots the network
│   │   └── nat-randomization <enable|disable>   # reboots the network
│   ├── power-saving
│   │   ├── enable [--schedule-enabled|--no-schedule-enabled]    # reboots the network
│   │   ├── disable [--schedule-enabled|--no-schedule-enabled]   # reboots the network
│   │   └── schedules
│   │       ├── list
│   │       ├── create --name <n> --day <d>… --start-time <t> --end-time <t> [--enabled|--no-enabled]
│   │       ├── update <schedule-id> [--name] [--day <d>…] [--start-time] [--end-time] [--enabled|--no-enabled]
│   │       └── delete <schedule-id>
│   ├── routing      # Routing table
│   ├── thread       # Thread network
│   │   ├── show
│   │   └── set [--credential-syncing|--no-credential-syncing] [--regenerate]   # unverified
│   └── support      # Support info
│       ├── show
│       └── bundle export
│
├── account          # Account-scoped (no --network-id)
│   ├── premium      # Account-wide premium/subscription status
│   ├── name set <name>                      # Read-first; unverified
│   ├── email        # Two-step change
│   │   ├── set <email>                      # Sends a verification code
│   │   └── verify <code>                    # Confirms the pending change
│   ├── phone        # Two-step change
│   │   ├── set <phone>                      # Sends a verification code
│   │   └── verify <code>                    # Confirms the pending change
│   ├── consents (--marketing-emails | --no-marketing-emails)   # Read-first; one is required
│   └── push set --set KEY=VALUE…            # No read exists, so this always writes
│
├── eero             # Mesh node management
│   ├── list         # List all Eero nodes
│   ├── show <id>    # Show Eero details
│   ├── reboot <id>  # Reboot one Eero (Y/N prompt)
│   ├── connections <id>                     # Connections for one node
│   ├── support <id> # Support data (404 on some nodes → "unavailable", exit 0)
│   ├── led          # LED settings
│   │   ├── show <id>
│   │   ├── on <id>
│   │   ├── off <id>
│   │   ├── brightness <id> <0-100>
│   │   └── cycle <id> --colors <c1,c2,…> --duration <d> --time-per-color <t>   # unverified
│   ├── nightlight   # Nightlight (Beacon only; exit 12 elsewhere); all writes unverified
│   │   ├── show <id>
│   │   ├── on <id>
│   │   ├── off <id>
│   │   ├── brightness <id> <0-100>
│   │   ├── schedule <id> (--on <HH:MM> --off <HH:MM> | --disable | --schedule-json <json>)
│   │   └── override <id> --brightness <0-100>   # one-shot override
│   ├── location set <id> <name>             # Location label; unverified
│   ├── pppoe set <id> --username <u> [--password <p>]   # prompts (hidden) when omitted; unverified
│   ├── ports cycle <id> [--reboot]          # Power-cycle every port; --reboot also restarts the node
│   ├── port <id> <interface> <ACTION>       # Per-port action; unverified
│   └── updates      # Software updates
│       ├── show
│       ├── check
│       └── apply                            # Type REBOOT: every node restarts
│
├── device           # Connected device management
│   ├── list         # List all devices
│   ├── show <id>    # Show device details
│   ├── rename <id> --name <name>
│   ├── block <id>                           # unverified
│   ├── unblock <id>
│   ├── pause <id>
│   ├── unpause <id>
│   ├── type set <id> <type>                 # read-first; no prompt
│   ├── labels show <id>                     # read only (the API's label write is a no-op)
│   └── wan-access <id> (--deny | --allow)   # Secondary-WAN access; reboots the network
│
├── profile          # User profile management
│   ├── list         # List all profiles
│   ├── show <id>    # Show profile details
│   ├── create <name>
│   ├── rename <id> <name>
│   ├── delete <id>  # Type DELETE to confirm
│   ├── pause <id>   # Pause internet access
│   ├── unpause <id> # Resume internet access
│   ├── apps         # Blocked applications (Eero Plus)
│   │   ├── list
│   │   ├── block <app>...                   # replaces the whole list; unverified
│   │   └── unblock <app>...                 # replaces the whole list; unverified
│   ├── devices set <id> <device>...         # replaces the profile's device list; unverified
│   ├── dns          # Per-profile domain policy (Eero Plus); unverified
│   │   ├── allow <id> <domain> [--override] [--delete]
│   │   └── block <id> <domain> [--override] [--delete]
│   └── schedule     # Internet schedule
│       ├── show <id>                        # List of schedules
│       ├── set <id> --start <HH:MM> --end <HH:MM> [--days mon,tue,…]   # "Bedtime" schedule; read-first; unverified
│       ├── delete <id> <schedule-id>        # One schedule entry; unverified
│       └── clear <id>
│
├── activity         # Activity data (Eero Plus)
│   ├── history      # Activity history (requires --start and --end)
│   ├── categories   # Blocked-traffic categories (requires --start and --end)
│   ├── devices      # Per-device insights   (--start --end --cadence --insight-type)
│   ├── device <id>  # One device's insights  (same flags)
│   ├── profiles     # Per-profile insights   (same flags)
│   └── profile <id> [--devices]             # One profile's insights, or its per-device insights
│
├── troubleshoot     # Troubleshooting tools
│   ├── connectivity # Network connectivity status
│   ├── ping --target <host> [--from <eero>]
│   ├── trace --target <host> [--from <eero>]
│   ├── doctor       # Run every check and summarise
│   └── diagnostics run [--device <id>] [--symptom <s>]   # Starts a diagnostics run; unverified
│
└── completion       # Shell completion
    ├── bash
    ├── zsh
    └── fish
```

### Commands new in 3.0.0

Reads take `--output` and `--network-id` (except `account premium`, which is not
network-scoped). Every write lists its tier, whether the SDK has verified it, and the
command to check the result with.

Rows marked **shape unverified** render generically (key/value dump in `table`/`list`/
`text`, raw `data` in `json`/`yaml`) until a live sample is captured; a dedicated view
follows once one is.

Shared time-window flags (`network usage *`, `activity devices|device|profiles|profile`):
`--start T` and `--end T` — ISO-8601 UTC (e.g. `2026-09-21T00:00:00Z`); `--end` defaults
to now; an inverted window is rejected with exit `2` before any request. `--cadence
{hourly, daily}` — required where the row says so. `--timezone NAME` (usage only) —
IANA name (e.g. `Europe/Lisbon`), defaults to UTC.

| Command | Flags / arguments | Kind | Notes |
|---------|-------------------|------|-------|
| `network speedtest history` | `--limit N` (≥ 1), `--start T`, `--end T` (ISO-8601 UTC) | read | Past speed tests. `speedtest show` is now literally `history --limit 1`. Shape unverified — rendered generically until a live sample is captured. |
| `network transfer` | `--device ID` (bare device id) | read | Network-wide or one device's transfer statistics. Shape unverified — rendered generically until a live sample is captured. |
| `network ouicheck <eero>` | `EERO_IDENTIFIER` (id, serial or name) | read | Serial and version are taken from the resolved eero. Shape unverified — rendered generically until a live sample is captured. |
| `network usage summary` | time window, `--cadence` **required**, `--timezone` | read | Network-wide data usage. Closes #46. Shape unverified — rendered generically until a live sample is captured. |
| `network usage breakdown` | time window, `--cadence` optional, `--timezone` | read | Shape unverified — rendered generically until a live sample is captured. |
| `network usage devices` | `--profile ID` (restrict to one profile's devices), time window, `--cadence` optional, `--timezone` | read | Per-device usage. Shape unverified — rendered generically until a live sample is captured. |
| `network usage device <mac>` | `DEVICE_MAC`, time window, `--cadence` **required**, `--timezone` | read | Shape unverified — rendered generically until a live sample is captured. |
| `network usage eeros` | time window, `--cadence` **required**, `--timezone` | read | Per-eero summary. Shape unverified — rendered generically until a live sample is captured. |
| `network usage eero <id>` | `EERO_ID`, time window, `--cadence` **required**, `--timezone` | read | Shape unverified — rendered generically until a live sample is captured. |
| `network usage profile <id>` | `PROFILE_ID`, time window, `--cadence` **required**, `--timezone` | read | Shape unverified — rendered generically until a live sample is captured. |
| `network usage unprofiled` | `--summary` (summary instead of the per-device list), time window, `--cadence` **required** for both forms, `--timezone` | read | Shape unverified — rendered generically until a live sample is captured. |
| `network usage report show` | — | read | Data-usage report settings; no time window. Shape unverified — rendered generically until a live sample is captured. |
| `network backup access-points list` | — | read | Configured backup access points (Eero Plus). Shape unverified — rendered generically until a live sample is captured. |
| `network backup access-points discover` | — | read | Nearby backup SSIDs (GET, SDK-verified). Shape unverified — rendered generically until a live sample is captured. |
| `network subnets show` | — | read | Subnet configuration. Shape unverified — rendered generically until a live sample is captured. |
| `network subnets filters show <subnet-id>` | `SUBNET_ID` (passed to the SDK verbatim) | read | Content filters for one subnet. Shape unverified — rendered generically until a live sample is captured. |
| `network wan multistaticip show` | — | read | Absent feature (`404` + `error.network.multistaticip_not_found`) prints "not configured", exits `0`, `data: null`; any other `404` is a wrong id → exit `5`. Shape unverified — rendered generically until a live sample is captured. |
| `network guest show` | — | read | Now reads the dedicated guest-network endpoint. The password is masked (`********`) in **every** format, including `json`/`yaml`. Shape unverified (field names assumed `enabled`/`name`/`password`). |
| `eero connections <id>` | `EERO_IDENTIFIER` (id, serial or name) | read | Connections for one node. Shape unverified — rendered generically until a live sample is captured. |
| `eero support <id>` | `EERO_IDENTIFIER` | read | Support data (takes the node's serial). `404` on some nodes → "unavailable", exit `0`, `data: null`. Shape unverified — rendered generically until a live sample is captured. |
| `device labels show <id>` | `DEVICE_IDENTIFIER` (id, MAC or name) | read | Read only — the API's label write is a documented no-op, so there is no `labels set`. Shape unverified — rendered generically until a live sample is captured. |
| `activity devices` | time window, `--cadence {hourly, daily}` **required**, `--insight-type {adblock, blocked, inspected}` **required** | read | Eero Plus. Shape unverified — rendered generically until a live sample is captured. |
| `activity device <id>` | `DEVICE_IDENTIFIER`, same flags | read | Eero Plus. Shape unverified — rendered generically until a live sample is captured. |
| `activity profiles` | same flags | read | Eero Plus. Shape unverified — rendered generically until a live sample is captured. |
| `activity profile <id>` | `PROFILE_IDENTIFIER`, `--devices` (the profile's per-device insights instead of its own), same flags | read | Eero Plus. Shape unverified — rendered generically until a live sample is captured. |
| `account premium` | — | read | Account-wide premium/subscription status. Undocumented shape → generic renderer. |
| `network entitlements show` | — | read | Premium features entitled to this network. Also backs the premium check in `troubleshoot doctor`. |
| `network entitlements upsell` | — | read | Features available via upgrade. |
| `network entitlements capabilities` | — | read | Per-model device feature capabilities. Bare network id only. |
| `network events` | `--page-size N` (≥ 1, sent as `page_size`), `--cursor C` (from a previous page, sent as `timestamp`) | read | Paginated. `json`/`yaml` carry the next cursor in `meta.next_cursor`. |
| `network scan` | — | read | Latest channel/neighbour scan. |
| `network channels` | `--start T`, `--end T` (both required, ISO-8601 UTC e.g. `2026-09-21T00:00:00Z`), `--band {band_2_4GHz, band_5GHz_low, band_5GHz_high, band_5GHz_full, band_6GHz}`, `--eero ID` (integer eero id), `--granularity M` (minutes per sample, ≥ 1), `--busy-threshold P` (percent, ≥ 1) | read | Wi-Fi channel utilization for a time window. |
| `network permissions` | — | read | Your `role` plus a per-capability map. Check this before assuming a `4` is a bug. |
| `network notifications show` | — | read | One boolean per event key. |
| `network notifications unread` | — | read | `data.has_unread`. |
| `network notifications history` | `--cursor C` | read | Paginated like `network events`. |
| `network dns policy show` | — | read | Eero Plus. `data.allowed_list` / `data.blocked_list`. Not a DNS write; no reboot. |
| `network members list` | — | read | `data.members`. Verified. |
| `network members invites` | — | read (unverified) | Pending invites. Some accounts get `403` here even though they can list members: prints "Not permitted for this account." and exits `4` (structured: `{"error": "not_permitted"}`). |
| `network dhcp show` | — | read | `dhcp`, `lease`, `connection`, `ip_settings`, `wan_type` from the network envelope. |
| `network wpa3 show` | — | read | Per-band WPA3 mode. Separate group from `network security wpa3 enable/disable`. |
| `network security fast-transition show` | — | read | 802.11r fast-transition setting. |
| `network security show` | — | read | Extended with `mlo_mode`, `passpoint`, `proxied_nodes`, `ddns` (read from the network envelope; no dedicated GETs). |
| `network power-saving schedules list` | — | read | Verified. Undocumented shape → generic renderer. |
| `device type set <id> <type>` | `DEVICE_IDENTIFIER` (id, MAC or name), `DEVICE_TYPE` (free string; the API's own type names), `--force`, `--network-id` | write · **LOW** · verified · no reboot | Read-first: skips the write when the type already matches. Read-back: `eero device show <id>`. |
| `network guest password set` | `--password <pass>` (omitted → hidden, confirmed prompt; `--non-interactive` without it exits `2` before any prompt), `--force` | write · **MEDIUM** · verified · disconnects guest clients | Never echoed. Read-back: `eero network guest show`. `network guest set --password` issues the same write. |
| `network guest password clear` | `--force` | write · **MEDIUM** · verified · disconnects guest clients | Read-back: `eero network guest show`. |
| `eero led brightness <id> <0-100>` | — | write · **LOW** · verified | Now read-first like `led on/off`: skips the write when brightness already matches (`--force` writes anyway). |
| `network speedtest run` | — | write · **LOW** · verified | Prints "Speed test started; results in ~1 min via `eero network speedtest history --limit 1`". |
| `profile schedule set <id>` | `PROFILE_IDENTIFIER`, `--start HH:MM` **required**, `--end HH:MM` **required**, `--days mon,tue,…` (comma-separated; omitted = every day), `--force` | write · **MEDIUM** · unverified · no reboot | Rewired: creates or replaces the profile's **Bedtime** schedule. Read-first: compares start/end/days with the existing Bedtime entry and skips when equal. Read-back: `eero profile schedule show`. |
| `profile schedule delete <id> <schedule-id>` | `PROFILE_IDENTIFIER`, `SCHEDULE_ID` (the entry's `id`, or the tail of its `url` from `schedule show`), `--force` | write · **MEDIUM** · unverified · no reboot | Unknown schedule id → exit `5`. Read-back: `eero profile schedule show <profile>`. |
| `profile devices set <id> <device>…` | `PROFILE_IDENTIFIER`, one or more `DEVICES` (id, MAC or name; every one must resolve or the command exits `5` before writing), `--force` | write · **MEDIUM** · unverified · no reboot | **Replaces** the profile's whole device assignment. Read-first: skips when the resolved set already matches. Read-back: `eero profile show <profile>`. |
| `profile dns allow <id> <domain>` | `PROFILE_IDENTIFIER`, `DOMAIN`, `--override` (override an existing block), `--delete` (remove from the allow list), `--force` | write · **MEDIUM** · unverified · no reboot | Eero Plus (`11` without it). Read-back: `eero profile show <profile>`. |
| `profile dns block <id> <domain>` | same, `--override` overrides an existing allow, `--delete` removes from the block list | write · **MEDIUM** · unverified · no reboot | Eero Plus. Read-back: `eero profile show <profile>`. |
| `network forwards create` | `--config-json '{…}'` **required** (non-empty JSON object, sent verbatim; the SDK does not document the fields), `--force` | write · **MEDIUM** · unverified · no reboot | Malformed or empty JSON → exit `2` before any prompt. Read-back: `eero network forwards list`. |
| `network forwards update <id>` | `FORWARD_ID` (bare id), `--config-json` **required** (fields to change), `--force` | write · **MEDIUM** · unverified · no reboot | Read-back: `eero network forwards list`. |
| `network forwards delete <id>` | `FORWARD_ID`, `--force` | write · **MEDIUM** · unverified · no reboot | Read-back: `eero network forwards list`. |
| `network dhcp reservation create` | `--config-json '{"mac": …, "ip": …}'` **required** (sent verbatim), `--force` | write · **MEDIUM** · unverified · no reboot | Note the singular group: `reservation create`, `reservations` lists. Read-back: `eero network dhcp reservations`. |
| `network dhcp reservation update <id>` | `RESERVATION_ID`, `--config-json` **required**, `--force` | write · **MEDIUM** · unverified · no reboot | Read-back: `eero network dhcp reservations`. |
| `network dhcp reservation delete <id>` | `RESERVATION_ID`, `--delete-forwards` / `--keep-forwards` (port forwards tied to the reservation; API default when neither is given), `--force` | write · **MEDIUM** · unverified · no reboot | Read-back: `eero network dhcp reservations`. |
| `network dhcp set` | at least one of `--mode {automatic, manual}`, `--start-ip`, `--end-ip`, `--subnet-ip`, `--subnet-mask` (the custom lease range), `--config-json` (raw `custom_v2` object); `--force` | write · **HIGH `REBOOT`** · unverified · reboots the mesh | No flags at all → exit `2`. No read-first (there is no dedicated DHCP GET). Read-back: `eero network show`. |
| `network dhcp connection-mode set <BRIDGE\|NAT>` | `MODE`, `--force` | write · **HIGH `REBOOT`** · unverified · reboots the mesh | No read-first. Read-back: `eero network show`. |
| `network dhcp nat-randomization enable\|disable` | `--force` | write · **HIGH `REBOOT`** · unverified · reboots the mesh | No read-first. Read-back: `eero network show`. |
| `network security mlo set <disabled\|single\|multi>` | `MODE`, `--force` | write · **HIGH `REBOOT`** · unverified · reboots the mesh | Read-first against `mlo_mode` on the network envelope. Read-back: `eero network security show`. |
| `network security passpoint enable\|disable` | `--force` | write · **MEDIUM** · unverified · no reboot | Read-first against `passpoint` on the network envelope. Read-back: `eero network security show`. |
| `network security proxied-nodes enable\|disable` | `--force` | write · **MEDIUM** · unverified · no reboot | Read-first against `proxied_nodes`. Read-back: `eero network security show`. |
| `network password set` | `--password <pass>` (omitted → hidden, confirmed prompt **after** the `DISCONNECT` confirmation; `--non-interactive` without it exits `2` before any prompt), `--force` | write · **HIGH `DISCONNECT`** · unverified · disconnects every client | Never echoed. Read-back: `eero network show`. |
| `network password clear` | `--force` | write · **HIGH `DISCONNECT`** · unverified · disconnects every client | Read-back: `eero network show`. |
| `network reboot` | `--force` | write · **HIGH `REBOOT`** · unverified · reboots the mesh | Follows the network envelope's published `reboot` link. No read-first (a reboot has no idempotent state). Prints "Network reboot initiated." Read-back: `eero network show`. |
| `network ddns enable\|disable` | `--force` | write · **MEDIUM** · unverified · no reboot | Read-first against `ddns` on the network envelope (no dedicated GET). Read-back: `eero network show`. |
| `network thread set` | at least one of `--credential-syncing` / `--no-credential-syncing`, `--regenerate` (new Thread credentials); `--force` | write · **MEDIUM** · unverified · no reboot | Neither flag → exit `2`. Two writes when both are given; one confirmation. Read-back: `eero network thread show`. |
| `troubleshoot diagnostics run` | `--device ID` (id/MAC/name to focus on), `--symptom S`, `--force`, `--network-id` | write · **LOW** · unverified · no reboot | Starts a diagnostics run; prints "Diagnostics run started." Read-back: `eero troubleshoot doctor`. |
| `eero location set <id> <name>` | `EERO_IDENTIFIER` (id, serial or name/location), `LOCATION_NAME`, `--force` | write · **LOW** · unverified · no reboot | Read-back: `eero eero show <id>`. |
| `eero pppoe set <id>` | `EERO_IDENTIFIER`, `--username` **required**, `--password` (omitted → hidden, confirmed prompt after confirmation; `--non-interactive` without it exits `2`), `--force` | write · **MEDIUM** · unverified · no reboot | Never echoed. Read-back: `eero eero show <id>`. |
| `eero ports cycle <id>` | `EERO_IDENTIFIER`, `--force` | write · **MEDIUM** · unverified · no reboot (wired clients drop while the ports reset) | `POWER_CYCLE_ALL_PORTS`. Read-back: `eero eero list`. |
| `eero ports cycle <id> --reboot` | `--reboot`, `--force` | write · **MEDIUM** · unverified · reboots this eero | `POWER_CYCLE_ALL_PORTS_AND_REBOOT`; the prompt says "reboots this eero". Read-back: `eero eero list`. |
| `eero port <id> <interface> <ACTION>` | `EERO_IDENTIFIER`, `INTERFACE_NUMBER`, `ACTION` ∈ `ENABLE_DATA`, `DISABLE_DATA`, `ENABLE_POE`, `DISABLE_POE`, `ENABLE_PORT`, `DISABLE_PORT`, `RESTART_POWER`, `ENABLE_PORT_SECURITY`, `DISABLE_PORT_SECURITY`; `--force` | write · **MEDIUM** · unverified · no reboot | Read-back: `eero eero show <id>`. |
| `eero led cycle <id>` | `EERO_IDENTIFIER`, `--colors c1,c2,…` **required**, `--duration` **required**, `--time-per-color` **required** (values passed to the API as given) | write · **LOW** · unverified · no reboot | Addresses the node by serial. Read-back: `eero eero led show`. |
| `eero nightlight override <id>` | `EERO_IDENTIFIER`, `--brightness 0-100` **required** | write · **LOW** · unverified · no reboot | One-shot override via the dedicated action, distinct from `nightlight brightness`. Beacon only (exit `12` elsewhere). Read-back: `eero eero nightlight show`. |
| `eero nightlight schedule <id>` | exactly one of: `--on HH:MM` **with** `--off HH:MM`; `--disable`; `--schedule-json '{…}'` (raw object, forwarded unchanged) | write · **LOW** · unverified · no reboot | **Renamed** from `--on-time/--off-time`. None or more than one mode → exit `2`. Shape unverified — no Beacon available. Read-back: `eero eero nightlight show`. |
| `eero updates apply` | `--force`, `--network-id` | write · **HIGH `REBOOT`** · unverified · reboots the mesh | Applies the pending update; every node restarts. No read-first. Read-back: `eero eero updates show`. |

| `network wpa3 set` | at least one of `--band-2-4 {WPA2, WPA2_WPA3, WPA3}`, `--band-5 {WPA2, WPA2_WPA3, WPA3}`; `--force`, `--network-id` | write · **HIGH `REBOOT`** · unverified · reboots the mesh | Neither flag → exit `2` before any prompt (the SDK rejects an empty update too). Read-first against `band_2_4_ghz`/`band_5_ghz`; an omitted band never counts as a difference. Read-back: `eero network wpa3 show`. |
| `network security fast-transition enable\|disable` | `--force` | write · **HIGH `REBOOT`** · unverified · reboots the mesh | 802.11r. Read-first against `enabled`. Read-back: `eero network security fast-transition show`. |
| `network dns policy allow <domain>` | `DOMAIN`, `--delete` (remove from the allow list instead), `--keep-profiles ID` (**repeatable** — one profile id per flag), `--force` | write · **MEDIUM** · unverified · no reboot | Eero Plus (`11` without it). Network-wide, and unlike the other `network dns` commands it does **not** reboot. Read-back: `eero network dns policy show`. |
| `network dns policy block <domain>` | same flags; `--delete` removes from the block list | write · **MEDIUM** · unverified · no reboot | Eero Plus. No reboot. Read-back: `eero network dns policy show`. |
| `network dns policy allow-cnames <domain>…` | one or more `DOMAINS` (**required**), `--force` | write · **MEDIUM** · unverified · no reboot | Eero Plus. No `--delete`: the API offers no removal for CNAMEs. Read-back: `eero network dns policy show`. |
| `network members invite create` | `--role {owner, admin}` **required**, `--force` | write · **MEDIUM** · unverified · no reboot | Takes **no email address** — `create_invite` mints an invite code/link for a role, it does not address an invitee. Read-back: `eero network members invites`. |
| `network members invite update <invite-id>` | `INVITE_ID`, `--nickname` **required**, `--force` | write · **MEDIUM** · unverified · no reboot | The only updatable field is the **nickname**, not the role. Read-back: `eero network members invites`. |
| `network members invite delete <invite-id>` | `INVITE_ID`, `--force` | write · **MEDIUM** · unverified · no reboot | Read-back: `eero network members invites`. |
| `network members invite respond <invite-id>` | `INVITE_ID`, exactly one of `--accept` / `--decline`, `--force` | write · **MEDIUM** · unverified · no reboot | Neither or both → exit `2`. Read-back: `eero network members invites`. |
| `network members promote <member>` | `MEMBER` (the member's id), `--force` | write · **MEDIUM** · unverified · no reboot | Read-back: `eero network members list`. |
| `network members remove-admin <user>` | `USER` (the user's id), `--force` | write · **HIGH `REMOVE`** · unverified · no reboot | Irreversible from this command alone — re-granting admin needs a fresh invite/promotion. Read-back: `eero network members list`. |
| `network members cancel-pending-admin` | `--force` | write · **MEDIUM** · unverified · no reboot | Takes **no id**: `cancel_pending_admin` acts on the caller's own pending request. Read-back: `eero network members invites`. |
| `network notifications set` | `--set KEY=VALUE` (**repeatable**; `VALUE` ∈ `true`/`false`/`1`/`0`), `--force`, `--network-id` | write · **LOW** · unverified · no reboot | Every `KEY` must already appear in `network notifications show`; an unknown key exits `2` instead of being silently added. Read-first: skips when every pair already matches. Read-back: `eero network notifications show`. |
| `network notifications mark-read` | `--force`, `--network-id` | write · **LOW** · unverified · no reboot | Marks everything read. No read-first (there is no idempotent state). Read-back: `eero network notifications show`. |
| `network usage report set` | `--cadence {daily, hourly}` **required**, `--notification-day VALUE` **required** (forwarded unchanged), `--force`, `--network-id` | write · **LOW** · unverified · no reboot | Both flags are required: the endpoint is a **full replace**, not a partial update. The cadence set is `daily\|hourly` — the same set the SDK validates data-usage reads against; there is no `weekly`/`monthly`. Read-first. Read-back: `eero network usage report show`. |
| `network power-saving enable\|disable` | `--schedule-enabled` / `--no-schedule-enabled` (omitted → left unchanged), `--force` | write · **HIGH `REBOOT`** · unverified · reboots the mesh | Read-first against the current power-saving state. Read-back: `eero network power-saving schedules list`. |
| `network power-saving schedules create` | `--name` **required**, `--day D` **required and repeatable** (one day per flag), `--start-time` **required**, `--end-time` **required**, `--enabled`/`--no-enabled` (default enabled), `--force` | write · **MEDIUM** · unverified · no reboot | Days are collected as repeated `--day`, not a comma-separated list. Times and day names are forwarded to the API unchanged. Read-back: `eero network power-saving schedules list`. |
| `network power-saving schedules update <id>` | `SCHEDULE_ID`, any of `--name`, `--day D` (repeatable), `--start-time`, `--end-time`, `--enabled`/`--no-enabled`; `--force` | write · **MEDIUM** · unverified · no reboot | No flags → exit `2` (the SDK rejects an empty update). Read-back: `eero network power-saving schedules list`. |
| `network power-saving schedules delete <id>` | `SCHEDULE_ID`, `--force` | write · **MEDIUM** · unverified · no reboot | Read-back: `eero network power-saving schedules list`. |
| `network backup access-points discover --start` | `--start` (without it the command is a plain read), `--force` | write · **MEDIUM** · unverified · no reboot | `--start` launches a scan; re-run without it to read the result. Read-back: `eero network backup access-points discover`. |
| `network backup access-points check` | `--force`, `--network-id` | write · **MEDIUM** · unverified · no reboot | Runs a backup connectivity check. Read-back: `eero network backup status`. |
| `network backup access-points add` | `--ssid` **required**, `--password` (omitted → hidden, confirmed prompt; `--non-interactive` without it exits `2`), `--uuid`, `--force` | write · **MEDIUM** · unverified · no reboot | Never echoed. Read-back: `eero network backup access-points list`. |
| `network backup access-points update <id>` | `BACKUP_NETWORK_ID`, any of `--ssid`, `--password` (omitted → unchanged, **not** prompted), `--enabled`/`--no-enabled`, `--uuid`; `--force` | write · **MEDIUM** · unverified · no reboot | No flags → exit `2`. Read-back: `eero network backup access-points list`. |
| `network backup access-points delete <id>` | `BACKUP_NETWORK_ID`, `--force` | write · **MEDIUM** · unverified · no reboot | Read-back: `eero network backup access-points list`. |
| `network backup access-points rearrange <id>…` | one or more `ORDER` ids (**required**) in the desired order, `--force` | write · **MEDIUM** · unverified · no reboot | Read-back: `eero network backup access-points list`. |
| `network subnets set` | `--config-json '{…}'` **required** (non-empty JSON object, sent verbatim), `--force` | write · **HIGH `REBOOT`** · unverified · reboots the mesh | The SDK documents no field names for this payload. Read-back: `eero network subnets show`. |
| `network subnets delete <subnet-type>` | `SUBNET_TYPE` (the `subnet_type` field from `subnets show`, **not** a subnet id), `--force` | write · **HIGH `REBOOT`** · unverified · reboots the mesh | Read-back: `eero network subnets show`. |
| `network subnets filters set <subnet-id>` | `SUBNET_ID`, `--config-json '{…}'` **required**, `--force` | write · **MEDIUM** · unverified · no reboot | `set_subnet_content_filters` is **network-scoped and takes no subnet id** — `SUBNET_ID` is used only to read the result back via `filters show`. The subnet the filters apply to must be named inside `--config-json` itself. Read-back: `eero network subnets filters show <subnet-id>`. |
| `network wan multistaticip set` | `--config-json '{…}'` **required**, `--force` | write · **HIGH `REBOOT`** · unverified · reboots the mesh | Undocumented payload; sent verbatim. Read-back: `eero network wan multistaticip show`. |
| `network wan secondary set` | `--config-json '{…}'` **required**, `--force` | write · **HIGH `REBOOT`** · unverified · reboots the mesh | Undocumented payload; sent verbatim. Read-back: `eero network show`. |
| `device wan-access <id>` | `DEVICE_IDENTIFIER` (id, MAC or name), exactly one of `--deny` / `--allow`, `--force`, `--network-id` | write · **HIGH `REBOOT`** · unverified · reboots the mesh | Secondary-WAN access for one device; the write is settings-class, so the whole mesh restarts. Neither or both flags → exit `2`. Read-back: `eero device show <id>`. |
| `account name set <name>` | `NAME`, `--force` | write · **MEDIUM** · unverified · no reboot | Not network-scoped (no `--network-id`). Read-first against the current account name. Read-back: `eero auth status`. |
| `account email set <email>` | `EMAIL`, `--force` | write · **MEDIUM** · unverified · no reboot | **Step 1 of 2**: sends a verification code to the new address and prints the follow-up command. The address does not change until step 2. Read-back: `eero auth status`. |
| `account email verify <code>` | `CODE`, `--force` | write · **MEDIUM** · unverified · no reboot | **Step 2 of 2** for `account email set`. Read-back: `eero auth status`. |
| `account phone set <phone>` | `PHONE`, `--force` | write · **MEDIUM** · unverified · no reboot | **Step 1 of 2**: sends a verification code to the new number. Read-back: `eero auth status`. |
| `account phone verify <code>` | `CODE`, `--force` | write · **MEDIUM** · unverified · no reboot | **Step 2 of 2** for `account phone set`. Read-back: `eero auth status`. |
| `account consents` | exactly one of `--marketing-emails` / `--no-marketing-emails` (**required**), `--force` | write · **MEDIUM** · unverified · no reboot | Neither → exit `2`. Read-first against the current consent. Read-back: `eero auth status`. |
| `account push set` | `--set KEY=VALUE` (**repeatable**; `true`/`false`/`1`/`0`), `--force` | write · **MEDIUM** · unverified · no reboot | No read exists for push settings, so there is **no read-first** and the write always goes out. Read-back: `eero account push set` (the write's own response is the only view). |

`--config-json` (forwards, reservations, `dhcp set`, `subnets set`, `subnets filters set`,
`wan multistaticip set`, `wan secondary set`) and `--schedule-json` must be a
non-empty JSON **object**; anything else exits `2` before any prompt or request.
eeroctl forwards the object to the API verbatim because the SDK types these payloads
as opaque dictionaries and documents no field names.

### Identifiers

Every `<id>` argument accepts, verbatim, what the API prints in `--output json`: a bare
id (`123456`), a host-relative path (`/2.2/eeros/123456`) or a full
`https://api-user.e2ro.com/…` URL. Where the command says so, a name, serial number or
MAC address is looked up for you (`eero eero show "Living Room"`,
`eero device block aa:bb:cc:dd:ee:ff`).

| Argument | What eeroctl does |
|----------|-------------------|
| starts with `/`, `http://` or `https://`, or contains `/` anywhere | Passed to the SDK **unchanged**. The SDK validates it before any request: a malformed path (`..`, whitespace, a query string or fragment), a path for a different network than the command addresses, or a URL not on `api-user.e2ro.com` → exit `2` with `Invalid input for '<field>': …`. |
| anything else (name, serial, MAC, numeric id, the empty string) | Resolved by list-and-match, as in 2.x; no match → exit `5`. |

So a nickname with `?` or `#` keeps resolving by name; a nickname containing `/` is
taken as a path and must be addressed by MAC, serial or id.

---

## 🔧 Global Flags

Global flags can be placed **anywhere** in the command line — before or after subcommands:

```bash
# All of these work:
eero --output json network list
eero network list --output json
eero network --output json list

# Combine with subcommand-specific options:
eero device block "iPhone" --force --network-id abc123
```

| Flag                | Short | Env var | Description                                        |
| ------------------- | ----- | ------- | -------------------------------------------------- |
| `--output`          | `-o`  | `EEROCTL_OUTPUT` | Output format: `table`, `list`, `json`, `yaml`, `text` |
| `--network-id`      | `-n`  | `EEROCTL_NETWORK_ID` | Specify network ID                             |
| `--non-interactive` |       | `EEROCTL_NON_INTERACTIVE` | Never prompt for input; exit `8` where a prompt would appear |
| `--force` / `--yes` | `-y`  | `EEROCTL_FORCE` | Skip confirmation prompts (warnings are still printed) |
| `--quiet`           | `-q`  | `EEROCTL_QUIET` | Suppress non-essential output                   |
| `--no-color`        |       | `EEROCTL_NO_COLOR`, `NO_COLOR` | Disable colored output           |
| `--debug`           |       | `EEROCTL_DEBUG` | Enable debug logging (`eero` logger, redacted)  |
| `--accept-language` |       | `EEROCTL_ACCEPT_LANGUAGE` | `Accept-Language` header sent to the API (default from config, or `en-US`); invalid value → exit `2` |
| `--get-retries N`   |       | `EEROCTL_GET_RETRIES` | Extra **GET-only** retry attempts on transport error / 5xx (default from config, or `0`; `N < 0` → exit `2`; writes are never retried) |
| `--no-legacy-cookie` |      | `EEROCTL_NO_LEGACY_COOKIE` | Do not send the legacy `s=` session cookie alongside the token header |

`--version` prints the eeroctl, Python and eero-api versions. The environment
variables come from Click's `EEROCTL` auto-prefix, so any global flag added later gets
one automatically.

### Option Precedence

Flag > environment variable > `config.json` > built-in default. When the same flag is
specified at multiple levels, the **most specific** (closest to the command) wins:

```bash
# --output json wins (more specific)
eero --output table device list --output json
```

---

## 📊 Exit Codes

| Code | Name | Meaning |
| ---- | ---- | ------- |
| 0    | `SUCCESS` | Success |
| 1    | `GENERIC_ERROR` | Any other error, including an API error with an unmapped status and **rate limiting** (HTTP 429) |
| 2    | `USAGE_ERROR` | Bad arguments or command usage; invalid input rejected by the SDK (bad id/path/URL, invalid `--accept-language`) |
| 3    | `AUTH_REQUIRED` | Not logged in, or the stored session was rejected — from every command |
| 4    | `FORBIDDEN` | The API refused the operation for this account/role (HTTP 403) |
| 5    | `NOT_FOUND` | Wrong id (HTTP 404). Absent optional features are *not* an error — they print "not configured" and exit `0` |
| 6    | `CONFLICT` | HTTP 409 |
| 7    | `TIMEOUT` | Request timed out (timeouts only) |
| 8    | `SAFETY_RAIL` | Confirmation declined or phrase mismatch; `--non-interactive` without `--force` |
| 10   | `PARTIAL_SUCCESS` | Multi-step command with a failed step |
| 11   | `PREMIUM_REQUIRED` | Feature requires an Eero Plus subscription |
| 12   | `FEATURE_UNAVAILABLE` | Feature not available on this device or network (e.g. nightlight on a non-Beacon) |
| 13   | `CLIENT_BLOCKED` | The API refuses this client version — stop, do not retry |
| 14   | `NETWORK_ERROR` | Could not reach the eero API (DNS failure, unreachable host, connection reset) — retry later |

`9` is reserved. Changes from 2.x (auth `1`→`3` in some paths, rate-limit `7`→`1`, new
`13`/`14`) are listed in [Migration → Exit codes](Migration#exit-codes).

Every SDK error message ends with `(error code: <code>)` when the API supplied one.
Response bodies are never printed.

---

## 🛡️ Safety Rails

Every write command is classified by **risk tier** (what kind of confirmation it
needs) and **verification status** (whether the SDK has confirmed the write against a
live network). The classification is a single registry in `safety.py`; the prompt
text comes from it, not from each command.

| Tier | Prompt | Applies to |
| ---- | ------ | ---------- |
| **LOW** | none | Cosmetic and per-device writes: `device rename`, `device type set`, `eero led *` (incl. `cycle`), `eero nightlight *` (incl. `override`), `eero location set`, `profile create`, `network speedtest run`, `troubleshoot diagnostics run`, `network notifications set/mark-read`, `network usage report set` |
| **MEDIUM — disconnects clients** | Y/N: "Proceed with `<command>` (disconnects connected clients) on `<target>`?" | `network rename`, `network guest enable/disable/set`, `network guest password set/clear` — connected (or guest) clients drop and reconnect |
| **MEDIUM — reboots this eero** | Y/N: "… (reboots this eero) …" | `eero reboot <id>`, `eero ports cycle --reboot` — one node restarts |
| **MEDIUM** (other) | Y/N: "Proceed with `<command>` on `<target>`?" | `device block/unblock/pause/unpause`, `profile pause/unpause/rename/devices set/dns allow/block/apps */schedule set/clear/delete`, `network backup enable/disable`, `network support bundle export`, `network security thread/passpoint/proxied-nodes *`, `network ddns *`, `network thread set`, `network forwards create/update/delete`, `network dhcp reservation create/update/delete`, `eero pppoe set`, `eero ports cycle`, `eero port`, `network dns policy allow/block/allow-cnames`, `network members invite create/update/delete/respond`, `network members promote/cancel-pending-admin`, `network power-saving schedules create/update/delete`, `network backup access-points add/update/delete/rearrange/check/discover --start`, `network subnets filters set`, `account name set`, `account email set/verify`, `account phone set/verify`, `account consents`, `account push set` |
| **HIGH — reboots the mesh** | Type `REBOOT`. Before the prompt: "Warning: Applying this change reboots every eero on the network. All clients lose Wi-Fi and internet while the mesh restarts. The outage begins a few minutes after this command returns, not immediately." | `network dns mode set / clear / caching *`, `network security wpa3 / band-steering / upnp / ipv6 *`, `network security mlo set`, `network sqm enable/disable`, `network dhcp set`, `network dhcp connection-mode set`, `network dhcp nat-randomization *`, `network reboot`, `eero updates apply`, `network wpa3 set`, `network security fast-transition enable/disable`, `network power-saving enable/disable`, `network subnets set/delete`, `network wan multistaticip set`, `network wan secondary set`, `device wan-access` |
| **HIGH** (other phrase) | Type the named phrase | `profile delete` → `DELETE`; `network password set/clear` → `DISCONNECT`; `network members remove-admin` → `REMOVE` (removing someone's admin role is irreversible from this command) |

The HIGH prompt reads "⚠ Warning: You are about to `<command>` (`<consequence>`)
`<target>`." followed by "To confirm, type `<PHRASE>` and press Enter:". A mismatch
exits `8` with "Confirmation phrase mismatch. Expected '`<PHRASE>`'."; declining a Y/N
prompt exits `8` with "Operation cancelled by user.".

Rules that apply at every tier:

- `--force` / `-y` skips the prompt. **Warnings are still printed to stderr** — the
  mesh-reboot warning and the unverified-write line above are printed before the
  force check, so a `--force` on a mesh-reboot write still tells you the network is
  about to restart.
- `--non-interactive` without `--force` exits `8` wherever a prompt would appear
  ("Operation '…' on '…' requires confirmation. Use --force to proceed in
  non-interactive mode."), and never hangs. LOW-tier writes never prompt, so they run
  under `--non-interactive` without `--force`.
- `EEROCTL_FORCE=1` behaves like `--force` and additionally prints
  `note: confirmation prompts disabled by EEROCTL_FORCE` on stderr **once per
  invocation** — on every command, reads included, while the variable is set — so a
  forgotten export is visible. `--quiet` suppresses the notice, not the force.
- Toggle commands **read first**: if the setting already has the requested value the
  command exits `0` with "Already configured as requested; no change made. Check with
  `<read command>`." on stderr and writes nothing. `--force` writes anyway. Commands
  with no read to compare against — `network reboot`, `eero updates apply`, the DHCP
  writes (no dedicated GET), forwards/reservations, `network password *`,
  `network thread set`, `eero pppoe/location/ports/port`, `led cycle`,
  `nightlight override`, `troubleshoot diagnostics run` — always write.
- A write is sent **once**. eeroctl never retries a write, and `--get-retries` applies
  to reads only. A 2xx means *accepted*, not *settled*: read-first commands print
  "Write accepted. Verify with `<read command>`." on stderr; the others print their
  own "… set." / "Verify with …" line. A non-2xx envelope prints "Write was not
  applied." and exits `1`.

### Unverified writes

eero-api 8 records which writes its maintainers have exercised against a live
network. For every other write eeroctl prints one line before the prompt (and before
the `--force` check) — *"This write has not been verified against a live network by
the SDK; check the result with `<read command>`."* — and, when the SDK issues the
request, prints `note: unverified write (<operation>); verify with `<read command>``
to stderr, where `<operation>` is the SDK's own description of the call (for example
`set network password for network`). The same note goes into `meta.warnings` for
`json`/`yaml`. `--quiet` suppresses the stderr note (the prompt line and
`meta.warnings` stay); `--debug` passes the SDK's raw `WARNING:eero.api.…` log line
through **instead of** the note. A command that triggers the same operation twice
prints the note once. It does not change the tier. The table of unverified commands
is in [Migration](Migration#unverified-commands).

Writes the SDK has verified (no note): `eero led on/off/brightness`, `device type set`,
`network guest enable/disable/set`, `network guest password set/clear`,
`network speedtest run`, `eero reboot`, `device pause/unpause`, `device rename`,
`device unblock`. Every other write command in the tree above is unverified.

### Scripting Mode

Use `--non-interactive` to fail instead of prompting:

```bash
# Exits with code 8 if confirmation would be needed
eero eero reboot "Living Room" --non-interactive
```

Use `--force` or `--yes` to skip confirmations:

```bash
# Proceeds without prompting; the reboot warning still goes to stderr
eero network sqm disable --force
```

---

## 📤 Output Formats

### Table (default)

Human-readable tabular format with Rich formatting, ideal for interactive use.

```bash
eero network list
eero --output table network list
```

### JSON

Machine-readable JSON with schema envelope for scripting and automation. stdout carries
only the envelope; prompts, warnings and notes go to stderr.

```bash
eero --output json network list
eero -o json network show | jq '.data.name'
```

Each envelope has `schema` (e.g. `eero.auth.status/v2`), `data`, and `meta` with
`warnings` (a list; empty when there is nothing to say). Paginated reads
(`network events`, `network notifications history`) add `meta.next_cursor`.

`json` and `yaml` are the **raw payload**: nothing is masked. Choosing them is your
opt-in to the full API response, so redirect the output somewhere safe.

### Redaction in `table`, `list` and `text`

Commands whose response shape the API does not document (`account premium`,
`network events`, `network entitlements *`, `network backup status`, …) print every
key of the payload through a generic key/value renderer. In `table`, `list` and `text`
that renderer replaces, at any nesting depth, the value of any key whose name contains
one of these substrings (case-insensitive) with the literal `<redacted>`:

- the SDK's own zero-visibility patterns (`eero.logging`, read at import time, so a
  future SDK addition is picked up automatically): `access_token`, `api_key`, `apikey`,
  `auth`, `authorization`, `bearer`, `cookie`, `credential`, `key`, `passwd`,
  `password`, `private`, `refresh_token`, `secret`, `session`, `session_id`, `token`,
  `user_token`
- contact keys added by eeroctl: `email`, `phone`, `sms`

Because matching is by substring, `key` also masks e.g. `public_key` and
`keyring_backend`, and `auth` masks `authenticated`. `network members list` is the one
deliberate exception: its dedicated table shows `email`, since showing who has access
is the command's purpose.

`serial`, `mac` and `url` are **not** masked — they are the CLI's normal identifiers.
Dedicated views (network/device/eero/profile tables) never showed these keys in the
first place.

### YAML

Human-readable structured format, great for configuration and debugging.

```bash
eero --output yaml network list
eero -o yaml device list
```

### Text

Plain text key-value pairs, useful for simple parsing.

```bash
eero --output text network show
eero -o text eero list
```

### List

Simple line-by-line output, grep-friendly.

```bash
eero --output list device list
eero -o list network list
```

---

## 🔗 Related Pages

- [Usage Examples](Usage-Examples) — Practical examples for common tasks
- [Migration](Migration) — Changes in 3.0.0
- [Configuration](Configuration) — Config keys and environment variables
