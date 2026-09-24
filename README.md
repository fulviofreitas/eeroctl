<div align="center">

# ⌨️ eeroctl

**Manage your Eero mesh Wi-Fi from the terminal**

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-3776ab?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![PyPI](https://img.shields.io/pypi/v/eeroctl?style=for-the-badge&logo=pypi&logoColor=white)](https://pypi.org/project/eeroctl/)
[![Homebrew](https://img.shields.io/badge/homebrew-eeroctl-FBB040?style=for-the-badge&logo=homebrew&logoColor=white)](https://github.com/fulviofreitas/homebrew-eeroctl)
[![License](https://img.shields.io/badge/license-MIT-22c55e?style=for-the-badge)](LICENSE)

---

_A powerful command-line interface for Eero mesh network management._  
_Intuitive commands, multiple output formats, and shell completion._

[Get Started](#-quick-start) · [Documentation](#-documentation) · [Install](#-install) · [License](#-license)

</div>

---

## ⚡ Features

- 🧭 **Intuitive commands** — noun-first structure (`eero network list`)
- 📊 **Multiple formats** — table, list, JSON, YAML, text
- 🛡️ **Safety rails** — Y/N prompts for disruptive writes, a typed `REBOOT` phrase for anything that restarts the mesh, and an explicit note on writes the SDK has not verified
- 🔧 **Script-friendly** — non-interactive mode, fixed exit codes, `EEROCTL_*` environment variables, `EEROCTL_SESSION_TOKEN` for CI
- 🐚 **Shell completion** — bash, zsh, fish

> **Upgrading from 2.x?** 3.0.0 changes exit codes, `auth status` output, environment-variable names and credential storage. See the [Migration guide](https://github.com/fulviofreitas/eeroctl/wiki/Migration).

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
eero network speedtest run && sleep 60 && eero network speedtest show
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
| [Migration](https://github.com/fulviofreitas/eeroctl/wiki/Migration) | Upgrading to 3.0.0 |

## 🔗 Dependencies

Requires [eero-api](https://github.com/fulviofreitas/eero-api) **8.0.3** (pinned exactly) and Python 3.12+.

## 📄 License

MIT — see [LICENSE](LICENSE)

---

<div align="center">

## 📊 Repository Metrics

![Repository Metrics](./metrics.repository.svg)

</div>
