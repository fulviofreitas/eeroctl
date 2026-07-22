# 📋 CLI Reference

Complete command reference for the Eero CLI.

---

## Command Structure

The CLI uses a **noun-first** command structure for consistency and discoverability.

```
eero
├── auth             # Authentication management
│   ├── login        # Login to Eero account
│   ├── logout       # Logout from account
│   ├── clear        # Clear stored credentials
│   └── status       # Check authentication status
│
├── network          # Network management
│   ├── list         # List all networks
│   ├── use <id>     # Set preferred network
│   ├── show         # Show network details
│   ├── rename       # Rename network (SSID)
│   ├── premium      # Check Eero Plus status
│   ├── dns          # DNS settings
│   │   ├── show
│   │   ├── mode <auto|cloudflare|google|opendns|custom>
│   │   └── caching <enable|disable>
│   ├── security     # Security settings
│   │   ├── show
│   │   ├── wpa3 <enable|disable>
│   │   ├── band-steering <enable|disable>
│   │   ├── upnp <enable|disable>
│   │   ├── ipv6 <enable|disable>
│   │   └── thread <enable|disable>
│   ├── sqm          # Smart Queue Management
│   │   ├── show
│   │   ├── enable
│   │   ├── disable
│   │   └── set --upload <mbps> --download <mbps>
│   ├── guest        # Guest network
│   │   ├── show
│   │   ├── enable
│   │   ├── disable
│   │   └── set --name <name> --password <pass>
│   ├── speedtest    # Speed testing
│   │   ├── run
│   │   └── show
│   └── backup       # Backup network (Eero Plus)
│       ├── show
│       ├── enable
│       ├── disable
│       └── status
│
├── eero             # Mesh node management
│   ├── list         # List all Eero nodes
│   ├── show <id>    # Show Eero details
│   ├── reboot <id>  # Reboot an Eero
│   ├── led          # LED settings
│   │   ├── show
│   │   ├── on
│   │   ├── off
│   │   └── brightness <0-100>
│   ├── nightlight   # Nightlight (Beacon only)
│   │   ├── show
│   │   ├── on
│   │   ├── off
│   │   ├── brightness <0-100>
│   │   └── schedule --on-time <HH:MM> --off-time <HH:MM>
│   └── updates      # Software updates
│       ├── show
│       └── check
│
├── device           # Connected device management
│   ├── list         # List all devices
│   ├── show <id>    # Show device details
│   ├── rename <id> --name <name>
│   ├── block <id>
│   ├── unblock <id>
│   ├── pause <id>
│   └── unpause <id>
│
├── profile          # User profile management
│   ├── list         # List all profiles
│   ├── show <id>    # Show profile details
│   ├── pause <id>   # Pause internet access
│   ├── unpause <id> # Resume internet access
│   ├── apps         # Blocked applications (Eero Plus)
│   │   ├── list
│   │   ├── block <app>...
│   │   └── unblock <app>...
│   └── schedule     # Internet schedule
│       ├── show
│       └── set
│
├── activity         # Activity data (Eero Plus)
│   ├── history      # Activity history (requires --start and --end)
│   └── categories   # Blocked-traffic categories (requires --start and --end)
│
├── troubleshoot     # Troubleshooting tools
│   ├── status       # Network health status
│   ├── speedtest    # Run speed test
│   ├── diagnostics  # Run diagnostics
│   └── restart      # Restart network/Eeros
│
└── completion       # Shell completion
    ├── bash
    ├── zsh
    └── fish
```

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

| Flag                | Short | Description                                        |
| ------------------- | ----- | -------------------------------------------------- |
| `--output`          | `-o`  | Output format: `table`, `list`, `json`, `yaml`, `text` |
| `--network-id`      | `-n`  | Specify network ID                                 |
| `--non-interactive` |       | Never prompt for input                             |
| `--force` / `--yes` | `-y`  | Skip confirmation prompts                          |
| `--quiet`           | `-q`  | Suppress non-essential output                      |
| `--no-color`        |       | Disable colored output                             |
| `--debug`           |       | Enable debug logging                               |

### Option Precedence

When the same option is specified at multiple levels, the **most specific** (closest to the command) takes precedence:

```bash
# --output json wins (more specific)
eero --output table device list --output json
```

---

## 📊 Exit Codes

| Code | Meaning                                     |
| ---- | ------------------------------------------- |
| 0    | Success                                     |
| 1    | Generic error                               |
| 2    | Usage/argument error                        |
| 3    | Authentication required                     |
| 4    | Forbidden (insufficient permissions)        |
| 5    | Resource not found                          |
| 6    | Conflict (resource already exists)          |
| 7    | Timeout                                     |
| 8    | Safety rail triggered (confirmation needed) |
| 10   | Partial success (some operations failed)    |

---

## 🛡️ Safety Rails

Certain disruptive actions require confirmation:

- **Rebooting Eeros:** Type `REBOOT` to confirm
- **Restarting all Eeros:** Type `RESTART ALL` to confirm
- **Renaming networks:** Prompts for confirmation (use `--force` to skip)
- **Blocking devices:** Prompts for confirmation (use `--force` to skip)

### Scripting Mode

Use `--non-interactive` to fail instead of prompting:

```bash
# Exits with code 8 if confirmation would be needed
eero eero reboot "Living Room" --non-interactive
```

Use `--force` or `--yes` to skip confirmations:

```bash
# Proceeds without prompting
eero eero reboot "Living Room" --force
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

Machine-readable JSON with schema envelope for scripting and automation.

```bash
eero --output json network list
eero -o json network show | jq '.data.name'
```

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
- [Legacy Commands](Legacy-Commands) — Mapping from deprecated commands
