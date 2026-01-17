# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 1.0.0 (2026-01-17)

### ⚠ BREAKING CHANGES

* Python 3.10 and 3.11 are no longer supported

- Update requires-python to >=3.12
- Update classifiers to 3.12, 3.13, 3.14
- Update mypy python_version to 3.12
- Update ruff/black target-version to py312

### ✨ Features

* add Bandit security scanning workflow 🔒 ([cb13ae2](https://github.com/fulviofreitas/eero-cli/commit/cb13ae2e94a80ba042a90ff8ec66d33e03383a33))
* **ci:** add Renovate for automated eero-client dependency updates ([067e9ca](https://github.com/fulviofreitas/eero-cli/commit/067e9ca4b2665cd6029abf9af22557a65b4e857f))
* **ci:** migrate workflows to use reusable actions from eero-client ([c23c961](https://github.com/fulviofreitas/eero-cli/commit/c23c961f0e2bec3fb1ddd4b10b6f82a2d417e11f))
* require Python 3.12 minimum ([1839deb](https://github.com/fulviofreitas/eero-cli/commit/1839deb0032984e471e5cda409fef2107aedf1ea))

### 🐛 Bug Fixes

* auth flow improvements and client list output consistency ([f9d8379](https://github.com/fulviofreitas/eero-cli/commit/f9d8379063ce5b485a7571e7e781bfe19e4b59ea))
* **ci:** correct matrix syntax for macOS test jobs ([5185f99](https://github.com/fulviofreitas/eero-cli/commit/5185f99f0f997f908951ad51724f9cb0d96d07a3))
* **ci:** properly report type-check and security job status ([b270dc0](https://github.com/fulviofreitas/eero-cli/commit/b270dc06d10ac1bf82ffb42c57520c769fd1d31a))
* **ci:** require ALL jobs to pass for CI Success ([ad85a5d](https://github.com/fulviofreitas/eero-cli/commit/ad85a5d2fbd20b8a687568ca8bc12cc8fd6126ca))
* **ci:** use master branch consistently in all workflows ([5fa591f](https://github.com/fulviofreitas/eero-cli/commit/5fa591f353fe3f0736d4271dbbe6a7083c3a6fc9))
* consistent columns between list and table output formats ([336bfad](https://github.com/fulviofreitas/eero-cli/commit/336bfad098a210520a564181b1f5e57f2e745230))
* remove unused variable and import (ruff F841, F401) ([db81e1a](https://github.com/fulviofreitas/eero-cli/commit/db81e1ae112a438aa07b206fadb3ed45c3eebac7))
* suppress status messages for parseable output formats ([0e054cc](https://github.com/fulviofreitas/eero-cli/commit/0e054cc59572f19a4aae40caafabcfcf3fc8345b))
* use lowercase values for Bandit confidence/severity levels ([f8ace21](https://github.com/fulviofreitas/eero-cli/commit/f8ace218602cfd3861a274856cabfed84543d164))

### 📚 Documentation

* improve installation instructions with venv details ([a2b5b4a](https://github.com/fulviofreitas/eero-cli/commit/a2b5b4a053d510aedb882838bf39318bb5497053))
* modernize README with emojis and wiki links ([c48f546](https://github.com/fulviofreitas/eero-cli/commit/c48f546572b97ff7c1e07e8c582d2afa0fa569fe))
* simplify main CLI help message ([c2ae74f](https://github.com/fulviofreitas/eero-cli/commit/c2ae74f913bd0d303a880c7643c11be122e95e3d))

### ♻️ Refactoring

* **auth:** improve auth status command with accurate session info ([c0531f6](https://github.com/fulviofreitas/eero-cli/commit/c0531f6beed70763e10b7d32da490e96fc680b78))
* **ci:** standardize pipeline chain format ([36f7f96](https://github.com/fulviofreitas/eero-cli/commit/36f7f9646f3e9ab93355e63d62042b1bb934c8f9))
* split network.py and eero.py into modular packages ([f89422d](https://github.com/fulviofreitas/eero-cli/commit/f89422d7127760d5564c469c1eb6d3d80007fcce))
* update repository_dispatch event type name ([62b7dbe](https://github.com/fulviofreitas/eero-cli/commit/62b7dbeb97ab6cb34703db49eb94f9838736caf3))
