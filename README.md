# 🌐 eeroctl

[![PyPI](https://img.shields.io/pypi/v/eeroctl.svg)](https://pypi.org/project/eeroctl/)
[![Homebrew](https://img.shields.io/badge/homebrew-eeroctl-orange)](https://github.com/fulviofreitas/homebrew-eeroctl)

> Manage your Eero mesh Wi-Fi from the terminal ✨

## ⚡ Features

- 🧭 **Intuitive commands** — noun-first structure (`eero network list`)
- 📊 **Multiple formats** — table, JSON, YAML, text
- 🛡️ **Safety rails** — confirmation for destructive actions
- 🔧 **Script-friendly** — non-interactive mode + machine-readable output
- 🐚 **Shell completion** — bash, zsh, fish

## 📦 Install

### Homebrew

```bash
brew install fulviofreitas/eeroctl/eeroctl
```

### PyPI

```bash
pip install eeroctl
```

<details>
<summary>From source</summary>

```bash
git clone https://github.com/fulviofreitas/eeroctl.git
cd eeroctl
uv sync && source .venv/bin/activate
```

Or with pip:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

</details>

## 🚀 Quick Start

```bash
eero auth login           # Authenticate
eero network list         # List networks
eero device list          # Connected devices
eero eero list            # Mesh nodes
eero troubleshoot speedtest --force
```

> **Tip:** Both `eero` and `eeroctl` commands are available and work identically.

## 📖 Documentation

Full documentation lives in the **[Wiki](https://github.com/fulviofreitas/eeroctl/wiki)**:

| 📚 Guide | Description |
|----------|-------------|
| [CLI Reference](https://github.com/fulviofreitas/eeroctl/wiki/CLI-Reference) | Commands, flags & exit codes |
| [Usage Examples](https://github.com/fulviofreitas/eeroctl/wiki/Usage-Examples) | Practical examples |
| [Configuration](https://github.com/fulviofreitas/eeroctl/wiki/Configuration) | Auth storage & env vars |
| [Troubleshooting](https://github.com/fulviofreitas/eeroctl/wiki/Troubleshooting) | Common issues |

## 🔗 Dependencies

Built on [eero-api](https://github.com/fulviofreitas/eero-api) for API communication.

## 📄 License

MIT — see [LICENSE](LICENSE)

---

<div align="center">

## 📊 Repository Metrics

![Repository Metrics](./metrics.repository.svg)

</div>
