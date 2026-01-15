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
```

---

## DNS & Security

```bash
# Show DNS settings
eero network dns show

# Set DNS to Cloudflare
eero network dns mode cloudflare --force

# Set custom DNS servers
eero network dns mode custom --servers 1.1.1.1 --servers 8.8.8.8

# Enable WPA3
eero network security wpa3 enable --force

# Disable UPnP
eero network security upnp disable --force
```

---

## Guest Network

```bash
# Enable guest network
eero network guest enable --name "Guest WiFi" --password "welcome123"

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

# Reboot an Eero (requires typing REBOOT to confirm)
eero eero reboot "Living Room"

# Turn off LED
eero eero led off "Living Room" --force

# Set nightlight schedule (Beacon only)
eero eero nightlight schedule "Bedroom" --on-time 22:00 --off-time 06:00
```

---

## Client Devices

```bash
# List all connected clients
eero client list

# Show client as JSON
eero --output json client show "iPhone"

# Rename a client
eero client rename "00:11:22:33:44:55" --name "Work Laptop"

# Block a device
eero client block "Smart TV" --force

# Prioritize a device for 30 minutes
eero client priority on "Gaming PC" --minutes 30
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
```

---

## Troubleshooting

```bash
# Check network health
eero troubleshoot status

# Run speed test
eero troubleshoot speedtest --force

# Run diagnostics
eero troubleshoot diagnostics

# Restart specific Eero
eero troubleshoot restart --eero "Living Room" --force

# Restart all Eeros (requires typing RESTART ALL)
eero troubleshoot restart --all
```

---

## Scripting & Automation

**Note:** Global flags like `--output` must be placed before the subcommand.

```bash
# JSON output for parsing
eero --output json network show | jq '.data.name'

# YAML output (human-readable structured format)
eero --output yaml network list

# Non-interactive mode (fails if confirmation needed)
eero --non-interactive network rename --name "NewSSID"
# Exit code 8: safety rail triggered

# Force mode skips confirmations
eero --force network rename --name "NewSSID"
```

### Bash Script Example

```bash
#!/bin/bash
set -e

# Get network name
NETWORK=$(eero --output json network show | jq -r '.data.name')
echo "Managing network: $NETWORK"

# List offline clients
eero --output json client list | jq -r '.data[] | select(.connected == false) | .display_name'
```

### Using with cron

```bash
# Run speed test daily at 3am and log results
0 3 * * * /usr/local/bin/eero --output json troubleshoot speedtest --force >> /var/log/eero-speedtest.json
```

---

## 🔗 Related Pages

- [CLI Reference](CLI-Reference) — Complete command structure and flags


