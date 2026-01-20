# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
