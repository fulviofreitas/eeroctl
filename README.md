# 🌐 Eero CLI

Command-line interface for managing your Eero mesh Wi-Fi network.

## Features

- **Noun-first command structure** for intuitive navigation
- **Multiple output formats**: table, JSON, YAML, text
- **Safety rails** for destructive operations
- **Shell completion** for bash, zsh, and fish
- **Non-interactive mode** for scripting and automation

## Installation

### Using uv (Recommended)

```bash
git clone https://github.com/fulviofreitas/eero-cli.git
cd eero-cli
uv sync
uv run eero --help
```

### Using pip

```bash
pip install git+https://github.com/fulviofreitas/eero-cli.git
eero --help
```

## Quick Start

```bash
# Authenticate
eero auth login

# List networks
eero network list

# Show network details
eero network show

# List connected devices
eero client list

# List Eero mesh nodes
eero eero list

# Run speed test
eero troubleshoot speedtest --force
```

## Command Structure

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
│   ├── dns          # DNS settings
│   ├── security     # Security settings
│   ├── guest        # Guest network
│   └── ...
│
├── eero             # Mesh node management
│   ├── list         # List all Eero nodes
│   ├── show <id>    # Show Eero details
│   ├── reboot <id>  # Reboot an Eero
│   ├── led          # LED settings
│   └── ...
│
├── client           # Connected device management
│   ├── list         # List all clients
│   ├── show <id>    # Show client details
│   ├── block <id>   # Block a device
│   └── ...
│
├── profile          # User profile management
│   ├── list         # List all profiles
│   ├── pause <id>   # Pause internet access
│   └── ...
│
├── activity         # Activity data (Eero Plus)
├── troubleshoot     # Troubleshooting tools
└── completion       # Shell completion
```

## Global Flags

Global flags must be placed **before** the subcommand:

```bash
# ✅ Correct
eero --output json network list

# ❌ Wrong
eero network list --output json
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

## Output Formats

```bash
# Human-readable table (default)
eero network list

# JSON for scripting
eero --output json network list | jq '.data[].name'

# YAML for debugging
eero --output yaml client list

# Plain text key-value pairs
eero --output text network show
```

## Safety Rails

Destructive operations require confirmation:

```bash
# Requires typing "REBOOT" to confirm
eero eero reboot "Living Room"

# Skip confirmation with --force
eero eero reboot "Living Room" --force

# Fail instead of prompting (for scripts)
eero --non-interactive eero reboot "Living Room"
```

## Dependencies

This CLI uses [eero-client](https://github.com/fulviofreitas/eero-client) for API communication.

## Documentation

See the [wiki](https://github.com/fulviofreitas/eero-cli/wiki) for complete documentation:

- [CLI Reference](https://github.com/fulviofreitas/eero-cli/wiki/CLI-Reference)
- [Usage Examples](https://github.com/fulviofreitas/eero-cli/wiki/Usage-Examples)
- [Configuration](https://github.com/fulviofreitas/eero-cli/wiki/Configuration)

## License

MIT License - see [LICENSE](LICENSE) for details.
