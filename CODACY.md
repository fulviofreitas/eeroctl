# Codacy configuration

`tests/` is excluded from Codacy's static-analysis engines (`.codacy.yaml`). Two
patterns fire there on every run without pointing at a real defect:

- **`assert` statements** (Bandit `B101`, Semgrep `python.lang.security.audit.assert-used`)
  — asserts are stripped under `python -O`, which matters for application code but is
  the standard, expected way to write a `pytest` assertion. This repo's own `ruff`
  configuration already agrees: it does not enable the bandit-equivalent `S101` rule.
- **Fixture-parameter shadowing** (Pylint `W0621`, "redefining name from outer scope")
  — a test function's parameter is conventionally named after the fixture it consumes
  (`def test_x(client): ...` where `client` is also a fixture function name). That is
  how `pytest` fixture injection works, not a naming collision.

Codacy's analysis environment also does not install this repo's dependencies, so its
`pyright` engine cannot resolve `eero`/`pytest` imports anywhere under `tests/` — a gap
in Codacy's own environment, not a code issue. Excluding `tests/**` suppresses that
noise too, since nothing under `src/` imports test-only dependencies.

Source code under `src/` is not excluded and remains fully analyzed.
