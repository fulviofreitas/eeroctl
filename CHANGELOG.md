# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.2](https://github.com/fulviofreitas/eeroctl/compare/v2.0.1...v2.0.2) (2026-01-23)

### 🐛 Bug Fixes

* **renovate:** move eero-api rule to end for precedence ([6486c97](https://github.com/fulviofreitas/eeroctl/commit/6486c974cfdeb98861e3913402835e9dcc425bfa))

## [2.0.1](https://github.com/fulviofreitas/eeroctl/compare/v2.0.0...v2.0.1) (2026-01-23)

### 🐛 Bug Fixes

* **renovate:** disable automerge for eero-api, require review ([d10eca7](https://github.com/fulviofreitas/eeroctl/commit/d10eca7ddf8444cebed614dbb050f6130265aca0))

## [2.0.0](https://github.com/fulviofreitas/eeroctl/compare/v1.8.0...v2.0.0) (2026-01-23)

### ⚠ BREAKING CHANGES

* migrate to eero-api v2.0.0 raw response architecture
* All command modules now use raw API responses
with the transformation layer.

Updated commands:
- device.py: Uses extract_devices, normalize_device
- eero/base.py: Uses extract_eeros, normalize_eero
- eero/led.py, nightlight.py, updates.py: Dict access for eero data
- profile.py: Uses extract_profiles, normalize_profile
- activity.py: Uses extract_data for activity responses
- troubleshoot.py: Uses transformers for network/device data
- network/guest.py, speedtest.py, dhcp.py: Dict access patterns

Updated transformers/__init__.py:
- Added safe_get and normalize_network to __all__

All 383 tests passing.
* Updates eeroctl to work with eero-api v2.0.0 which
returns raw JSON responses instead of Pydantic models.

Changes:
- Add transformers package with base utilities and entity transformers
  - base.py: extract_data, extract_list, extract_id_from_url, safe_get
  - network.py, device.py, eero.py, profile.py: entity-specific transforms
- Update const.py with local enum definitions (moved from eero-api)
- Update formatting modules to use dict access instead of model attrs
- Update network commands to use new transformation layer
- Update tests to use raw API response fixtures

This change is part of Phase 2 of the raw-response-migration-plan.

### ✨ Features

* add transformation layer for eero-api raw responses ([4d27530](https://github.com/fulviofreitas/eeroctl/commit/4d27530bae1851f1a304a71f24ef19336944d05d))
* **ci:** standardize renovate workflow with reusable actions ([0093415](https://github.com/fulviofreitas/eeroctl/commit/0093415fe6a31b3b90c465dc7f6a7a72d676cbaa))
* complete Phase 2 - update all commands for raw responses ([c071d17](https://github.com/fulviofreitas/eeroctl/commit/c071d1708307f0f0dccbb809a06c6be0f4428b87))
* migrate to eero-api v2.0.0 raw response architecture ([cfffccc](https://github.com/fulviofreitas/eeroctl/commit/cfffccc9a939d9ea86bec8d09fffbf91d6079b94))
* **renovate:** treat eero-api as feature release for minor version bumps ([2c35b83](https://github.com/fulviofreitas/eeroctl/commit/2c35b83d925855dbeca1fdd86c8a7a1d8ea63307))

### 🐛 Bug Fixes

* **renovate:** ensure consistent config matching all Python managers ([d29cfa4](https://github.com/fulviofreitas/eeroctl/commit/d29cfa42337767cfcc99c97dc02192bdb0917217))
* **renovate:** restore critical and needs-review labels for eero packages ([96b7a15](https://github.com/fulviofreitas/eeroctl/commit/96b7a157df4295c15b3ed5e9f5d1abdef899ea78))
* **renovate:** wait for PyPI indexing before running Renovate ([d8792c4](https://github.com/fulviofreitas/eeroctl/commit/d8792c4d307f588129ae29c6af6bb10362abc336))
* resolve mypy type errors for raw response migration ([b7830c5](https://github.com/fulviofreitas/eeroctl/commit/b7830c5c13b8626ba146d24e51c2a32f93f5b7b0))
* update test_status_json_output mock to use raw response ([fd72340](https://github.com/fulviofreitas/eeroctl/commit/fd72340dce8817fd8a3e1bedb201cc944425e556))

## [1.8.0](https://github.com/fulviofreitas/eeroctl/compare/v1.7.1...v1.8.0) (2026-01-21)

### ✨ Features

* trigger minor release ([c05c3d2](https://github.com/fulviofreitas/eeroctl/commit/c05c3d214c511f9185d163528e370122cad59c3a))

## [1.7.1](https://github.com/fulviofreitas/eeroctl/compare/v1.7.0...v1.7.1) (2026-01-21)

### 🐛 Bug Fixes

* trigger release ([05294c2](https://github.com/fulviofreitas/eeroctl/commit/05294c2d9da51a92a299a5a86b3ad32900dc8770))

### ♻️ Refactoring

* **formatting:** split God Object into modular package ([a4e082b](https://github.com/fulviofreitas/eeroctl/commit/a4e082bc668c24456fe4d04528f9c55d7b7f4976))

## [1.7.0](https://github.com/fulviofreitas/eeroctl/compare/v1.6.0...v1.7.0) (2026-01-21)

### ✨ Features

* **formatting:** enrich device show output with detailed panels ([b46dcb0](https://github.com/fulviofreitas/eeroctl/commit/b46dcb04782d42dc3ad670f75645f7d808814ba7))
* **formatting:** enrich eero show output with detailed panels ([53a39a9](https://github.com/fulviofreitas/eeroctl/commit/53a39a999731111c27d78bafa28cbdf80b05893d))
* **formatting:** enrich network show output with detailed panels ([caa895b](https://github.com/fulviofreitas/eeroctl/commit/caa895b4e3a71ad3ce7b087197fd8c9735e5a59d))
* **formatting:** enrich profile show output with detailed panels ([526afa9](https://github.com/fulviofreitas/eeroctl/commit/526afa9f136f71c459f2668a7724ab6db7f719b0))

## [1.6.0](https://github.com/fulviofreitas/eeroctl/compare/v1.5.0...v1.6.0) (2026-01-21)

### ✨ Features

* **cli:** add eeroctl command alias ([58a9503](https://github.com/fulviofreitas/eeroctl/commit/58a9503ecfc7d409a55f6baa79eaf59c2b7039eb))

### 🐛 Bug Fixes

* **cli:** display network status value instead of enum representation ([f4be157](https://github.com/fulviofreitas/eeroctl/commit/f4be157a39af790e317a90a28184f9ee3f5b347a))

### ♻️ Refactoring

* **formatting:** simplify format_network_status for clean values ([f7d51f7](https://github.com/fulviofreitas/eeroctl/commit/f7d51f74bb45989ad747e6bd28e7f18f4edd674b))

## [1.5.0](https://github.com/fulviofreitas/eeroctl/compare/v1.4.0...v1.5.0) (2026-01-21)

### ✨ Features

* **cli:** add display option decorators for debug/quiet/color (Phase 5) ([c1783a5](https://github.com/fulviofreitas/eeroctl/commit/c1783a5a642518704303db0783cf298ceebf8dab))
* **cli:** add shared option decorators for flexible option placement ([ef9b2df](https://github.com/fulviofreitas/eeroctl/commit/ef9b2df07129c5804a6322e9d105ea08b81ff6e3))
* **cli:** apply --force option to destructive commands (Phase 4) ([2e12dcb](https://github.com/fulviofreitas/eeroctl/commit/2e12dcbccecb4055f0cea39a31a9d54fe7b83fe5))
* **cli:** apply --network-id option to network-dependent commands (Phase 3) ([66572b9](https://github.com/fulviofreitas/eeroctl/commit/66572b99c488d4ca7df7918830e688f32e8151b1))
* **cli:** apply --output option to list/show commands (Phase 2) ([ddb2a2d](https://github.com/fulviofreitas/eeroctl/commit/ddb2a2d1e0d03ff7ec41fe966402ceb8dc347b33))

### 📚 Documentation

* update documentation for flexible option placement (Phase 6) ([164f9b3](https://github.com/fulviofreitas/eeroctl/commit/164f9b3ef0458aed1746b72dc309d6e80d21dda9))

## [Unreleased]

### ♻️ Refactoring

* **formatting:** split God Object `formatting.py` (2,810 lines) into modular package
  * New package structure: `src/eeroctl/formatting/`
  * `base.py` - Shared utilities (console, field helpers, status formatters)
  * `network.py` - Network formatting (659 lines)
  * `eero.py` - Eero device formatting (591 lines)
  * `device.py` - Connected device formatting (430 lines)
  * `profile.py` - Profile formatting (443 lines)
  * `misc.py` - Speed test and blacklist formatting (87 lines)
  * Backward compatible via `__init__.py` re-exports

### 🐛 Bug Fixes

* **auth:** add debug logging to exception handlers (resolves Bandit B110 warnings)

### 🔧 Maintenance

* **dev:** add pre-commit hooks configuration (`.pre-commit-config.yaml`)

### ✨ Features

* **cli:** flexible option placement - options can now appear anywhere in commands
  * `--output/-o` can be placed after subcommands: `eero device list --output json`
  * `--network-id/-n` works at any level: `eero eero show "Living Room" -n abc123`
  * `--force/-y` can be placed after subcommands: `eero device block "iPhone" --force`
  * New display options: `--debug`, `--quiet/-q`, `--no-color` work per-command
* **cli:** add shared option decorators for reusable option definitions
  * `output_option`, `network_option`, `force_option`, `non_interactive_option`
  * `debug_option`, `quiet_option`, `no_color_option`
  * Combined decorators: `common_options`, `safety_options`, `display_options`, `all_options`

### 🧪 Tests

* add 54 tests for option decorators and `apply_options` helper

### 🧹 Maintenance

* remove legacy `eero_cli/` package (orphaned since v1.0.0 rename to eeroctl)

## [1.4.0](https://github.com/fulviofreitas/eeroctl/compare/v1.3.1...v1.4.0) (2026-01-20)

### ✨ Features

* switch eero-api to PyPI and enhance --version output ([fb75814](https://github.com/fulviofreitas/eeroctl/commit/fb7581424b43e2bcd8c53fa447f8f1cdf5730af5))

## [1.3.1](https://github.com/fulviofreitas/eeroctl/compare/v1.3.0...v1.3.1) (2026-01-20)

### 🐛 Bug Fixes

* **ci:** add prTitle config for squash merge commitlint compliance ([dd6c890](https://github.com/fulviofreitas/eeroctl/commit/dd6c890442d459da8e4570be3302ebbcee570636))

## [1.3.0](https://github.com/fulviofreitas/eeroctl/compare/v1.2.2...v1.3.0) (2026-01-20)

### ✨ Features

* add version_info tuple for programmatic version access ([7de5a37](https://github.com/fulviofreitas/eeroctl/commit/7de5a37e86c5e11cf5b6b2f18da4346c6dbe002a))

## [1.2.2](https://github.com/fulviofreitas/eeroctl/compare/v1.2.1...v1.2.2) (2026-01-20)

### 🐛 Bug Fixes

* **ci:** prevent commitlint body-max-line-length failures on Renovate PRs ([422938f](https://github.com/fulviofreitas/eeroctl/commit/422938fd328b794f142b97fd78b0b3ba201b22ea))

## [1.2.1](https://github.com/fulviofreitas/eeroctl/compare/v1.2.0...v1.2.1) (2026-01-19)

### 🐛 Bug Fixes

* update PyPI badge to include SVG format ([03040ad](https://github.com/fulviofreitas/eeroctl/commit/03040ad6d4560b1fc3bdb98a2e2ae049f68c2605))

## [1.2.0](https://github.com/fulviofreitas/eeroctl/compare/v1.1.1...v1.2.0) (2026-01-19)

### ✨ Features

* add get_version() helper function ([26c11cf](https://github.com/fulviofreitas/eeroctl/commit/26c11cf28d4a9ad7e674305da5d52b2a427f2f64))

## [1.1.1](https://github.com/fulviofreitas/eeroctl/compare/v1.1.0...v1.1.1) (2026-01-19)

### 🐛 Bug Fixes

* **release:** add full build steps to PyPI publish jobs ([eb6a844](https://github.com/fulviofreitas/eeroctl/commit/eb6a844c021107260ddac57444e007db375b2b96))

## [1.1.0](https://github.com/fulviofreitas/eeroctl/compare/v1.0.5...v1.1.0) (2026-01-19)

### ✨ Features

* add PyPI and Homebrew publishing to release workflow ([4572158](https://github.com/fulviofreitas/eeroctl/commit/4572158bf27b11b70cea7d2f900834d2c5032634))

## [1.0.5](https://github.com/fulviofreitas/eeroctl/compare/v1.0.4...v1.0.5) (2026-01-19)

### 🐛 Bug Fixes

* **deps:** update eero-api to v1.3.1 with type compatibility fixes ([3997e9d](https://github.com/fulviofreitas/eeroctl/commit/3997e9dd6c4c983d9a030bffaa770526d4eb6df8))

## [1.0.4](https://github.com/fulviofreitas/eeroctl/compare/v1.0.3...v1.0.4) (2026-01-19)

### 🐛 Bug Fixes

* **ci:** remove invalid workflows permission from auto-merge ([489276d](https://github.com/fulviofreitas/eeroctl/commit/489276d8d106145ceba638ada28402c0ed2028ce))

## [1.0.3](https://github.com/fulviofreitas/eeroctl/compare/v1.0.2...v1.0.3) (2026-01-18)

### 🐛 Bug Fixes

* **ci:** use GitHub App for auto-merge to support workflow file changes ([3e7b679](https://github.com/fulviofreitas/eeroctl/commit/3e7b679f3a828f266ad8ce137703ed88ba82fa8b))

### ♻️ Refactoring

* rename eero-client to eero-api in GitHub workflows ([0f84d36](https://github.com/fulviofreitas/eeroctl/commit/0f84d3668429d6e014ae23424c5c74083c923697))

## [1.0.2](https://github.com/fulviofreitas/eeroctl/compare/v1.0.1...v1.0.2) (2026-01-18)

### 🐛 Bug Fixes

* correct repository_dispatch event type for eero-api ([a8a0e3d](https://github.com/fulviofreitas/eeroctl/commit/a8a0e3dadfe9520ae9f0de528b39f6d29fd8c40c))

## [1.0.1](https://github.com/fulviofreitas/eeroctl/compare/v1.0.0...v1.0.1) (2026-01-18)

### 🐛 Bug Fixes

* correct Renovate config validation errors ([114eb19](https://github.com/fulviofreitas/eeroctl/commit/114eb1918b4bef17f3a75ef12a269d29ce2ab9d8))

## 1.0.0 (2026-01-18)

### ⚠ BREAKING CHANGES

* Package import path changed from eero_cli to eeroctl
* Python 3.10 and 3.11 are no longer supported

- Update requires-python to >=3.12
- Update classifiers to 3.12, 3.13, 3.14
- Update mypy python_version to 3.12
- Update ruff/black target-version to py312

### ✨ Features

* add __version__ to package ([27e1c04](https://github.com/fulviofreitas/eeroctl/commit/27e1c04bfa47709eb67340ae81e9219a50385223))
* add Bandit security scanning workflow 🔒 ([cb13ae2](https://github.com/fulviofreitas/eeroctl/commit/cb13ae2e94a80ba042a90ff8ec66d33e03383a33))
* **ci:** add Renovate for automated eero-client dependency updates ([067e9ca](https://github.com/fulviofreitas/eeroctl/commit/067e9ca4b2665cd6029abf9af22557a65b4e857f))
* **ci:** migrate workflows to use reusable actions from eero-client ([c23c961](https://github.com/fulviofreitas/eeroctl/commit/c23c961f0e2bec3fb1ddd4b10b6f82a2d417e11f))
* require Python 3.12 minimum ([1839deb](https://github.com/fulviofreitas/eeroctl/commit/1839deb0032984e471e5cda409fef2107aedf1ea))
* **security:** migrate from Bandit to Semgrep ([c1085d1](https://github.com/fulviofreitas/eeroctl/commit/c1085d197d7775081d476506b2e577108e20d575))

### 🐛 Bug Fixes

* auth flow improvements and client list output consistency ([f9d8379](https://github.com/fulviofreitas/eeroctl/commit/f9d8379063ce5b485a7571e7e781bfe19e4b59ea))
* **ci:** correct matrix syntax for macOS test jobs ([5185f99](https://github.com/fulviofreitas/eeroctl/commit/5185f99f0f997f908951ad51724f9cb0d96d07a3))
* **ci:** properly report type-check and security job status ([b270dc0](https://github.com/fulviofreitas/eeroctl/commit/b270dc06d10ac1bf82ffb42c57520c769fd1d31a))
* **ci:** require ALL jobs to pass for CI Success ([ad85a5d](https://github.com/fulviofreitas/eeroctl/commit/ad85a5d2fbd20b8a687568ca8bc12cc8fd6126ca))
* **ci:** use master branch consistently in all workflows ([5fa591f](https://github.com/fulviofreitas/eeroctl/commit/5fa591f353fe3f0736d4271dbbe6a7083c3a6fc9))
* consistent columns between list and table output formats ([336bfad](https://github.com/fulviofreitas/eeroctl/commit/336bfad098a210520a564181b1f5e57f2e745230))
* improve concurrency group for PR workflows ([c38d6b0](https://github.com/fulviofreitas/eeroctl/commit/c38d6b0066300b3a640d1386e57f4ccf7882f649))
* improve Renovate and auto-merge configuration ([5cc6b0e](https://github.com/fulviofreitas/eeroctl/commit/5cc6b0ebcf3658bd8d98d9eca6f30f16e34a9945))
* remove unused variable and import (ruff F841, F401) ([db81e1a](https://github.com/fulviofreitas/eeroctl/commit/db81e1ae112a438aa07b206fadb3ed45c3eebac7))
* suppress status messages for parseable output formats ([0e054cc](https://github.com/fulviofreitas/eeroctl/commit/0e054cc59572f19a4aae40caafabcfcf3fc8345b))
* use lowercase values for Bandit confidence/severity levels ([f8ace21](https://github.com/fulviofreitas/eeroctl/commit/f8ace218602cfd3861a274856cabfed84543d164))

### 📚 Documentation

* improve installation instructions with venv details ([a2b5b4a](https://github.com/fulviofreitas/eeroctl/commit/a2b5b4a053d510aedb882838bf39318bb5497053))
* modernize README with emojis and wiki links ([c48f546](https://github.com/fulviofreitas/eeroctl/commit/c48f546572b97ff7c1e07e8c582d2afa0fa569fe))
* simplify main CLI help message ([c2ae74f](https://github.com/fulviofreitas/eeroctl/commit/c2ae74f913bd0d303a880c7643c11be122e95e3d))

### ♻️ Refactoring

* **auth:** improve auth status command with accurate session info ([c0531f6](https://github.com/fulviofreitas/eeroctl/commit/c0531f6beed70763e10b7d32da490e96fc680b78))
* **ci:** standardize pipeline chain format ([36f7f96](https://github.com/fulviofreitas/eeroctl/commit/36f7f9646f3e9ab93355e63d62042b1bb934c8f9))
* rename project from eero-cli to eeroctl ([40ca250](https://github.com/fulviofreitas/eeroctl/commit/40ca2505de92ef317ca9ecd10329c27e659a27ab))
* split network.py and eero.py into modular packages ([f89422d](https://github.com/fulviofreitas/eeroctl/commit/f89422d7127760d5564c469c1eb6d3d80007fcce))
* update repository_dispatch event type name ([62b7dbe](https://github.com/fulviofreitas/eeroctl/commit/62b7dbeb97ab6cb34703db49eb94f9838736caf3))

## [1.2.2](https://github.com/fulviofreitas/eeroctl/compare/v1.2.1...v1.2.2) (2026-01-18)

### 🐛 Bug Fixes

* improve Renovate and auto-merge configuration ([5cc6b0e](https://github.com/fulviofreitas/eeroctl/commit/5cc6b0ebcf3658bd8d98d9eca6f30f16e34a9945))

## [1.2.1](https://github.com/fulviofreitas/eeroctl/compare/v1.2.0...v1.2.1) (2026-01-18)

### 🐛 Bug Fixes

* improve concurrency group for PR workflows ([c38d6b0](https://github.com/fulviofreitas/eeroctl/commit/c38d6b0066300b3a640d1386e57f4ccf7882f649))

## [1.2.0](https://github.com/fulviofreitas/eeroctl/compare/v1.1.0...v1.2.0) (2026-01-17)

### ✨ Features

* **security:** migrate from Bandit to Semgrep ([c1085d1](https://github.com/fulviofreitas/eeroctl/commit/c1085d197d7775081d476506b2e577108e20d575))

## [1.1.0](https://github.com/fulviofreitas/eeroctl/compare/v1.0.0...v1.1.0) (2026-01-17)

### ✨ Features

* add __version__ to package ([27e1c04](https://github.com/fulviofreitas/eeroctl/commit/27e1c04bfa47709eb67340ae81e9219a50385223))

## 1.0.0 (2026-01-17)

### ⚠ BREAKING CHANGES

* Python 3.10 and 3.11 are no longer supported

- Update requires-python to >=3.12
- Update classifiers to 3.12, 3.13, 3.14
- Update mypy python_version to 3.12
- Update ruff/black target-version to py312

### ✨ Features

* add Bandit security scanning workflow 🔒 ([cb13ae2](https://github.com/fulviofreitas/eeroctl/commit/cb13ae2e94a80ba042a90ff8ec66d33e03383a33))
* **ci:** add Renovate for automated eero-api dependency updates ([067e9ca](https://github.com/fulviofreitas/eeroctl/commit/067e9ca4b2665cd6029abf9af22557a65b4e857f))
* **ci:** migrate workflows to use reusable actions from eero-api ([c23c961](https://github.com/fulviofreitas/eeroctl/commit/c23c961f0e2bec3fb1ddd4b10b6f82a2d417e11f))
* require Python 3.12 minimum ([1839deb](https://github.com/fulviofreitas/eeroctl/commit/1839deb0032984e471e5cda409fef2107aedf1ea))

### 🐛 Bug Fixes

* auth flow improvements and client list output consistency ([f9d8379](https://github.com/fulviofreitas/eeroctl/commit/f9d8379063ce5b485a7571e7e781bfe19e4b59ea))
* **ci:** correct matrix syntax for macOS test jobs ([5185f99](https://github.com/fulviofreitas/eeroctl/commit/5185f99f0f997f908951ad51724f9cb0d96d07a3))
* **ci:** properly report type-check and security job status ([b270dc0](https://github.com/fulviofreitas/eeroctl/commit/b270dc06d10ac1bf82ffb42c57520c769fd1d31a))
* **ci:** require ALL jobs to pass for CI Success ([ad85a5d](https://github.com/fulviofreitas/eeroctl/commit/ad85a5d2fbd20b8a687568ca8bc12cc8fd6126ca))
* **ci:** use master branch consistently in all workflows ([5fa591f](https://github.com/fulviofreitas/eeroctl/commit/5fa591f353fe3f0736d4271dbbe6a7083c3a6fc9))
* consistent columns between list and table output formats ([336bfad](https://github.com/fulviofreitas/eeroctl/commit/336bfad098a210520a564181b1f5e57f2e745230))
* remove unused variable and import (ruff F841, F401) ([db81e1a](https://github.com/fulviofreitas/eeroctl/commit/db81e1ae112a438aa07b206fadb3ed45c3eebac7))
* suppress status messages for parseable output formats ([0e054cc](https://github.com/fulviofreitas/eeroctl/commit/0e054cc59572f19a4aae40caafabcfcf3fc8345b))
* use lowercase values for Bandit confidence/severity levels ([f8ace21](https://github.com/fulviofreitas/eeroctl/commit/f8ace218602cfd3861a274856cabfed84543d164))

### 📚 Documentation

* improve installation instructions with venv details ([a2b5b4a](https://github.com/fulviofreitas/eeroctl/commit/a2b5b4a053d510aedb882838bf39318bb5497053))
* modernize README with emojis and wiki links ([c48f546](https://github.com/fulviofreitas/eeroctl/commit/c48f546572b97ff7c1e07e8c582d2afa0fa569fe))
* simplify main CLI help message ([c2ae74f](https://github.com/fulviofreitas/eeroctl/commit/c2ae74f913bd0d303a880c7643c11be122e95e3d))

### ♻️ Refactoring

* **auth:** improve auth status command with accurate session info ([c0531f6](https://github.com/fulviofreitas/eeroctl/commit/c0531f6beed70763e10b7d32da490e96fc680b78))
* **ci:** standardize pipeline chain format ([36f7f96](https://github.com/fulviofreitas/eeroctl/commit/36f7f9646f3e9ab93355e63d62042b1bb934c8f9))
* split network.py and eero.py into modular packages ([f89422d](https://github.com/fulviofreitas/eeroctl/commit/f89422d7127760d5564c469c1eb6d3d80007fcce))
* update repository_dispatch event type name ([62b7dbe](https://github.com/fulviofreitas/eeroctl/commit/62b7dbeb97ab6cb34703db49eb94f9838736caf3))
